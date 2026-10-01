"""Write the insight tables the charts read (3_insight_tables/), plus _index.csv.

Each table answers one business question and holds every number, ratio, label and colour
category a chart needs, so 07_figures.py only plots. Growth metrics carry a text Direction
("Growing" / "Declining" / "Stable", the same +/-5% band as the venue trend) and ready-made
display labels ("+18%", "−$659K"); columns have plain-English names and dates are YYYY-MM-DD,
so the CSVs also read well on their own.

File and column names never contain a year, so the charts keep working after a fresh download
moves the data forward: the outlook year is "Next-Year", the year in progress is
"Current-Year", and the actual years sit in value columns (Forecast Year, ...) and in the labels.

Files are prefixed by topic:
  p1_  Group overview                p2_  Venue performance
  p3_  Venue types & acquisitions    p4_  Outlook (next year)
_index.csv lists every file with the question it answers and its row count.

Money comes in two bases:
  Drink sales (reported)   liquor + wine + beer sales (the data)
  Est. total revenue       drink sales / alcohol share of segment revenue (RCI FY2024 10-K)
"""
import calendar

import numpy as np
import pandas as pd

from common import (ACTIVE_WINDOW_MONTHS, ALCOHOL_SHARE, BASE_YEAR, INTERMEDIATE, SELECTED_MODEL, TABLES,
                    TREND_BAND, VENUE_MONTH, VENUES, forecast_year, money, pct)

DRINK_BASIS, EST_BASIS = "Drink sales (reported)", "Est. total revenue"
COMPONENTS = ["Same-venue growth", "New venues (opened / other)", "Acquired venues", "Closed venues"]
SERIES = ["Actual", "Forecast", "Forecast low (80%)", "Forecast high (80%)"]
MODEL_NAMES = {"ensemble": "Ensemble (ETS + Prophet + GBM)", "ets": "Exponential smoothing",
               "prophet": "Prophet", "gbm": "Gradient boosting (all venues)",
               "snaive": "Same month last year (baseline)"}
INDEX = []


# ---------------------------------------------------------------- helpers
def direction(v: float, band: float = 0.0) -> str:
    """Growing / Declining / Stable. Use band=TREND_BAND for % growth, 0 for $ changes."""
    if pd.isna(v):
        return ""
    return "Growing" if v > band else "Declining" if v < -band else "Stable"


def gross_up(values: pd.Series, types: pd.Series) -> pd.Series:
    return values / types.map(ALCOHOL_SHARE)


def whole_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Float columns that only hold whole numbers (years, counts, ranks, orders) become Int64, so
    the CSV shows 2007 rather than 2007.0000 and a missing value stays blank."""
    out = df.copy()
    for c in out.columns:
        v = out[c]
        if pd.api.types.is_float_dtype(v) and v.notna().any() and (v.dropna() % 1 == 0).all():
            out[c] = v.astype("Int64")
    return out


def save(df: pd.DataFrame, name: str, section: str, question: str) -> None:
    """Write one insight table and its _index.csv row."""
    empty = [c for c in df.columns if df[c].isna().all()]
    assert not empty, f"{name}: NaN-only columns {empty}"
    df = whole_numbers(df)
    df.to_csv(TABLES / name, index=False, float_format="%.4f", date_format="%Y-%m-%d")
    back = pd.read_csv(TABLES / name, dtype=str)
    dotted = [c for c in df.columns if pd.api.types.is_integer_dtype(df[c])
              and back[c].str.contains(".", regex=False).any()]
    assert not dotted, f"{name}: whole-number columns written with decimals {dotted}"
    INDEX.append({"File": name, "Section": section, "Question It Answers": question, "Row Count": len(df)})
    print(f"  {name:42} {len(df):>6,} rows")


def long_series(df: pd.DataFrame, keys: list, join_month: pd.Series) -> pd.DataFrame:
    """Actual / Forecast / Forecast low / Forecast high as one `Series` column.

    The three forecast series also get a row at the last actual month (value = actual) so
    the lines connect; that row has Include In Totals = False. Summing Drink Revenue with
    Include In Totals = True gives actual + forecast with nothing counted twice.
    """
    cols = {"Actual": "actual", "Forecast": "forecast", "Forecast low (80%)": "forecast_low",
            "Forecast high (80%)": "forecast_high"}
    parts = []
    for series, col in cols.items():
        p = df.loc[df[col].notna(), keys + ["month", col]].rename(columns={col: "Drink Revenue"})
        p["Series"] = series
        p["Include In Totals"] = series in ("Actual", "Forecast")
        parts.append(p)
        if series != "Actual":
            j = df.loc[join_month & df["actual"].notna(), keys + ["month", "actual"]]
            j = j.rename(columns={"actual": "Drink Revenue"}).assign(Series=series, **{"Include In Totals": False})
            parts.append(j)
    out = pd.concat(parts, ignore_index=True)
    out["Series Order"] = out["Series"].map({s: i for i, s in enumerate(SERIES, 1)})
    out["Year"] = out["month"].dt.year
    return out


# ---------------------------------------------------------------- section 1
def page1(rci, venues, ctx, gf, bridge, summ, acc, best, sc) -> dict:
    latest, fy, cy = ctx["latest"], ctx["fy"], ctx["cy"]
    p = "1 Group overview"

    # ---- trend + forecast, long
    trend = long_series(gf, [], gf["month"] == latest)
    active = rci[rci["trading"]].groupby("month")["venue_name"].nunique()
    trend["Active Venues"] = np.where(trend["Series"] == "Actual", trend["month"].map(active), np.nan)
    trend = trend.rename(columns={"month": "Month"})[
        ["Month", "Year", "Series", "Series Order", "Drink Revenue", "Include In Totals", "Active Venues"]]
    trend = trend.sort_values(["Series Order", "Month"])
    save(trend, "p1_group_trend_and_forecast.csv", p,
         f"How has monthly drink revenue moved since {rci['month'].min():%Y}, and where is it heading to Dec {fy}?")

    # ---- yearly totals, Actual / Forecast split
    y = gf.assign(Year=gf["month"].dt.year).groupby("Year")[["actual", "forecast", "forecast_low", "forecast_high"]].sum()
    yl = y[["actual", "forecast"]].rename(columns={"actual": "Actual", "forecast": "Forecast"})
    yl = yl.reset_index().melt(id_vars="Year", var_name="Part", value_name="Drink Revenue")
    yl = yl[yl["Drink Revenue"] > 0].sort_values(["Year", "Part"])
    total = y["actual"] + y["forecast"]
    growth = total / total.shift() - 1
    status = np.where(y["forecast"] == 0, "Actual", np.where(y["actual"] == 0, "Forecast", "Actual + forecast"))
    info = pd.DataFrame({"Year Status": status, "Year Total Label": total.map(money),
                         "Growth vs Prior Year": growth.map(lambda v: pct(v, 1)),
                         "Direction": growth.map(lambda v: direction(v, TREND_BAND)),
                         "80% Range Label": [f"80% range {money(lo)}–{money(hi)}" if a == 0 else ""
                                             for a, lo, hi in zip(y["actual"], y["forecast_low"], y["forecast_high"])]},
                        index=y.index)
    info.loc[info.index.min(), "Direction"] = ""   # first year has no prior year
    yearly = yl.merge(info, left_on="Year", right_index=True)
    nxt = latest + pd.DateOffset(months=1)
    save(yearly, "p1_group_yearly_totals.csv", p,
         f"What did the group sell each year, and how much of {cy}-{fy} is forecast?")

    # ---- revenue by venue type per year, long by Revenue Basis
    tm = rci.groupby(["month", "venue_type"]).agg(rev=("total", "sum"), venues=("trading", "sum")).reset_index()
    tm = pd.concat([tm.assign(basis=DRINK_BASIS, value=tm["rev"]),
                    tm.assign(basis=EST_BASIS, value=gross_up(tm["rev"], tm["venue_type"]))])
    ty = tm.assign(Year=tm["month"].dt.year).groupby(["basis", "Year", "venue_type"])["value"].sum().reset_index()
    ty["share"] = ty["value"] / ty.groupby(["basis", "Year"])["value"].transform("sum")
    last_month = {yr: m for yr, m in rci.groupby(rci["month"].dt.year)["month"].max().items()}
    ty_out = pd.DataFrame({
        "Year": ty["Year"],
        "Year Label": [f"{yr} (Jan–{last_month[yr]:%b})" if last_month[yr].month < 12 else str(yr) for yr in ty["Year"]],
        "Venue Type": ty["venue_type"], "Revenue Basis": ty["basis"], "Revenue": ty["value"],
        "Revenue Label": ty["value"].map(money), "Share of Year": ty["share"],
        "Share Label": ty["share"].map(lambda v: pct(v, 0, signed=False))})
    save(ty_out.sort_values(["Revenue Basis", "Year", "Venue Type"]), "p1_revenue_by_type_yearly.csv", p,
         "Which venue types make up each year's revenue?")

    # ---- growth bridge: waterfall + component table
    periods = list(dict.fromkeys(bridge["period"]))
    window = ctx["window"]
    years = [str(yy) for yy in range(BASE_YEAR + 1, ctx["last_full"] + 1)]
    b_window = bridge[bridge["period"].isin(years)].assign(period=window)
    start_window = rci.loc[rci["month"].dt.year == BASE_YEAR, "total"].sum()
    end_window = rci.loc[rci["month"].dt.year == ctx["last_full"], "total"].sum()

    def period_totals(period):
        if period == window:
            return str(BASE_YEAR), start_window, str(ctx["last_full"]), end_window
        g = bridge[bridge["period"] == period]
        if period.startswith("TTM"):
            return "Prior 12 months", g["prior_revenue"].sum(), "Last 12 months", g["current_revenue"].sum()
        return str(int(period) - 1), g["prior_revenue"].sum(), period, g["current_revenue"].sum()

    both = pd.concat([bridge, b_window], ignore_index=True)
    wf_rows = []
    for period in periods + [window]:
        b = both[both["period"] == period]
        start_label, start, end_label, end = period_totals(period)
        for detail, keys in (("By component", ["component"]), ("By component and venue type", ["component", "venue_type"])):
            steps = b.groupby(keys)["change"].sum().reset_index()
            steps["o"] = steps["component"].map(COMPONENTS.index)
            steps = steps.sort_values(["o"] + keys[1:])
            steps = steps[steps["change"].abs() > 0]
            common = {"Period": period, "Detail": detail}
            wf_rows.append({**common, "Step Order": 0, "Step": start_label, "Component": "Total",
                            "Venue Type": "All venues", "Change": start, "Bar Start": 0.0, "Bar End": start,
                            "Kind": "Total"})
            run = start
            for i, r in enumerate(steps.itertuples(), 1):
                vt = r.venue_type if detail != "By component" else "All venues"
                wf_rows.append({**common, "Step Order": i,
                                "Step": r.component if detail == "By component" else f"{r.component}: {vt}",
                                "Component": r.component, "Venue Type": vt, "Change": r.change,
                                "Bar Start": run, "Bar End": run + r.change,
                                "Kind": "Increase" if r.change > 0 else "Decrease"})
                run += r.change
            assert abs(run - end) < 1, (period, detail)
            wf_rows.append({**common, "Step Order": len(steps) + 1, "Step": end_label, "Component": "Total",
                            "Venue Type": "All venues", "Change": end, "Bar Start": 0.0, "Bar End": end,
                            "Kind": "Total"})
    wf = pd.DataFrame(wf_rows)
    wf["Bar Length"] = wf["Bar End"] - wf["Bar Start"]
    wf["Change Label"] = [money(c) if k == "Total" else money(c, signed=True) for c, k in zip(wf["Change"], wf["Kind"])]
    wf["Is Latest"] = wf["Period"] == ctx["ttm_label"]
    wf["Is Long Run"] = wf["Period"] == window
    wf = wf[["Period", "Is Latest", "Is Long Run", "Detail", "Step Order", "Step", "Component", "Venue Type", "Kind",
             "Change", "Change Label", "Bar Start", "Bar End", "Bar Length"]]
    save(wf, "p1_growth_bridge_waterfall.csv", p,
         "What changed revenue between two periods: same-venue sales, new venues, acquisitions or closures?")

    # ---- KPIs, long
    b_ttm = bridge[bridge["period"] == ctx["ttm_label"]]
    cur, prior = b_ttm["current_revenue"].sum(), b_ttm["prior_revenue"].sum()
    sv = b_ttm[b_ttm["component"] == "Same-venue growth"]
    sv_growth = sv["current_revenue"].sum() / sv["prior_revenue"].sum() - 1
    gfy = gf[gf["month"].dt.year == fy]
    lo, hi = gfy["forecast_low"].sum(), gfy["forecast_high"].sum()
    est, base = summ.loc["Base", "estimate_current_year"], summ.loc["Base", "revenue_forecast_year"]
    per_venue = rci[(rci["month"] > latest - pd.DateOffset(months=12)) & rci["trading"]]["total"].mean()
    act = sc[(sc["status"] == "Active") & sc["yoy_pct"].notna()]
    n_yoy, n_down5, n_below = len(act), int((act["trend"] == "Declining").sum()), int((act["yoy_pct"] < 0).sum())
    n_active = int((venues["status"] == "Active").sum())
    model_names = MODEL_NAMES
    ttm_span, bt_span = ctx["ttm_span"], ctx["bt_span"]
    k = [
        ("Drink revenue, last 12 months", ttm_span, cur, money(cur),
         f"{pct(cur / prior - 1, 1)} vs prior 12 months ({money(prior)})", direction(cur / prior - 1, TREND_BAND)),
        ("Growth vs prior 12 months", ttm_span, cur / prior - 1, pct(cur / prior - 1, 1),
         f"{money(cur)} vs {money(prior)}", direction(cur / prior - 1, TREND_BAND)),
        ("Same-venue growth", ttm_span, sv_growth, pct(sv_growth, 1),
         "venues open throughout both 12-month periods", direction(sv_growth, TREND_BAND)),
        ("Active venues", f"{latest:%b %Y}", n_active, str(n_active), f"trading in the last {ACTIVE_WINDOW_MONTHS} months", ""),
        ("Venues down more than 5%", ttm_span, n_down5, f"{n_down5} of {n_yoy}",
         "active venues with 2 years of history, down more than 5% on a year ago", "Declining"),
        ("Venues below last year", ttm_span, n_below, f"{n_below} of {n_yoy}",
         "active venues with 2 years of history selling less than a year ago", "Declining"),
        ("Avg monthly drink revenue per venue", ttm_span, per_venue, money(per_venue),
         "last 12 months, trading venue-months", ""),
        ("Current-year estimate", str(cy), est, money(est),
         f"{cy}: actual Jan–{latest:%b} + forecast {nxt:%b}–Dec", ""),
        ("Next-year forecast (base)", str(fy), base, money(base),
         f"{fy}: 80% range {money(lo)}–{money(hi)}; {pct(base / est - 1, 1)} vs {cy} estimate",
         direction(base / est - 1, TREND_BAND)),
        ("Next-year forecast low (80%)", str(fy), lo, money(lo), f"{fy}: 80% range, low end", ""),
        ("Next-year forecast high (80%)", str(fy), hi, money(hi), f"{fy}: 80% range, high end", ""),
        ("Forecast error (venue WAPE)", bt_span, acc.loc[best, "venue_wape"], pct(acc.loc[best, "venue_wape"], 1, False),
         f"{model_names[best]}; baseline {pct(acc.loc['snaive', 'venue_wape'], 1, False)}", ""),
        ("Baseline error (venue WAPE)", bt_span, acc.loc["snaive", "venue_wape"],
         pct(acc.loc["snaive", "venue_wape"], 1, False), "same month last year", ""),
        ("Avg 12-month group error", bt_span, acc.loc[best, "group_abs"], pct(acc.loc[best, "group_abs"], 1, False),
         f"{model_names[best]}: mean |12-month group total error| over the back-tests", ""),
        ("Forecast model", bt_span, np.nan, model_names[best],
         "lowest back-tested venue-level error" if best != "snaive" else "no model beat the baseline", ""),
        ("Data through", f"{latest:%b %Y}", np.nan, f"{latest:%b %Y}", "latest month of filings", ""),
    ]
    kpis = pd.DataFrame(k, columns=["KPI", "Period", "Value", "Display Text", "Subtitle", "Direction"])
    kpis.insert(0, "Sort Order", range(1, len(kpis) + 1))
    save(kpis, "p1_kpis.csv", p,
         "What are the headline numbers?")
    return {"trend": trend, "yearly": yearly, "wf": wf, "kpis": kpis,
            "est": est, "base": base, "start_window": start_window, "end_window": end_window}


# ---------------------------------------------------------------- section 2
def page2(ctx, sc, fvm) -> dict:
    fy = ctx["fy"]
    p = "2 Venue performance"
    fnext = fvm[fvm["month"].dt.year == fy].groupby("venue_name")["forecast"].sum()
    s = pd.DataFrame({
        "Venue": sc["venue_name"], "Venue Type": sc["venue_type"], "Brand": sc["brand"], "City": sc["city"],
        "Entry Route": sc["entry_route"], "Status": sc["status"], "RCI Since": sc["rci_first_month"],
        "Last Trading Month": sc["rci_last_month"], "TTM Drink Revenue": sc["ttm_revenue"],
        "Prior TTM Drink Revenue": sc["prior_ttm_revenue"],
        "YoY Change $": sc["ttm_revenue"] - sc["prior_ttm_revenue"], "YoY Growth %": sc["yoy_pct"],
        "3-yr CAGR %": sc["cagr_3yr_pct"], "Trend": sc["trend"], "TTM Rank": sc["ttm_rank"],
        "Share of Group (TTM)": sc["share_of_group_ttm"],
        "Est. Total Revenue (TTM)": gross_up(sc["ttm_revenue"], sc["venue_type"]),
        "Next-Year Forecast Drink Revenue": sc["venue_name"].map(fnext), "Forecast Year": fy,
        "Lifetime Drink Revenue (RCI)": sc["lifetime_revenue"], "Months Under RCI": sc["months_under_rci"],
        "Avg Monthly Drink Revenue": sc["avg_monthly_revenue"],
        "Liquor Share (TTM)": sc["ttm_liquor_share"], "Wine Share (TTM)": sc["ttm_wine_share"],
        "Beer Share (TTM)": sc["ttm_beer_share"]})
    for c in ("RCI Since", "Last Trading Month"):
        s[c] = pd.to_datetime(s[c])
    s["Direction"] = s["YoY Growth %"].map(lambda v: direction(v, TREND_BAND))
    s["YoY Label"] = s["YoY Growth %"].map(pct)
    s["YoY Change Label"] = s["YoY Change $"].map(lambda v: money(v, signed=True))
    s["3-yr CAGR Label"] = s["3-yr CAGR %"].map(pct)
    s["TTM Revenue Label"] = s["TTM Drink Revenue"].map(money)
    s["Top 10 (TTM)"] = s["TTM Rank"].le(10)
    save(s, "p2_venue_scorecard.csv", p,
         "How is every venue doing: revenue, growth, trend, rank, next-year forecast?")

    g = s[(s["Status"] == "Active") & s["YoY Growth %"].notna()].sort_values("YoY Growth %", ascending=False)
    g = g[["Venue", "Venue Type", "City", "TTM Drink Revenue", "Prior TTM Drink Revenue", "YoY Change $",
           "YoY Growth %", "Direction", "YoY Label", "YoY Change Label", "Trend",
           "Next-Year Forecast Drink Revenue"]].copy()
    g.insert(0, "Sort Order", range(1, len(g) + 1))
    save(g, "p2_venue_growth_active.csv", p,
         "Which active venues are growing and which are declining (last 12 months vs the 12 before)?")

    # ---- seasonality and type drinks mix
    seas = pd.read_csv(INTERMEDIATE / "seasonality.csv")
    seas_out = pd.DataFrame({
        "Venue Type": seas["venue_type"], "Month Number": seas["month_num"],
        "Month Name": seas["month_num"].map(lambda m: calendar.month_abbr[m]),
        "Seasonality Index": seas["seasonality_index"],
        "vs Average Month": seas["seasonality_index"] - 1,
        "vs Average Label": (seas["seasonality_index"] - 1).map(pct),
        "Above or Below Average": np.where(seas["seasonality_index"] >= 1, "Above average", "Below average")})
    save(seas_out, "p2_seasonality_by_type.csv", p,
         "Which months are busy or quiet for each venue type?")

    mix = pd.read_csv(INTERMEDIATE / "drinks_mix.csv")
    mix = mix.melt(id_vars=["venue_type", "year"], value_vars=["liquor", "wine", "beer"],
                   var_name="Drink", value_name="Drink Revenue")
    mix["Share of Drinks"] = mix["Drink Revenue"] / mix.groupby(["venue_type", "year"])["Drink Revenue"].transform("sum")
    mix["Share Label"] = mix["Share of Drinks"].map(lambda x: pct(x, 0, signed=False))
    mix["Drink"] = mix["Drink"].str.title()
    mix = mix.rename(columns={"venue_type": "Venue Type", "year": "Year"}).sort_values(["Venue Type", "Year", "Drink"])
    save(mix, "p2_drinks_mix_by_type.csv", p,
         "What share of drink sales is liquor, wine and beer for each venue type, by year?")
    return {"sc": s, "mix": mix}


# ---------------------------------------------------------------- section 3
def page3(ctx) -> dict:
    p = "3 Venue types & acquisitions"
    ts = pd.read_csv(INTERMEDIATE / "type_summary.csv")
    y0, y1, window = BASE_YEAR, ctx["last_full"], ctx["window"]
    tag = f"change_{y0}_{y1}_"
    t = pd.DataFrame({
        "Venue Type": ts["venue_type"], "TTM Drink Revenue": ts["ttm_revenue"],
        "Est. Total Revenue (TTM)": gross_up(ts["ttm_revenue"], ts["venue_type"]),
        "Active Venues": ts["active_venues"].astype(int), "Closure Rate": ts["closure_rate"],
        "Avg Monthly Drink Revenue per Venue": ts["avg_monthly_revenue_per_venue_ttm"],
        "Est. Avg Monthly Total Revenue per Venue": gross_up(ts["avg_monthly_revenue_per_venue_ttm"], ts["venue_type"])})

    comp_map = {"same_venue_growth": "Same-venue growth", "new_venues": "New venues (opened / other)",
                "acquired_venues": "Acquired venues", "closed_venues": "Closed venues"}
    c = ts.melt(id_vars="venue_type", value_vars=[tag + k for k in comp_map], var_name="Component", value_name="Change")
    c["Component"] = c["Component"].str.replace(tag, "", regex=False).map(comp_map)
    net_label = ts.set_index("venue_type")[tag + "total"].map(lambda v: "net " + money(v, signed=True))
    c = pd.DataFrame({"Window": window, "Venue Type": c["venue_type"], "Component": c["Component"],
                      "Component Order": c["Component"].map(COMPONENTS.index) + 1, "Change": c["Change"],
                      "Direction": c["Change"].map(direction),
                      "Change Label": c["Change"].map(lambda v: money(v, signed=True)),
                      "Venue Type Net Change Label": c["venue_type"].map(net_label)})
    c = c[c["Change"] != 0]   # a type with no venue in a component has nothing to show
    save(c.sort_values(["Venue Type", "Component Order"]), f"p3_type_growth_sources_since_{BASE_YEAR}.csv", p,
         f"Which venue types grew from {y0} to {y1}, and through which route (same-venue, new, acquired, closed)?")

    rb = pd.concat([
        pd.DataFrame({"Venue Type": t["Venue Type"], "Revenue Basis": DRINK_BASIS, "TTM Revenue": t["TTM Drink Revenue"],
                      "Avg Monthly Revenue per Venue": t["Avg Monthly Drink Revenue per Venue"]}),
        pd.DataFrame({"Venue Type": t["Venue Type"], "Revenue Basis": EST_BASIS, "TTM Revenue": t["Est. Total Revenue (TTM)"],
                      "Avg Monthly Revenue per Venue": t["Est. Avg Monthly Total Revenue per Venue"]})])
    rb["Share of Group (TTM)"] = rb["TTM Revenue"] / rb.groupby("Revenue Basis")["TTM Revenue"].transform("sum")
    rb["Share Label"] = rb["Share of Group (TTM)"].map(lambda v: pct(v, 0, signed=False))
    rb["TTM Revenue Label"] = rb["TTM Revenue"].map(money)
    rb["Per Venue Label"] = rb["Avg Monthly Revenue per Venue"].map(money)
    rb = rb.merge(t[["Venue Type", "Active Venues", "Closure Rate"]], on="Venue Type")
    save(rb, "p3_type_revenue_by_basis.csv", p,
         "Which venue type earns most per venue, on drink sales and on estimated total revenue?")

    ramp = pd.read_csv(INTERMEDIATE / "ramp_curves.csv")
    ramp["smoothed"] = (ramp.groupby("venue_type")["median_revenue"]
                            .transform(lambda s: s.rolling(3, center=True, min_periods=1).mean()))
    ramp_out = pd.DataFrame({
        "Venue Type": ramp["venue_type"], "Months Since Joining": ramp["months_since_entry"],
        "Avg Monthly Drink Revenue": ramp["avg_revenue"], "Median Monthly Drink Revenue": ramp["median_revenue"],
        "Median Monthly Drink Revenue (3-month smoothed)": ramp["smoothed"], "Venues in Sample": ramp["venues"],
        "Show In Chart": (ramp["venues"] >= 3) & ramp["months_since_entry"].between(1, 30)
                         & ramp["venue_type"].ne("Other bar / nightclub")})
    save(ramp_out, "p3_ramp_curves.csv", p,
         "How does a new or acquired venue's revenue develop in its first 30 months?")

    up = pd.read_csv(INTERMEDIATE / "acquisition_uplift.csv", parse_dates=["acquired_month"])
    acq = pd.DataFrame({
        "Venue": up["venue_name"], "Venue Type": up["venue_type"], "Acquired": up["acquired_month"],
        "Status": up["status"], "Acquisition Kind": up["acquisition_kind"],
        "Trading Months Before": up["pre_months"], "Trading Months After": up["post_months"],
        "Avg Monthly Drinks: 12m Before": up["pre_12m_avg_monthly"],
        "Avg Monthly Drinks: 12m After": up["post_12m_avg_monthly"], "Uplift %": up["uplift_pct"]})
    acq["Uplift Label"] = acq["Uplift %"].map(pct)
    acq["Direction"] = acq["Uplift %"].map(lambda v: direction(v, TREND_BAND))
    save(acq, "p3_acquisitions.csv", p,
         "Which venues did RCI acquire, when, and did drink sales rise after the takeover?")

    return {"t": t, "c": c, "rb": rb}


# ---------------------------------------------------------------- section 4
def page4(rci, ctx, summ, bt, best, fvm) -> dict:
    fy, cy = ctx["fy"], ctx["cy"]
    p = "4 Outlook (next year)"
    core = ["Bear", "Base", "Bull"]
    ss = summ.reset_index()
    ss_out = pd.DataFrame({
        "Scenario": ss["scenario"],
        "Scenario Group": np.where(ss["scenario"].isin(core), "Core", "What-if: add venues"),
        "Sort Order": range(1, len(ss) + 1), "Forecast Year": ss["forecast_year"],
        "Forecast Drink Revenue": ss["revenue_forecast_year"], "From New Venues": ss["new_venue_revenue"],
        "Current-Year Estimate": ss["estimate_current_year"],
        "vs Current-Year Estimate %": ss["vs_current_year_estimate_pct"], "Assumptions": ss["assumptions"]})
    ss_out["Direction"] = ss_out["vs Current-Year Estimate %"].map(lambda v: direction(v, TREND_BAND))
    ss_out["Display Label"] = [f"{money(r)} ({pct(g, 1)})" for r, g in
                               zip(ss_out["Forecast Drink Revenue"], ss_out["vs Current-Year Estimate %"])]
    save(ss_out, "p4_scenario_summary.csv", p,
         f"What could {fy} drink revenue be under bear / base / bull and 'add venues' assumptions?")

    # current-year estimate vs next-year forecast by venue type
    types = fvm.drop_duplicates("venue_name").set_index("venue_name")["venue_type"]
    a_cy = rci[rci["month"].dt.year == cy].groupby("venue_type")["total"].sum()
    f = fvm.assign(venue_type=fvm["venue_name"].map(types), year=fvm["month"].dt.year)
    f_cy = f[f["year"] == cy].groupby("venue_type")["forecast"].sum()
    f_fy = f[f["year"] == fy].groupby("venue_type")["forecast"].sum()
    bt_type = pd.DataFrame({"Current-Year Estimate": a_cy.add(f_cy, fill_value=0), "Next-Year Forecast": f_fy}).fillna(0)
    bt_type["Change"] = bt_type["Next-Year Forecast"] - bt_type["Current-Year Estimate"]
    bt_type["Change %"] = bt_type["Change"] / bt_type["Current-Year Estimate"]
    bt_type = bt_type.reset_index().rename(columns={"index": "Venue Type", "venue_type": "Venue Type"})
    bt_type.insert(1, "Current Year", cy)
    bt_type.insert(2, "Forecast Year", fy)
    bt_type["Direction"] = bt_type["Change %"].map(lambda v: direction(v, TREND_BAND))
    bt_type["Change Label"] = [f"{money(c, signed=True)} ({pct(g, 1)})" for c, g in zip(bt_type["Change"], bt_type["Change %"])]
    bt_type["Next-Year Label"] = bt_type["Next-Year Forecast"].map(money)
    save(bt_type, "p4_forecast_next_year_by_type.csv", p,
         f"How much will each venue type sell in {fy} (base forecast) vs the {cy} estimate?")

    fa = bt.groupby("model")[["venue_wape", "group_monthly_wape", "group_12m_total_error_pct"]].mean()
    fa["group_abs"] = bt.assign(a=bt["group_12m_total_error_pct"].abs()).groupby("model")["a"].mean()
    names = MODEL_NAMES
    fa = fa.sort_values("venue_wape").reset_index()
    fa_out = pd.DataFrame({
        "Model": fa["model"].map(names), "Selected": fa["model"].eq(best),
        "Is Baseline": fa["model"].eq("snaive"),
        "Venue-level Error (WAPE)": fa["venue_wape"], "Group Monthly Error (WAPE)": fa["group_monthly_wape"],
        "Group 12-month Total Bias": fa["group_12m_total_error_pct"],
        "Group 12-month Abs Error": fa["group_abs"]})
    fa_out["Venue Error Label"] = fa_out["Venue-level Error (WAPE)"].map(lambda v: pct(v, 1, signed=False))
    fa_out["Bias Label"] = fa_out["Group 12-month Total Bias"].map(lambda v: pct(v, 1))
    fa_out["Abs Error Label"] = fa_out["Group 12-month Abs Error"].map(lambda v: pct(v, 1, signed=False))
    fa_out["Model Role"] = np.where(fa_out["Selected"], "Selected", np.where(fa_out["Is Baseline"], "Baseline", "Other"))
    fa_out.insert(0, "Sort Order", range(1, len(fa_out) + 1))
    save(fa_out, "p4_forecast_accuracy.csv", p,
         "How accurate is the forecast model vs the naive 'same month last year' baseline?")
    return {"ss": ss_out, "bt_type": bt_type, "fa": fa_out}


# ---------------------------------------------------------------- main
def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    for old in TABLES.glob("*.csv"):
        old.unlink()   # so a renamed file never lingers
    vm = pd.read_csv(VENUE_MONTH, parse_dates=["month"])
    venues = pd.read_csv(VENUES, parse_dates=["rci_first_month", "rci_last_month", "closed_month"])
    rci = vm[vm["owner_period"] == "RCI"]
    latest = rci["month"].max()
    gf = pd.read_csv(INTERMEDIATE / "forecast_group_monthly.csv", parse_dates=["month"])
    fvm = pd.read_csv(INTERMEDIATE / "forecast_venue_monthly.csv", parse_dates=["month"])
    bridge = pd.read_csv(INTERMEDIATE / "growth_bridge.csv", dtype={"period": str})
    sc = pd.read_csv(INTERMEDIATE / "venue_scorecard.csv")
    summ = pd.read_csv(INTERMEDIATE / "scenario_summary.csv").set_index("scenario")
    bt = pd.read_csv(INTERMEDIATE / "forecast_backtest.csv", parse_dates=["origin"])
    acc = bt.groupby("model")[["venue_wape"]].mean()
    acc["group_abs"] = bt.assign(a=bt["group_12m_total_error_pct"].abs()).groupby("model")["a"].mean()
    best = SELECTED_MODEL.read_text().strip()   # chosen (and checked against the baseline) in 04

    # Every date in labels and notes comes from the data, so a fresh download stays consistent.
    fy = forecast_year(latest)
    last_full = latest.year if latest.month == 12 else latest.year - 1
    origins = sorted(bt["origin"].unique())
    ctx = {"latest": latest, "fy": fy, "cy": fy - 1, "last_full": last_full,
           "ttm_label": f"TTM {latest:%b %Y}",
           "ttm_span": f"{latest - pd.DateOffset(months=11):%b %Y}–{latest:%b %Y}",
           "window": f"{BASE_YEAR} to {last_full}",
           "bt_origin_list": origins,
           "bt_origins": ", ".join(f"{pd.Timestamp(o):%b %Y}" for o in origins),
           "bt_span": f"back-tests from {pd.Timestamp(origins[0]):%b %Y}–{pd.Timestamp(origins[-1]):%b %Y}"}
    assert (summ["forecast_year"] == fy).all(), "scenarios were run for a different forecast year"

    r1 = page1(rci, venues, ctx, gf, bridge, summ, acc, best, sc)
    r2 = page2(ctx, sc, fvm)
    r3 = page3(ctx)
    r4 = page4(rci, ctx, summ, bt, best, fvm)
    pd.DataFrame(INDEX).to_csv(TABLES / "_index.csv", index=False)
    print(f"  {'_index.csv':42} {len(INDEX):>6,} tables listed")

    # ---------------- reconciliation checks
    total = rci["total"].sum()
    fc_total = gf["forecast"].sum()
    tr, yearly = r1["trend"], r1["yearly"]
    # group: actual series = all RCI sales; Include In Totals = actual + forecast, nothing double counted
    assert abs(tr.loc[tr["Series"] == "Actual", "Drink Revenue"].sum() - total) < 1
    assert abs(tr.loc[tr["Include In Totals"], "Drink Revenue"].sum() - (total + fc_total)) < 1
    assert abs(yearly["Drink Revenue"].sum() - (total + fc_total)) < 1
    y_cy = yearly.loc[yearly["Year"] == ctx["cy"], "Drink Revenue"].sum()
    assert abs(y_cy - r1["est"]) < 1, "p1 yearly current-year total != current-year estimate"
    y_fy = yearly.loc[yearly["Year"] == fy, "Drink Revenue"].sum()
    assert abs(y_fy - r1["base"]) < 1, "p1 yearly next-year total != base scenario"
    # revenue by type per year (both bases)
    est_total = gross_up(rci["total"], rci["venue_type"]).sum()
    ty = pd.read_csv(TABLES / "p1_revenue_by_type_yearly.csv")
    assert abs(ty.loc[ty["Revenue Basis"] == DRINK_BASIS, "Revenue"].sum() - total) < 1
    assert abs(ty.loc[ty["Revenue Basis"] == EST_BASIS, "Revenue"].sum() - est_total) < 1
    # bridge: every waterfall ends where the period's revenue ends (asserted while building); its steps
    # sum to the group change; the long-run window reproduces the type summary
    wf = r1["wf"]
    steps = wf[(wf["Detail"] == "By component") & (wf["Kind"] != "Total")]
    for period, g in bridge.groupby("period"):
        assert abs(steps.loc[steps["Period"] == period, "Change"].sum() - g["change"].sum()) < 1, period
    window = steps[steps["Is Long Run"]]
    assert abs(window["Change"].sum() - (r1["end_window"] - r1["start_window"])) < 1
    assert abs(window["Change"].sum() - r3["c"]["Change"].sum()) < 1
    # venues: scorecard TTM = KPI TTM
    kp = r1["kpis"].set_index("KPI")["Value"]
    assert abs(r2["sc"]["TTM Drink Revenue"].fillna(0).sum() - kp["Drink revenue, last 12 months"]) < 1
    assert abs(r2["mix"]["Drink Revenue"].sum() - rci[["liquor", "wine", "beer"]].sum().sum()) < 1
    # outlook: types add up to the group current-year estimate and next-year base
    bt_type = r4["bt_type"]
    assert abs(bt_type["Current-Year Estimate"].sum() - r1["est"]) < 1
    assert abs(bt_type["Next-Year Forecast"].sum() - r1["base"]) < 1
    print(f"Reconciled: actuals ${total / 1e6:,.1f}M; TTM ${kp['Drink revenue, last 12 months'] / 1e6:,.1f}M; "
          f"{ctx['cy']} est ${r1['est'] / 1e6:,.1f}M; {fy} base ${r1['base'] / 1e6:,.1f}M")


if __name__ == "__main__":
    main()
