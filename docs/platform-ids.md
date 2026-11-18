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

## MetaHub (Task 12, 2026-11-17)
Four ENDORSED business glossary terms (Harmonized SKU, Price Authority, Channel Price Variance, Canonical Product ID),
all associated to the CPG Product model (asset id `1b92cb0c-1210-4ca5-bec4-ab2b79590c3b`, external id = universe id).
`python3 seed/metahub_seed.py` is idempotent (second run: 0 new associations). The associations list answers under
the key `associations`, not `data`.

## Boomi connections (Task 6, 2026-11-17), folder `Sku Harmonization POC`
| Component | ID | Notes |
|---|---|---|
| HARM - DataHub REST Connection | `4d1eed8d-a76f-48a2-bafb-ed084da5c8a2` | from `datahub-connection.sh bootstrap rest`; paths start with `/mdm/` |
| HARM - AWSMP Connection | `bdb7bfb9-968b-478c-980c-aa9d3fa8a307` | REST, no auth, `http://host.docker.internal:4120` |
| HARM - Elementary Runner Connection | `770b6955-e530-4a4b-bac0-f6fba23bd56c` | REST, no auth, `http://host.docker.internal:4121` |
| HARM - Postgres Connection | `2cfb95ba-e422-47cc-8f11-78158250bb88` | Database V2 to the shared RDS (not the local container); password to be entered in the UI |
| HARM - Shopify Connection | `aab59412-0881-4d60-b43f-b1d086d6f002` | native Shopify connector, OAuth 2.0 authorization code (created in the UI; app URL host set to platform.boomi.com) |

## Task 7 components (in progress)
| Component | ID |
|---|---|
| HARM - DataHub CPG Product Batch XML Profile | `10abde49-c279-440c-b3bf-e8a068d6a6b3` |
| HARM - DataHub Post CPG Product Batch (REST op, POST `/mdm/universes/<universe>/records?returnApplicationErrors=true`, XML) | `1785f14c-d6f1-41f5-809a-1b58f1e9d8c5` |
| HARM - Shopify Query Products (native op, QUERY Product, API 2024-04) | `80144b08-5ab0-486e-bb15-7b47ed7a7bee` |
| Shopify Product QUERY Response (JSON profile, generated by the import) | `9f52eea8-7131-499a-90d0-2dcba022808d` |
| HARM - Probe Shopify Query (temporary probe process, delete at end of Task 7) | `2c0e066d-bee9-4810-ab41-95e79a6d2e53` |

Shopify op notes: by default the response omits product `title`, `vendor`, `status` (they are filter-only in the import); fixed by setting selectable/selected=true on those ConnectorFields and pushing the op (v2). `tags` is not filterable: filter for `harmonization-poc` in the process. Variants carry `sku`, `barcode`, `price` (all 12 POC products are single-variant). The shared store returns 31 products in total.
| HARM - Harmonized SKU (UDF: LeftTrim 8 + concat `CPG-`) | `b09466fa-3019-423b-bb33-404a9921bcb8` |
| HARM - Map Shopify to Product Batch | `fd014690-ce09-4b4b-9e2b-78cc45984008` |
| HARM - Inbound Shopify (process, v2: DataHub branch + Postgres branch) | `cbaf668d-0135-48f3-8cc4-593ac0eb9bfb` |
| HARM - Source Product Upsert Request / Response (JSON profiles; request field order = SQL `?` order, never re-sort) | `25c667dd-7d0e-437a-bec0-dc12bc8327ea` / `0eda0deb-e07b-40a3-b385-e9ea1f3eabe9` |
| HARM - Postgres Upsert Source Product (DB V2 Standard Insert + ON CONFLICT) | `04c50e22-4b54-436d-b398-d5cfb0c48c69` |
| HARM - Map Shopify to Source Product Row | `bf6bd6dd-ac56-4b8f-9fc7-86d474a4f696` |

Task 7 DataHub half verified 2026-11-17: 12 `shopify` records posted, 12 golden, 0 quarantine, all match the oracle; shopify initial load FINISHED. Postgres branch verified too: 12 `shopify` rows in `public.harm_source_products` match the oracle; re-run is idempotent. The probe process (`2c0e066d...`) is undeployed; delete it in the UI.
