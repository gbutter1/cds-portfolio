-- Every dollar sold in the three point-of-sale systems must land in the daily department sales
-- mart exactly once. Returns a row (fails) for any department whose totals differ by more than a cent.
with src as (
    select 'Retail' as department, sum(line_amount) as total from {{ ref('stg_rr_retail_pos_lines') }}
    union all
    select 'Café', sum(net_sales) from {{ ref('stg_rr_cafe_sales') }}
    union all
    select 'Auto Center', sum(amount) from {{ ref('stg_rr_auto_lines') }}
),
mart as (
    select department, sum(net_sales) as total from {{ ref('rr_daily_department_sales') }} group by 1
)
select s.department, s.total as source_total, m.total as mart_total
from src s
left join mart m using (department)
where m.total is null or abs(s.total - m.total) > 0.01
