-- CDC ILINet weekly influenza-like illness for Georgia. ili_pct is the share
-- of all outpatient visits at reporting providers that were for ILI.
select
    lower(trim(region))                     as region,
    epiweek::integer                        as epiweek,
    week_start::date                        as week_start,
    nullif(ili_pct, '')::numeric            as ili_pct,
    nullif(num_ili, '')::integer            as num_ili,
    nullif(num_patients, '')::integer       as num_patients,
    nullif(num_providers, '')::integer      as num_providers,
    nullif(release_date, '')::date          as release_date
from {{ source('raw_healthcare_diagnosis', 'cdc_ilinet_ga') }}
