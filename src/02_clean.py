"""Turn the raw Comptroller filings into one clean venue x month table.

Outputs
  data/2_clean/venue_month.csv    one row per venue per month while in business
                                  (short closures kept as $0 rows, trading=False)
  data/2_clean/venues.csv         one row per venue: type, entry route, dates, status

Rules
  - A venue is a site (address + city) mapped through config/venue_types.csv;
    relocations inside the same building/road share one venue_name.
  - Months where the old and new owner both filed (handover) are summed.
  - $0 filings are permits held while not trading: they are not sales.
  - Gaps of up to 12 months inside a venue's life are kept as $0 months (temporary
    closure); longer gaps are dropped (closed, later reopened).
"""
import pandas as pd

from common import (ACTIVE_WINDOW_MONTHS, CLEAN, DRINKS, RAW, VENUE_MONTH,
                    VENUE_TYPES, VENUES)

MAX_GAP_MONTHS = 12


def load_raw() -> pd.DataFrame:
    raw = pd.read_csv(RAW)
    raw["month"] = pd.to_datetime(raw["obligation_end_date_yyyymmdd"]).dt.to_period("M").dt.to_timestamp()
    raw = raw.rename(columns={f"{d}_receipts": d for d in DRINKS} | {"total_receipts": "total"})
    return raw


def main() -> None:
    raw = load_raw()
    types = pd.read_csv(VENUE_TYPES)
    df = raw.merge(types, on=["location_address", "location_city"], how="left", validate="many_to_one")
    assert df["venue_name"].notna().all(), "site missing from config/venue_types.csv"

    # One row per venue-month; RCI owns the month if it filed at all.
    df["is_rci"] = df["owner_period"].eq("RCI")
    vm = (df.groupby(["venue_name", "month"])
            .agg(**{d: (d, "sum") for d in DRINKS}, total=("total", "sum"), rci=("is_rci", "any"))
            .reset_index())
    vm["owner_period"] = vm.pop("rci").map({True: "RCI", False: "pre_RCI"})
    assert abs(vm["total"].sum() - raw["total"].sum()) < 1, "totals changed during aggregation"

    # Venue attributes from the trading months.
    trading = vm[vm["total"] > 0]
    latest = vm["month"].max()
    active_from = latest - pd.DateOffset(months=ACTIVE_WINDOW_MONTHS - 1)
    rci_trading = trading[trading["owner_period"] == "RCI"]
    venues = (types.drop(columns=["location_address", "location_city"])
                   .drop_duplicates("venue_name").set_index("venue_name"))
    venues["city"] = types.groupby("venue_name")["location_city"].first().str.title()
    venues["first_trading_month"] = trading.groupby("venue_name")["month"].min()
    venues["rci_first_month"] = rci_trading.groupby("venue_name")["month"].min()
    venues["rci_last_month"] = rci_trading.groupby("venue_name")["month"].max()
    has_pre = vm[vm["owner_period"] == "pre_RCI"].groupby("venue_name").size().gt(0)
    venues["has_pre_rci_filings"] = venues.index.isin(has_pre[has_pre].index)

    def entry_route(v) -> str:
        if pd.isna(v["rci_first_month"]):
            return "Never traded under RCI"
        if v["has_pre_rci_filings"]:
            return "Acquired"
        if v["brand"] == "Bombshells":
            return "Opened by RCI"
        if v["rci_first_month"] == vm["month"].min():
            return "Legacy (owned before 2007)"
        return "Added (route not confirmed)"

    venues["entry_route"] = venues.apply(entry_route, axis=1)
    venues["status"] = "Closed"
    venues.loc[venues["rci_last_month"] >= active_from, "status"] = "Active"
    venues.loc[venues["entry_route"] == "Never traded under RCI", "status"] = "Never traded"
    venues["closed_month"] = venues["rci_last_month"].where(venues["status"] == "Closed")

    # Full monthly panel from first to last trading month (any owner). Short gaps
    # (temporary closures, e.g. COVID) become $0 months; gaps longer than
    # MAX_GAP_MONTHS mean the venue closed and later reopened, so they are left out.
    panels = []
    for name, g in vm.groupby("venue_name"):
        t = g[g["total"] > 0]
        if t.empty:
            continue
        idx = pd.date_range(t["month"].min(), t["month"].max(), freq="MS")
        p = g.set_index("month").reindex(idx).rename_axis("month").reset_index()
        p["venue_name"] = name
        p[DRINKS + ["total"]] = p[DRINKS + ["total"]].fillna(0)
        p["owner_period"] = p["owner_period"].ffill().bfill()
        idle = p["total"].le(0)
        run_id = (idle != idle.shift()).cumsum()
        run_len = idle.groupby(run_id).transform("size")
        panels.append(p[~(idle & (run_len > MAX_GAP_MONTHS))])
    panel = pd.concat(panels, ignore_index=True)
    panel["trading"] = panel["total"] > 0
    for d in DRINKS:
        panel[f"{d}_share"] = (panel[d] / panel["total"]).where(panel["trading"]).round(4)
    panel = panel.merge(venues[["venue_type", "brand", "city"]], left_on="venue_name", right_index=True)
    panel = panel[["venue_name", "venue_type", "brand", "city", "month", "owner_period", "trading",
                   *DRINKS, "total", *[f"{d}_share" for d in DRINKS]]]

    # Checks: unique venue-month, nothing lost.
    assert not panel.duplicated(["venue_name", "month"]).any()
    assert abs(panel["total"].sum() - raw["total"].sum()) < 1

    CLEAN.mkdir(parents=True, exist_ok=True)
    panel.to_csv(VENUE_MONTH, index=False)
    venues.reset_index().to_csv(VENUES, index=False)

    print(f"venue_month: {len(panel):,} rows, {panel['venue_name'].nunique()} venues, "
          f"{panel['month'].min():%b %Y} – {panel['month'].max():%b %Y}; total ${panel['total'].sum() / 1e6:,.1f}M")
    print(venues.groupby(["venue_type", "status"]).size().unstack(fill_value=0))
    print(venues["entry_route"].value_counts())


if __name__ == "__main__":
    main()
