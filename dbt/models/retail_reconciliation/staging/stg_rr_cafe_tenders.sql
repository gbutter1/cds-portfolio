-- Cafe card/cash per shift. batch_date is when the card batch actually closed, which is
-- normally the business date but is the next day when a shift's batch was left open.
select
    x.store_id,
    to_date(t.business_date, 'MM/DD/YYYY')     as business_date,
    upper(trim(t.shift))                       as shift,
    t.card_total::numeric(12, 2)               as card_total,
    t.cash_total::numeric(12, 2)               as cash_total,
    to_date(t.batch_date, 'MM/DD/YYYY')        as batch_date,
    trim(t.closed_by)                          as closed_by
from {{ source('raw_retail_reconciliation', 'cafe_shift_tenders') }} t
left join {{ ref('rr_store_xref') }} x on x.cafe_location = lower(trim(t.location))
