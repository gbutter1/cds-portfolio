select
    s.school_code,
    s.school_name,
    s.school_level,
    s.cluster,
    s.is_title_i,
    count(st.student_id)                          as students_enrolled
from {{ ref('stg_schools') }} s
left join {{ ref('stg_students') }} st on st.school_code = s.school_code
group by 1, 2, 3, 4, 5
