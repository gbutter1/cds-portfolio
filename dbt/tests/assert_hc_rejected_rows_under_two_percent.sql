-- Fail the run if more than 2% of encounter rows are rejected.
select sum(pct_of_rows) as rejected_pct
from {{ ref('hc_data_quality') }}
where dq_status <> 'valid'
having sum(pct_of_rows) > 2
