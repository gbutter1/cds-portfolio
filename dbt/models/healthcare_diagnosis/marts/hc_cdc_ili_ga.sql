select epiweek, week_start, ili_pct / 100.0 as ili_share, num_ili, num_patients, num_providers, release_date
from {{ ref('stg_hc_cdc_ili') }}
