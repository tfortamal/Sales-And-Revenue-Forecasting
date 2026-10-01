"""Shared paths and constants for the pipeline scripts.

Folder flow: data/1_raw (download, untouched) -> data/2_clean (one row per venue-month)
-> data/intermediate (working tables the scripts pass to each other)
-> 3_insight_tables (one CSV per business question, read by the charts)
-> 4_python_visuals (PNG charts) -> images (the charts the README embeds).
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "1_raw"
RAW = RAW_DIR / "rci_texas_mixed_beverage_receipts.csv"
VENUE_TYPES = ROOT / "config" / "venue_types.csv"
CLEAN = ROOT / "data" / "2_clean"
INTERMEDIATE = ROOT / "data" / "intermediate"
TABLES = ROOT / "3_insight_tables"   # one CSV per insight, read by the charts
VISUALS = ROOT / "4_python_visuals"
IMAGES = ROOT / "images"

VENUE_MONTH = CLEAN / "venue_month.csv"
VENUES = CLEAN / "venues.csv"

DRINKS = ["liquor", "wine", "beer"]

# Alcohol's share of segment revenue in RCI's FY2024 10-K. Used only to show an
# *estimated* total revenue (drink sales / share) so venue types can be compared
# fairly: clubs earn much of their revenue from service fees, which this data lacks.
ALCOHOL_SHARE = {
    "Gentlemen's club": 0.433,        # Nightclubs segment
    "Latin-themed club": 0.433,       # Nightclubs segment
    "Other bar / nightclub": 0.433,   # assumed nightclub-like
    "Sports-bar restaurant": 0.543,   # Bombshells segment
}
# "43% nightclubs, 54% Bombshells": the shares above as chart / note text.
ALCOHOL_SHARE_NOTE = "{:.0%} nightclubs, {:.0%} Bombshells".format(
    ALCOHOL_SHARE["Gentlemen's club"], ALCOHOL_SHARE["Sports-bar restaurant"])
# A venue counts as active if it filed sales in any of the last N months
# (filings can arrive a little late).
ACTIVE_WINDOW_MONTHS = 3
# Growth within +/-5% counts as "Stable" (venue trend, and every Direction column).
TREND_BAND = 0.05
# Long-run growth window starts here: the last full pre-COVID year.
BASE_YEAR = 2019


# The forecast window follows the data, so a fresh download moves every date forward.
def forecast_year(latest):
    """Year the outlook is for: the calendar year after the latest month of data."""
    return latest.year + 1


def backtest_origins(latest):
    """Back-test starting points: the same month 3, 2 and 1 years before the latest month."""
    return [latest - pd.DateOffset(years=k) for k in (3, 2, 1)]
SELECTED_MODEL = INTERMEDIATE / "forecast_selected_model.txt"   # written by 04, read by 06 / 07


# Display formatting shared by the insight tables (06) and the charts (07).
def money(v: float, signed: bool = False, dp: int = 1) -> str:
    """$52.1M / $152K; signed adds + or − (a true minus sign). Blank for a missing value."""
    if pd.isna(v):
        return ""
    a = abs(v)
    body = f"${a / 1e6:,.{dp}f}M" if a >= 1e6 else f"${a / 1e3:,.0f}K"
    sign = ("+" if v > 0 else "−" if v < 0 else "") if signed else ("−" if v < 0 else "")
    return sign + body


def pct(v: float, dp: int = None, signed: bool = True) -> str:
    """+18% / −4.6%. By default one decimal under 10%, so −4.6% (Stable) and −5.4% (Declining)
    never both show as "−5%"; a value that rounds to zero shows as 0% with no sign; unsigned
    shows the size only. Blank for a missing value."""
    if pd.isna(v):
        return ""
    if dp is None:
        dp = 1 if abs(v) < 0.10 else 0
    if round(abs(v) * 100, dp) == 0:
        return f"{0:.{dp}f}%"
    sign = ("+" if v > 0 else "−" if v < 0 else "") if signed else ""
    return f"{sign}{abs(v) * 100:.{dp}f}%"
