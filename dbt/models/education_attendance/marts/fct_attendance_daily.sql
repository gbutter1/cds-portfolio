-- One row per student per school day, valid records only.
select
    student_id::text || '|' || attendance_date::text     as attendance_key,
    a.student_id,
    a.school_code,
    a.attendance_date,
    c.month_start,
    c.term,
    c.school_year,
    a.attendance_status,
    a.attendance_status_desc,
    a.absence_type,
    (a.attendance_status = 'P')::int                     as is_present,
    (a.attendance_status = 'A')::int                     as is_absent,
    (a.attendance_status = 'T')::int                     as is_tardy,
    (a.attendance_status = 'A' and a.absence_type = 'Unexcused')::int as is_unexcused_absence
from {{ ref('stg_attendance') }} a
join {{ ref('stg_calendar') }} c on c.calendar_date = a.attendance_date
where a.dq_status = 'valid'
