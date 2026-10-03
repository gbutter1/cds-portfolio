-- Check 5: does what the registers sold agree with the product master?
-- One row per store x SKU x week. Flags SKUs that are not set up in the master, and registers
-- charging a price other than the one the price book says applied that day.
with lines as (
    select l.*, b.price as book_price
    from {{ ref('stg_rr_retail_pos_lines') }} l
    left join {{ ref('stg_rr_price_book') }} b
        on b.sku = l.sku and l.business_date between b.effective_from and b.effective_to
)
select
    store_id,
    sku,
    date_trunc('week', business_date)::date               as week_start,
    max(item_description)                                 as item_description,
    bool_and(in_product_master)                           as in_product_master,
    sum(qty)                                              as units,
    sum(line_amount)                                      as net_sales,
    sum(qty) filter (where unit_price <> book_price)      as units_off_price,
    min(business_date) filter (where unit_price <> book_price) as first_date_off_price,
    max(business_date) filter (where unit_price <> book_price) as last_date_off_price,
    max(unit_price) filter (where unit_price <> book_price)    as price_charged,
    max(book_price) filter (where unit_price <> book_price)    as book_price,
    round(coalesce(sum((unit_price - book_price) * qty) filter (where unit_price <> book_price), 0), 2) as price_impact,
    case
        when not bool_and(in_product_master)                  then 'not_in_master'
        when count(*) filter (where unit_price <> book_price) > 0 then 'price_mismatch'
        else 'matched'
    end as match_status
from lines
group by store_id, sku, date_trunc('week', business_date)
