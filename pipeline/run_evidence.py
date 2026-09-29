"""
Run Evidence commands using the single DATABASE_URL credential.

Evidence's Postgres connector reads its settings from environment variables
named EVIDENCE_SOURCE__CDS__<FIELD>. This wrapper derives them from
DATABASE_URL and runs the requested npm script inside evidence/.

Usage:
    python pipeline/run_evidence.py sources   # pull query results from the database
    python pipeline/run_evidence.py dev       # local preview at http://localhost:3000
    python pipeline/run_evidence.py build     # static site -> evidence/build/
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "evidence"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2
    if not (EVIDENCE_DIR / "node_modules").exists():
        print("evidence/node_modules missing: run `npm install` inside the evidence folder first.", file=sys.stderr)
        return 2

    u = urlparse(url)
    q = parse_qs(u.query)
    sslmode = q.get("sslmode", ["prefer"])[0]
    env = dict(os.environ)
    # Keys after the source name are case-sensitive and must match the
    # connector's option names exactly (host, port, user, password, database).
    env.update(
        {
            "EVIDENCE_SOURCE__cds__host": u.hostname or "localhost",
            "EVIDENCE_SOURCE__cds__port": str(u.port or 5432),
            "EVIDENCE_SOURCE__cds__user": unquote(u.username or ""),
            "EVIDENCE_SOURCE__cds__password": unquote(u.password or ""),
            "EVIDENCE_SOURCE__cds__database": u.path.lstrip("/"),
        }
    )
    if sslmode != "disable":
        # Neon's certificate comes from a public CA, so full verification works.
        # A local Postgres without TLS uses ?sslmode=disable in its URL.
        env["EVIDENCE_SOURCE__cds__ssl__sslmode"] = "verify-full" if sslmode == "require" else sslmode
        env["EVIDENCE_SOURCE__cds__ssl__rejectUnauthorized"] = "true"
    npm = shutil.which("npm") or "npm"
    args = sys.argv[1:] or ["dev"]
    return subprocess.call([npm, "run", *args], cwd=EVIDENCE_DIR, env=env)


if __name__ == "__main__":
    sys.exit(main())
