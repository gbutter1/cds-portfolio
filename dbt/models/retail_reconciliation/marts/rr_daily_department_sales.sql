-- One row per store x business date x department: what the three point-of-sale systems say was sold.
-- Cost: product master cost for merchandise and parts; menu food-cost % for the cafe; labor at a
-- standard 45% of labor revenue. Items with no cost on file use an estimated ratio (flagged).
with retail as (
    select store_id, business_date, 'Retail'::text as department,
           sum(line_amount)                                                as net_sales,
           sum(coalesce(unit_cost * qty, line_amount * 0.80))              as cost,
           count(distinct txn_id)                                          as transactions,
           bool_or(unit_cost is null)                                      as cost_estimated
    from {{ ref('stg_rr_retail_pos_lines') }}
    group by 1, 2
),
cafe as (
    select s.store_id, s.business_date, 'Café'::text,
           sum(s.net_sales), sum(s.net_sales * s.food_cost_pct), sum(s.qty_sold)::bigint, false
    from {{ ref('stg_rr_cafe_sales') }} s
    group by 1, 2
),
auto_lines as (
    select a.*, p.unit_cost
    from {{ ref('stg_rr_auto_lines') }} a
    left join {{ ref('stg_rr_products') }} p on p.sku = a.sku
),
auto as (
    select store_id, business_date, 'Auto Center'::text,
           sum(amount),
           sum(case line_type when 'PART'  then coalesce(unit_cost * qty, amount * 0.78)
                              when 'LABOR' then amount * 0.45 else 0 end),
           count(distinct wo_number),
           bool_or(line_type = 'PART' and unit_cost is null)
    from auto_lines
    group by 1, 2
)
select store_id, business_date, date_trunc('week', business_date)::date as week_start, department,
       round(net_sales, 2) as net_sales, round(cost, 2) as cost, transactions, cost_estimated
from (select * from retail union all select * from cafe union all select * from auto) u
