"""Run the whole pipeline: clean -> analyse -> forecast -> scenarios -> insight tables -> charts.

    python run_all.py              # uses the raw download already in data/1_raw/
    python run_all.py --download   # re-download the latest filings into data/1_raw/ first

Folder flow:
    data/1_raw/          raw Comptroller filings (01_download_data.py), never edited
    data/2_clean/        one row per venue-month + venue list (02_clean.py)
    data/intermediate/   working tables passed between scripts (03-05)
    3_insight_tables/    one CSV per business question + _index.csv (06)
    4_python_visuals/    one labelled PNG chart per insight (07)
    images/              the key charts for the README + _list.txt (07)
"""
import runpy
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
STEPS = ["02_clean.py", "03_growth_analysis.py", "04_forecast.py", "05_scenarios.py",
         "06_insight_tables.py", "07_figures.py"]

if __name__ == "__main__":
    sys.dont_write_bytecode = True   # keep src/ free of __pycache__
    sys.path.insert(0, str(SRC))
    steps = (["01_download_data.py"] if "--download" in sys.argv else []) + STEPS
    for step in steps:
        start = time.time()
        print(f"\n=== {step} ===")
        runpy.run_path(str(SRC / step), run_name="__main__")
        print(f"--- {step} done in {time.time() - start:.0f}s")
