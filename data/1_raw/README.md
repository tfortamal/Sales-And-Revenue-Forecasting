# RCI Hospitality — Texas venue drink sales (2007–2026)

**File:** `rci_texas_mixed_beverage_receipts.csv` (5,780 rows, in `data/1_raw/`; rebuild with `python src/01_download_data.py` or `python run_all.py --download`)
**Source:** Texas Comptroller of Public Accounts, *Mixed Beverage Gross Receipts*, via the
[Texas Open Data Portal](https://data.texas.gov/resource/naix-2893) (public data; no login required).
**Downloaded:** 2026-09-26. Latest complete month: Aug 2026.

Every Texas venue with a mixed-beverage permit must report its monthly receipts from liquor,
wine, beer and cover charges. This file contains the filings for venues run by
**RCI Hospitality Holdings (NASDAQ: RICK)**, a multi-venue group running gentlemen's clubs
(Rick's Cabaret, Baby Dolls, Scarlett's, XTC, Silver City…), Bombshells sports-bar restaurants
and Chicas Locas Latin nightclubs.

## How RCI venues were identified
| Rule | Why |
|---|---|
| Filing entity address is `10737 CUTTEN RD` (current HQ) or `10959 CUTTEN RD` (former HQ) | RCI's subsidiaries file from head office |
| Entity name starts `BMB DINING SERVICES` | Bombshells chain entities; some file from an accountant's address instead of HQ |
| Entity name starts `ROCKWALL RESTAURANT GROUP` | Bombshells Rowlett |
| Excluded: other Cutten Rd addresses | Apartments and unrelated businesses on the same road |

**Acquisition history (`owner_period = pre_RCI`)**: filings by earlier owners at the same address and city,
kept only where ownership passed directly to the next owner (the previous owner's last filing is within about 1 month, either side, of the next owner's first). One site written differently by its earlier owner (`3601 HIGHWAY 157, BEDFORD` = `3601 S HIGHWAY 157, EULESS`) is mapped through `ADDRESS_ALIASES` in the script.
This drops new-build sites where an unrelated business had left long before, and other tenants
filing at the same address at the same time.

| Venue today | Pre-RCI history | RCI since |
|---|---|---|
| Baby Dolls, Dallas | TTNA → BDS Restaurant, 2007– | Mar 2023 |
| Chicas Locas, Houston | Michael's International → Chicas Locas, 2007– | Mar 2023 |
| Chicas Locas, Dallas | Cabaret Royale, 2007– | Mar 2023 |
| Chicas Locas, Arlington | Fare Arlington, 2007– | Mar 2024 |
| PT's Showclub, Odessa | The Catwalk, 2020– | Jul 2022 |
| Baby Dolls, Euless (Hwy 157) | DB Entertainment, 2007– (dormant after 2020) | Mar 2023; closed after a fire, Jul 2024 |
| The New West, Aledo | New West, 2007– | Oct 2010 (never traded under RCI) |

The `Acquired` date in the insight tables is the first month with sales under RCI, so it can be later than the date above:
Aug 2022 for PT's Showclub and Jun 2023 for Baby Dolls Euless (Hwy 157).

## Columns used
| Column | Meaning |
|---|---|
| `obligation_end_date_yyyymmdd` | Reporting month (last day of the month) |
| `location_name`, `location_address`, `location_city` | Venue. **Use address + city as the venue key** — names repeat (e.g. several "BOMBSHELLS" in Houston) |
| `taxpayer_name`, `taxpayer_number` | Legal entity filing (one per venue, changes on acquisition) |
| `tabc_permit_number` | Alcohol permit |
| `liquor_receipts`, `wine_receipts`, `beer_receipts` | Gross drink sales, USD |
| `cover_charge_receipts` | Cover (door) charges. Zero on almost every row (233 of 5,780 rows are non-zero, mostly under previous owners; $205K in total, of which about $32K under RCI). Included in `total_receipts`. |
| `total_receipts` | Sum of the four above (verified on every row) |
| `owner_period` | `RCI` or `pre_RCI` (added by the download script) |

## Known limitations / cleaning notes
- **Drinks only.** Door fees (apart from small cover-charge amounts), dance/service revenue, food and merchandise are
  not in this data.
  Per RCI's FY2024 10-K, alcohol was about 43% of nightclub revenue and about 54% of Bombshells revenue.
- **Texas only.** RCI also has venues in other states.
- Some venue-months are **handover months** where the old and new owner both filed. `02_clean.py` sums these by venue and month.
- Many rows have **zero receipts** (permits held while a venue was closed or not yet open). `02_clean.py` treats these as non-trading months, not as sales of $0.
- Filings can be amended or submitted late, so re-download before a final run.

## Sanity check vs RCI's FY2024 10-K (fiscal year Oct–Sep)
| | This data (Texas drinks) | 10-K (all states, all revenue) |
|---|---|---|
| Bombshells FY24 growth | −14.7% | −9.2% |
| Nightclubs FY24 growth | +45.3% (full year of the Mar-2023 acquisitions) | +3.0% |

(Recomputed on the final cleaned data, `data/2_clean/venue_month.csv`, RCI-owned months.)

The Bombshells decline matches in direction and roughly in size (Texas drink sales fell somewhat faster than company-wide revenue). The nightclub gap is explained by acquisitions, which is why the analysis
separates **same-venue growth** from **new or acquired venues**.
