-- Clean the encounter extract. Every row keeps a dq_status; marts use only
-- dq_status = 'valid'.
--
-- Diagnosis codes are NORMALIZED, not rejected, when the problem is only
-- formatting: trimmed, upper-cased, and the decimal point restored after the
-- third character (ICD-10-CM codes are stored without the dot by many
-- systems: J111 -> J11.1). Rows are only rejected when the code is truly
-- missing or is not a known ICD-10 code after normalizing.
--
-- Rules, in order of precedence:
--   duplicate         exact duplicate of another row (first copy kept)
--   invalid_date      date can't be parsed or falls outside the extract window
--   unknown_facility  facility_id not on the facility list
--   missing_code      no diagnosis code
--   invalid_code      code is not in the ICD-10 reference after normalizing
--   valid

with typed as (

    select
        trim(encounter_id)                                    as encounter_id,
        upper(trim(facility_id))                              as facility_id,
        case when pg_input_is_valid(trim(encounter_date), 'date')
             then trim(encounter_date)::date end              as encounter_date,
        nullif(trim(patient_age), '')::integer                as patient_age,
        upper(trim(patient_sex))                              as patient_sex,
        trim(encounter_type)                                  as encounter_type,
        primary_dx_code                                       as raw_dx_code,
        nullif(upper(trim(primary_dx_code)), '')              as dx_trimmed,
        _load_ts,
        row_number() over (
            partition by encounter_id, facility_id, encounter_date, primary_dx_code, patient_age, patient_sex
            order by _load_ts
        )                                                     as dup_rank
    from {{ source('raw_healthcare_diagnosis', 'encounters') }}

),

normalized as (

    select
        t.*,
        case
            when dx_trimmed is null then null
            when position('.' in dx_trimmed) = 0 and length(dx_trimmed) > 3
                then left(dx_trimmed, 3) || '.' || substr(dx_trimmed, 4)
            else dx_trimmed
        end as icd10_code
    from typed t

),

flagged as (

    select
        n.*,
        (n.icd10_code is distinct from trim(n.raw_dx_code))   as code_was_normalized,
        case
            when n.dup_rank > 1                                                  then 'duplicate'
            when n.encounter_date is null
              or n.encounter_date not between date '2024-10-01' and date '2026-09-30' then 'invalid_date'
            when f.facility_id is null                                           then 'unknown_facility'
            when n.icd10_code is null                                            then 'missing_code'
            when r.icd10_code is null                                            then 'invalid_code'
            else 'valid'
        end as dq_status
    from normalized n
    left join {{ ref('stg_hc_facilities') }} f on f.facility_id = n.facility_id
    left join {{ ref('icd10_reference') }}  r on r.icd10_code = n.icd10_code

)

select
    encounter_id,
    facility_id,
    encounter_date,
    date_trunc('month', encounter_date)::date                         as month_start,
    (encounter_date - extract(dow from encounter_date)::int)          as week_start,  -- Sunday, matching CDC MMWR weeks
    patient_age,
    case
        when patient_age < 5  then '0-4'
        when patient_age < 18 then '5-17'
        when patient_age < 45 then '18-44'
        when patient_age < 65 then '45-64'
        else '65+'
    end                                                               as age_group,
    patient_sex,
    encounter_type,
    raw_dx_code,
    icd10_code,
    code_was_normalized,
    dq_status
from flagged
