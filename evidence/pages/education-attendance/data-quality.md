---
title: Data Quality Report
---

Every row of the source extract is kept and labeled with the outcome of the
validation rules. Nothing is silently dropped: the marts use only rows marked
**valid**, and this page shows everything else.

```sql dq
select
    dq_status,
    description,
    row_count,
    pct_of_rows / 100 as pct
from cds.attendance_data_quality
order by row_count desc
```

```sql totals
select
    sum(row_count)                                             as total_rows,
    sum(row_count) filter (where dq_status = 'valid')          as valid_rows,
    sum(row_count) filter (where dq_status <> 'valid')         as rejected_rows,
    sum(pct) filter (where dq_status <> 'valid')               as rejected_pct
from ${dq}
```

<Grid cols=3>
  <BigValue data={totals} value=total_rows title="Rows received" fmt="#,##0" />
  <BigValue data={totals} value=valid_rows title="Rows accepted" fmt="#,##0" />
  <BigValue data={totals} value=rejected_pct title="Rejected" fmt="pct2" />
</Grid>

```sql rejected
select * from ${dq} where dq_status <> 'valid'
```

<BarChart
  data={rejected}
  x=dq_status
  y=row_count
  swapXY=true
  title="Rejected rows by reason"
  yFmt="#,##0"
/>

<DataTable data={dq} rows=6>
  <Column id=dq_status title="Status" />
  <Column id=description wrap=true />
  <Column id=row_count title="Rows" fmt="#,##0" />
  <Column id=pct title="% of rows" fmt="pct3" />
</DataTable>

## How each rule works

**Duplicate.** Source systems re-send batches. Rows are ranked within
(student, date, school, status, absence type) by load time and only the first
copy is kept.

**Invalid status.** Attendance status must be `P`, `A` or `T`. Values like
`PRESENT`, `X` or blank usually mean a code-table change upstream; they are
reported rather than guessed.

**Non-school day.** A row dated on a weekend or holiday is almost always a
keying error. The rule joins to the district calendar, so a calendar change
automatically changes what is accepted.

**Unknown student.** The student ID is not on the roster extract. Typically a
timing gap between the roster and attendance extracts.

**Outside enrollment.** The row is dated before the student's enrollment date
or after their withdrawal date. Counting these would inflate absences for
students who have already transferred out.

## Guardrails on the pipeline itself

Beyond row-level rules, the dbt layer runs **36 automated tests** on every
build, including uniqueness of every key, referential integrity between
attendance, students and schools, accepted values on every code, range checks
on every rate, and a threshold test that **fails the whole run** if more than
2% of source rows are rejected, on the theory that a bad extract should stop
the pipeline rather than quietly produce a bad dashboard.
