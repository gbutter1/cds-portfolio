-- Type and standardize the school roster.
select
    upper(trim(school_code))                    as school_code,
    trim(school_name)                           as school_name,
    trim(school_level)                          as school_level,
    trim(cluster)                               as cluster,
    lower(trim(title_i)) in ('true', 't', '1')  as is_title_i
from {{ source('raw_education_attendance', 'schools') }}
