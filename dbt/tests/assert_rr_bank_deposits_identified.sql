-- Every card and cash deposit on the bank statement must be traced to a store and a batch date.
-- A row here means a bank description format changed or a merchant ID is missing from the crosswalk.
select bank_line_id, post_date, description, amount
from {{ ref('stg_rr_bank_transactions') }}
where processor <> 'OTHER'
  and (store_id is null or batch_date is null)
