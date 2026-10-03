# Creative Data Solutions · Work Portfolio

End-to-end data projects, from raw extract to decision-ready dashboard, built
on the same stack we use for clients. Every project here is fully open: the
ingestion code, the data model, the validation rules and the dashboards all
live in this repository.

**Live site:** https://gbutter1.github.io/cds-portfolio/
**Company:** https://creativedatasolutions.tech

## Projects

| Project | Sector | What it shows |
|---|---|---|
| [K-12 Daily Attendance & Chronic Absenteeism](projects/education_attendance/) | Education | Messy daily-attendance extract → validated student/school/month models → attendance and chronic-absenteeism dashboards, with a data-quality report of every rejected row |
| [Diagnosis & Flu Explorer](projects/healthcare_diagnosis/) ([open the app](https://gbutter1.github.io/cds-portfolio/apps/diagnosis-explorer/)) | Healthcare | Interactive app: pick a facility, month and age group to see its top diagnosis codes and flu-season trend, compared with real CDC flu surveillance data for Georgia |
| [Store-to-Bank Reconciliation](projects/retail_reconciliation/) ([open the report](https://gbutter1.github.io/cds-portfolio/reports/retail-reconciliation/)) | Retail / Finance | Data integration: five systems for a three-department retailer (retail, café, auto center) reconciled into a printable weekly exceptions report |

More projects are added here as they are completed. Each follows the same shape.

## How every project is built

```
 source extract        raw layer            staging               marts                 dashboards
 (CSV / API / DB)  →   Postgres, all   →    typed, cleaned,   →   facts, dims,     →    Evidence pages
 Python generates      text, COPY-loaded    every row labeled     rollups; tested       (Markdown + SQL)
 or receives it        with load timestamp  with a dq_status      grain per table       static site
                       pipeline/load_raw.py dbt staging/          dbt marts/            evidence/pages/
```

Orchestrated by GitHub Actions: generate (and fetch public data) → load →
`dbt build` (seeds, models and tests) → Evidence build → GitHub Pages. A failing test stops the run before
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
dbt/                    models, tests, macros
evidence/               sources, pages, theme
.github/workflows/      the pipeline
```

## Run it yourself

Requires Python 3.11+, Node.js 20+ and a Postgres database (a free Neon
project works). Create a file named `.env` in the repository root containing
one line, `DATABASE_URL=<your Postgres connection string>`, then:

```
pip install -r requirements.txt
python projects/education_attendance/generate.py
python projects/healthcare_diagnosis/generate.py
python projects/healthcare_diagnosis/fetch_cdc_flu.py
python pipeline/load_raw.py education_attendance
python pipeline/load_raw.py healthcare_diagnosis
python projects/retail_reconciliation/generate.py
python pipeline/load_raw.py retail_reconciliation
python pipeline/run_dbt.py build
python pipeline/export_app_data.py
python pipeline/build_recon_report.py
cd evidence && npm install && cd ..
python pipeline/run_evidence.py sources
python pipeline/run_evidence.py dev
```

## About the data

No client, student or patient data appears anywhere in this repository.
Datasets are generated from a fixed random seed with realistic structure,
seasonality and error patterns so the engineering can be shown in full.
The one exception is the CDC flu comparison in the Diagnosis & Flu Explorer, which
uses real, public CDC ILINet surveillance data for Georgia (state-level
weekly totals, no individual records).
