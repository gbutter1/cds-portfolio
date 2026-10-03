-- Top 10 diagnoses per facility per month (all ages), with the prior month's
-- count and change. 'ALL' is the whole system. Ties are broken by code so
-- the ranking is stable.
with monthly as (
    select facility_id, month_start, icd10_code, count(*) as encounters
    from {{ ref('hc_fct_encounter') }}
    group by 1, 2, 3
    union all
    select 'ALL', month_start, icd10_code, count(*)
    from {{ ref('hc_fct_encounter') }}
    group by 2, 3
),
with_prior as (
    select
        m.*,
        lag(encounters) over (partition by facility_id, icd10_code order by month_start) as prior_month_encounters,
        lag(month_start) over (partition by facility_id, icd10_code order by month_start) as prior_month_start,
        sum(encounters) over (partition by facility_id, month_start)                     as facility_month_total,
        row_number() over (partition by facility_id, month_start
                           order by encounters desc, icd10_code)                         as dx_rank
    from monthly m
)
select
    facility_id,
    month_start,
    dx_rank,
    icd10_code,
    encounters,
    round(encounters::numeric / facility_month_total, 4)                   as share_of_visits,
    -- only compare to the immediately preceding month
    case when prior_month_start = (month_start - interval '1 month')::date
         then prior_month_encounters end                                   as prior_month_encounters,
    case when prior_month_start = (month_start - interval '1 month')::date and prior_month_encounters > 0
         then round((encounters - prior_month_encounters)::numeric / prior_month_encounters, 4) end
                                                                           as pct_change_vs_prior
from with_prior
where dx_rank <= 10
