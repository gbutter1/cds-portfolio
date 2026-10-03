-- Exception amounts are dollars at risk: never negative, never missing.
select exception_id, check_name, amount
from {{ ref('rr_exceptions') }}
where amount is null or amount < 0
