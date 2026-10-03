-- Weekly influenza encounters per facility (and 'ALL'), with an alert
-- baseline. The baseline is the facility's mean weekly flu share during the
-- off-season (June-September) plus two standard deviations, the same idea
-- CDC uses for its ILI baseline, with a floor of 1% of visits so that a
-- handful of sporadic summer cases can't trigger an alert. A week is flagged
-- when its flu share exceeds the baseline.
with weekly as (
    select facility_id, week_start,
           count(*)                                   as total_encounters,
           count(*) filter (where is_influenza)       as flu_encounters
    from {{ ref('hc_fct_encounter') }}
    group by 1, 2
    union all
    select 'ALL', week_start, count(*), count(*) filter (where is_influenza)
    from {{ ref('hc_fct_encounter') }}
    group by 2
),
shares as (
    select *, flu_encounters::numeric / nullif(total_encounters, 0) as flu_share
    from weekly
),
baseline as (
    select facility_id,
           greatest(avg(flu_share) + 2 * coalesce(stddev_samp(flu_share), 0), 0.01) as baseline_share
    from shares
    where extract(month from week_start) between 6 and 9
    group by 1
)
select
    s.facility_id,
    s.week_start,
    s.total_encounters,
    s.flu_encounters,
    round(s.flu_share, 4)                         as flu_share,
    round(b.baseline_share, 4)                    as baseline_share,
    s.flu_share > b.baseline_share                as above_baseline,
    -- flu seasons run October through September; a week belongs to the
    -- season its Wednesday (mid-week) falls in
    case when extract(month from s.week_start + 3) >= 10
         then extract(year from s.week_start + 3)::int
         else extract(year from s.week_start + 3)::int - 1 end as season_start_year
from shares s
join baseline b using (facility_id)
