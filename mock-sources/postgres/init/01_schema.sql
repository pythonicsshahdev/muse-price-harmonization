-- Warehouse tables the Boomi processes write and dbt/Elementary read.
-- Lives in the public schema with a harm_ prefix: the demo warehouse is a shared
-- RDS database, so the prefix keeps these apart from other teams' tables.

-- One row per channel listing, written by the two inbound processes.
create table if not exists public.harm_source_products (
    source      text        not null,           -- 'shopify' or 'aws_marketplace'
    source_key  text        not null,           -- channel SKU
    gtin        text,                           -- null when the channel has none
    name        text,
    price       numeric(10,2),
    loaded_at   timestamptz not null default now(),
    primary key (source, source_key)
);

-- One row per golden record, written by the export process.
create table if not exists public.harm_golden_products (
    golden_id       text primary key,
    gtin            text not null unique,
    harmonized_sku  text,
    name            text,
    price           numeric(10,2),
    shopify_sku     text,
    aws_sku         text,
    updated_at      timestamptz not null default now()
);
