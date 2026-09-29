-- School x month rollup used by the trend charts.
-- Grain is school x month only: terms straddle month boundaries, so including
-- term here would double-count months (the unique_combination test catches it).
select
    f.school_code,
    d.school_name,
    d.school_level,
    d.cluster,
    d.is_title_i,
    f.month_start,
    to_char(f.month_start, 'Mon YYYY')                          as month_label,
    count(distinct f.attendance_date)                           as school_days,
    count(distinct f.student_id)                                as students,
    count(*)                                                    as student_days,
    sum(f.is_absent)                                            as absences,
    sum(f.is_unexcused_absence)                                 as unexcused_absences,
    sum(f.is_tardy)                                             as tardies,
    round(1 - sum(f.is_absent)::numeric / count(*), 4)          as attendance_rate
from {{ ref('fct_attendance_daily') }} f
join {{ ref('dim_school') }} d on d.school_code = f.school_code
group by 1, 2, 3, 4, 5, 6, 7
