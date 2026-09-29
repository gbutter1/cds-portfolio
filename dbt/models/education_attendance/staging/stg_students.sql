-- Type the student roster. Names are kept out of the analytics layer entirely:
-- nothing downstream needs them, so they never leave staging.
select
    student_id::integer                              as student_id,
    upper(trim(school_code))                         as school_code,
    upper(trim(grade_level))                         as grade_level,
    case upper(trim(grade_level))
        when 'K' then 0 else nullif(trim(grade_level), '')::integer
    end                                              as grade_order,
    enrollment_date::date                            as enrollment_date,
    nullif(trim(withdrawal_date), '')::date          as withdrawal_date
from {{ source('raw_education_attendance', 'students') }}
