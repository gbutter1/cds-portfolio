-- Check 4 (cross-department): every part the auto center bills should come off the store's
-- inventory against that work order. The shop uses vendor part numbers; inventory uses store SKUs,
-- so each line is translated through the parts crosswalk first.
with parts as (
    select a.*, p.unit_cost
    from {{ ref('stg_rr_auto_lines') }} a
    left join {{ ref('stg_rr_products') }} p on p.sku = a.sku
    where a.line_type = 'PART'
),
issued as (
    select reference as wo_number, sku, -sum(qty) as qty_issued
    from {{ ref('stg_rr_inventory_movements') }}
    where movement_type = 'AUTO_ISSUE'
    group by 1, 2
)
select
    p.wo_number,
    p.line_no,
    p.store_id,
    p.business_date,
    date_trunc('week', p.business_date)::date as week_start,
    p.item_code_raw,
    p.sku,
    p.code_was_normalized,
    p.description,
    p.qty                as qty_billed,
    i.qty_issued,
    p.amount,
    p.unit_cost,
    case
        when p.sku is null            then 'unmapped_part'
        when i.qty_issued is null     then 'not_issued'
        when i.qty_issued <> p.qty    then 'qty_mismatch'
        else 'matched'
    end as match_status,
    case
        when p.sku is null            then p.amount
        when i.qty_issued is null     then round(p.qty * p.unit_cost, 2)
        when i.qty_issued <> p.qty    then round(abs(p.qty - i.qty_issued) * p.unit_cost, 2)
        else 0
    end as amount_at_risk
from parts p
left join issued i on i.wo_number = p.wo_number and i.sku = p.sku
