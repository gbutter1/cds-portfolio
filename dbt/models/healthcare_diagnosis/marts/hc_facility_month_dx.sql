-- Encounter counts at the grain the app filters on:
-- facility x month x age group x diagnosis code.
select
    facility_id,
    month_start,
    age_group,
    icd10_code,
    count(*) as encounters
from {{ ref('hc_fct_encounter') }}
group by 1, 2, 3, 4
