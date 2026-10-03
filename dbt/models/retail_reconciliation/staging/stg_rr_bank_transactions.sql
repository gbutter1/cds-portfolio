-- Bank statement credits. Everything needed for matching is inside the free-text description:
--   PEACHPAY MERCH SETTLE MID 884100101 BATCH 0412   (batch date as MMDD, year implied)
--   TABLESIDE PAY DEP CB-7701 BD 20260412
--   ARMORED CAR DEP LOC 101 BAG 20260412
with b as (
    select
        row_number() over (order by post_date, description, amount) as bank_line_id,
        post_date::date             as post_date,
        trim(description)           as description,
        amount::numeric(12, 2)      as amount
    from {{ source('raw_retail_reconciliation', 'bank_transactions') }}
),
parsed as (
    select
        b.*,
        case
            when description like 'PEACHPAY%'  then 'PEACHPAY'
            when description like 'TABLESIDE%' then 'TABLESIDE'
            when description like 'ARMORED%'   then 'ARMORED'
            else 'OTHER'
        end                                                             as processor,
        substring(description from 'MID ([0-9]+)')                      as card_mid,
        substring(description from 'PAY DEP ([A-Z]{2}-[0-9]+)')         as cafe_mid,
        substring(description from 'LOC ([0-9]+)')                      as cash_loc,
        substring(description from 'BATCH ([0-9]{4})')                  as mmdd,
        substring(description from '(?:BD|BAG) ([0-9]{8})')             as yyyymmdd
    from b
),
dated as (
    select
        p.*,
        case
            when yyyymmdd is not null then to_date(yyyymmdd, 'YYYYMMDD')
            when mmdd is not null then
                -- a MMDD batch belongs to the most recent such date on or before the post date
                case when to_date(extract(year from post_date)::text || mmdd, 'YYYYMMDD') <= post_date
                     then to_date(extract(year from post_date)::text || mmdd, 'YYYYMMDD')
                     else to_date((extract(year from post_date) - 1)::text || mmdd, 'YYYYMMDD') end
        end as batch_date
    from parsed p
)
select
    d.bank_line_id,
    d.post_date,
    d.description,
    d.amount,
    d.processor,
    d.batch_date,
    coalesce(xc.store_id, xf.store_id, xl.store_id) as store_id
from dated d
left join {{ ref('rr_store_xref') }} xc on xc.card_merchant_id = d.card_mid
left join {{ ref('rr_store_xref') }} xf on xf.cafe_merchant_id = d.cafe_mid
left join {{ ref('rr_store_xref') }} xl on xl.retail_store_no = d.cash_loc
