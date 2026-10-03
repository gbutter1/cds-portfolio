"""
Synthetic outpatient / emergency encounter extract for six fictional
Atlanta-area facilities, Oct 2024 - Sep 2026 (two full flu seasons).

Diagnosis codes are real ICD-10-CM codes (see dbt/seeds/icd10_reference.csv);
the patients, visits and facilities are invented. Every facility type has its
own diagnosis mix and every code has its own seasonality (flu peaks in
winter, allergies in spring, injuries in summer, school physicals in
July-August, immunizations in the fall), so the numbers behave like a real
health system's would.

Deliberate data-quality problems are injected so the dbt layer has real work
to do: codes typed in lower case or without the dot, invalid codes, missing
codes, duplicate rows, an unknown facility ID, and impossible dates.

Usage:
    python projects/healthcare_diagnosis/generate.py
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SEED = 20261003
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "healthcare_diagnosis"
START = date(2024, 10, 1)
END = date(2026, 9, 30)

# id, name, type, city, county, avg visits per open day, open weekends?
FACILITIES = [
    ("F01", "Chattahoochee Ridge Medical Center (Emergency)", "Emergency", "Duluth", "Gwinnett", 92, True),
    ("F02", "Sweetwater Urgent Care", "Urgent care", "Lawrenceville", "Gwinnett", 58, True),
    ("F03", "Briarwood Family Practice", "Family medicine", "Norcross", "Gwinnett", 64, False),
    ("F04", "Oakmont Pediatrics", "Pediatrics", "Suwanee", "Gwinnett", 52, False),
    ("F05", "Pinecrest Internal Medicine", "Internal medicine", "Alpharetta", "Fulton", 46, False),
    ("F06", "Lakeview Community Health Center", "Community health center", "Decatur", "DeKalb", 44, False),
]

AGE_GROUPS = ["0-4", "5-17", "18-44", "45-64", "65+"]
AGE_RANGES = {"0-4": (0, 4), "5-17": (5, 17), "18-44": (18, 44), "45-64": (45, 64), "65+": (65, 92)}
AGE_MIX = {
    "Emergency": [0.08, 0.10, 0.38, 0.26, 0.18],
    "Urgent care": [0.07, 0.16, 0.44, 0.23, 0.10],
    "Family medicine": [0.08, 0.14, 0.30, 0.28, 0.20],
    "Pediatrics": [0.45, 0.55, 0.0, 0.0, 0.0],
    "Internal medicine": [0.0, 0.0, 0.22, 0.40, 0.38],
    "Community health center": [0.10, 0.15, 0.33, 0.28, 0.14],
}
ENCOUNTER_TYPE = {
    "Emergency": "ED visit", "Urgent care": "Urgent care visit", "Family medicine": "Office visit",
    "Pediatrics": "Office visit", "Internal medicine": "Office visit", "Community health center": "Office visit",
}

CODES = ["J10.1", "J11.1", "J06.9", "J02.9", "J20.9", "J01.90", "J18.9", "J45.909", "J30.9", "U07.1",
         "R05.9", "R50.9", "R51.9", "R07.9", "R10.9", "B34.9", "A08.4", "H66.90", "L03.90", "N39.0",
         "I10", "E11.9", "E78.5", "E66.9", "K21.9", "G43.909", "F41.1", "F32.A", "M54.50", "M25.561",
         "S93.401A", "S01.81XA", "Z00.00", "Z00.129", "Z23"]
IDX = {c: i for i, c in enumerate(CODES)}

# Base relative frequency of each code by facility type (unlisted codes get 0.2).
BASE = {
    "Emergency": {"R07.9": 9, "R10.9": 9, "S01.81XA": 6, "S93.401A": 5, "J18.9": 5, "N39.0": 4, "R51.9": 4,
                  "L03.90": 3, "J06.9": 4, "R50.9": 3, "A08.4": 3, "R05.9": 3, "M54.50": 3, "J45.909": 2,
                  "U07.1": 2, "J11.1": 1, "J10.1": 0.5, "I10": 1, "E11.9": 0.6, "G43.909": 1.5, "F41.1": 1.5},
    "Urgent care": {"J06.9": 10, "J02.9": 8, "J01.90": 6, "J20.9": 5, "R05.9": 5, "S93.401A": 4, "N39.0": 4,
                    "H66.90": 3, "B34.9": 3, "U07.1": 3, "S01.81XA": 3, "L03.90": 2, "J11.1": 1.2, "J10.1": 0.6,
                    "A08.4": 2, "J30.9": 2, "M54.50": 2, "R50.9": 2},
    "Family medicine": {"I10": 9, "E11.9": 6, "E78.5": 6, "Z00.00": 6, "J06.9": 5, "M54.50": 4, "F41.1": 3,
                        "F32.A": 3, "E66.9": 3, "K21.9": 3, "Z23": 3, "J01.90": 3, "J02.9": 2, "Z00.129": 2,
                        "J30.9": 2, "N39.0": 2, "J11.1": 0.8, "J10.1": 0.4, "M25.561": 2, "U07.1": 1},
    "Pediatrics": {"Z00.129": 12, "J06.9": 10, "H66.90": 8, "J02.9": 6, "Z23": 6, "R50.9": 5, "J45.909": 4,
                   "B34.9": 4, "A08.4": 3, "R05.9": 4, "J30.9": 3, "J20.9": 2, "J11.1": 1.2, "J10.1": 0.6,
                   "U07.1": 1},
    "Internal medicine": {"I10": 12, "E11.9": 9, "E78.5": 9, "Z00.00": 5, "E66.9": 4, "K21.9": 4, "M54.50": 3,
                          "M25.561": 3, "F32.A": 2, "F41.1": 2, "Z23": 3, "J06.9": 2, "N39.0": 2, "G43.909": 1,
                          "J11.1": 0.5, "J10.1": 0.3, "U07.1": 1, "J18.9": 1},
    "Community health center": {"I10": 8, "E11.9": 7, "Z00.00": 5, "Z00.129": 4, "E78.5": 4, "J06.9": 5,
                                "F32.A": 3, "F41.1": 3, "E66.9": 3, "Z23": 3, "M54.50": 3, "J02.9": 2,
                                "N39.0": 2, "H66.90": 2, "J11.1": 0.8, "J10.1": 0.4, "U07.1": 1, "K21.9": 2},
}

# Codes that only make sense for some ages (multiplier per age group).
AGE_FIT = {
    "Z00.129": [1, 1, 0, 0, 0], "Z00.00": [0, 0, 1, 1, 1], "H66.90": [3, 1.2, 0.3, 0.1, 0.1],
    "I10": [0, 0.02, 0.4, 1.4, 1.8], "E11.9": [0, 0.05, 0.4, 1.4, 1.5], "E78.5": [0, 0, 0.3, 1.4, 1.6],
    "R07.9": [0.1, 0.3, 1, 1.4, 1.5], "J18.9": [0.8, 0.5, 0.6, 1, 2.2], "F32.A": [0, 0.5, 1.3, 1, 0.8],
    "F41.1": [0, 0.5, 1.4, 1, 0.6], "G43.909": [0, 0.6, 1.4, 1, 0.4], "M25.561": [0, 0.4, 0.8, 1.3, 1.5],
    "M54.50": [0, 0.3, 1.1, 1.3, 1.1], "E66.9": [0, 0.6, 1, 1.2, 0.8], "K21.9": [0.2, 0.3, 0.9, 1.3, 1.3],
    "Z23": [1.6, 1.2, 0.6, 0.9, 1.5], "N39.0": [0.3, 0.6, 1, 1, 1.6],
}

FLU_PEAKS = [(date(2025, 2, 3), 24.0), (date(2025, 12, 29), 28.0)]  # (peak day, width in days)
FLU = {"J10.1", "J11.1"}
RESP = {"J06.9", "J02.9", "J20.9", "J01.90", "R05.9", "R50.9", "B34.9", "H66.90", "J18.9", "J45.909"}


def flu_curve(d: date) -> float:
    return sum(math.exp(-((d - p).days ** 2) / (2 * w * w)) for p, w in FLU_PEAKS)


def seasonal(code: str, d: date) -> float:
    doy = d.timetuple().tm_yday
    winter = 0.5 * (1 + math.cos(2 * math.pi * (doy - 15) / 365.25))  # 1 in mid-Jan, 0 in mid-Jul
    f = flu_curve(d)
    if code in FLU:
        return 0.06 + 9 * f
    if code in RESP:
        return 0.7 + 0.8 * winter + 0.9 * f
    if code == "U07.1":
        return 0.4 + 1.2 * math.exp(-((doy - 225) ** 2) / (2 * 22 ** 2)) + 0.8 * winter
    if code == "J30.9":
        return 0.4 + 1.8 * math.exp(-((doy - 105) ** 2) / (2 * 20 ** 2)) + 0.6 * math.exp(-((doy - 270) ** 2) / (2 * 18 ** 2))
    if code == "A08.4":
        return 0.6 + 1.0 * winter
    if code in {"S93.401A", "S01.81XA", "L03.90"}:
        return 0.8 + 0.6 * (1 - winter)
    if code == "Z00.129":
        return 0.6 + 1.6 * math.exp(-((doy - 215) ** 2) / (2 * 18 ** 2))
    if code == "Z23":
        return 0.4 + 2.2 * math.exp(-((doy - 290) ** 2) / (2 * 25 ** 2))
    return 1.0


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def build_encounters(rng: random.Random, nrng: np.random.Generator) -> list[dict]:
    rows: list[dict] = []
    enc_no = 0
    for fid, _name, ftype, *_rest, per_day, weekends in FACILITIES:
        base = np.array([BASE[ftype].get(c, 0.2) for c in CODES], dtype=float)
        age_fit = np.array([AGE_FIT.get(c, [1, 1, 1, 1, 1]) for c in CODES], dtype=float)  # codes x ages
        for d in daterange(START, END):
            wd = d.weekday()
            if not weekends and wd == 6:
                continue
            day_factor = {0: 1.15, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.95, 5: 0.75 if weekends else 0.35, 6: 0.85}[wd]
            season_vec = np.array([seasonal(c, d) for c in CODES])
            volume_boost = 1 + 0.25 * flu_curve(d) + 0.1 * (season_vec.mean() - 1)
            n = nrng.poisson(per_day * day_factor * volume_boost)
            if n == 0:
                continue
            ages = nrng.choice(5, size=n, p=AGE_MIX[ftype])
            for ai in range(5):
                k = int((ages == ai).sum())
                if not k:
                    continue
                w = base * season_vec * age_fit[:, ai]
                if w.sum() == 0:
                    continue
                counts = nrng.multinomial(k, w / w.sum())
                lo, hi = AGE_RANGES[AGE_GROUPS[ai]]
                for ci in np.nonzero(counts)[0]:
                    for _ in range(int(counts[ci])):
                        enc_no += 1
                        rows.append({
                            "encounter_id": f"E{enc_no:07d}",
                            "facility_id": fid,
                            "encounter_date": d.isoformat(),
                            "patient_age": rng.randint(lo, hi),
                            "patient_sex": rng.choice(["F", "M"]) if rng.random() > 0.004 else "U",
                            "encounter_type": ENCOUNTER_TYPE[ftype],
                            "primary_dx_code": CODES[ci],
                            "source_system": "EHR",
                            "extract_ts": "2026-10-01T03:00:00",
                        })
    return rows


def inject_quality_issues(rng: random.Random, rows: list[dict]) -> list[dict]:
    n = len(rows)
    # Formatting problems that cleaning should FIX (not reject): lower case, missing dot, stray spaces
    for i in rng.sample(range(n), k=int(n * 0.03)):
        c = rows[i]["primary_dx_code"]
        rows[i]["primary_dx_code"] = rng.choice([c.lower(), c.replace(".", ""), f" {c} "])
    # Invalid codes ~0.2%
    for i in rng.sample(range(n), k=int(n * 0.002)):
        rows[i]["primary_dx_code"] = rng.choice(["XYZ.1", "J11.9Q", "999", "ICD10", "N/A"])
    # Missing codes ~0.1%
    for i in rng.sample(range(n), k=int(n * 0.001)):
        rows[i]["primary_dx_code"] = ""
    # Unknown facility ~0.05%
    for i in rng.sample(range(n), k=int(n * 0.0005)):
        rows[i]["facility_id"] = "F99"
    # Impossible dates ~0.05%
    for i in rng.sample(range(n), k=int(n * 0.0005)):
        rows[i]["encounter_date"] = rng.choice(["2031-01-15", "1900-01-01", "2026-13-02"])
    # Duplicate rows (re-sent batch) ~0.3%
    out = list(rows)
    for i in rng.sample(range(n), k=int(n * 0.003)):
        out.append(dict(rows[i]))
    rng.shuffle(out)
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows):>9,} rows -> {path.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    rng = random.Random(SEED)
    nrng = np.random.default_rng(SEED)

    facilities = [
        {"facility_id": f, "facility_name": n, "facility_type": t, "city": c, "county": co}
        for f, n, t, c, co, *_ in FACILITIES
    ]
    write_csv(args.out / "facilities.csv", facilities)
    write_csv(args.out / "encounters.csv", inject_quality_issues(rng, build_encounters(rng, nrng)))


if __name__ == "__main__":
    main()
