select
    upper(trim(facility_id))   as facility_id,
    trim(facility_name)        as facility_name,
    trim(facility_type)        as facility_type,
    trim(city)                 as city,
    trim(county)               as county
from {{ source('raw_healthcare_diagnosis', 'facilities') }}
