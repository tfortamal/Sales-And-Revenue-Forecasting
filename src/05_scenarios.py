"""Next-year scenarios and the 'what should we add next' playbook.

venue_playbook.csv
  For every venue type x entry route (opened by RCI / acquired going concern / acquired
  dormant club reopened / other), what a venue typically brings in: median revenue in its
  1st, 2nd and 3rd year after joining, and how many were still trading 3 years later.
  Also the typical annual revenue of an established venue of each type (2+ years under RCI).
  Sample sizes are small for acquisitions, so `venues` is always shown alongside.

scenarios_monthly.csv / scenario_summary.csv
  Group drink revenue for the forecast year (the year after the latest data, currently 2027)
  under explicit assumptions (edit SCENARIOS below):
    Base  the model forecast for today's venues
    Bear  same-venue sales 5% below forecast, 2 weakest declining venues close from July
    Bull  same-venue sales 3% above forecast
  plus 'what-if' lines: Base + adding venues of a given type from January of the forecast year.
  A new build is valued at the typical first-year revenue of RCI's past openings of that type;
  an acquired going concern at the typical annual revenue of an established venue of that type
  (acquisition samples are too small, 1-3 deals per type, to value it on their own).
"""
import numpy as np
import pandas as pd

from common import INTERMEDIATE, VENUE_MONTH, VENUES, forecast_year

CLOSE_FROM_MONTH = 7       # Bear: the weakest venues close from this month (7 = July)

# Additions are (venue_type, entry_route, count); each starts trading in January.
SCENARIOS = {
    "Bear": {"same_venue": -0.05, "close_weakest": 2, "add": []},
    "Base": {"same_venue": 0.00, "close_weakest": 0, "add": []},
    "Bull": {"same_venue": +0.03, "close_weakest": 0, "add": []},
    "Base + acquire 2 gentlemen's clubs": {"same_venue": 0.0, "close_weakest": 0,
                                           "add": [("Gentlemen's club", "Acquired", 2)]},
    "Base + acquire 2 Latin-themed clubs": {"same_venue": 0.0, "close_weakest": 0,
                                            "add": [("Latin-themed club", "Acquired", 2)]},
    "Base + open 2 sports-bar restaurants": {"same_venue": 0.0, "close_weakest": 0,
                                             "add": [("Sports-bar restaurant", "Opened by RCI", 2)]},
}


def venue_words(vtype: str, n: int) -> str:
    """"Latin-themed club", 2 -> "Latin-themed clubs"; lower-case unless it starts with a proper name."""
    name = vtype if vtype.startswith("Latin") else vtype[0].lower() + vtype[1:]
    return name + ("s" if n != 1 else "")


def route_words(route: str) -> str:
    """"Opened by RCI" -> "opened by RCI", "Acquired" -> "acquired"."""
    return route[0].lower() + route[1:]


def playbook(vm: pd.DataFrame, venues: pd.DataFrame, uplift: pd.DataFrame) -> pd.DataFrame:
    """Revenue in years 1-3 after joining RCI, per venue type x entry route (venues added after 2007)."""
    rci = vm[vm["owner_period"] == "RCI"].merge(venues[["venue_name", "entry_route", "rci_first_month"]],
                                                 on="venue_name")
    latest = rci["month"].max()
    rci = rci[rci["rci_first_month"] > rci["month"].min()]
    rci["year_n"] = (((rci["month"].dt.year - rci["rci_first_month"].dt.year) * 12
                      + rci["month"].dt.month - rci["rci_first_month"].dt.month) // 12) + 1
    per_venue = rci[rci["year_n"] <= 3].pivot_table(index="venue_name", columns="year_n",
                                                     values="total", aggfunc="sum")
    per_venue.columns = [f"year{c}_revenue" for c in per_venue.columns]
    v = venues.set_index("venue_name").join(per_venue, how="inner")
    # Only count a year once the venue has had the chance to complete it.
    for n in (1, 2, 3):
        due = v["rci_first_month"] + pd.DateOffset(months=12 * n - 1) <= latest
        v.loc[~due, f"year{n}_revenue"] = np.nan
    three_years = v["rci_first_month"] + pd.DateOffset(months=35) <= latest
    survived = v["rci_last_month"] >= v["rci_first_month"] + pd.DateOffset(months=35)
    v["survived_3yrs"] = survived.astype(float).where(three_years)
    kind = uplift.set_index("venue_name")["acquisition_kind"]
    route = v["entry_route"].replace({"Added (route not confirmed)": "Other / unconfirmed"})
    acquired = route == "Acquired"
    route[acquired] = "Acquired – " + kind.reindex(route[acquired].index).str.lower()
    g = v.assign(entry_route=route).groupby(["venue_type", "entry_route"])
    out = g.agg(venues=("year1_revenue", "size"),
                median_year1_revenue=("year1_revenue", "median"),
                median_year2_revenue=("year2_revenue", "median"),
                median_year3_revenue=("year3_revenue", "median"),
                venues_with_3yr_history=("survived_3yrs", "count"),
                survived_3yrs=("survived_3yrs", "sum"))
    out["survival_rate_3yrs"] = out["survived_3yrs"] / out["venues_with_3yr_history"].replace(0, np.nan)
    out = out.reset_index()

    # Typical established venue per type: TTM revenue of active venues with 2+ years under RCI.
    ttm = vm[(vm["owner_period"] == "RCI") & (vm["month"] > latest - pd.DateOffset(months=12))]
    ttm = ttm.groupby("venue_name")["total"].sum()
    est = venues[(venues["status"] == "Active")
                 & (venues["rci_first_month"] <= latest - pd.DateOffset(months=23))].set_index("venue_name")
    est = est.join(ttm.rename("ttm")).groupby("venue_type")["ttm"].agg(["median", "size"])
    out["established_venue_median_ttm"] = out["venue_type"].map(est["median"])
    out["established_venues"] = out["venue_type"].map(est["size"])
    return out


def main() -> None:
    vm = pd.read_csv(VENUE_MONTH, parse_dates=["month"])
    venues = pd.read_csv(VENUES, parse_dates=["rci_first_month", "rci_last_month"])
    fc = pd.read_csv(INTERMEDIATE / "forecast_venue_monthly.csv", parse_dates=["month"])
    sc = pd.read_csv(INTERMEDIATE / "venue_scorecard.csv")
    season = pd.read_csv(INTERMEDIATE / "seasonality.csv").pivot(index="month_num", columns="venue_type",
                                                             values="seasonality_index")
    pb = playbook(vm, venues, pd.read_csv(INTERMEDIATE / "acquisition_uplift.csv"))
    pb.to_csv(INTERMEDIATE / "venue_playbook.csv", index=False)

    year = forecast_year(vm.loc[vm["owner_period"] == "RCI", "month"].max())
    months = pd.date_range(f"{year}-01-01", f"{year}-12-01", freq="MS")
    base = fc[fc["month"].isin(months)].pivot_table(index="month", columns="venue_name", values="forecast")
    weakest = (sc[(sc["trend"] == "Declining")].nsmallest(2, "ttm_revenue")["venue_name"].tolist())

    rows, summary = [], []
    for name, s in SCENARIOS.items():
        venue_rev = base * (1 + s["same_venue"])
        closed = weakest[: s["close_weakest"]]
        venue_rev.loc[venue_rev.index.month >= CLOSE_FROM_MONTH, closed] = 0
        total = venue_rev.sum(axis=1)
        added = pd.Series(0.0, index=months)
        for vtype, route, n in s["add"]:
            if route == "Opened by RCI":
                year1 = pb.set_index(["venue_type", "entry_route"]).loc[(vtype, route), "median_year1_revenue"]
            else:   # acquired going concern -> typical established venue of that type
                year1 = pb.loc[pb["venue_type"] == vtype, "established_venue_median_ttm"].iat[0]
            idx = season.loc[months.month, vtype].values
            added += n * year1 / 12 * idx / idx.mean()
        total = total + added
        rows += [{"scenario": name, "month": m, "revenue": r, "of_which_new_venues": a}
                 for m, r, a in zip(months, total, added)]
        desc = [f"same-venue {s['same_venue']:+.0%} vs forecast" if s["same_venue"] else "same-venue sales as forecast"]
        if closed:
            desc.append(f"closes {' & '.join(closed)} from {pd.Timestamp(2000, CLOSE_FROM_MONTH, 1):%B}")
        desc += [f"adds {n} {venue_words(vt, n)} ({route_words(r)}) in January" for vt, r, n in s["add"]]
        summary.append({"scenario": name, "forecast_year": year, "revenue_forecast_year": total.sum(),
                        "new_venue_revenue": added.sum(), "assumptions": "; ".join(desc)})

    est_current = (vm[(vm["owner_period"] == "RCI") & (vm["month"].dt.year == year - 1)]["total"].sum()
                   + fc[(fc["month"].dt.year == year - 1)]["forecast"].sum())
    summ = pd.DataFrame(summary)
    summ["vs_current_year_estimate_pct"] = summ["revenue_forecast_year"] / est_current - 1
    summ["estimate_current_year"] = est_current
    pd.DataFrame(rows).to_csv(INTERMEDIATE / "scenarios_monthly.csv", index=False)
    summ.to_csv(INTERMEDIATE / "scenario_summary.csv", index=False)

    pd.set_option("display.width", 250, "display.max_colwidth", 120)
    print("Venue playbook ($K):")
    show = pb.copy()
    for c in show.filter(regex="median").columns:
        show[c] = (show[c] / 1e3).round(0)
    print(show.to_string(index=False))
    print(f"\n{year - 1} estimate (actual + forecast): ${est_current / 1e6:,.1f}M")
    print(summ.assign(revenue_forecast_year=lambda d: (d["revenue_forecast_year"] / 1e6).round(1),
                      vs_current_year_estimate_pct=lambda d: (d["vs_current_year_estimate_pct"] * 100).round(1))
              [["scenario", "revenue_forecast_year", "vs_current_year_estimate_pct", "assumptions"]].to_string(index=False))


if __name__ == "__main__":
    main()
