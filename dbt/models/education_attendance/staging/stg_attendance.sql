-- Clean the daily attendance extract. Every row keeps a `dq_status` so the
-- data-quality mart can report exactly what was rejected and why, and every
-- downstream model filters to dq_status = 'valid'.
--
-- Rules, in order of precedence:
--   duplicate          exact duplicate of another row (first copy is kept)
--   invalid_status     status not in P / A / T
--   non_school_day     date is not a school day on the calendar
--   unknown_student    student_id not on the roster
--   outside_enrollment date is before enrollment or after withdrawal
--   valid              everything else

with raw as (

    select
        nullif(trim(student_id), '')::integer     as student_id,
        upper(trim(school_code))                  as school_code,
        attendance_date::date                     as attendance_date,
        upper(trim(attendance_status))            as attendance_status,
        nullif(trim(absence_type), '')            as absence_type,
        source_system,
        extract_ts::timestamp                     as extract_ts,
        row_number() over (
            partition by
                nullif(trim(student_id), '')::integer,
                attendance_date::date,
                upper(trim(school_code)),
                upper(trim(attendance_status)),
                nullif(trim(absence_type), '')
            order by _load_ts
        )                                         as dup_rank
    from {{ source('raw_education_attendance', 'attendance_daily') }}

),

flagged as (

    select
        r.*,
        case
            when r.dup_rank > 1                                   then 'duplicate'
            when r.attendance_status not in ('P', 'A', 'T')       then 'invalid_status'
            when c.is_school_day is distinct from true            then 'non_school_day'
            when s.student_id is null                             then 'unknown_student'
            when r.attendance_date < s.enrollment_date
              or r.attendance_date > coalesce(s.withdrawal_date, '9999-12-31'::date)
                                                                  then 'outside_enrollment'
            else 'valid'
        end as dq_status
    from raw r
    left join {{ ref('stg_calendar') }} c on c.calendar_date = r.attendance_date
    left join {{ ref('stg_students') }} s on s.student_id = r.student_id

)

select
    student_id,
    school_code,
    attendance_date,
    attendance_status,
    case attendance_status
        when 'P' then 'Present' when 'A' then 'Absent' when 'T' then 'Tardy'
    end                                   as attendance_status_desc,
    absence_type,
    dq_status,
    source_system,
    extract_ts
from flagged
