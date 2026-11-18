-- AWS Marketplace listings that no golden record claims: their GTIN is missing
-- or malformed, so they quarantined in DataHub instead of matching.
select
    s.source_key,
    s.gtin,
    s.name,
    s.price
from {{ ref('stg_source_products') }} s
where s.source = 'aws_marketplace'
  and s.source_key not in (select aws_sku from {{ ref('stg_golden_products') }} where aws_sku is not null)
