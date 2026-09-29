"""
Load raw CSV extracts into Postgres (Neon), one schema per project.

Design choices worth knowing:
  * Every raw column is loaded as TEXT. The raw layer is a faithful copy of
    the source extract; typing, trimming and validation happen in dbt staging
    models where they are visible, tested and documented.
  * Tables are rebuilt each run (drop cascade + create + COPY); dbt recreates
    any staging views that depended on them on its next run. Raw is disposable;
    the CSVs are the system of record for this portfolio.
  * A `_load_ts` column records when each row landed, for auditability.
  * COPY is used instead of row-by-row inserts: ~400k rows load in seconds.

Usage:
    python pipeline/load_raw.py education_attendance
    python pipeline/load_raw.py education_attendance --dir data/raw/education_attendance

Requires DATABASE_URL in the environment (or in a .env file at the repo root).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]


def sanitize(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name.lower())


def load_csv(cur, schema: str, csv_path: Path) -> int:
    table = sanitize(csv_path.stem)
    with csv_path.open(newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    cols = [sanitize(c) for c in header]
    col_ddl = ", ".join(f'"{c}" text' for c in cols)

    cur.execute(f'drop table if exists "{schema}"."{table}" cascade')
    cur.execute(
        f'create table "{schema}"."{table}" ({col_ddl}, "_load_ts" timestamptz not null default now())'
    )
    col_list = ", ".join(f'"{c}"' for c in cols)
    with csv_path.open("r", encoding="utf-8") as f:
        cur.copy_expert(
            f'copy "{schema}"."{table}" ({col_list}) from stdin with (format csv, header true)', f
        )
    cur.execute(f'select count(*) from "{schema}"."{table}"')
    return cur.fetchone()[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="project name, e.g. education_attendance")
    ap.add_argument("--dir", type=Path, help="folder of CSVs (default data/raw/<project>)")
    args = ap.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2

    src_dir = args.dir or REPO_ROOT / "data" / "raw" / args.project
    csvs = sorted(src_dir.glob("*.csv"))
    if not csvs:
        print(f"no CSV files found in {src_dir}", file=sys.stderr)
        return 1

    schema = f"raw_{sanitize(args.project)}"
    t0 = time.time()
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(f'create schema if not exists "{schema}"')
            for path in csvs:
                n = load_csv(cur, schema, path)
                print(f"  {schema}.{sanitize(path.stem):<20} {n:>9,} rows")
        conn.commit()
    print(f"done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
