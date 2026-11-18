select
    source,
    source_key,
    gtin,
    name,
    price,
    loaded_at
from {{ source('warehouse', 'harm_source_products') }}
