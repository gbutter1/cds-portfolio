# Creative Data Solutions · Work Portfolio

End-to-end data projects, from raw extract to decision-ready dashboard, built
on the same stack we use for clients. Every project here is fully open: the
ingestion code, the data model, the validation rules and the dashboards all
live in this repository.

**Live site:** https://YOUR-GITHUB-USERNAME.github.io/cds-portfolio/
**Company:** https://creativedatasolutions.tech

## Projects

| Project | Sector | What it shows |
|---|---|---|
| [K-12 Daily Attendance & Chronic Absenteeism](projects/education_attendance/) | Education | Messy daily-attendance extract → validated student/school/month models → attendance and chronic-absenteeism dashboards, with a data-quality report of every rejected row |

More projects (small-business KPIs, nonprofit program outcomes, healthcare
operations) are added here as they are completed. Each follows the same shape.

## How every project is built

```
 source extract        raw layer            staging               marts                 dashboards
 (CSV / API / DB)  →   Postgres, all   →    typed, cleaned,   →   facts, dims,     →    Evidence pages
 Python generates      text, COPY-loaded    every row labeled     rollups; tested       (Markdown + SQL)
 or receives it        with load timestamp  with a dq_status      grain per table       static site
                       pipeline/load_raw.py dbt staging/          dbt marts/            evidence/pages/
```

Orchestrated by GitHub Actions: generate → load → `dbt build` (models + 36
tests) → Evidence build → GitHub Pages. A failing test stops the run before
anything is published.

## Stack

| Layer | Tool | Why |
|---|---|---|
| Storage | Postgres on [Neon](https://neon.tech) | Serverless Postgres; raw, staging and mart schemas |
| Ingestion | Python (psycopg2 `COPY`) | Bulk loads; ~427k rows in under a second |
| Transformation & tests | [dbt Core](https://docs.getdbt.com) | Version-controlled SQL models with lineage, docs and automated tests |
| Reporting | [Evidence](https://docs.evidence.dev) (open-source) | Markdown + SQL compiled to a static site, so dashboards live in git |
| Orchestration | GitHub Actions | Scheduled runs and publishing, no servers |

## Repository layout

```
projects/<project>/     generate.py: builds that project's synthetic source extract
pipeline/               load_raw.py, run_dbt.py, run_evidence.py (all read DATABASE_URL)
dbt/                    models, tests, macros (see docs/how-dbt-works.md)
evidence/               sources, pages, theme (see docs/how-evidence-works.md)
data/samples/           small committed samples of each extract; full data is regenerated
docs/                   getting started + one short explainer per tool
.github/workflows/      the pipeline
```

## Run it yourself

See [docs/getting-started-windows.md](docs/getting-started-windows.md) (Mac/Linux
users: same commands with forward slashes). Short version:

```
pip install -r requirements.txt
copy .env.example .env                      # add your DATABASE_URL
python projects/education_attendance/generate.py
python pipeline/load_raw.py education_attendance
python pipeline/run_dbt.py build
cd evidence && npm install && cd ..
python pipeline/run_evidence.py sources
python pipeline/run_evidence.py dev
```

## About the data

No client, student or patient data appears anywhere in this repository.
Datasets are generated from a fixed random seed with realistic structure,
seasonality and error patterns so the engineering can be shown in full.
