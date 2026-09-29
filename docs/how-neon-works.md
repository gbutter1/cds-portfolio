# How Neon works (the 5-minute version)

Neon is hosted Postgres. Everything you know about Postgres applies; these are
the Neon-specific things worth knowing.

## What you have

- **Project** `cds-portfolio` (free plan: up to 10 projects, 0.5 GB storage each, 100 compute-hours/month).
- **Branch** `production` — the default branch of the database. A branch is a
  copy-on-write clone of the whole database, like a git branch. You can create
  a `dev` branch to try a risky change, then delete it. Not needed day one.
- **Compute** that scales between 0.25 and 2 CU and **suspends after ~5 minutes
  idle**. The first query after a pause takes about a second to wake it. This
  is why the GitHub Actions workflow runs weekly: it keeps the data fresh and
  proves the pipeline still works.
- **Database** `neondb`, **role** `neondb_owner` (full owner rights).

## Schemas the pipeline creates

| Schema | Created by | Contents |
|---|---|---|
| `raw_education_attendance` | `pipeline/load_raw.py` | source CSVs, all text |
| `staging` | dbt | typed/cleaned views |
| `marts` | dbt | tables the dashboards read |
| `analytics` | dbt (default schema) | anything without an explicit schema; currently empty |

## Connection strings

Neon offers two hosts per branch:

- `ep-xxx.us-east-2.aws.neon.tech` — direct. **Use this** for dbt, the loader, and Evidence.
- `ep-xxx-pooler.us-east-2.aws.neon.tech` — pooled (PgBouncer). For web apps with many short connections; unnecessary here.

The string always ends in `?sslmode=require&channel_binding=require`; leave that on.

## Useful places in the console

- **SQL Editor** (sidebar → Postgres database → SQL Editor): run any query; same job as SSMS.
- **Tables**: browse schemas and row counts.
- **Monitoring**: see when compute was active and how much storage is used.
- **Connect → Reset password**: rotate the credential (then update `.env` and the GitHub secret).

## Storage budget

The full attendance dataset uses roughly 60–80 MB including indexes, well
under the 0.5 GB limit. Rough guide: each additional project of similar size
fits comfortably; something 5× bigger would need thinning or a second project.
