select store_id, store_name, city, retail_store_no, cafe_location, auto_shop_code, gl_entity
from {{ ref('rr_store_xref') }}
