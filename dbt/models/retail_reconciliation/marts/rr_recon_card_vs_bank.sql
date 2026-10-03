-- Check 2: did each card batch turn into a bank deposit for the right amount?
-- Expected deposit = card sales (tax included) minus the contract processing fee.
-- PeachPay settles retail + auto center batches; TableSide settles cafe batches by the date the
-- batch actually closed. Deposits are matched on processor + store + batch date parsed from the
-- bank description.
with retail_card as (
    select store_id, business_date as batch_date, sum(line_amount) as net
    from {{ ref('stg_rr_retail_pos_lines') }}
    where tender_type = 'CARD'
    group by 1, 2
),
auto_wo as (
    select store_id, business_date as batch_date, wo_number, sum(amount) as net
    from {{ ref('stg_rr_auto_lines') }}
    where is_card
    group by 1, 2, 3
),
tax as (select store_id, sales_tax_rate from {{ ref('rr_store_xref') }}),
expected as (
    select 'PEACHPAY'::text as processor, store_id, batch_date, round(sum(gross), 2) as card_gross
    from (
        select r.store_id, r.batch_date, r.net * (1 + t.sales_tax_rate) as gross
        from retail_card r join tax t using (store_id)
        union all
        select a.store_id, a.batch_date, round(a.net * (1 + t.sales_tax_rate), 2)
        from auto_wo a join tax t using (store_id)
    ) x
    group by 1, 2, 3
    union all
    select 'TABLESIDE', store_id, batch_date, sum(card_total)
    from {{ ref('stg_rr_cafe_tenders') }}
    group by 1, 2, 3
),
dep as (
    select processor, store_id, batch_date, post_date, amount, bank_line_id
    from {{ ref('stg_rr_bank_transactions') }}
    where processor in ('PEACHPAY', 'TABLESIDE')
),
j as (
    select
        coalesce(e.processor, d.processor)   as processor,
        coalesce(e.store_id, d.store_id)     as store_id,
        coalesce(e.batch_date, d.batch_date) as batch_date,
        e.card_gross,
        p.contract_fee_rate,
        round(e.card_gross - round(e.card_gross * p.contract_fee_rate, 2), 2) as expected_deposit,
        d.amount       as deposit_amount,
        d.post_date    as deposit_date,
        d.bank_line_id
    from expected e
    full outer join dep d using (processor, store_id, batch_date)
    join {{ ref('rr_processors') }} p on p.processor = coalesce(e.processor, d.processor)
),
m as (
    select
        j.*,
        round(deposit_amount - expected_deposit, 2)                 as difference,
        (deposit_date - batch_date)                                 as days_to_deposit,
        case when card_gross > 0 and deposit_amount is not null
             then round((card_gross - deposit_amount) / card_gross, 5) end as implied_fee_rate
    from j
),
flagged as (
    select
        m.*,
        -- a fee problem looks like the same small extra percentage on several batches in a row
        (difference < -1 and implied_fee_rate - contract_fee_rate between 0.003 and 0.008) as fee_like,
        count(*) filter (where difference < -1 and implied_fee_rate - contract_fee_rate between 0.003 and 0.008)
            over (partition by processor, store_id order by batch_date
                  range between interval '7 days' preceding and interval '7 days' following) as fee_like_nearby
    from m
)
select
    processor, store_id, batch_date, date_trunc('week', batch_date)::date as week_start,
    card_gross, contract_fee_rate, expected_deposit, deposit_amount, deposit_date, days_to_deposit,
    difference, implied_fee_rate, bank_line_id,
    case
        when card_gross is null                         then 'unexpected_deposit'
        when deposit_amount is null                     then 'missing'
        when abs(difference) <= 1 and days_to_deposit > 6 then 'late'
        when abs(difference) <= 1                        then 'matched'
        when fee_like and fee_like_nearby >= 3           then 'fee_above_contract'
        when difference < 0                              then 'short'
        else 'over'
    end as match_status
from flagged
