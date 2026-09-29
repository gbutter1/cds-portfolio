-- Singular test: if more than 2% of source rows are rejected, something is
-- wrong upstream (a bad extract, a calendar not loaded) and the run should fail.
select sum(pct_of_rows) as rejected_pct
from {{ ref('attendance_data_quality') }}
where dq_status <> 'valid'
having sum(pct_of_rows) > 2
