"""Where did the group's growth come from, venue by venue and type by type?

Group analyses use RCI-owned months only; pre-acquisition months are used only
for the acquisition before/after comparison.

Outputs (data/intermediate/)
  group_monthly.csv       group and per-type revenue by month, active venue count
  growth_bridge.csv       change vs prior period split into same-venue / new venues /
                          acquisitions / closures, by venue type (calendar years + TTM)
  venue_scorecard.csv     one row per venue: TTM revenue, YoY %, 3-yr CAGR, trend, rank
  type_summary.csv        per venue type: revenue, venues, revenue per venue, closure rate,
                          contribution to growth since BASE_YEAR (2019, see common.py)
  ramp_curves.csv         revenue by months since the venue joined RCI, per type
  acquisition_uplift.csv  12 months before vs after RCI took over each acquired venue
  seasonality.csv         monthly seasonality index per type
  drinks_mix.csv          liquor / wine / beer share by type and year
"""
import numpy as np
import pandas as pd

from common import BASE_YEAR, DRINKS, INTERMEDIATE, TREND_BAND, VENUE_MONTH, VENUES   # TREND_BAND: |YoY| within 5% = Stable

COVID = ("2020-03-01", "2021-06-01")   # excluded from seasonality
DORMANT_RATIO = 0.10       # pre-acquisition sales below 10% of post = dormant club


def load():
    vm = pd.read_csv(VENUE_MONTH, parse_dates=["month"])
    venues = pd.read_csv(VENUES, parse_dates=["first_trading_month", "rci_first_month",
                                               "rci_last_month", "closed_month"])
    vm = vm.merge(venues[["venue_name", "entry_route", "status", "rci_first_month"]], on="venue_name")
    return vm, venues


def periods(latest: pd.Timestamp):
    """Calendar years with a full prior year, plus trailing-12-months (TTM)."""
    out = []
    for y in range(2008, latest.year + (latest.month == 12)):
        out.append((str(y), pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-01")))
    ttm_end = latest
    ttm_start = latest - pd.DateOffset(months=11)
    out.append((f"TTM {ttm_end:%b %Y}", ttm_start, ttm_end))
    return out


def growth_bridge(rci: pd.DataFrame, latest: pd.Timestamp) -> pd.DataFrame:
    """Split each period's change into same-venue, new venue, acquisition and closure effects.

    A venue is 'in the portfolio' in any month it has a row under RCI (short $0 closures
    included). Same-venue = in the portfolio for all 24 months of prior + current period.
    Closure = its portfolio presence ends before the current period ends.
    New = everything else (joined during the two periods), split by how it joined.
    """
    rows = []
    for label, cur_start, cur_end in periods(latest):
        prev_start = cur_start - pd.DateOffset(years=1)
        prev_end = cur_end - pd.DateOffset(years=1)
        win = rci[(rci["month"] >= prev_start) & (rci["month"] <= cur_end)]
        for venue, g in win.groupby("venue_name"):
            prev = g[g["month"] <= prev_end]
            cur = g[g["month"] >= cur_start]
            if len(prev) == 12 and len(cur) == 12:
                component = "Same-venue growth"
            elif g["month"].max() < cur_end:
                component = "Closed venues"
            elif g["entry_route"].iat[0] == "Acquired":
                component = "Acquired venues"
            else:
                component = "New venues (opened / other)"
            rows.append({"period": label, "period_end": cur_end, "venue_name": venue,
                         "venue_type": g["venue_type"].iat[0], "component": component,
                         "prior_revenue": prev["total"].sum(), "current_revenue": cur["total"].sum()})
    b = pd.DataFrame(rows)
    b["change"] = b["current_revenue"] - b["prior_revenue"]

    # Check: components add up exactly to the group change for every period.
    for label, g in b.groupby("period"):
        _, cs, ce = next(p for p in periods(latest) if p[0] == label)
        ps, pe = cs - pd.DateOffset(years=1), ce - pd.DateOffset(years=1)
        group_change = (rci.loc[rci["month"].between(cs, ce), "total"].sum()
                        - rci.loc[rci["month"].between(ps, pe), "total"].sum())
        assert abs(g["change"].sum() - group_change) < 1, label
    return b


def venue_scorecard(rci: pd.DataFrame, venues: pd.DataFrame, latest: pd.Timestamp) -> pd.DataFrame:
    def window(end, months=12):
        start = end - pd.DateOffset(months=months - 1)
        w = rci[rci["month"].between(start, end)]
        return w.groupby("venue_name").agg(rev=("total", "sum"), months=("month", "size"))

    ttm = window(latest)
    prior = window(latest - pd.DateOffset(years=1))
    three = window(latest - pd.DateOffset(years=3))
    sc = venues.set_index("venue_name")[["venue_type", "brand", "city", "entry_route", "status",
                                          "rci_first_month", "rci_last_month"]].copy()
    sc = sc[sc["status"] != "Never traded"]
    sc["ttm_revenue"] = ttm["rev"]
    sc["prior_ttm_revenue"] = prior["rev"]
    full_prior = prior["months"].eq(12)
    sc["yoy_pct"] = (ttm["rev"] / prior["rev"].where(full_prior) - 1)
    full_three = three["months"].eq(12)
    sc["cagr_3yr_pct"] = (ttm["rev"] / three["rev"].where(full_three)) ** (1 / 3) - 1
    life = rci.groupby("venue_name").agg(lifetime_revenue=("total", "sum"),
                                          months_under_rci=("month", "size"),
                                          avg_monthly_revenue=("total", "mean"))
    sc = sc.join(life)
    mix = rci[rci["month"] > latest - pd.DateOffset(months=12)].groupby("venue_name")[DRINKS + ["total"]].sum()
    for d in DRINKS:
        sc[f"ttm_{d}_share"] = mix[d] / mix["total"]

    def trend(r):
        if r["status"] != "Active":
            return "Closed"
        if pd.isna(r["yoy_pct"]):
            return "New (<2 yrs)"
        if r["yoy_pct"] > TREND_BAND:
            return "Growing"
        if r["yoy_pct"] < -TREND_BAND:
            return "Declining"
        return "Stable"

    sc["trend"] = sc.apply(trend, axis=1)
    active = sc["status"] == "Active"
    sc.loc[active, "ttm_rank"] = sc.loc[active, "ttm_revenue"].rank(ascending=False, method="min")
    sc["share_of_group_ttm"] = sc["ttm_revenue"] / sc.loc[active, "ttm_revenue"].sum()
    return sc.reset_index().sort_values(["status", "ttm_revenue"], ascending=[True, False])


def type_summary(rci, venues, bridge, latest) -> pd.DataFrame:
    ttm_start = latest - pd.DateOffset(months=11)
    ttm = rci[rci["month"] >= ttm_start]
    ever = venues[venues["status"] != "Never traded"]
    t = pd.DataFrame({
        "ttm_revenue": ttm.groupby("venue_type")["total"].sum(),
        "active_venues": ever[ever["status"] == "Active"].groupby("venue_type").size(),
        "venues_ever": ever.groupby("venue_type").size(),
        "venues_closed": ever[ever["status"] == "Closed"].groupby("venue_type").size(),
        "avg_monthly_revenue_per_venue_ttm": ttm[ttm["trading"]].groupby("venue_type")["total"].mean(),
    }).fillna(0)
    t["closure_rate"] = t["venues_closed"] / t["venues_ever"]
    t["share_of_group_ttm"] = t["ttm_revenue"] / t["ttm_revenue"].sum()

    # Contribution to growth, BASE_YEAR -> latest full year: the yearly bridges add up
    # (telescope) to the total change, so each component is counted exactly once.
    last_full = latest.year if latest.month == 12 else latest.year - 1
    years = [str(y) for y in range(BASE_YEAR + 1, last_full + 1)]
    contrib = bridge[bridge["period"].isin(years)].pivot_table(
        index="venue_type", columns="component", values="change", aggfunc="sum", fill_value=0)
    tag = f"change_{BASE_YEAR}_{last_full}"
    contrib.columns = [f"{tag}_{c.split(' (')[0].lower().replace(' ', '_').replace('-', '_')}"
                       for c in contrib.columns]
    t = t.join(contrib).fillna(0)
    t[f"{tag}_total"] = t.filter(like=tag).sum(axis=1)
    t[f"revenue_{BASE_YEAR}"] = rci[rci["month"].dt.year == BASE_YEAR].groupby("venue_type")["total"].sum()
    t[f"revenue_{last_full}"] = rci[rci["month"].dt.year == last_full].groupby("venue_type")["total"].sum()
    t = t.fillna(0)

    # Same-venue growth rate, TTM vs prior TTM.
    ttm_label = f"TTM {latest:%b %Y}"
    sv = bridge[(bridge["period"] == ttm_label) & (bridge["component"] == "Same-venue growth")]
    sv = sv.groupby("venue_type")[["prior_revenue", "current_revenue"]].sum()
    t["same_venue_growth_ttm_pct"] = sv["current_revenue"] / sv["prior_revenue"] - 1
    return t.reset_index().sort_values("ttm_revenue", ascending=False)


def ramp_curves(rci: pd.DataFrame, max_months: int = 60) -> pd.DataFrame:
    """Average monthly revenue by months since the venue joined RCI (venues added after 2007)."""
    new = rci[rci["rci_first_month"] > rci["month"].min()].copy()
    new["months_since_entry"] = ((new["month"].dt.year - new["rci_first_month"].dt.year) * 12
                                 + new["month"].dt.month - new["rci_first_month"].dt.month + 1)
    new = new[new["months_since_entry"] <= max_months]
    return (new.groupby(["venue_type", "months_since_entry"])
               .agg(avg_revenue=("total", "mean"), median_revenue=("total", "median"),
                    venues=("venue_name", "nunique"))
               .reset_index())


def acquisition_uplift(vm: pd.DataFrame, venues: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, v in venues[venues["entry_route"] == "Acquired"].iterrows():
        g = vm[vm["venue_name"] == v["venue_name"]].set_index("month")["total"]
        start = v["rci_first_month"]
        # Skip the handover month itself: both owners may have filed part-months.
        pre = g[(g.index < start) & (g.index >= start - pd.DateOffset(months=12))]
        post = g[(g.index > start) & (g.index <= start + pd.DateOffset(months=12))]
        rows.append({"venue_name": v["venue_name"], "venue_type": v["venue_type"],
                     "acquired_month": start, "status": v["status"],
                     "pre_months": int((pre > 0).sum()), "post_months": int((post > 0).sum()),
                     "pre_12m_avg_monthly": pre.mean() if len(pre) else np.nan,
                     "post_12m_avg_monthly": post.mean() if len(post) else np.nan})
    u = pd.DataFrame(rows)
    # A club bought while barely trading (< 10% of what it did after) is a reopening,
    # not an uplift: a % change against a near-zero base means nothing.
    going = ((u["pre_months"] >= 10) & (u["post_months"] >= 10)
             & (u["pre_12m_avg_monthly"] >= DORMANT_RATIO * u["post_12m_avg_monthly"]))
    u["acquisition_kind"] = np.where(going, "Going concern", "Dormant / reopened")
    u["uplift_pct"] = (u["post_12m_avg_monthly"] / u["pre_12m_avg_monthly"] - 1).where(going)
    return u.sort_values("acquired_month")


def seasonality(rci: pd.DataFrame) -> pd.DataFrame:
    s = rci[rci["trading"] & ~rci["month"].between(*COVID)].copy()
    s["year"] = s["month"].dt.year
    s = s[s.groupby(["venue_name", "year"])["month"].transform("size") == 12]
    s["index"] = s["total"] / s.groupby(["venue_name", "year"])["total"].transform("mean")
    s["month_num"] = s["month"].dt.month
    return (s.groupby(["venue_type", "month_num"])["index"].mean().rename("seasonality_index")
             .reset_index())


def main() -> None:
    vm, venues = load()
    rci = vm[vm["owner_period"] == "RCI"]
    latest = vm["month"].max()
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)

    gm = rci.pivot_table(index="month", columns="venue_type", values="total", aggfunc="sum", fill_value=0)
    gm["Group total"] = gm.sum(axis=1)
    gm["active_venues"] = rci[rci["trading"]].groupby("month")["venue_name"].nunique()
    gm.reset_index().to_csv(INTERMEDIATE / "group_monthly.csv", index=False)

    bridge = growth_bridge(rci, latest)
    bridge.to_csv(INTERMEDIATE / "growth_bridge.csv", index=False)
    sc = venue_scorecard(rci, venues, latest)
    sc.to_csv(INTERMEDIATE / "venue_scorecard.csv", index=False)
    ts = type_summary(rci, venues, bridge, latest)
    ts.to_csv(INTERMEDIATE / "type_summary.csv", index=False)
    ramp_curves(rci).to_csv(INTERMEDIATE / "ramp_curves.csv", index=False)
    up = acquisition_uplift(vm, venues)
    up.to_csv(INTERMEDIATE / "acquisition_uplift.csv", index=False)
    seasonality(rci).to_csv(INTERMEDIATE / "seasonality.csv", index=False)
    mix = rci.assign(year=rci["month"].dt.year).groupby(["venue_type", "year"])[DRINKS + ["total"]].sum()
    for d in DRINKS:
        mix[f"{d}_share"] = mix[d] / mix["total"]
    mix.reset_index().to_csv(INTERMEDIATE / "drinks_mix.csv", index=False)

    # Console summary
    pd.set_option("display.width", 250, "display.max_columns", 20, "display.float_format", "{:,.2f}".format)
    ttm_label = f"TTM {latest:%b %Y}"
    b = bridge[bridge["period"] == ttm_label]
    print(f"\n{ttm_label}: group ${b['current_revenue'].sum() / 1e6:,.1f}M vs prior ${b['prior_revenue'].sum() / 1e6:,.1f}M "
          f"({b['current_revenue'].sum() / b['prior_revenue'].sum() - 1:+.1%})")
    print((b.pivot_table(index="component", columns="venue_type", values="change", aggfunc="sum",
                         fill_value=0, margins=True) / 1e6).round(2))
    print("\nType summary:")
    print(ts.set_index("venue_type")[["ttm_revenue", "active_venues", "avg_monthly_revenue_per_venue_ttm",
                                       "closure_rate", "same_venue_growth_ttm_pct"]])
    print(ts.set_index("venue_type").filter(regex="^(change|revenue)_").div(1e6).round(2).T)
    print("\nTrend:", sc[sc["status"] == "Active"]["trend"].value_counts().to_dict())
    print("\nAcquisitions:")
    print(up[["venue_name", "acquired_month", "pre_12m_avg_monthly", "post_12m_avg_monthly",
              "acquisition_kind", "uplift_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
