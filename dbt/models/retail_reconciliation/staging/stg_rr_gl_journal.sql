-- Journal lines with store and department attached. Revenue is the credit side of the revenue accounts.
select
    x.store_id,
    to_date(g.posting_date, 'YYYYMMDD')     as posting_date,
    trim(g.account)                         as account,
    a.department,
    coalesce(a.is_revenue, false)           as is_revenue,
    trim(g.description)                     as description,
    g.debit::numeric(12, 2)                 as debit,
    g.credit::numeric(12, 2)                as credit,
    g.credit::numeric(12, 2) - g.debit::numeric(12, 2) as net_credit,
    upper(trim(g.source))                   as source
from {{ source('raw_retail_reconciliation', 'gl_journal') }} g
left join {{ ref('rr_store_xref') }} x on x.gl_entity = trim(g.entity)
left join {{ ref('rr_gl_accounts') }} a on a.account = trim(g.account)
