select facility_id, facility_name, facility_type, city, county
from {{ ref('stg_hc_facilities') }}
