-- One row per valid encounter.
select
    e.encounter_id,
    e.facility_id,
    e.encounter_date,
    e.month_start,
    e.week_start,
    e.age_group,
    e.patient_sex,
    e.encounter_type,
    e.icd10_code,
    r.category      as dx_category,
    r.is_influenza
from {{ ref('stg_hc_encounters') }} e
join {{ ref('icd10_reference') }} r using (icd10_code)
where e.dq_status = 'valid'
