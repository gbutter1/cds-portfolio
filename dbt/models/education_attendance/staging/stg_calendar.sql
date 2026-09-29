select
    calendar_date::date                                  as calendar_date,
    school_year,
    term,
    lower(trim(is_school_day)) in ('true', 't', '1')     as is_school_day,
    day_of_week,
    date_trunc('month', calendar_date::date)::date       as month_start
from {{ source('raw_education_attendance', 'calendar') }}
