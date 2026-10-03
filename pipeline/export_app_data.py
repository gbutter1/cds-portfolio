"""
Export the healthcare marts to a compact JSON file for the Diagnosis & Flu Explorer
app, which runs entirely in the browser (no server, no database connection).

Reads:  marts.hc_* tables and reference.icd10_reference (built by dbt)
Writes: evidence/static/apps/diagnosis-explorer/data.json

Counts are written as index-encoded arrays rather than objects to keep the
file small (a few hundred KB) so the app loads instantly.

Usage:
    python pipeline/export_app_data.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "evidence" / "static" / "apps" / "diagnosis-explorer" / "data.json"
AGE_GROUPS = ["0-4", "5-17", "18-44", "45-64", "65+"]


def q(cur, sql: str) -> list[tuple]:
    cur.execute(sql)
    return cur.fetchall()


def num(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        facilities = q(cur, """select facility_id, facility_name, facility_type, city, county
                              from marts.hc_dim_facility order by facility_id""")
        codes = q(cur, """select icd10_code, description, category, is_influenza
                         from reference.icd10_reference order by icd10_code""")
        months = [r[0] for r in q(cur, "select distinct month_start from marts.hc_facility_month_dx order by 1")]
        counts = q(cur, """select facility_id, month_start, age_group, icd10_code, encounters
                          from marts.hc_facility_month_dx""")
        flu = q(cur, """select facility_id, week_start, total_encounters, flu_encounters, flu_share,
                              baseline_share, above_baseline, season_start_year
                       from marts.hc_facility_week_flu order by facility_id, week_start""")
        cdc = q(cur, """select week_start, epiweek, ili_share, num_ili, num_patients, num_providers, release_date
                       from marts.hc_cdc_ili_ga order by week_start""")
        dq = q(cur, """select dq_status, description, row_count, codes_normalized, pct_of_rows
                      from marts.hc_data_quality order by row_count desc""")

    fac_idx = {f[0]: i for i, f in enumerate(facilities)}
    code_idx = {c[0]: i for i, c in enumerate(codes)}
    month_idx = {m: i for i, m in enumerate(months)}
    age_idx = {a: i for i, a in enumerate(AGE_GROUPS)}

    flu_by_fac: dict[str, list] = {}
    baseline: dict[str, float] = {}
    for fid, wk, tot, n, share, base, above, season in flu:
        flu_by_fac.setdefault(fid, []).append([wk.isoformat(), tot, n, num(share), bool(above), season])
        baseline[fid] = num(base)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "age_groups": AGE_GROUPS,
        "facilities": [dict(zip(["id", "name", "type", "city", "county"], f)) for f in facilities],
        "codes": [dict(zip(["code", "description", "category", "is_flu"], c)) for c in codes],
        "months": [m.isoformat() for m in months],
        # [facility, month, age_group, code, encounters] as indexes into the lists above
        "counts": [[fac_idx[f], month_idx[m], age_idx[a], code_idx[c], n] for f, m, a, c, n in counts],
        # per facility (and ALL): [week_start, total, flu, flu_share, above_baseline, season_start_year]
        "flu_weekly": flu_by_fac,
        "flu_baseline": baseline,
        "cdc": {
            "region": "Georgia",
            "source": "CDC ILINet (FluView), via the Delphi Epidata API",
            "weeks": [[w.isoformat(), e, num(s), ni, npt, npr] for w, e, s, ni, npt, npr, _rd in cdc],
            "latest_release": max((rd for *_, rd in cdc if rd), default=None),
        },
        "data_quality": [dict(zip(["status", "description", "rows", "normalized", "pct"], map(num, r))) for r in dq],
    }
    if isinstance(data["cdc"]["latest_release"], date):
        data["cdc"]["latest_release"] = data["cdc"]["latest_release"].isoformat()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_ROOT)} ({OUT.stat().st_size / 1024:,.0f} KB, "
          f"{len(data['counts']):,} count rows, {len(data['cdc']['weeks'])} CDC weeks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
