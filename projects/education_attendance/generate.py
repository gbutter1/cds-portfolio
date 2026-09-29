"""
Synthetic K-12 daily attendance dataset.

Generates a realistic, messy source extract the way a student information
system might hand it to you: a school roster, a student roster with mid-year
transfers, a school calendar, and one row per student per school day.

No real student data is used or resembled. Everything here is produced from a
fixed random seed so the dataset is reproducible run to run.

Deliberate data-quality problems are injected (see `inject_quality_issues`)
so the downstream dbt layer has something real to validate and clean.

Usage:
    python generate.py                 # writes CSVs to ../../data/raw/education_attendance/
    python generate.py --students 500  # smaller dataset for quick local runs
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SEED = 20260817
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "education_attendance"

SCHOOL_YEAR_START = date(2025, 8, 4)
SCHOOL_YEAR_END = date(2026, 5, 20)

# (school_code, school_name, level, cluster, title_i, target_enrollment_share)
SCHOOLS = [
    ("ELM01", "Riverbend Elementary", "Elementary", "North", True, 0.09),
    ("ELM02", "Peachtree Grove Elementary", "Elementary", "North", False, 0.10),
    ("ELM03", "Sugar Hill Elementary", "Elementary", "Central", True, 0.08),
    ("ELM04", "Oak Hollow Elementary", "Elementary", "Central", False, 0.09),
    ("ELM05", "Meadowlark Elementary", "Elementary", "South", True, 0.08),
    ("ELM06", "Chattahoochee Elementary", "Elementary", "South", False, 0.07),
    ("MID01", "Riverbend Middle", "Middle", "North", True, 0.10),
    ("MID02", "Sugar Hill Middle", "Middle", "Central", False, 0.09),
    ("MID03", "Meadowlark Middle", "Middle", "South", True, 0.08),
    ("HIG01", "North Cluster High", "High", "North", False, 0.12),
    ("HIG02", "South Cluster High", "High", "South", True, 0.10),
]

GRADES_BY_LEVEL = {
    "Elementary": ["K", "1", "2", "3", "4", "5"],
    "Middle": ["6", "7", "8"],
    "High": ["9", "10", "11", "12"],
}

# Observed-holidays / breaks (inclusive ranges) for the calendar
BREAKS = [
    (date(2025, 9, 1), date(2025, 9, 1)),  # Labor Day
    (date(2025, 10, 13), date(2025, 10, 14)),  # Fall break
    (date(2025, 11, 24), date(2025, 11, 28)),  # Thanksgiving
    (date(2025, 12, 22), date(2026, 1, 5)),  # Winter break
    (date(2026, 1, 19), date(2026, 1, 19)),  # MLK Day
    (date(2026, 2, 16), date(2026, 2, 17)),  # Winter holiday
    (date(2026, 4, 6), date(2026, 4, 10)),  # Spring break
]

FIRST_NAMES = ["Avery", "Jordan", "Riley", "Quinn", "Morgan", "Casey", "Taylor", "Reese",
               "Skyler", "Emerson", "Rowan", "Dakota", "Parker", "Sawyer", "Finley", "Hayden",
               "Kai", "Elliot", "Micah", "Noel", "Sage", "Remy", "Tatum", "Blake"]
LAST_NAMES = ["Nguyen", "Patel", "Garcia", "Kim", "Johnson", "Okafor", "Smith", "Hernandez",
              "Brown", "Chen", "Williams", "Singh", "Jones", "Martinez", "Davis", "Lopez",
              "Robinson", "Ali", "Thompson", "Reyes", "Walker", "Rivera", "Carter", "Diaz"]


def build_calendar() -> list[dict]:
    rows = []
    d = SCHOOL_YEAR_START
    while d <= SCHOOL_YEAR_END:
        weekday = d.weekday() < 5
        in_break = any(a <= d <= b for a, b in BREAKS)
        is_school_day = weekday and not in_break
        if d < date(2025, 10, 10):
            term = "Q1"
        elif d < date(2025, 12, 20):
            term = "Q2"
        elif d < date(2026, 3, 13):
            term = "Q3"
        else:
            term = "Q4"
        rows.append(
            {
                "calendar_date": d.isoformat(),
                "school_year": "2025-26",
                "term": term,
                "is_school_day": is_school_day,
                "day_of_week": d.strftime("%A"),
            }
        )
        d += timedelta(days=1)
    return rows


def build_students(rng: random.Random, n_students: int) -> list[dict]:
    rows = []
    shares = np.array([s[5] for s in SCHOOLS])
    shares = shares / shares.sum()
    counts = np.random.default_rng(SEED).multinomial(n_students, shares)
    sid = 100000
    for (code, _name, level, _cluster, _title_i, _share), n in zip(SCHOOLS, counts):
        grades = GRADES_BY_LEVEL[level]
        for _ in range(int(n)):
            sid += 1
            # ~6% of students enroll late or withdraw early (transfers)
            enroll = SCHOOL_YEAR_START
            withdraw = None
            r = rng.random()
            if r < 0.03:
                enroll = SCHOOL_YEAR_START + timedelta(days=rng.randint(10, 150))
            elif r < 0.06:
                withdraw = SCHOOL_YEAR_START + timedelta(days=rng.randint(30, 260))
            # each student has a latent absence propensity; a long tail is chronic
            propensity = float(np.clip(rng.lognormvariate(-3.1, 0.75), 0.005, 0.6))
            rows.append(
                {
                    "student_id": sid,
                    "first_name": rng.choice(FIRST_NAMES),
                    "last_name": rng.choice(LAST_NAMES),
                    "school_code": code,
                    "grade_level": rng.choice(grades),
                    "enrollment_date": enroll.isoformat(),
                    "withdrawal_date": withdraw.isoformat() if withdraw else "",
                    "_propensity": propensity,  # stripped before writing
                }
            )
    return rows


def seasonal_multiplier(d: date) -> float:
    """Absences rise in flu season and in the last two weeks of the year."""
    if d.month in (1, 2):
        return 1.35
    if d >= SCHOOL_YEAR_END - timedelta(days=14):
        return 1.6
    if d.month == 8:
        return 0.8
    return 1.0


def dow_multiplier(d: date) -> float:
    return {0: 1.15, 1: 0.95, 2: 0.9, 3: 0.95, 4: 1.25}[d.weekday()]


def build_attendance(rng: random.Random, students: list[dict], calendar: list[dict]) -> list[dict]:
    school_factor = {s[0]: (1.25 if s[4] else 0.9) for s in SCHOOLS}  # Title I schools slightly higher
    school_days = [date.fromisoformat(r["calendar_date"]) for r in calendar if r["is_school_day"]]
    rows = []
    for st in students:
        enroll = date.fromisoformat(st["enrollment_date"])
        withdraw = date.fromisoformat(st["withdrawal_date"]) if st["withdrawal_date"] else None
        p = st["_propensity"] * school_factor[st["school_code"]]
        for d in school_days:
            if d < enroll or (withdraw and d > withdraw):
                continue
            prob_absent = min(0.95, p * seasonal_multiplier(d) * dow_multiplier(d))
            r = rng.random()
            if r < prob_absent:
                status = "A"
                absence_type = "Excused" if rng.random() < 0.55 else "Unexcused"
            elif r < prob_absent + 0.04:
                status = "T"
                absence_type = ""
            else:
                status = "P"
                absence_type = ""
            rows.append(
                {
                    "student_id": st["student_id"],
                    "school_code": st["school_code"],
                    "attendance_date": d.isoformat(),
                    "attendance_status": status,
                    "absence_type": absence_type,
                    "source_system": "SIS",
                    "extract_ts": "2026-06-01T02:15:00",
                }
            )
    return rows


def inject_quality_issues(rng: random.Random, attendance: list[dict], calendar: list[dict], students: list[dict]) -> list[dict]:
    """
    Make the extract look like a real one. Each issue is something the dbt
    layer detects and handles, and the data-quality page reports on.
    """
    non_school_days = [r["calendar_date"] for r in calendar if not r["is_school_day"]]
    out = list(attendance)
    n = len(out)

    # 1. Exact duplicate rows (re-sent batches) ~0.4%
    for i in rng.sample(range(n), k=int(n * 0.004)):
        out.append(dict(out[i]))

    # 2. Inconsistent casing / whitespace on school_code ~0.5%
    for i in rng.sample(range(n), k=int(n * 0.005)):
        out[i]["school_code"] = out[i]["school_code"].lower() + " "

    # 3. Invalid status codes ~0.1%
    for i in rng.sample(range(n), k=int(n * 0.001)):
        out[i]["attendance_status"] = rng.choice(["X", "", "PRESENT", "?"])

    # 4. Records on non-school days (holiday keyed in error) ~0.1%
    for i in rng.sample(range(n), k=int(n * 0.001)):
        row = dict(out[i])
        row["attendance_date"] = rng.choice(non_school_days)
        out.append(row)

    # 5. Orphan student IDs not on the roster ~0.05%
    for i in rng.sample(range(n), k=int(n * 0.0005)):
        row = dict(out[i])
        row["student_id"] = 999000 + rng.randint(1, 500)
        out.append(row)

    # 6. Attendance posted for withdrawn students after their withdrawal date
    #    (SIS keeps generating rows until the withdrawal is processed)
    withdrawn = [st for st in students if st["withdrawal_date"]]
    for st in rng.sample(withdrawn, k=min(25, len(withdrawn))):
        wd = date.fromisoformat(st["withdrawal_date"])
        for k in range(1, rng.randint(2, 6)):
            d = wd + timedelta(days=k)
            if d.weekday() < 5 and d <= SCHOOL_YEAR_END:
                out.append({"student_id": st["student_id"], "school_code": st["school_code"],
                            "attendance_date": d.isoformat(), "attendance_status": "A",
                            "absence_type": "Unexcused", "source_system": "SIS",
                            "extract_ts": "2026-06-01T02:15:00"})

    rng.shuffle(out)
    return out


def write_csv(path: Path, rows: list[dict], drop: tuple[str, ...] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [k for k in rows[0].keys() if k not in drop]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows):>9,} rows -> {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=2400)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    rng = random.Random(SEED)
    calendar = build_calendar()
    students = build_students(rng, args.students)
    attendance = inject_quality_issues(rng, build_attendance(rng, students, calendar), calendar, students)

    schools = [
        {"school_code": c, "school_name": n, "school_level": lvl, "cluster": cl, "title_i": t}
        for c, n, lvl, cl, t, _ in SCHOOLS
    ]
    write_csv(args.out / "schools.csv", schools)
    write_csv(args.out / "students.csv", students, drop=("_propensity",))
    write_csv(args.out / "calendar.csv", calendar)
    write_csv(args.out / "attendance_daily.csv", attendance)


if __name__ == "__main__":
    main()
