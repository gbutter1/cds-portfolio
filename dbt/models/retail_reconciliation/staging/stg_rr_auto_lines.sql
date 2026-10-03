-- Auto center work-order lines. Timestamps arrive as "4/12/2026 3:42 PM" and amounts as "$1,234.50".
with l as (
    select
        trim(wo_number)                                                 as wo_number,
        trim(shop_code)                                                 as shop_code,
        to_timestamp(trim(closed_at), 'FMMM/FMDD/YYYY FMHH12:MI AM')::timestamp as closed_at,
        line_no::int                                                    as line_no,
        upper(trim(line_type))                                          as line_type,
        item_code                                                       as item_code_raw,
        upper(regexp_replace(item_code, '[^A-Za-z0-9]', '', 'g'))       as part_key,
        trim(description)                                               as description,
        qty::int                                                        as qty,
        replace(replace(amount, '$', ''), ',', '')::numeric(12, 2)      as amount,
        upper(trim(payment_method))                                     as payment_method
    from {{ source('raw_retail_reconciliation', 'auto_work_order_lines') }}
)
select
    l.wo_number,
    x.store_id,
    l.closed_at,
    l.closed_at::date                                 as business_date,
    l.line_no,
    l.line_type,
    l.item_code_raw,
    case when l.line_type = 'PART' then l.part_key end as part_key,
    case when l.line_type = 'PART' then xr.sku end    as sku,
    (l.line_type = 'PART' and xr.sku is not null
        and trim(l.item_code_raw) <> xr.vendor_part_no) as code_was_normalized,
    l.description,
    l.qty,
    l.amount,
    l.payment_method,
    (l.payment_method <> 'CASH')                      as is_card
from l
left join {{ ref('rr_store_xref') }} x on x.auto_shop_code = l.shop_code
left join {{ ref('stg_rr_part_xref') }} xr on xr.part_key = l.part_key and l.line_type = 'PART'
