"""
Run dbt using the single DATABASE_URL credential.

dbt-postgres wants host/user/password/db as separate settings, while the
Python loader and Evidence use one connection URL. This wrapper splits the
URL into the PG* variables that dbt/profiles.yml reads, then runs dbt with
whatever arguments you pass. Works the same on Windows, Mac, Linux and CI.

Usage:
    python pipeline/run_dbt.py run
    python pipeline/run_dbt.py test
    python pipeline/run_dbt.py build --select education_attendance
    python pipeline/run_dbt.py docs generate
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = REPO_ROOT / "dbt"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2

    u = urlparse(url)
    q = parse_qs(u.query)
    env = dict(os.environ)
    env.update(
        {
            "PGHOST": u.hostname or "localhost",
            "PGPORT": str(u.port or 5432),
            "PGUSER": unquote(u.username or ""),
            "PGPASSWORD": unquote(u.password or ""),
            "PGDATABASE": u.path.lstrip("/"),
            "PGSSLMODE": q.get("sslmode", ["prefer"])[0],
            "DBT_PROFILES_DIR": str(DBT_DIR),
        }
    )
    # Run dbt through the current interpreter so it works even when the
    # Python Scripts folder is not on PATH (common on Windows).
    cmd = [sys.executable, "-W", "ignore::RuntimeWarning", "-m", "dbt.cli.main", *sys.argv[1:]]
    return subprocess.call(cmd, cwd=DBT_DIR, env=env)


if __name__ == "__main__":
    sys.exit(main())
