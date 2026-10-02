---
title: Creative Data Solutions · Work Portfolio
hide_title: true
---

# Work Portfolio

**End-to-end data projects, from raw extract to decision-ready dashboard.**
Every project here is fully open: the pipeline code, the data model, the
validation rules and the dashboards all live in one public repository, built
on the same stack we use for clients.

**Source code:** [github.com/gbutter1/cds-portfolio](https://github.com/gbutter1/cds-portfolio)
&nbsp;·&nbsp; **Company site:** [creativedatasolutions.tech](https://creativedatasolutions.tech)

Each project follows the same shape, whatever the sector:

```sql pipeline_stages
select 1 as step, 'Ingest' as stage, 'Land the source extract untouched (every column as text) so nothing is lost and everything is auditable.' as what
union all select 2, 'Clean & type', 'Trim, standardize and type every field; flag every row that fails a rule instead of silently dropping it.'
union all select 3, 'Validate', 'Automated tests on every table: uniqueness, referential integrity, accepted values, ranges, and rejection thresholds.'
union all select 4, 'Model', 'Facts and dimensions at a documented grain, with business definitions written down next to the SQL.'
union all select 5, 'Report', 'Interactive pages built from the modeled tables, including a data-quality page that shows what was rejected and why.'
```

<DataTable data={pipeline_stages} rows=5>
  <Column id=step title="#" align=center />
  <Column id=stage />
  <Column id=what title="What happens" wrap=true />
</DataTable>

## Projects

### K-12 Daily Attendance & Chronic Absenteeism

A school district's daily attendance extract (2,400 students, 11 schools, one
school year, ~427,000 rows) is cleaned, validated and modeled into
student-, school- and month-level tables, then reported as an attendance
dashboard with a chronic-absenteeism tiering that mirrors the federal
definition. The source data is synthetic and messy on purpose: duplicates,
bad status codes, holiday-dated rows, orphan IDs and post-withdrawal records
are all present and all caught.

<LinkButton url="/education-attendance">Open the attendance dashboard →</LinkButton>
<LinkButton url="/education-attendance/data-quality">Data quality report</LinkButton>
<LinkButton url="/education-attendance/how-it-works">How it was built</LinkButton>

*More projects (small-business KPIs, nonprofit program outcomes, healthcare
operations) are added to this same repository as they are completed.*

## The stack

```sql stack
select 'Postgres (Neon)' as tool, 'Storage' as role, 'Serverless Postgres; the raw, staging and mart schemas all live here.' as why
union all select 'Python', 'Ingestion', 'Generates or receives the source extracts and bulk-loads them with COPY.'
union all select 'dbt Core', 'Transformation & tests', 'SQL models with version control, lineage, documentation and automated tests.'
union all select 'Evidence', 'Reporting', 'Markdown + SQL pages compiled to a static site, so dashboards live in git next to the pipeline.'
union all select 'GitHub Actions', 'Orchestration', 'Runs the whole pipeline on a schedule and publishes this site.'
```

<DataTable data={stack} rows=5>
  <Column id=tool />
  <Column id=role />
  <Column id=why wrap=true />
</DataTable>

<Details title="About the data in this portfolio">

No client or student data appears anywhere in this portfolio. Datasets are
generated from a fixed random seed with realistic structure, seasonality and
error patterns, so the engineering can be shown in full without exposing
anyone's records. Where a project is modeled on real engagement work, the
case study says so on the company website.

</Details>
