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

## Task 8 components (done 2026-11-18)
| Component | ID |
|---|---|
| HARM - Inbound AWS Marketplace (process; pages 5 per page via a loop-back Decision on DPP_NEXT_TOKEN) | `d702f13c-063a-4304-909e-b98ee421b7d3` |
| HARM - AWSMP ListEntities / DescribeEntity (REST ops) | `e12fc0e5-5f5a-422f-b47d-bd48ea7b3962` / `864d854b-4831-492d-8ba5-3ca7c8007212` |
| HARM - AWSMP ListEntities Response / DescribeEntity Response (JSON profiles) | `e429f608-9b3a-49e5-8f6d-1c323a2ac4f4` / `6e9eb001-369c-4523-ba68-2ca6089dc17f` |
| HARM - Map AWSMP to Product Batch / (No GTIN) | `4001304d-343f-4ceb-8bf4-7aa74ba4ea01` / `bde3e0b2-2e53-4c6d-bcaf-ceb7a077c1b9` |
| HARM - Map AWSMP to Source Product Row / (No GTIN) | `46382f14-ec18-4757-ab1a-a810d25daa08` / `32ddbfee-d829-49bc-b505-6b06fdf80143` |
| HARM - Source Product Upsert (No GTIN) Request (4 fields) | `8d37e179-d606-4aef-8d22-72a53b7c916b` |
| HARM - Postgres Upsert Source Product (No GTIN) (4 `?`) | `008e91f9-8e42-40e3-978e-f0e5b5a48d87` |

Verified: 12 `aws_marketplace` rows in `public.harm_source_products` (PF-0001 gtin NULL, PF-0002 gtin kept as received); DataHub 12 golden (10 with `aws_sku`), quarantine exactly 2 x REQUIRED_FIELD, drift GTINs keep the Shopify price; aws_marketplace initial load FINISHED. Why two Postgres operations: DB V2 binds `?` positionally, so a missing GTIN shifts the parameters ("No value specified for parameter 5"); a GTIN-less listing uses the 4-field operation instead.

## Task 9 components (in progress 2026-11-18)
| Component | ID |
|---|---|
| HARM - Outbound Push (process; AWS half verified, Shopify half pending) | `0926e189-7ef1-4d5a-8481-eef2bc12d779` |
| HARM - DataHub Golden Query Response (XML profile) | `67f67ea1-417b-495a-be24-a0cfc95de0dd` |
| HARM - DataHub Query CPG Products (REST op, POST `/records/query`) | `31f314c0-16df-41af-8cbf-3e093bb1c6b8` |
| HARM - AWSMP StartChangeSet (REST op) | `689f1b4b-7d74-40fa-bd48-e20b1f4c10d0` |
Verified: after a run, the 10 matched AWS listings have ListPrice = golden (Shopify) price and HarmonizedSku = CPG-<last 8 of GTIN>; the 2 unmatched are untouched. The push converges the AWS mock, so price drift only reappears after `scripts/reset.sh` or a new Shopify price change.
| HARM - Shopify Update Product (native op, Product UPDATE; created in the UI by importing, renamed from the probe) | `2f0acb30-a3eb-4434-9f13-33101e24a669` |
| Shopify Product UPDATE Request / Response (JSON profiles, from the import) | `05e04bce-4f54-404f-bafc-3331a3cc31e7` / `57c3aba2-c432-4dbe-afd0-9fbeb9aa7d5c` |

Task 9 DONE 2026-11-18. HARM - Outbound Push v2 = Branch: (1) golden query -> AWS StartChangeSet for the 10 with an aws_sku; (2) Shopify query (tag filter) -> look up the golden record by GTIN -> write product metafield `harmonization.harmonized_sku`. Shopify has no Metafield object in the connector, but Product UPDATE accepts a `metafields` array. No model change needed (the golden record has no Shopify product id, so the process starts from the Shopify product, which has it). Verified: 12 products carry the metafield = canonical SKU; SKUs, prices and tags unchanged; re-run idempotent.

## Task 10 components (done 2026-11-18)
| Component | ID |
|---|---|
| HARM - Export Golden to Postgres (process) | `70b8b157-b6cf-439b-aadb-0c9b99434b59` |
| HARM - Postgres Upsert Golden Product / (No AWS SKU) | `b2e96432-2c5d-4536-abba-0f5a38577057` / `e319334f-d3da-4466-af31-3c4f2124a68f` |
| HARM - Golden Product Upsert Request / (No AWS SKU) Request | `47357409-6898-448c-bcda-e0a86117a3bb` / `5f381a60-d134-409e-9605-8b68eb33794a` |
| HARM - Map Golden to Postgres Row / (No AWS SKU) | `bed96e70-8c11-4973-bf38-6b80354264ca` / `47ec018a-8d16-4d7e-85f4-ca5083d969e8` |
Verified: 12 rows in `public.harm_golden_products`, harmonized_sku = canonical for all, NULL aws_sku for the 2 unmatched; re-run keeps 12.

## Task 13 components (built 2026-11-18; endpoints awaiting auth to test)
| Component | ID |
|---|---|
| HARM - Muse API (API Service Component, base path `muse`, routes below `/ws/rest/muse/harmonization/`) | `ac1ad2c0-48de-4100-9163-246dcc35b844` |
| HARM - Run Harmonization (POST `runHarmonization`) | `d96fad04-17c0-45af-a317-a7fb04ece1ab` |
| HARM - Change Shopify Price API (POST `changeShopifyPrice`) | `c2ed2b97-65bf-4f99-903b-683afc992649` |
| HARM - Show Elementary Results API (GET `showElementaryResults`) | `596967b0-f95b-4ad8-ac2f-93b7497fa206` |
| WSS ops: Run / Change Price / Show Results | `b16dfd0e-a0ad-4265-961f-84753359c290` / `c02fae7a-29c1-4516-bbe9-3e00972a2ece` / `c5afbf13-1be7-4733-94d9-a1208eaddbca` |
| HARM - Change Price Request (JSON profile) | `767bc5d2-c4ca-4757-94ea-c0a0b0c1105f` |
| HARM - Elementary Run / Results (REST ops) | `01f6f854-c5c7-44cf-82d8-f487dcb69412` / `283abeb1-feff-471c-87c3-17f57c138a91` |

Runtime facts found 2026-11-18: the Atom is the Docker container `Boomi_Runtime` (boomi/atom), shared web server on container port 8078 (not published) and 9092 (published to the Mac as `localhost:9092`); `localhost:8078` on the Mac is an unrelated SSH tunnel. Requests currently return 401: the web server needs Basic credentials (`SERVER_TOKEN` in `.env` is empty). Muse is Meta's hosted agent, so it needs a public tunnel to port 9092. OpenAPI file for Muse: `docs/muse/openapi.yaml` (set the tunnel host in `servers`).

## Task 13 verified 2026-11-18 (through the public tunnel `https://shahnewapigateway.ngrok.dev` -> localhost:9092)
- runHarmonization: 200, status ok, 5 flagged (3 drift + 2 unmatched) on a fresh reset, ~68s. Two simultaneous runs: one ok, one `in_progress`.
- changeShopifyPrice: 200 for a valid price (Shopify changed, SKU and tags untouched); 400 for 0, -1, abc, 1.234, empty, 0.00; 404 for an unknown GTIN; store unchanged on errors.
- showElementaryResults: 200 with the latest summary.
- Fixes found while testing: (1) the show-results route must be GET (ASC route override httpMethod="GET", otherwise it registers as POST); (2) subprocesses started with the caller's document made the Shopify QUERY step fail with "Could not unmarshall query filter", so an empty Message step now precedes each subprocess call and the Shopify query in the price process.
- The tunnel (ngrok, domain shahnewapigateway.ngrok.dev -> 9092) was already running from an earlier project (Akima). Basic credentials for the Atom's shared web server are needed by every caller, including Muse.

## How Muse reaches the API (confirmed 2026-11-18)
Public door: `https://shahapigateway.ngrok.devsecops-prod.boomi.com` (ngrok, already running) -> `localhost:8078` = the `Boomi_Prod_Gateway` container (Boomi API Gateway) -> the Atom (`Boomi_Runtime`). `HARM - Muse API` is registered in API Management on Local_Runtime with plan "APIM Unlimited". Callers send the API Management key in the `x-api-key` header (the key is `HARM_MUSE_API_KEY` in `.env`; never commit or paste it). Without the key the gateway answers 401. Paths: `/ws/rest/muse/harmonization/runHarmonization` (POST), `.../changeShopifyPrice` (POST), `.../showElementaryResults` (GET). OpenAPI for Muse: `docs/muse/openapi.yaml`. Direct access to the Atom (`localhost:9092`, tunnel `shahnewapigateway.ngrok.dev`) needs Basic credentials instead; Muse should use the gateway.
Known gap: the `report_url` in responses is `http://localhost:4121/report`, which Muse (hosted) cannot open.

## showGlossary (added 2026-11-18)
| Component | ID |
|---|---|
| HARM - Show Glossary API (listener process, GET `showGlossary`) | `08679f36-5926-4a7f-9471-7524a5e7aff6` |
| HARM - WSS Show Glossary (listener op) | `a0b89f92-3a36-4b11-993c-6d3b8278a43d` |
| HARM - Elementary Glossary (REST op, GET `/glossary` on the runner) | `bd93e36e-4ea4-44c5-9e2e-5dda8e3ac6cb` |
`HARM - Muse API` is now v3 with a fourth route. The runner's `GET /glossary` reads MetaHub (JWT from the Boomi API token; associations for the CPG Product model, then each term's content). Verified through the public gateway: 200, 4 terms with definitions.

Results now include `details` (price_drift with GTIN, name, channel price, golden price, percent gap; unmatched_listings) from `analytics/runner/details.py`. Verified through the public gateway after a run: 3 drifts (10.03, 8.35, 8.34 percent) and 2 unmatched listings.
