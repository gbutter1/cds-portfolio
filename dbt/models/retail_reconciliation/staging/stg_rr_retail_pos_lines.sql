-- Retail register lines: typed, mapped to store_id, and flagged when the SKU is not in the product master.
select
    l.txn_id,
    x.store_id,
    l.register_no::int                         as register_no,
    l.txn_ts::timestamp                        as txn_ts,
    l.txn_ts::timestamp::date                  as business_date,
    lpad(trim(l.sku), 8, '0')                  as sku,
    trim(l.item_description)                   as item_description,
    l.qty::int                                 as qty,
    l.unit_price::numeric(12, 2)               as unit_price,
    l.line_discount::numeric(12, 2)            as line_discount,
    l.line_amount::numeric(12, 2)              as line_amount,
    upper(trim(l.tender_type))                 as tender_type,
    (p.sku is not null)                        as in_product_master,
    p.category,
    p.unit_cost
from {{ source('raw_retail_reconciliation', 'retail_pos_lines') }} l
left join {{ ref('rr_store_xref') }} x on x.retail_store_no = trim(l.store_no)
left join {{ ref('stg_rr_products') }} p on p.sku = lpad(trim(l.sku), 8, '0')
