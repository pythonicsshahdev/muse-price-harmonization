-- One row per channel listing that matched a golden record, with how far its
-- price sits from the golden price. Listings with no usable GTIN never join,
-- so they show up in fct_unmatched_products instead.
select
    g.gtin,
    s.source,
    s.source_key,
    s.price as channel_price,
    g.price as golden_price,
    round((s.price - g.price) / nullif(g.price, 0) * 100, 2) as variance_pct
from {{ ref('stg_source_products') }} s
join {{ ref('stg_golden_products') }} g on g.gtin = s.gtin
