-- One row per week x store x department: sales, margin and the reconciliation exceptions that
-- belong to that department (bank exceptions that span departments are reported at store level).
with sales as (
    select week_start, store_id, department,
           sum(net_sales) as net_sales, sum(cost) as cost, sum(transactions) as transactions
    from {{ ref('rr_daily_department_sales') }}
    group by 1, 2, 3
),
ex as (
    select week_start, store_id, department,
           count(*) filter (where not is_timing)                  as open_exceptions,
           coalesce(sum(amount) filter (where not is_timing), 0)  as open_amount
    from {{ ref('rr_exceptions') }}
    group by 1, 2, 3
)
select
    s.week_start,
    s.store_id,
    s.department,
    round(s.net_sales, 2)                                  as net_sales,
    round(s.cost, 2)                                       as cost,
    round(s.net_sales - s.cost, 2)                         as gross_margin,
    round((s.net_sales - s.cost) / nullif(s.net_sales, 0), 4) as gross_margin_pct,
    s.transactions,
    coalesce(e.open_exceptions, 0)                         as open_exceptions,
    coalesce(e.open_amount, 0)                             as open_amount
from sales s
left join ex e using (week_start, store_id, department)
