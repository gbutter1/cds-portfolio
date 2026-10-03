select
    dq_status,
    case dq_status
        when 'valid'            then 'Passed all checks'
        when 'duplicate'        then 'Exact duplicate of another row (re-sent batch)'
        when 'invalid_date'     then 'Date unreadable or outside the extract window'
        when 'unknown_facility' then 'Facility ID not on the facility list'
        when 'missing_code'     then 'No diagnosis code recorded'
        when 'invalid_code'     then 'Not a recognized ICD-10 code, even after cleanup'
    end                                                      as description,
    count(*)                                                 as row_count,
    count(*) filter (where code_was_normalized)              as codes_normalized,
    round(100.0 * count(*) / sum(count(*)) over (), 3)       as pct_of_rows
from {{ ref('stg_hc_encounters') }}
group by 1, 2
