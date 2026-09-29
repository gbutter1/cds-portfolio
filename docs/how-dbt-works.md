# How dbt works (the 10-minute version)

You already know 90% of dbt: it's SQL. This note covers the other 10%.

## The one idea

A **model** is a `.sql` file containing a single `SELECT`. When you run
`dbt run`, dbt wraps each SELECT in `CREATE VIEW ... AS` or
`CREATE TABLE ... AS` and executes it against the database. The file name is
the table/view name.

`models/education_attendance/staging/stg_schools.sql` → `staging.stg_schools`

That's it. Your temp-table workflow from SQL Server (`SELECT ... INTO #temp`,
then build on it) becomes a folder of SELECT files that reference each other.

## `ref()` and `source()`: how files reference each other

Instead of hard-coding `staging.stg_students`, you write:

```sql
select * from {{ ref('stg_students') }}
```

dbt fills in the real schema-qualified name, and, more importantly, now knows
`this model depends on stg_students`, so it builds things in the right order
and can draw a lineage graph. `{{ source('raw_education_attendance', 'students') }}`
does the same for raw tables that dbt didn't create (declared in `_sources.yml`).

The `{{ }}` bits are Jinja templating. You'll rarely need more than `ref`,
`source` and `env_var`.

## Views vs tables

`dbt_project.yml` says staging models are **views** (cheap, always current)
and marts are **tables** (fast for dashboards). You can override per model
with `{{ config(materialized='table') }}` at the top of a file.

## Tests: the part that makes this worth it

In a `.yml` file next to the models you declare expectations:

```yaml
- name: fct_attendance_daily
  columns:
    - name: attendance_key
      tests: [unique, not_null]
    - name: attendance_status
      tests:
        - accepted_values:
            arguments:
              values: ['P', 'A', 'T']
```

`dbt test` turns each one into a query that returns failing rows; zero rows =
pass. Four built-ins: `unique`, `not_null`, `accepted_values`,
`relationships` (foreign key). Custom reusable tests are short macros in
`tests/generic/` (see `unique_combination.sql`); one-off assertions are plain
SQL files in `tests/` that must return zero rows (see
`assert_rejected_rows_under_two_percent.sql`).

## The commands

| Command | What it does |
|---|---|
| `dbt run` | build all models |
| `dbt test` | run all tests |
| `dbt build` | run + test together, in dependency order (use this one) |
| `dbt build --select stg_attendance+` | that model and everything downstream of it |
| `dbt docs generate && dbt docs serve` | browsable docs with a lineage graph |

In this repo you run them through `python pipeline/run_dbt.py <command>`, which
just sets the connection from `DATABASE_URL` first.

## Where things are

```
dbt/
  dbt_project.yml        project settings: which folders are views vs tables, schema names
  profiles.yml           connection (reads env vars; no secrets in the file)
  models/
    education_attendance/
      staging/           _sources.yml, stg_*.sql, _staging.yml (tests)
      marts/             dim_*, fct_*, rollups, _marts.yml (tests)
  tests/                 singular tests + generic/ custom test macros
  macros/                generate_schema_name.sql (keeps schema names clean)
  target/                generated SQL and docs (git-ignored)
```

## Postgres differences you'll notice coming from SQL Server / Snowflake

- Quoted identifiers are case-sensitive; unquoted are folded to lower case. Stay lower-case and unquoted.
- `text` instead of `varchar(max)`; `::date` casts (`'2026-01-01'::date`) instead of `CAST`/`CONVERT` (both work, `::` is idiomatic).
- `limit 10` instead of `top 10`.
- `count(*) filter (where ...)` is a tidy alternative to `sum(case when ...)`.
- Integer ÷ integer is integer division; cast one side to `numeric` (done throughout the marts).
- `date_trunc('month', d)` and `to_char(d, 'Mon YYYY')` for month buckets and labels.
