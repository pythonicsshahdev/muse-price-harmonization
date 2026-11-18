select
    golden_id,
    gtin,
    harmonized_sku,
    name,
    price,
    shopify_sku,
    aws_sku,
    updated_at
from {{ source('warehouse', 'harm_golden_products') }}
