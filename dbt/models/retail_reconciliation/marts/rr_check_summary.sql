-- One row per week x check: how many items were compared, how many matched, and what is open.
with items as (
    select 'Sales vs. accounting'::text as check_name, week_start,
           count(*) as items_checked, count(*) filter (where match_status = 'matched') as items_matched
    from {{ ref('rr_recon_sales_vs_gl') }} group by 1, 2
    union all
    select 'Card sales vs. bank', week_start, count(*), count(*) filter (where match_status = 'matched')
    from {{ ref('rr_recon_card_vs_bank') }} group by 1, 2
    union all
    select 'Cash vs. bank', week_start, count(*), count(*) filter (where match_status = 'matched')
    from {{ ref('rr_recon_cash_vs_bank') }} group by 1, 2
    union all
    select 'Auto parts vs. inventory', week_start, count(*), count(*) filter (where match_status = 'matched')
    from {{ ref('rr_recon_auto_parts_vs_inventory') }} group by 1, 2
    union all
    select 'Registers vs. product master', week_start, count(*), count(*) filter (where match_status = 'matched')
    from {{ ref('rr_recon_product_master') }} group by 1, 2
),
ex as (
    select check_name, week_start,
           count(*)                                         as exceptions,
           count(*) filter (where not is_timing)            as open_exceptions,
           coalesce(sum(amount) filter (where not is_timing), 0) as open_amount,
           coalesce(sum(amount) filter (where is_timing), 0)     as timing_amount
    from {{ ref('rr_exceptions') }} group by 1, 2
)
select
    i.check_name,
    i.week_start,
    i.items_checked,
    i.items_matched,
    round(i.items_matched::numeric / nullif(i.items_checked, 0), 4) as match_rate,
    coalesce(e.exceptions, 0)      as exceptions,
    coalesce(e.open_exceptions, 0) as open_exceptions,
    coalesce(e.open_amount, 0)     as open_amount,
    coalesce(e.timing_amount, 0)   as timing_amount
from items i
left join ex e using (check_name, week_start)
