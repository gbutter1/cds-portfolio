"""
Fetch Georgia's weekly influenza-like-illness (ILI) data from the CDC's
ILINet surveillance network, via the public Delphi Epidata API
(Carnegie Mellon University), which republishes CDC FluView data.

Source:      CDC ILINet / FluView (U.S. Outpatient Influenza-like Illness
             Surveillance Network), public U.S. government data.
Republisher: https://api.delphi.cmu.edu/epidata/fluview/
Docs:        https://cmu-delphi.github.io/delphi-epidata/api/fluview.html

Writes data/raw/healthcare_diagnosis/cdc_ilinet_ga.csv with one row per
MMWR epiweek, plus the Sunday the week starts on, so it lines up with the
facility data. Uses only the Python standard library.

If the API cannot be reached, the script writes a header-only file and exits
successfully: the rest of the pipeline still runs, and the app shows a
"CDC data unavailable" note instead of the comparison chart.

Usage:
    python projects/healthcare_diagnosis/fetch_cdc_flu.py
    python projects/healthcare_diagnosis/fetch_cdc_flu.py --region ga --from 202440 --to 202639
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.delphi.cmu.edu/epidata/fluview/"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "healthcare_diagnosis"
FIELDS = ["region", "epiweek", "week_start", "ili_pct", "wili_pct", "num_ili", "num_patients",
          "num_providers", "release_date", "issue"]


def mmwr_week_start(epiweek: int) -> date:
    """Sunday on which MMWR week YYYYWW begins.

    MMWR week 1 is the first Sunday-to-Saturday week with at least four days in
    the calendar year, which is always the week that contains January 4th.
    """
    year, week = divmod(epiweek, 100)
    jan4 = date(year, 1, 4)
    week1_start = jan4 - timedelta(days=(jan4.weekday() + 1) % 7)  # back up to Sunday
    return week1_start + timedelta(weeks=week - 1)


def fetch(region: str, first: int, last: int) -> list[dict]:
    url = f"{API}?regions={region}&epiweeks={first}-{last}"
    req = urllib.request.Request(url, headers={"User-Agent": "cds-portfolio pipeline"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if payload.get("result") != 1:
        raise RuntimeError(f"API returned result={payload.get('result')}: {payload.get('message')}")
    rows = []
    for rec in payload["epidata"]:
        rows.append({
            "region": rec["region"],
            "epiweek": rec["epiweek"],
            "week_start": mmwr_week_start(int(rec["epiweek"])).isoformat(),
            "ili_pct": rec.get("ili"),
            "wili_pct": rec.get("wili"),
            "num_ili": rec.get("num_ili"),
            "num_patients": rec.get("num_patients"),
            "num_providers": rec.get("num_providers"),
            "release_date": rec.get("release_date"),
            "issue": rec.get("issue"),
        })
    return sorted(rows, key=lambda r: r["epiweek"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="ga")
    ap.add_argument("--from", dest="first", type=int, default=202440)
    ap.add_argument("--to", dest="last", type=int, default=202639)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "cdc_ilinet_ga.csv"
    try:
        rows = fetch(args.region, args.first, args.last)
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError, KeyError) as e:
        print(f"WARNING: could not fetch CDC FluView data ({e}). Writing an empty file; "
              "the app will show the comparison as unavailable.", file=sys.stderr)
        rows = []

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows):>9,} rows -> {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
