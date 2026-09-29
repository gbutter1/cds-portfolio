# How Evidence works (the 10-minute version)

Evidence turns Markdown files with SQL in them into an interactive website.
This repo uses the **open-source** Evidence (docs at https://docs.evidence.dev).
There is also a paid hosted product called Evidence Studio at evidence.studio
with different syntax; ignore anything you find under that name.

## Two kinds of SQL, two places it runs

**1. Source queries** — `evidence/sources/cds/*.sql`

These run against **Postgres (Neon)** when you run
`python pipeline/run_evidence.py sources`. Each file's result is saved as a
Parquet file under `evidence/static/data/` (git-ignored) and becomes a table
named `cds.<filename>`. Write native Postgres SQL here. Keep them simple:
`select * from marts.<table>` plus an `order by` is usually all you need,
because the modeling was already done in dbt.

**2. Page queries** — the ```` ```sql name ```` blocks inside pages

These run **in the browser** against those Parquet files, using DuckDB.
That's why the dashboard stays interactive on a static site with no server.
They query the `cds.*` tables and use DuckDB SQL, which is Postgres-flavored;
the differences you'll hit are `strftime(date, '%A')` for day names and that
`/` is already floating-point division.

A page query can reference another page query with `${name}`, and an input's
current value with `${inputs.myinput.value}`.

## Anatomy of a page

````markdown
---
title: K-12 Attendance Dashboard
---

Some intro text in plain Markdown.

```sql monthly
select * from cds.school_monthly_attendance
where school_level like '${inputs.level.value}'
```

<Dropdown data={schools} name=level value=school_level title="School level" defaultValue="%">
  <DropdownOption value="%" valueLabel="All levels" />
</Dropdown>

<LineChart data={monthly} x=month_start y=attendance_rate series=school_name yFmt="pct1" />

<DataTable data={monthly} />
````

Components are written like HTML tags. The ones used in this repo:
`BigValue`, `LineChart`, `BarChart`, `DataTable` + `Column`, `Dropdown` +
`DropdownOption`, `Grid`, `Details`. The full list with every option is at
https://docs.evidence.dev/components/all-components.

## Files and folders

```
evidence/
  evidence.config.yaml   plugins, theme colors, basePath for GitHub Pages
  sources/cds/           connection.yaml (no secrets) + one .sql per source table
  pages/                 index.md = home page; each folder = a URL path
    education-attendance/
      index.md           /education-attendance
      data-quality.md    /education-attendance/data-quality
      how-it-works.md    /education-attendance/how-it-works
  static/                images, and the generated data/ folder
  build/                 the finished static site (git-ignored; CI deploys it)
```

Adding a page = adding a `.md` file. The sidebar navigation builds itself from
the folder structure and each page's `title`.

## Commands (run from the repo root)

| Command | What it does |
|---|---|
| `python pipeline/run_evidence.py sources` | run the source queries against Neon, refresh the Parquet files |
| `python pipeline/run_evidence.py dev` | local preview at http://localhost:3000, live-reloads on edits |
| `python pipeline/run_evidence.py build` | produce the static site in `evidence/build/` |

Re-run `sources` whenever the dbt models change; `dev` picks up page edits
without a restart.

## Formatting codes you'll use

`pct0`, `pct1`, `pct2` (percent with N decimals) · `#,##0` (thousands
separators) · `#,##0.0` · `usd0` · `mmm yyyy` (date as "Jan 2026").

## Theme

Colors live in `evidence.config.yaml` under `theme:`. The categorical palette
was checked with a colorblind-safety validator; keep the order
(blue, amber, teal, purple) and add colors at the end rather than reshuffling.
