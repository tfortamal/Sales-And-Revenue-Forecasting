"""Download RCI Hospitality's Texas venue filings from the Texas Comptroller
Mixed Beverage Gross Receipts dataset (data.texas.gov, id naix-2893).

Every Texas venue holding a mixed-beverage permit files monthly receipts for
liquor, wine, beer and cover charges. RCI venues are picked out by the
taxpayer entity that files for them:
  - HQ address 10737 Cutten Rd (current) or 10959 Cutten Rd (former), Houston
  - "BMB DINING SERVICES ..." entities (the Bombshells restaurant chain),
    some of which file from an accountant's address
  - Rockwall Restaurant Group (Bombshells Rowlett)
Other businesses on Cutten Rd (apartments, unrelated restaurants) are excluded.

Many RCI venues were acquired. Filings by earlier owners at the same street
address are also pulled and tagged owner_period = "pre_RCI", so each venue's
history before and after acquisition can be compared.

Output: data/1_raw/rci_texas_mixed_beverage_receipts.csv (raw, never edited by later steps)

Usage: python src/01_download_data.py   (or: python run_all.py --download)
"""
import pandas as pd
import requests

from common import RAW as OUT   # data/1_raw/rci_texas_mixed_beverage_receipts.csv

API = "https://data.texas.gov/resource/naix-2893.csv"

RCI_WHERE = (
    "taxpayer_address in ('10737 CUTTEN RD', '10959 CUTTEN RD') "
    "OR upper(taxpayer_name) like 'BMB DINING SERVICES%' "
    "OR upper(taxpayer_name) like 'ROCKWALL RESTAURANT GROUP%'"
)

# Same site written differently by an earlier owner -> RCI's spelling of it.
ADDRESS_ALIASES = {
    ("3601 HIGHWAY 157", "BEDFORD"): ("3601 S HIGHWAY 157", "EULESS"),  # Baby Dolls Fort Worth
}


def download(where: str, page_size: int = 50_000) -> pd.DataFrame:
    pages, offset = [], 0
    while True:
        params = {"$where": where, "$order": "obligation_end_date_yyyymmdd, taxpayer_number",
                  "$limit": page_size, "$offset": offset}
        resp = requests.get(API, params=params, timeout=120)
        resp.raise_for_status()
        page = pd.read_csv(pd.io.common.StringIO(resp.text))
        pages.append(page)
        if len(page) < page_size:
            return pd.concat(pages, ignore_index=True)
        offset += page_size


def sql_list(values) -> str:
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


def keep_handover_chain(pre: pd.DataFrame, rci: pd.DataFrame) -> pd.DataFrame:
    """Keep only earlier owners that handed a site straight to the next owner.

    Walking back from RCI's first month at a site, an entity is kept if its last
    filing is within ~1 month (either side) of the next owner's first filing. That drops
    unrelated businesses that left the site long before (RCI new-builds) and
    ones filing alongside RCI at the same address (other tenants).
    """
    site = ["location_address", "location_city"]
    month = "obligation_end_date_yyyymmdd"
    pre, rci = pre.copy(), rci.copy()
    pre[month] = pd.to_datetime(pre[month])
    rci_start = rci.assign(**{month: pd.to_datetime(rci[month])}).groupby(site)[month].min()
    spans = pre.groupby(site + ["taxpayer_number"])[month].agg(["min", "max"]).reset_index()

    keep = []
    for key, owners in spans.groupby(site):
        boundary = rci_start[key]
        for _, o in owners.sort_values("max", ascending=False).iterrows():
            if abs(o["max"] - boundary) <= pd.Timedelta(days=45):
                keep.append((*key, o["taxpayer_number"]))
                boundary = o["min"]
    keep = pd.DataFrame(keep, columns=site + ["taxpayer_number"])
    pre = pre.merge(keep, on=site + ["taxpayer_number"])
    pre[month] = pre[month].dt.strftime("%Y-%m-%dT%H:%M:%S.000")
    return pre


def main() -> None:
    rci = download(RCI_WHERE)
    rci["owner_period"] = "RCI"

    # Earlier owners at RCI venue addresses (chunked to keep the URL short).
    rci_taxpayers = sql_list(rci["taxpayer_number"].unique())
    addresses = sorted(set(rci["location_address"]) | {a for a, _ in ADDRESS_ALIASES})
    pre = []
    for i in range(0, len(addresses), 20):
        where = (f"location_address in ({sql_list(addresses[i:i + 20])}) "
                 f"AND taxpayer_number not in ({rci_taxpayers})")
        pre.append(download(where))
    pre = pd.concat(pre, ignore_index=True)
    for (addr, city), (to_addr, to_city) in ADDRESS_ALIASES.items():
        hit = (pre["location_address"] == addr) & (pre["location_city"] == city)
        pre.loc[hit, ["location_address", "location_city"]] = [to_addr, to_city]
    # Same street address must also be the same city to count as the same venue.
    rci_sites = rci[["location_address", "location_city"]].drop_duplicates()
    pre = pre.merge(rci_sites, on=["location_address", "location_city"])
    pre = keep_handover_chain(pre, rci)
    pre["owner_period"] = "pre_RCI"

    df = pd.concat([pre, rci], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Saved {len(df):,} rows -> {OUT}")
    print(df.groupby("owner_period").agg(rows=("taxpayer_number", "size"),
                                         entities=("taxpayer_number", "nunique")))


if __name__ == "__main__":
    main()
