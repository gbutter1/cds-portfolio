---
title: K-12 Attendance Dashboard
---

School year 2025-26 · 11 schools · daily attendance for every enrolled student.
Use the filters to narrow by school level or cluster; every chart and table
below responds.

```sql schools
select school_code, school_name, school_level, cluster, is_title_i
from cds.dim_school
```

<Dropdown data={schools} name=level value=school_level title="School level" defaultValue="%" >
  <DropdownOption value="%" valueLabel="All levels" />
</Dropdown>
<Dropdown data={schools} name=cluster value=cluster title="Cluster" defaultValue="%">
  <DropdownOption value="%" valueLabel="All clusters" />
</Dropdown>

```sql monthly
select *
from cds.school_monthly_attendance
where school_level like '${inputs.level.value}'
  and cluster like '${inputs.cluster.value}'
order by month_start, school_name
```

```sql headline
select
    sum(student_days)                                   as student_days,
    1 - sum(absences) / sum(student_days)               as attendance_rate,
    sum(absences)                                       as absences,
    sum(unexcused_absences) / nullif(sum(absences), 0)  as unexcused_share
from ${monthly}
```

```sql chronic_headline
select
    count(*)                                                  as students,
    count(*) filter (where is_chronically_absent)             as chronic_students,
    count(*) filter (where is_chronically_absent) / count(*)  as chronic_rate
from cds.student_attendance_summary s
join cds.dim_school d using (school_code)
where d.school_level like '${inputs.level.value}'
  and d.cluster like '${inputs.cluster.value}'
  and s.days_enrolled >= 20
```

<Grid cols=4>
  <BigValue data={headline} value=attendance_rate title="Attendance rate" fmt="pct1" />
  <BigValue data={chronic_headline} value=chronic_rate title="Chronically absent" fmt="pct1" />
  <BigValue data={chronic_headline} value=chronic_students title="Students chronically absent" fmt="#,##0" />
  <BigValue data={headline} value=unexcused_share title="Unexcused share of absences" fmt="pct0" />
</Grid>

## Attendance rate by month

```sql monthly_by_level
select
    month_start,
    school_level,
    1 - sum(absences) / sum(student_days) as attendance_rate
from ${monthly}
group by 1, 2
order by 1, 2
```

<LineChart
  data={monthly_by_level}
  x=month_start
  y=attendance_rate
  series=school_level
  yFmt="pct1"
  yMin=0.85
  title="Monthly attendance rate by school level"
  subtitle="Share of enrolled student-days marked present or tardy"
  xFmt="mmm yyyy"
  markers=true
/>

The seasonal dip in January–February (flu season) and the sharper drop in the
final two weeks of May are the two patterns district attendance officers plan
around; both are visible in every level.

## Chronic absenteeism by school

```sql by_school
select
    d.school_name,
    d.school_level,
    d.cluster,
    case when d.is_title_i then 'Title I' else 'Non-Title I' end as title_i,
    count(*)                                                     as students,
    count(*) filter (where s.is_chronically_absent)              as chronic_students,
    count(*) filter (where s.is_chronically_absent) / count(*)   as chronic_rate,
    avg(s.attendance_rate)                                       as attendance_rate
from cds.student_attendance_summary s
join cds.dim_school d using (school_code)
where d.school_level like '${inputs.level.value}'
  and d.cluster like '${inputs.cluster.value}'
  and s.days_enrolled >= 20
group by 1, 2, 3, 4
order by chronic_rate desc
```

<BarChart
  data={by_school}
  x=school_name
  y=chronic_rate
  series=title_i
  swapXY=true
  yFmt="pct1"
  title="Share of students chronically absent (≥10% of enrolled days)"
  subtitle="Students enrolled fewer than 20 days are excluded"
  sort=false
/>

<DataTable data={by_school} rows=11 search=false>
  <Column id=school_name title="School" />
  <Column id=school_level title="Level" />
  <Column id=cluster />
  <Column id=title_i title="Title I" />
  <Column id=students fmt="#,##0" />
  <Column id=chronic_students title="Chronic" fmt="#,##0" />
  <Column id=chronic_rate title="Chronic rate" fmt="pct1" contentType=bar barColor="#1F6FB0" />
  <Column id=attendance_rate title="Attendance rate" fmt="pct1" />
</DataTable>

## Absence tiers by grade

```sql tiers_by_grade
select
    s.grade_level,
    s.grade_order,
    s.absence_tier,
    count(*) as students
from cds.student_attendance_summary s
join cds.dim_school d using (school_code)
where d.school_level like '${inputs.level.value}'
  and d.cluster like '${inputs.cluster.value}'
  and s.absence_tier <> 'Insufficient days'
group by 1, 2, 3
order by s.grade_order,
  case s.absence_tier
    when 'Satisfactory (<5%)' then 1 when 'At risk (5-10%)' then 2
    when 'Chronic (10-20%)' then 3 else 4 end
```

<BarChart
  data={tiers_by_grade}
  x=grade_level
  y=students
  series=absence_tier
  type=stacked100
  yFmt="pct0"
  title="Students by absence tier and grade"
  subtitle="Tiers follow the common 5% / 10% / 20% thresholds"
  sort=false
  seriesOrder={['Satisfactory (<5%)', 'At risk (5-10%)', 'Chronic (10-20%)', 'Severe (20%+)']}
/>

## Day-of-week pattern

```sql dow
select
    strftime(attendance_date, '%A')                  as weekday,
    dayofweek(attendance_date)                       as dow,
    1 - sum(absences) / sum(student_days)            as attendance_rate
from cds.fct_attendance_daily f
join cds.dim_school d using (school_code)
where d.school_level like '${inputs.level.value}'
  and d.cluster like '${inputs.cluster.value}'
group by 1, 2
order by 2
```

<BarChart
  data={dow}
  x=weekday
  y=attendance_rate
  yFmt="pct1"
  yMin=0.85
  title="Attendance rate by day of week"
  sort=false
/>

Mondays and Fridays run lower than mid-week in every school; this is the
pattern behind "Friday attendance" interventions.

<Details title="Definitions">

- **Attendance rate**: (present + tardy student-days) ÷ enrolled student-days. Tardy counts as present, matching most state reporting rules.
- **Chronically absent**: absent on 10% or more of enrolled school days, for students enrolled at least 20 days.
- **Enrolled student-day**: a school day between the student's enrollment date and withdrawal date (inclusive).
- Only rows that passed every data-quality check are counted. See the [data quality report](/education-attendance/data-quality).

</Details>
