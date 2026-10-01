# Multi-Venue Drink Revenue Review & 2027 Outlook
**Portfolio:** RCI Hospitality's Texas venues: gentlemen's clubs, Bombshells sports-bar restaurants and Chicas Locas Latin-themed clubs
**Data:** monthly drink sales filed with the Texas Comptroller, Jan 2007 – Aug 2026 (29 active venues, 47 run by RCI over the period)
**Prepared by:** Tamal · September 2026

---

## The short version
1. **Drink revenue is falling right now.** The last 12 months came to **$52.1M, down 7.7%**. Venues open throughout both
   periods were down **8.0%**, and 18 of the 27 active venues with two full years of history are declining.
2. **Growth since 2019 was bought and built, not grown.** Revenue rose from $35.2M (2019) to $52.7M (2025).
   **Acquisitions added $21.2M** and **new venues added $19.0M**. Existing venues **lost $14.7M** and closures cost $8.0M.
3. **Acquiring established clubs has worked better than building sports bars.** Gentlemen's clubs (+$11.7M) and
   Latin-themed clubs (+$7.7M) grew mainly through acquisitions. Sports bars gained +$15.5M from new openings but still
   ended **−$1.7M**, because existing sports bars lost $11.6M and closures cost $5.6M.
4. **2027 outlook: roughly flat.** The base forecast is **$52.4M** (approximate 80% range $48.3M–$56.5M, based on how far past back-tested forecasts were off,
   widened for months further ahead), −1.7% on the 2026
   estimate of $53.3M. Growth in 2027 depends on adding venues or reversing the same-venue decline.

![Where growth came from, 2019 to 2025](../images/02_growth_sources_since_2019.png)

## What each venue type contributed (2019 → 2025)
| Venue type | Last 12 months | Share | Same-venue growth (last 12 months) | Change 2019→2025 | Mainly from |
|---|---|---|---|---|---|
| Gentlemen's club (13 active) | $22.6M | 43% | −7.1% | **+$11.7M** | acquisitions +$12.1M |
| Sports-bar restaurant (12) | $20.5M | 39% | −5.6% | **−$1.7M** | openings +$15.5M, existing −$11.6M, closures −$5.6M |
| Latin-themed club (3) | $7.1M | 14% | **−17%** | **+$7.7M** | acquisitions +$9.1M |
| Other bar / nightclub (1) | $1.9M | 4% | −3.1% | −$269K | closures −$406K |

On **estimated total revenue**, which adds back the door and dance income clubs earn beyond drinks (from RCI's 10-K
segment mix), a Latin-themed club averages about **$431K a month**, a gentlemen's club about $337K and a sports bar
about $274K.

![Change by venue type and source, 2019 to 2025](../images/04_change_by_venue_type_since_2019.png)

## Evidence for acquisition decisions
- **Every going-concern acquisition sold more drinks in its first 12 months under RCI than in its last 12 before.**
  Chicas Locas Arlington rose +9.9%, Chicas Locas Houston +17%, Baby Dolls Dallas +50% and Chicas Locas Dallas +129%.
  Treat these figures carefully. There are only 4 deals, and the Chicas Locas Dallas jump coincided with rebranding
  the former Cabaret Royale. Part of any increase may also reflect the previous owner's reporting.
- **The gains fade.** The acquired Latin-themed clubs peaked about 12–15 months after purchase and are now **−17%**
  on a same-venue basis over the last 12 months. Acquisitions need a plan to hold the uplift after the first year.
- **New sports bars have a "honeymoon".** A new Bombshells does about $253K a month at opening, then falls about 36%
  to about $162K by month 18 (median, 3-month smoothed). Median first-year drink sales are $2.58M, falling to **$1.96M in
  year 2 (−24%)**. Judge new sites on their year-2 run-rate.
- **Concentration risk.** Baby Dolls Dallas alone is **18% of the active venues' drink revenue**, and it's down 6.7%.

![Acquisitions: 12 months before vs after](../images/11_acquisitions_before_vs_after.png)

## 2027 scenarios (drink revenue)
| Scenario | 2027 | vs 2026 est. | Assumption |
|---|---|---|---|
| Bear | $49.1M | −7.9% | same-venue sales 5% below forecast; the 2 weakest declining venues (PT's Showclub Odessa, Club Onyx Houston) close in July |
| **Base** | **$52.4M** | **−1.7%** | model forecast of today's 29 venues |
| Bull | $54.0M | +1.2% | same-venue sales 3% above forecast |
| Base + acquire 2 gentlemen's clubs | $54.7M | +2.6% | each performs like a typical established club ($1.17M drinks a year) |
| Base + acquire 2 Latin-themed clubs | $56.6M | +6.2% | each performs like a typical established Latin-themed club ($2.12M) |
| Base + open 2 sports bars | $57.5M | +7.9% | first-year honeymoon ($2.58M each); expect about −24% in year 2 |

![2027 scenarios](../images/15_scenarios_next_year.png)

## Recommendations
1. **Prioritise buying established, trading clubs over new sports-bar builds.** They have delivered the most growth and
   the highest revenue per venue once non-drink income is counted. Put a 12–24 month retention plan in place so the
   post-acquisition uplift doesn't fade.
2. **Fix same-venue decline first.** It's the biggest drag (−$4.2M over the last 12 months). Start with the largest
   dollar declines: Chicas Locas Dallas (−$718K), Baby Dolls Dallas (−$659K) and Bombshells Katy (−$469K).
3. **Value new sports-bar sites on year-2 revenue, not opening months.** Review underperformers against the ramp curve
   at month 12.
4. **Use the monthly forecast for planning** (stock, staffing, budgets). In back-tests it had a 14.8% venue-level
   error (WAPE) against 20.7% for "same month last year", and a 4.7% average error on the 12-month group total
   against 11.5% for the baseline. It was chosen on venue-level error; on the group total it is similar to, not
   better than, exponential smoothing (4.3%) and Prophet (4.1%).

## How this applies to any multi-venue group
The same pipeline runs on any group's till or accounting exports: clean → growth bridge (same-venue / new / acquired /
closed) → venue scorecard → forecast with a back-test → scenarios → charts. With item-level till (point-of-sale)
data it can also split growth into **volume, price and product mix**, and forecast by week or day for staff
scheduling and stock planning.

## Limitations
Drink sales only: door, dance, food and merchandise revenue aren't in the data, and "estimated total revenue" is an
estimate based on RCI's FY2024 10-K (alcohol was 43.3% of nightclub and 54.3% of Bombshells revenue). The data covers
Texas only and is monthly. There are no costs, margins or purchase prices, so this measures revenue, not return on
investment. The venue type is inferred for 6 of the 47 venues. There are only 4 going-concern acquisitions, so read
the acquisition findings as directional.
