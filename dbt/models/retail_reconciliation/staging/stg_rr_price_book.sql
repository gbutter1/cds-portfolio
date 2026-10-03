-- One row per price period: price applies from effective_from through effective_to (inclusive).
with b as (
    select
        lpad(trim(sku), 8, '0')         as sku,
        effective_date::date            as effective_from,
        price::numeric(12, 2)           as price
    from {{ source('raw_retail_reconciliation', 'price_book') }}
)
select
    sku,
    effective_from,
    coalesce(lead(effective_from) over (partition by sku order by effective_from) - 1, date '9999-12-31') as effective_to,
    price
from b
