-- Every reconciliation problem in one list, one row per problem, written so a store manager or
-- accountant can act on it without opening five systems: what doesn't match, by how much, which
-- system is most likely wrong, and what to do about it.
-- is_timing marks items that clear on their own (posted a day late, deposit arrived late); they are
-- reported but not counted as unmatched dollars.
with stores as (select store_id, city from {{ ref('rr_dim_store') }}),

sales_gl as (
    select
        'Sales vs. accounting'::text as check_name,
        r.store_id || '|' || r.business_date || '|' || r.department as item_key,
        r.business_date, r.store_id, r.department,
        abs(r.difference) as amount,
        case r.match_status
            when 'timing'           then r.department || ' sales booked a day late'
            when 'wrong_store'      then r.department || ' sales booked under another store'
            when 'wrong_department' then r.department || ' sales booked to another department'
            when 'unexplained'      then case when r.difference > 0 then 'Books show more ' || lower(r.department) || ' sales than the registers'
                                              else 'Books show less ' || lower(r.department) || ' sales than the registers' end
        end as issue,
        case r.match_status
            when 'timing' then format('Registers %s, books %s. The missing %s was booked on %s instead.',
                                      {{ rr_money('r.pos_sales') }}, {{ rr_money('r.gl_sales') }}, {{ rr_money('abs(r.difference)') }},
                                      to_char(r.counterpart_date, 'Mon FMDD'))
            when 'wrong_store' then format('Registers %s, books %s. The same %s was booked under the %s store.',
                                      {{ rr_money('r.pos_sales') }}, {{ rr_money('r.gl_sales') }}, {{ rr_money('abs(r.difference)') }}, cs.city)
            when 'wrong_department' then format('%s of %s sales was booked as %s revenue.',
                                      {{ rr_money('abs(r.difference)') }}, r.department, r.counterpart_department)
            else format('Registers %s, books %s, a difference of %s with nothing to offset it.',
                        {{ rr_money('r.pos_sales') }}, {{ rr_money('r.gl_sales') }}, {{ rr_money('abs(r.difference)') }})
        end as detail,
        case r.match_status
            when 'timing'           then 'Accounting (posting date)'
            when 'wrong_store'      then 'Accounting (store coding)'
            when 'wrong_department' then 'Accounting (account mapping)'
            else case when r.difference > 0 then 'Accounting (manual entry)' else 'Accounting (missing posting)' end
        end as likely_source,
        case r.match_status
            when 'timing'           then 'No correction needed; the next day offsets it. Close every shift batch the same day.'
            when 'wrong_store'      then 'Move the entry to the correct store with a reclass journal entry.'
            when 'wrong_department' then 'Reclass to the correct revenue account and fix the account mapping in the source system.'
            else case when r.difference > 0 then 'Review manual journal entries for this day; reverse any duplicate.'
                      else 'Find and post the missing sales summary.' end
        end as suggested_action,
        (r.match_status = 'timing') as is_timing,
        r.match_status
    from {{ ref('rr_recon_sales_vs_gl') }} r
    left join stores cs on cs.store_id = r.counterpart_store
    where r.is_exception
),

card as (
    select
        'Card sales vs. bank'::text,
        c.processor || '|' || c.store_id || '|' || c.batch_date,
        c.batch_date, c.store_id,
        case c.processor when 'PEACHPAY' then 'Retail & Auto Center' else 'Café' end,
        case c.match_status
            when 'missing' then c.expected_deposit
            when 'late'    then c.deposit_amount
            when 'unexpected_deposit' then c.deposit_amount
            else abs(c.difference) end,
        case c.match_status
            when 'missing'            then 'Card deposit never arrived'
            when 'late'               then 'Card deposit arrived late'
            when 'fee_above_contract' then 'Processor fee above the contract rate'
            when 'short'              then 'Card deposit short'
            when 'over'               then 'Card deposit higher than expected'
            else 'Deposit with no matching card sales' end,
        case c.match_status
            when 'missing' then format('%s batch for %s: expected %s (card sales %s less the contract fee). No deposit found.',
                                       case c.processor when 'PEACHPAY' then 'PeachPay' else 'TableSide Pay' end, to_char(c.batch_date, 'Mon FMDD'), {{ rr_money('c.expected_deposit') }}, {{ rr_money('c.card_gross') }})
            when 'late' then format('%s arrived %s days after the batch; it normally takes 1 to 2 business days.',
                                    {{ rr_money('c.deposit_amount') }}, c.days_to_deposit)
            when 'fee_above_contract' then format('Charged %s%% instead of the contract %s%% on %s of card sales: %s more than agreed.',
                                    to_char(c.implied_fee_rate * 100, 'FM0.00'), to_char(c.contract_fee_rate * 100, 'FM0.00'),
                                    {{ rr_money('c.card_gross') }}, {{ rr_money('abs(c.difference)') }})
            when 'short' then format('Expected %s, received %s. Most likely a chargeback or adjustment taken out of the settlement.',
                                     {{ rr_money('c.expected_deposit') }}, {{ rr_money('c.deposit_amount') }})
            when 'over' then format('Expected %s, received %s.', {{ rr_money('c.expected_deposit') }}, {{ rr_money('c.deposit_amount') }})
            else format('%s deposited with no card sales recorded for that batch date.', {{ rr_money('c.deposit_amount') }}) end,
        'Card processor (' || case c.processor when 'PEACHPAY' then 'PeachPay' else 'TableSide Pay' end || ')',
        case c.match_status
            when 'missing'            then 'Open a ticket with the processor for the missing settlement.'
            when 'late'               then 'No correction needed. Watch for a pattern of slow settlements.'
            when 'fee_above_contract' then 'Request a refund of the overcharge and confirm the contract rate with the processor.'
            when 'short'              then 'Match it to the processor''s chargeback report; dispute it if it isn''t valid.'
            else 'Confirm the deposit with the processor before booking it.' end,
        (c.match_status = 'late'),
        c.match_status
    from {{ ref('rr_recon_card_vs_bank') }} c
    where c.match_status <> 'matched'
),

cash as (
    select
        'Cash vs. bank'::text,
        c.store_id || '|' || c.business_date,
        c.business_date, c.store_id, 'All departments'::text,
        coalesce(abs(c.difference), c.expected_cash, c.deposit_amount),
        case c.match_status when 'short' then 'Cash deposit short' when 'over' then 'Cash deposit over'
                            when 'missing' then 'Cash deposit missing' else 'Cash deposit with no sales' end,
        format('Registers recorded %s in cash (all departments, tax included); the bank received %s.',
               coalesce({{ rr_money('c.expected_cash') }}, 'nothing'), coalesce({{ rr_money('c.deposit_amount') }}, 'nothing')),
        'Store cash handling',
        'Check the drawer counts and the armored-car receipt for this day.',
        false,
        c.match_status
    from {{ ref('rr_recon_cash_vs_bank') }} c
    where c.match_status <> 'matched'
),

parts as (
    select
        'Auto parts vs. inventory'::text,
        p.wo_number || '|' || p.line_no,
        p.business_date, p.store_id, 'Auto Center'::text,
        p.amount_at_risk,
        case p.match_status
            when 'unmapped_part' then 'Part number not recognized'
            when 'not_issued'    then 'Installed part not taken out of inventory'
            else 'Inventory issued a different quantity' end,
        case p.match_status
            when 'unmapped_part' then format('Work order %s billed "%s" (%s, %s). No store SKU matches, so inventory can''t be updated.',
                                             p.wo_number, trim(p.item_code_raw), p.description, {{ rr_money('p.amount') }})
            when 'not_issued' then format('Work order %s billed %s x %s, but inventory shows no matching issue. Stock is overstated by %s at cost.',
                                          p.wo_number, p.qty_billed, p.description, {{ rr_money('p.amount_at_risk') }})
            else format('Work order %s billed %s x %s; inventory issued %s. Stock is off by %s at cost.',
                        p.wo_number, p.qty_billed, p.description, p.qty_issued, {{ rr_money('p.amount_at_risk') }}) end,
        case p.match_status when 'unmapped_part' then 'Auto center (part number entry)' else 'Auto center (parts issue)' end,
        case p.match_status
            when 'unmapped_part' then 'Correct the part number on the work order, then issue it from inventory.'
            else 'Issue the correct quantity against the work order in the inventory system.' end,
        false,
        p.match_status
    from {{ ref('rr_recon_auto_parts_vs_inventory') }} p
    where p.match_status <> 'matched'
),

product as (
    select
        'Registers vs. product master'::text,
        m.store_id || '|' || m.sku || '|' || m.week_start,
        coalesce(m.first_date_off_price, m.week_start), m.store_id, 'Retail'::text,
        case m.match_status when 'not_in_master' then m.net_sales else abs(m.price_impact) end,
        case m.match_status when 'not_in_master' then 'Item sold that isn''t in the product master'
                            else 'Registers charging an outdated price' end,
        case m.match_status
            when 'not_in_master' then format('SKU %s "%s": %s units, %s in sales, with no cost or inventory record.',
                                             m.sku, m.item_description, m.units, {{ rr_money('m.net_sales') }})
            else format('SKU %s "%s": registers charged %s; the price book says %s (%s to %s, %s units).',
                        m.sku, m.item_description, {{ rr_money('m.price_charged') }}, {{ rr_money('m.book_price') }},
                        to_char(m.first_date_off_price, 'Mon FMDD'), to_char(m.last_date_off_price, 'Mon FMDD'), m.units_off_price) end,
        case m.match_status when 'not_in_master' then 'Merchandising (item setup)' else 'Store registers (price update)' end,
        case m.match_status when 'not_in_master' then 'Set the item up in the product master with its cost and price.'
                            else 'Push the current price to the registers and confirm the change took.' end,
        false,
        m.match_status
    from {{ ref('rr_recon_product_master') }} m
    where m.match_status <> 'matched'
),

u as (
    select * from sales_gl
    union all select * from card
    union all select * from cash
    union all select * from parts
    union all select * from product
)
select
    left(md5(u.check_name || '|' || u.item_key), 12)       as exception_id,
    u.check_name,
    u.match_status                                          as exception_type,
    date_trunc('week', u.business_date)::date               as week_start,
    u.business_date,
    u.store_id,
    s.city                                                  as store,
    u.department,
    u.issue,
    u.detail,
    round(u.amount, 2)                                      as amount,
    u.likely_source,
    u.suggested_action,
    case when u.is_timing then 'Low'
         when u.match_status = 'missing' or u.amount >= 500 then 'High'
         when u.amount >= 100 then 'Medium'
         else 'Low' end                                     as severity,
    u.is_timing
from u
left join stores s on s.store_id = u.store_id
