# Platform IDs

None of these are secrets. Credentials live only in `.env`.

## Repository ID
`1828d39c-1f0a-4c1b-ba05-5dbf51c6f7c3` (name `enterprise-data-hub`, USA East Hub Cloud 02,
`https://c02-usa-east.hub.boomi.com`). Shared with other POCs: 8 deployed universes. Do not
modify universes this project did not create.

## Environment ID
`5ad3daf5-de1d-4c5b-bd34-993544796267` (`Local_Runtime`). Other environments: Test
`7e958f51-4b90-4d0d-8e66-7afec3967901`, Production `ce7c388e-330a-498a-9851-bd24c40476c7`.

## Folder ID
`Rjo4OTczNjc5` = `boomi_shah_abdullah/Sku Harmonization POC` (set as `BOOMI_TARGET_FOLDER`). Process names are prefixed `HARM - `.

## Universe ID
`df443425-d048-44ab-9482-a7cc903b3b3c` (= model id; deployed 2026-11-17 to repository `enterprise-data-hub` `1828d39c-1f0a-4c1b-ba05-5dbf51c6f7c3`, 0 records). The model name is `CPG Product` (confirmed 2026-11-17; batch element `cpgproduct`), not `Product`: a model with that name already exists
(`b2d57b23-f6af-425b-8a88-f7a0a2cbb674`, 300 golden records, belongs to an earlier project).

## Muse entry point
UNCONFIRMED. Needed for Task 13: what URL and auth Muse can call.

## Shopify
Store `boomi-demo-store.myshopify.com` (shared demo store). App `SKU Harmonization POC`
(Dev Dashboard, custom distribution). POC products are tagged `harmonization-poc`.

## Local containers (project `harmonization-poc`)
AWS Marketplace mock: host port 4120. Postgres: host port 5442. Elementary runner: host port 4121 (Task 11).

## Warehouse (decided 2026-11-17)
Shared RDS Postgres 16 (`RDS_POSTGRES_*` in `.env`, db `postgresdemo`). Our tables live in `public`
with a `harm_` prefix: `harm_source_products`, `harm_golden_products`. The `public` schema and
others hold other teams' tables: never alter or drop anything not prefixed `harm_`. dbt/Elementary
objects go in their own schemas. The local container (port 5442, db `harmonization`) mirrors the
same tables and is for development and tests only.

## Analytics runner (Task 11, built 2026-11-17)
`elementary` compose service on host port 4121 (container 4021): `POST /run`, `GET /results`, `GET /report`, `GET /health`.
`WAREHOUSE=rds` (default) uses the RDS keys; `WAREHOUSE=local` uses the local container.
dbt models in schema `harm`; Elementary in `harm_elementary`. Results table for Task 13:
`harm_elementary.elementary_test_results`. Elementary 0.26.1 (pip and dbt package). Tests:
`price_drift_between_channels`, `unmatched_aws_listings`, golden `gtin` not_null/unique, freshness on `loaded_at`.
`tests_failed` counts flagged rows (3 drifts + 2 unmatched = 5 on seed data), not test count.
Verified locally on seed-derived rows (3 passed, 5 flagged) and against RDS with empty tables (5 passed).

## DataHub model and sources (Task 5, in progress 2026-11-17)
Sources created: `shopify`, `aws_marketplace`. Model created as a DRAFT: id `df443425-d048-44ab-9482-a7cc903b3b3c`,
stored name `cpgproduct` (the API rejected "CPG Product" as an invalid name, so it was created as `CPGProduct`; the
platform lowercases it, so the batch element is `cpgproduct` as planned). PUBLISHED and DEPLOYED (deployed version `08ec1185-4cf4-4f82-aaab-98ca4ce4dc6f`). Sources `shopify` and `aws_marketplace` are attached with state CREATED: each needs the initial-load lifecycle (`datahub-source.sh enable-initial-load` → upsert → `finish-initial-load`, one source at a time) before its first batch upsert. Source ranking: `price` has shopify rank 1; GTIN, BRAND, HARMONIZEDSKU, SHOPIFYSKU still aws first (harmless). Ranking lives in the model XML as `<mdm:sourceRankings>`: keep it when updating the model through the API.
