-- Check 3: did each day's cash (all three departments, tax included) reach the bank?
with tax as (select store_id, sales_tax_rate from {{ ref('rr_store_xref') }}),
cash as (
    select r.store_id, r.business_date, sum(r.line_amount) * (1 + t.sales_tax_rate) as gross
    from {{ ref('stg_rr_retail_pos_lines') }} r join tax t using (store_id)
    where r.tender_type = 'CASH'
    group by r.store_id, r.business_date, t.sales_tax_rate
    union all
    select a.store_id, a.business_date, round(sum(a.amount) * (1 + t.sales_tax_rate), 2)
    from {{ ref('stg_rr_auto_lines') }} a join tax t using (store_id)
    where not a.is_card
    group by a.store_id, a.business_date, a.wo_number, t.sales_tax_rate
    union all
    select store_id, business_date, cash_total
    from {{ ref('stg_rr_cafe_tenders') }}
),
expected as (
    select store_id, business_date, round(sum(gross), 2) as expected_cash
    from cash group by 1, 2
),
dep as (
    select store_id, batch_date as business_date, amount, post_date, bank_line_id
    from {{ ref('stg_rr_bank_transactions') }}
    where processor = 'ARMORED'
)
select
    coalesce(e.store_id, d.store_id)                         as store_id,
    coalesce(e.business_date, d.business_date)               as business_date,
    date_trunc('week', coalesce(e.business_date, d.business_date))::date as week_start,
    e.expected_cash,
    d.amount                                                 as deposit_amount,
    d.post_date                                              as deposit_date,
    round(d.amount - e.expected_cash, 2)                     as difference,
    d.bank_line_id,
    case
        when e.expected_cash is null                      then 'unexpected_deposit'
        when d.amount is null                             then 'missing'
        when abs(d.amount - e.expected_cash) <= 1         then 'matched'
        when d.amount < e.expected_cash                   then 'short'
        else 'over'
    end as match_status
from expected e
full outer join dep d using (store_id, business_date)
