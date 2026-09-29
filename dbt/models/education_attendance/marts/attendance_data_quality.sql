-- What the pipeline rejected and why. Reported on the dashboard so the
-- cleaning is visible rather than silent.
select
    dq_status,
    case dq_status
        when 'valid'              then 'Passed all checks'
        when 'duplicate'          then 'Exact duplicate of another row (re-sent batch)'
        when 'invalid_status'     then 'Attendance status not in P / A / T'
        when 'non_school_day'     then 'Dated on a holiday or weekend'
        when 'unknown_student'    then 'Student ID not on the roster'
        when 'outside_enrollment' then 'Dated before enrollment or after withdrawal'
    end                                                     as description,
    count(*)                                                as row_count,
    round(100.0 * count(*) / sum(count(*)) over (), 3)      as pct_of_rows
from {{ ref('stg_attendance') }}
group by 1, 2
