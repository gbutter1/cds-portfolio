-- Cafe items sold per shift. Location codes and item codes arrive in mixed case; dates as MM/DD/YYYY.
select
    x.store_id,
    to_date(s.business_date, 'MM/DD/YYYY')     as business_date,
    upper(trim(s.shift))                       as shift,
    upper(trim(s.item_code))                   as item_code,
    (s.item_code <> upper(trim(s.item_code)))  as code_was_normalized,
    trim(s.item_name)                          as item_name,
    s.qty_sold::int                            as qty_sold,
    s.gross_sales::numeric(12, 2)              as net_sales,
    m.food_cost_pct::numeric(5, 3)             as food_cost_pct
from {{ source('raw_retail_reconciliation', 'cafe_shift_sales') }} s
left join {{ ref('rr_store_xref') }} x on x.cafe_location = lower(trim(s.location))
left join {{ source('raw_retail_reconciliation', 'cafe_menu') }} m on m.item_code = upper(trim(s.item_code))
