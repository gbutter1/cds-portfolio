-- Merchandising product master, with the price that applied on any date from the price book.
select
    lpad(trim(p.sku), 8, '0')          as sku,
    trim(p.description)                as description,
    trim(p.category)                   as category,
    p.unit_cost::numeric(12, 2)        as unit_cost,
    p.list_price::numeric(12, 2)       as current_price
from {{ source('raw_retail_reconciliation', 'products') }} p
