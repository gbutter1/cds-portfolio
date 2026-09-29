-- One row per student for the year. "Chronic absenteeism" follows the common
-- federal/state definition: absent 10% or more of enrolled school days.
with days as (
    select
        student_id,
        count(*)                       as days_enrolled,
        sum(is_present) + sum(is_tardy) as days_present,
        sum(is_absent)                 as days_absent,
        sum(is_tardy)                  as days_tardy,
        sum(is_unexcused_absence)      as days_unexcused
    from {{ ref('fct_attendance_daily') }}
    group by 1
)
select
    s.student_id,
    s.school_code,
    d.school_name,
    d.school_level,
    s.grade_level,
    s.grade_order,
    s.enrollment_date,
    s.withdrawal_date,
    coalesce(x.days_enrolled, 0)                                     as days_enrolled,
    coalesce(x.days_present, 0)                                      as days_present,
    coalesce(x.days_absent, 0)                                       as days_absent,
    coalesce(x.days_tardy, 0)                                        as days_tardy,
    coalesce(x.days_unexcused, 0)                                    as days_unexcused,
    round(coalesce(x.days_absent, 0)::numeric / nullif(x.days_enrolled, 0), 4) as absence_rate,
    round(coalesce(x.days_present, 0)::numeric / nullif(x.days_enrolled, 0), 4) as attendance_rate,
    case
        when x.days_enrolled is null or x.days_enrolled < 20 then 'Insufficient days'
        when x.days_absent::numeric / x.days_enrolled >= 0.20 then 'Severe (20%+)'
        when x.days_absent::numeric / x.days_enrolled >= 0.10 then 'Chronic (10-20%)'
        when x.days_absent::numeric / x.days_enrolled >= 0.05 then 'At risk (5-10%)'
        else 'Satisfactory (<5%)'
    end                                                              as absence_tier,
    (x.days_enrolled >= 20 and x.days_absent::numeric / x.days_enrolled >= 0.10) as is_chronically_absent
from {{ ref('stg_students') }} s
join {{ ref('dim_school') }} d on d.school_code = s.school_code
left join days x on x.student_id = s.student_id
