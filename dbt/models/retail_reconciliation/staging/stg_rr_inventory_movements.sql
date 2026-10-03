-- Inventory movements. The inventory system drops leading zeros from SKUs, so they are padded back.
select
    lpad(trim(i.item_no), 8, '0')   as sku,
    x.store_id,
    upper(trim(i.movement_type))    as movement_type,
    i.movement_date::date           as movement_date,
    i.qty::int                      as qty,
    trim(i.reference)               as reference
from {{ source('raw_retail_reconciliation', 'inventory_movements') }} i
left join {{ ref('rr_store_xref') }} x on x.retail_store_no = trim(i.location)
