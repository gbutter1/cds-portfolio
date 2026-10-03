-- Check 1: does each department's point-of-sale total match the revenue accounting booked for the
-- same store and day? Every difference is explained where the pattern allows:
--   timing            the same amount appears the next (or previous) day: posted late, clears itself
--   wrong_store       the same amount appears under another store that day
--   wrong_department  the same amount appears under another department that day
--   unexplained       nothing offsets it
-- Paired differences produce one exception (the short side); the offsetting row is marked as such.
with pos as (
    select store_id, business_date, department, net_sales
    from {{ ref('rr_daily_department_sales') }}
),
gl as (
    select store_id, posting_date as business_date, department, sum(net_credit) as gl_sales
    from {{ ref('stg_rr_gl_journal') }}
    where is_revenue
    group by 1, 2, 3
),
j as (
    select
        coalesce(p.store_id, g.store_id)           as store_id,
        coalesce(p.business_date, g.business_date) as business_date,
        coalesce(p.department, g.department)       as department,
        coalesce(p.net_sales, 0)                   as pos_sales,
        coalesce(g.gl_sales, 0)                    as gl_sales,
        round(coalesce(g.gl_sales, 0) - coalesce(p.net_sales, 0), 2) as difference
    from pos p
    full outer join gl g using (store_id, business_date, department)
),
d as (select * from j where abs(difference) > 1)
select
    j.store_id,
    j.business_date,
    date_trunc('week', j.business_date)::date as week_start,
    j.department,
    j.pos_sales,
    j.gl_sales,
    j.difference,
    case when abs(j.difference) <= 1 then 'matched' else coalesce(cp.explanation, 'unexplained') end as match_status,
    -- the side that carries the exception: the short side of a pair, or any unexplained difference
    (abs(j.difference) > 1 and (cp.explanation is null or j.difference < 0)) as is_exception,
    cp.business_date as counterpart_date,
    cp.store_id      as counterpart_store,
    cp.department    as counterpart_department
from j
left join lateral (
    select c.*
    from (
        select 1 as priority, 'timing' as explanation, d2.business_date, d2.store_id, d2.department
        from d d2
        where d2.store_id = j.store_id and d2.department = j.department
          and d2.business_date in (j.business_date + 1, j.business_date - 1)
          and abs(j.difference + d2.difference) <= 1
        union all
        select 2, 'wrong_store', d2.business_date, d2.store_id, d2.department
        from d d2
        where d2.business_date = j.business_date and d2.department = j.department
          and d2.store_id <> j.store_id and abs(j.difference + d2.difference) <= 1
        union all
        select 3, 'wrong_department', d2.business_date, d2.store_id, d2.department
        from d d2
        where d2.business_date = j.business_date and d2.store_id = j.store_id
          and d2.department <> j.department and abs(j.difference + d2.difference) <= 1
    ) c
    where abs(j.difference) > 1
    order by c.priority
    limit 1
) cp on true
