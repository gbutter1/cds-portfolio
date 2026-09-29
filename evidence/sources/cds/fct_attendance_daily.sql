-- Daily grain by school and status; small enough to ship to the browser.
select school_code, attendance_date, month_start, term,
       count(*)                     as student_days,
       sum(is_absent)               as absences,
       sum(is_unexcused_absence)    as unexcused_absences,
       sum(is_tardy)                as tardies
from marts.fct_attendance_daily
group by 1, 2, 3, 4
order by 2, 1
