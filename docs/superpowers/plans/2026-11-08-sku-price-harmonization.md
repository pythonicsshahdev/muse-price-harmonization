# SKU and Price Harmonization POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker-based CPG proof of concept in which Muse triggers Boomi processes that harmonize Shopify and AWS Marketplace SKUs and prices through DataHub, with MetaHub terms and Elementary monitoring.

**Architecture:** A local Atom runs Boomi processes. Inbound processes load a real Shopify development store and an AWS Marketplace mock into one DataHub `CPG Product` model matched on GTIN. Outbound processes push the golden price and harmonized SKU back to both channels. Golden and source rows land in a Postgres container where dbt and Elementary test them. Three WSS-listener processes are the entry points Muse calls.

**Tech Stack:** Boomi Integration (boomi-integration and bc-datahub skill scripts), Boomi DataHub, MetaHub REST API, Python 3 + FastAPI + pytest, Docker (`docker-compose`, hyphenated), Postgres 16, dbt-postgres, Elementary.

**Spec:** `docs/superpowers/specs/2026-10-28-sku-price-harmonization-design.md`

## Global Constraints

- Use hyphenated `docker-compose`; `docker compose` (v2) is not installed.
- Compose project name is `harmonization-poc` (top-level `name:`). Never rely on the folder name: the Children's project also has a `mock-sources` folder, and Compose would treat the two as one project and flag its containers as orphans. Never use `--remove-orphans`.
- Host ports 4020, 4040, 4041, 5433 and 5434 are taken on the presenter's machine (SSH tunnel, ngrok); check with `lsof -nP -iTCP:<port> -sTCP:LISTEN` before choosing any new port.
- The Atom is local and reaches containers at `host.docker.internal:<port>`. Ports (plan's call): AWS mock 4120, Elementary runner 4121, Postgres 5442.
- Never call the DataHub REST API with hand-rolled curl. Use the `bc-datahub` scripts (`datahub-*.sh`); a bad path can delete a repository.
- DataHub: one match rule, on `gtin`. Initial load one source at a time; run `finish-initial-load` before the next source or any re-run.
- DataHub native connector and `datahub-*.sh` need hub credentials (`DATAHUB_REPO_URI`, `DATAHUB_REPO_USERNAME`, `DATAHUB_REPO_AUTH_TOKEN`), not the Boomi API token. USA East hub cloud.
- MetaHub: base `https://metahub.boomi.com/metahub`; JWT from `GET https://api.boomi.com/auth/jwt/generate/{accountId}` with basic auth and no `Accept` header; refresh every 4 minutes (tokens last 5).
- Boomi Map limits: no function chaining in a cell (compute upstream in Set Properties and read via DDP); no standalone map preview (test through a process); DB V2 returns no generated keys.
- Remove `branchId` from pulled XML before deploying.
- Credentials live only in `.env` (gitignored). Boomi components all go in one new folder, `SKU Harmonization POC`, named with the prefix `HARM - `.
- No Groovy unless a Map genuinely cannot do the transformation.
- Harmonized SKU rule (plan's call): `"CPG-" + last 8 digits of GTIN`.
- Shopify wins on price. Native channel SKUs are never overwritten.

## Review Focus

1. Initial load re-run before `finish-initial-load` creates POSSIBLE_DUPLICATE quarantine entries (Task 7, Task 8 verify none appear).
2. Muse price change with `0`, a negative, a non-number, or more than 2 decimals must return HTTP 400 and leave the store unchanged (Task 3, Task 13).
3. AWS mock list calls with multiple pages, an exact page boundary, and an empty list must all load correctly (Task 2, Task 8).
4. A second `runHarmonization` call while one is running must return a clear "run in progress" answer, not interleave two runs (Task 11, Task 13).
5. Missing `.env` keys or a Shopify 429 must fail with a message naming the key or honoring `Retry-After`, never a bare stack trace (Task 3).

---

### Task 0: Foundation and discovery

**Files:**
- Modify: `.env` (not committed)
- Create: `docs/platform-ids.md`

**Interfaces:**
- Produces: `docs/platform-ids.md` with the headings `Repository ID`, `Folder ID`, `Universe ID`, `Environment ID`, `Muse entry point`. Later tasks read IDs from it.

- [ ] **Step 1: Locate the script directories.** In a shell: `BI=$(ls -d ~/.claude/plugins/cache/boomi-companion/bc-integration/*/skills/boomi-integration/scripts | sort -V | tail -1)` and `DH=$(ls -d ~/.claude/plugins/cache/boomi-companion/bc-datahub/*/skills/boomi-datahub/scripts | sort -V | tail -1)`. All later `bash $BI/...` and `bash $DH/...` commands assume these.
- [ ] **Step 2: Add keys to `.env`:** `DATAHUB_REPO_URI`, `DATAHUB_REPO_USERNAME`, `DATAHUB_REPO_AUTH_TOKEN` (hub Configure screen, Copy buttons), `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_API_VERSION`, `POSTGRES_HOST=host.docker.internal`, `POSTGRES_PORT=5442`, `POSTGRES_DB=harmonization`, `POSTGRES_USER=harm`, `POSTGRES_PASSWORD` (local container), and `RDS_POSTGRES_JDBC_URL`, `RDS_POSTGRES_USERNAME`, `RDS_POSTGRES_PASSWORD` (shared RDS demo warehouse, the one the Boomi processes and the Elementary runner use).
- [ ] **Step 3: Verify the environment.** Run `bash $BI/boomi-env-check.sh` and `bash $DH/datahub-env-check.sh`. Expected: required Boomi keys SET; Platform API reachable; Repository API live check passes.
- [ ] **Step 4: Discovery.** `bash $DH/datahub-repository.sh list` and identify the repository attached to the local Atom; `bash $DH/datahub-model.sh list --name "CPG Product"`. Expected: no existing `CPG Product` model. If one exists, stop and ask the presenter.
- [ ] **Step 5: Create the folder.** `bash $BI/boomi-folder-create.sh "SKU Harmonization POC"`; set `BOOMI_TARGET_FOLDER` in `.env` to the new folder ID. Run `bash $BI/boomi-folder-list.sh` to confirm.
- [ ] **Step 6: Record IDs** in `docs/platform-ids.md`. Under `Muse entry point`, write what the presenter says Muse can call (URL and auth), or `UNCONFIRMED`. Task 13 is blocked on this line only.
- [ ] **Step 7: Commit** `docs/platform-ids.md` (`git add docs/platform-ids.md && git commit -m "docs: record platform IDs"`).

### Task 1: Canonical dataset and oracle

**Files:**
- Create: `seed/packs/cpg/products.json`, `seed/packs/cpg/glossary.json`, `seed/dataset.py`, `seed/tests/test_dataset.py`, `requirements-dev.txt`, `pytest.ini`

**Interfaces:**
- Produces in `seed/dataset.py`:
  - `@dataclass(frozen=True) class Product: gtin: str; name: str; brand: str; shopify_sku: str; shopify_price: Decimal; aws_sku: str; aws_name: str; aws_price: Decimal; aws_gtin: str | None`
  - `load_products(pack: str = "cpg") -> list[Product]` (reads `seed/packs/cpg/products.json`; a new vertical is a new folder under `seed/packs/`)
  - `canonical_sku(gtin: str, prefix: str = "CPG") -> str`
  - `expected_matched(products) -> list[str]` (GTINs), `expected_unmatched(products) -> list[str]` (AWS SKUs), `expected_price_drift(products) -> list[str]` (GTINs)

- [ ] **Step 1: Write failing tests** in `seed/tests/test_dataset.py`: `test_twelve_products_unique_gtins` (12 products, all `gtin` 13 digits and unique, shopify_sku values unique), `test_canonical_sku_rule` (`canonical_sku("0012345678905") == "CPG-45678905"`), `test_canonical_sku_unique_across_products`, `test_expected_matched_is_ten`, `test_expected_unmatched_is_two_aws_skus` (one product with `aws_gtin=None`, one with a 12-digit `aws_gtin`), `test_expected_price_drift_is_three` (matched products whose aws_price != shopify_price), `test_two_products_have_name_variants` (aws_name != name).
- [ ] **Step 2: Run** `python3 -m pytest seed/tests/test_dataset.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `seed/dataset.py` and write `seed/packs/cpg/products.json` with 12 invented CPG products (beverages, snacks, household), prices with two decimals, shaped to the counts above. `requirements-dev.txt`: `pytest`, `fastapi`, `httpx`, `requests`, `responses`, `uvicorn`. `pytest.ini`: `testpaths = seed mock-sources analytics`.
- [ ] **Step 4: Run** the same command. Expected: 7 passed.
- [ ] **Step 5: Commit** (`git add seed requirements-dev.txt pytest.ini && git commit -m "feat: canonical CPG dataset and oracle"`).

### Task 2: AWS Marketplace mock

**Files:**
- Create: `mock-sources/awsmp/main.py`, `mock-sources/awsmp/Dockerfile`, `mock-sources/awsmp/requirements.txt`, `mock-sources/awsmp/tests/test_main.py`, `mock-sources/docker-compose.yml`, `docs/awsmp-api-notes.md`

**Interfaces:**
- Consumes: `seed/packs/cpg/products.json` (mounted read-only at `/app/data/products.json`)
- Produces (mock mirrors the AWS Marketplace Catalog API operation names; `Details` is the mock's own JSON string because the real shape varies by product type):
  - `POST /ListEntities` body `{"Catalog": str, "EntityType": str, "MaxResults": int, "NextToken": str | null}` → `{"EntitySummaryList": [{"EntityId", "Name", "EntityType", "LastModifiedDate"}], "NextToken": str | null}`
  - `GET /DescribeEntity?catalog=AWSMarketplace&entityId=<id>` → `{"EntityType", "EntityIdentifier", "EntityArn", "LastModifiedDate", "Details": "<json string with Sku, Gtin, ListPrice, HarmonizedSku>", "DetailsDocument": {...}}` (verified against the real API on 2026-11-12; see `docs/awsmp-api-notes.md`)
  - `POST /StartChangeSet` body `{"Catalog", "ChangeSet": [{"ChangeType": "UpdateInformation", "Entity": {"Identifier": str}, "Details": "<json string>"}]}` → `{"ChangeSetId": str}`; the next DescribeEntity reflects the change
  - `POST /admin/reset` (mock only) restores seed state; `GET /health`

- [ ] **Step 1: Verify real shapes.** Read the AWS Marketplace Catalog API reference for `ListEntities`, `DescribeEntity`, `StartChangeSet`; record the real field names and any deviations in `docs/awsmp-api-notes.md`. Adjust the Interfaces above to match before writing tests.
- [ ] **Step 2: Write failing tests** with FastAPI `TestClient`: `test_health`, `test_list_returns_all_twelve_with_large_page`, `test_list_pages_of_five_cover_all_without_duplicates` (pages 5/5/2, final `NextToken` null), `test_list_exact_boundary_page_of_twelve_has_no_next_token`, `test_describe_returns_sku_gtin_price` (GET with query parameters), `test_missing_gtin_product_has_null_gtin`, `test_start_change_set_updates_price_and_harmonized_sku`, `test_describe_unknown_entity_is_404`, `test_reset_restores_seed`.
- [ ] **Step 3: Run** `python3 -m pytest mock-sources/awsmp -v`. Expected: FAIL.
- [ ] **Step 4: Implement** `main.py` (data loaded at import from `/app/data/products.json`, path overridable by env `PRODUCTS_PATH` for tests), Dockerfile, and a compose service `awsmp` on `4120:4020` with the data volume and `restart: unless-stopped`.
- [ ] **Step 5: Run** the tests. Expected: 14 passed. Then `cd mock-sources && docker-compose up -d awsmp && curl -s localhost:4120/health`. Expected: `{"status":"ok"}`.
- [ ] **Step 6: Commit.**

### Task 3: Shopify development store seeding

**Files:**
- Create: `seed/shopify_seed.py`, `seed/tests/test_shopify_seed.py`

**Interfaces:**
- Consumes: `seed.dataset.load_products`
- Auth: Shopify no longer allows new legacy custom apps (since 2026-01-01). The app is created in the Dev Dashboard and gets a 24-hour Admin API token by `POST https://{shop}.myshopify.com/admin/oauth/access_token` (form body `grant_type=client_credentials`, `client_id`, `client_secret`); it works only when the app and the store are in the same Shopify organization.
- Safety: the store may be shared. Every product this code creates carries the tag `harmonization-poc`, and `reset_store`, `set_price` and `check_store` only ever touch tagged products.
- Produces (Admin REST API; GTIN lives in the variant `barcode`, channel SKU in `sku`):
  - `get_token() -> str` (cached; refreshed 60 seconds before `expires_in`)
  - `seed_store(products: list[Product]) -> int` (idempotent by barcode; returns count of products present)
  - `reset_store(products: list[Product]) -> None` (restores seeded name and price, leaves other fields)
  - `set_price(gtin: str, price: Decimal) -> None` (raises `ValueError` for price <= 0 or more than 2 decimals; `LookupError` if gtin unknown)
  - `check_store(products) -> dict` with keys `count`, `prices_match_seed`
  - CLI: `python3 seed/shopify_seed.py seed|reset|check`

- [ ] **Step 1: Verify** the current stable Admin API version and set `SHOPIFY_API_VERSION` in `.env`.
- [ ] **Step 2: Write failing tests** with the `responses` library: `test_seed_is_idempotent_by_barcode` (second run issues no POSTs), `test_set_price_rejects_zero_negative_and_three_decimals`, `test_set_price_unknown_gtin_raises_lookup_error`, `test_retries_on_429_honoring_retry_after` (assert sleep called with the header value), `test_missing_env_key_names_the_key` (error text contains `SHOPIFY_CLIENT_SECRET`), `test_token_cached_and_refreshed_before_expiry`, `test_never_modifies_untagged_products` (a product with a matching barcode but no `harmonization-poc` tag is left alone), `test_reset_restores_seed_price`.
- [ ] **Step 3: Run** `python3 -m pytest seed/tests/test_shopify_seed.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement** `seed/shopify_seed.py` using `requests`; read credentials from `.env` without printing them.
- [ ] **Step 5: Run** the tests. Expected: 6 passed. Then live: `python3 seed/shopify_seed.py seed && python3 seed/shopify_seed.py check`. Expected: `count` 12, `prices_match_seed` true. Confirm in the Shopify admin that the products show.
- [ ] **Step 6: Commit.**

### Task 4: Postgres warehouse

**Files:**
- Create: `mock-sources/postgres/init/01_schema.sql`
- Modify: `mock-sources/docker-compose.yml`

**Interfaces:**
- Produces tables in `public` (shared RDS warehouse; local container mirrors them):
  - `public.harm_source_products(source text, source_key text, gtin text null, name text, price numeric(10,2), loaded_at timestamptz default now(), primary key (source, source_key))`
  - `public.harm_golden_products(golden_id text primary key, gtin text unique not null, harmonized_sku text, name text, price numeric(10,2), shopify_sku text null, aws_sku text null, updated_at timestamptz default now())`

- [ ] **Step 1: Add** a compose service `postgres` (`postgres:16`, `5442:5432`, db `harmonization`, user `harm`, password from `.env`, init dir mounted, named volume).
- [ ] **Step 2: Write the schema SQL** above.
- [ ] **Step 3: Verify.** `docker-compose up -d postgres`, then `docker-compose exec postgres psql -U harm -d harmonization -c "\dt public.harm_*"`. Expected: both tables listed. Insert and delete one row in each table to confirm the constraints (a duplicate `(source, source_key)` insert fails).
- [ ] **Step 4: Commit.**

### Task 5: DataHub `CPG Product` model and sources

**Files:**
- Create: `active-development/mdm.model/cpg_product.xml`, `active-development/mdm.source/shopify.xml`, `active-development/mdm.source/aws_marketplace.xml`
- Modify: `docs/platform-ids.md`

**Interfaces:**
- Produces: model `CPG Product` (batch element `cpgproduct`) with fields `gtin` (required, match field, 13 digits), `harmonized_sku`, `name`, `brand`, `price` (decimal), `shopify_sku`, `aws_sku`; sources `shopify` and `aws_marketplace` (the `src` values in batch XML); universe ID (equals model ID after deploy) recorded in `docs/platform-ids.md`.

- [x] **Step 1: Read** the `bc-datahub` skill's `references/` for the model and source XML shapes, match rules, source ranking and data quality steps.
- [x] **Step 2: Create the sources** with `bash $DH/datahub-source.sh create <file>`; then author `cpg_product.xml` with exactly one match rule on `gtin`, `gtin` required, a data quality step rejecting any `gtin` that is not 13 digits, and source ranking with `shopify` first for `price`.
- [x] **Step 3: Create, publish, deploy.** `datahub-model.sh create active-development/mdm.model/cpg_product.xml`; `datahub-model.sh publish <model-id> --notes "initial"`; `datahub-deployment.sh deploy <model-id> <repository-id> --version <v>`.
- [x] **Step 4: Verify.** `datahub-model.sh list --name "CPG Product"` shows the model published; `datahub-deployment.sh list` shows the universe. Record the universe ID.
- [ ] **Step 5: Commit** the XML and `docs/platform-ids.md`.

### Task 6: Boomi connections

**Files:**
- Create in `active-development/connections/`: Shopify connection, AWSMP HTTP connection, Postgres DB V2 connection, Elementary runner HTTP connection, DataHub REST connection

**Interfaces:**
- Produces components (all in folder `SKU Harmonization POC`): `HARM - Shopify Connection` (native Shopify connector if it supports the 24-hour client-credentials token, otherwise an HTTP Client connection with OAuth 2.0 client credentials against `https://{shop}.myshopify.com/admin/oauth/access_token`), `HARM - AWSMP Connection` (HTTP Client, `http://host.docker.internal:4120`), `HARM - Postgres Connection` (DB V2, `host.docker.internal:5442`, db `harmonization`), `HARM - Elementary Runner Connection` (HTTP Client, `http://host.docker.internal:4121`), `HARM - DataHub REST Connection` (from `datahub-connection.sh bootstrap rest`; paths must start with `/mdm/`). Component IDs recorded in `docs/platform-ids.md`.

- [x] **Step 1: Create the DataHub REST connection:** `bash $DH/datahub-connection.sh bootstrap rest "HARM - DataHub REST Connection" <folder-id>`; note the printed ID.
- [x] **Step 2: Build the other four** with the boomi-integration skill (read its connection references first); push with `bash $BI/boomi-component-create.sh <file>`. Put hostnames and credentials in environment extensions, not the component.
- [x] **Step 3: Verify.** `bash $BI/boomi-component-search.sh` for the folder lists all five names. Execute the connection check each connector offers (or defer to the first process in Task 7).
- [ ] **Step 4: Commit** the XML and IDs.

### Task 7: Inbound Shopify process

**Files:**
- Create in `active-development/`: Shopify operation and profiles, `HARM - Map Shopify to Product Batch`, process `HARM - Inbound Shopify`, query file `active-development/feedback/queries/all-products.xml`

**Interfaces:**
- Consumes: `HARM - Shopify Connection`, `HARM - DataHub REST Connection`, `HARM - Postgres Connection`; universe ID.
- Produces: process `HARM - Inbound Shopify` that reads products, computes `harmonized_sku` in a Set Properties step (DDP) per the rule in Global Constraints, branches to (a) map to batch XML with `src="shopify"` and POST to `/mdm/universes/{universeId}/records?returnApplicationErrors=true`, and (b) an upsert into `public.harm_source_products` with `source='shopify'`, `source_key` = variant SKU, `gtin` = barcode.

- [x] **Step 1: Build the components** and push; no Groovy.
- [x] **Step 2: Enable initial load:** `bash $DH/datahub-source.sh enable-initial-load --repository <repo> --universe <uid> shopify`.
- [x] **Step 3: Run once:** `bash $BI/boomi-test-execute.sh --process-id <id>`. Expected: execution COMPLETE; 12 documents posted.
- [x] **Step 4: Verify.** `bash $DH/datahub-quarantine.sh query --universe <uid>` returns no entries; `datahub-golden-record.sh query --universe <uid> active-development/feedback/queries/all-products.xml` returns 12 records with `harmonized_sku` matching `canonical_sku` for each GTIN; `public.harm_source_products` has 12 `shopify` rows.
- [x] **Step 5: Finish initial load:** `datahub-source.sh finish-initial-load ...`. Do not re-run the process before this returns. Verify `status` shows INITIAL_LOAD_FINISHED.
- [x] **Step 6: Commit.**

### Task 8: Inbound AWS Marketplace process

**Files:**
- Create in `active-development/`: HTTP operations for ListEntities and DescribeEntity, profiles, `HARM - Map AWSMP to Product Batch`, process `HARM - Inbound AWS Marketplace`

**Interfaces:**
- Consumes: `HARM - AWSMP Connection`, Task 7 conventions.
- Produces: process that pages `ListEntities` until `NextToken` is null (handles an empty list), describes each entity, computes `harmonized_sku` (skipped when GTIN is missing or malformed so the record quarantines), posts with `src="aws_marketplace"`, and upserts `public.harm_source_products` with `source='aws_marketplace'`, `source_key` = AWS SKU.

- [x] **Step 1: Build and push** the components.
- [x] **Step 2: Enable initial load** for `aws_marketplace` (only after Task 7 Step 5 finished).
- [x] **Step 3: Run once.** Expected: COMPLETE.
- [x] **Step 4: Verify.** Quarantine query returns exactly 2 entries, both REQUIRED_FIELD (a missing GTIN, and a malformed one that the process sends without a GTIN) and none with cause POSSIBLE_DUPLICATE; golden query returns 12 records, 10 with `aws_sku` set; for the 3 drift GTINs the golden `price` equals the Shopify price (Shopify ranked first). `public.harm_source_products` has 12 `aws_marketplace` rows.
- [x] **Step 5: Finish initial load.**
- [x] **Step 6: Commit.**

### Task 9: Outbound push process

**Files:**
- Create in `active-development/`: golden-record query operation, Shopify update operation(s), AWS StartChangeSet operation, map(s), process `HARM - Outbound Push`

**Interfaces:**
- Consumes: golden records via `HARM - DataHub REST Connection`.
- Produces: process that, per golden record, updates the AWS listing price and `HarmonizedSku` through `StartChangeSet`, and writes `harmonized_sku` to Shopify as a variant or product metafield (use the native connector if it supports metafields; otherwise a generic HTTP Client against the Admin API using the same token). It never changes a channel's native SKU.

- [x] **Step 1: Build and push.**
- [x] **Step 2: Run:** `bash $BI/boomi-test-execute.sh --process-id <id>`. Expected: COMPLETE.
- [x] **Step 3: Verify.** `GET localhost:4120/DescribeEntity?catalog=AWSMarketplace&entityId=<aws sku>` for each drift GTIN's entity shows `ListPrice` equal to the Shopify price and a `HarmonizedSku`; `python3 seed/shopify_seed.py check` still reports 12 products with seed prices and unchanged SKUs.
- [x] **Step 4: Commit.**

### Task 10: Golden export to Postgres

**Files:**
- Create in `active-development/`: DB V2 upsert operation, map, process `HARM - Export Golden to Postgres`

**Interfaces:**
- Produces: process that queries golden records and upserts each into `public.harm_golden_products` (`ON CONFLICT (gtin) DO UPDATE`), setting `shopify_sku` and `aws_sku` from the record's channel fields. Source rows are already written by Tasks 7 and 8.

- [x] **Step 1: Build and push.**
- [x] **Step 2: Run, then verify** `select count(*) from public.harm_golden_products` is 12 and `harmonized_sku` equals `canonical_sku(gtin)` for every row. Run again and confirm the count is still 12.
- [x] **Step 3: Commit.**

### Task 11: dbt, Elementary and runner

**Files:**
- Create: `analytics/dbt_project.yml`, `analytics/profiles.yml`, `analytics/packages.yml`, `analytics/models/staging/stg_source_products.sql`, `analytics/models/staging/stg_golden_products.sql`, `analytics/models/marts/fct_price_variance.sql`, `analytics/models/marts/fct_unmatched_products.sql`, `analytics/models/schema.yml`, `analytics/tests/generic/price_within_tolerance.sql`, `analytics/runner/app.py`, `analytics/runner/tests/test_app.py`, `analytics/Dockerfile`
- Modify: `mock-sources/docker-compose.yml`

**Interfaces:**
- Produces: runner (FastAPI, port 4121) with `POST /run` → `{"status": "ok"|"failed", "tests_passed": int, "tests_failed": int, "report_url": str}` (HTTP 409 `{"status": "in_progress"}` if a run is active), `GET /results` → latest summary JSON, `GET /report` → Elementary HTML report.

- [x] **Step 1: Verify Postgres support** (verified 2026-11-17) against the Elementary quickstart (`docs.elementary-data.com/oss/quickstart`) and the Elementary adapter list. If Postgres is unsupported, stop and ask the presenter; do not switch warehouse.
- [ ] **Step 2: Write failing runner tests** with `subprocess.run` patched: `test_run_returns_counts_from_dbt_output`, `test_second_run_while_active_returns_409`, `test_results_before_any_run_is_404_with_message`, `test_report_serves_html_when_present`.
- [ ] **Step 3: Run** `python3 -m pytest analytics/runner -v`. Expected: FAIL; then implement `app.py` (a lock around `dbt run`, `dbt test`, `edr report`). Expected after: 4 passed.
- [ ] **Step 4: Build the dbt project.** `price_within_tolerance` takes `tolerance_pct` and compares each channel price to the golden price; `fct_unmatched_products` lists `aws_marketplace` source rows whose `source_key` is not any golden `aws_sku`; add `not_null`/`unique` tests on golden `gtin` and an Elementary freshness test on `loaded_at`.
- [ ] **Step 5: Add** the `elementary` compose service (Dockerfile installs dbt-postgres and elementary, runs the runner) on `4121:4121`.
- [ ] **Step 6: Verify on seed data.** With Tasks 7 to 10 complete, `curl -X POST localhost:4121/run`. Expected: `price_within_tolerance` fails for exactly 3 GTINs and the unmatched-products test fails for exactly 2 rows; `GET /report` returns HTML. Also confirm the Elementary results table name in Postgres (record it in `docs/platform-ids.md` for Task 13).
- [ ] **Step 7: Commit.**

### Task 12: MetaHub glossary

**Files:**
- Create: `seed/metahub_seed.py`, `seed/tests/test_metahub_seed.py` (terms are read from `seed/packs/<pack>/glossary.json`, a list of `{name, purpose, content_html}`)

**Interfaces:**
- Produces: `ensure_glossary(name: str, purpose: str, content_html: str, endorse: bool) -> str` (returns glossary ID; idempotent by name), `associate(glossary_id: str, universe_id: str) -> None` (`assetType: DATAHUB_MODEL`), `get_token() -> str` (refreshes on a 4-minute clock). Terms: Harmonized SKU, Price Authority, Channel Price Variance, Canonical Product ID.

- [x] **Step 1: Write failing tests** with `responses`: `test_ensure_glossary_reuses_existing_name`, `test_token_refreshes_after_four_minutes` (patched clock), `test_re_endorse_409_is_ignored`, `test_token_request_sends_no_accept_header`.
- [x] **Step 2: Run** `python3 -m pytest seed/tests/test_metahub_seed.py -v`. Expected: FAIL; implement, adapting the pattern in `Childrens - Datahub_Healthcare_Usecase /active-development/feedback/metahub_seed.py`. Expected after: 4 passed.
- [x] **Step 3: Run live** `python3 seed/metahub_seed.py` twice. Expected: second run creates nothing new. Confirm four ENDORSED terms associated to the `CPG Product` model in the MetaHub UI.
- [ ] **Step 4: Commit.**

### Task 13: Muse trigger APIs

**Files:**
- Create in `active-development/`: WSS operations and processes `HARM - Run Harmonization`, `HARM - Change Shopify Price API`, `HARM - Show Elementary Results API`

**Interfaces:**
- Produces (listener paths): `POST /ws/simple/runHarmonization` → `{"status": "ok"|"in_progress"|"failed", "tests_failed": int, "report_url": str}`; `POST /ws/simple/changeShopifyPrice` body `{"gtin": str, "price": str}` → 200 `{"gtin", "price"}` or 400 `{"error": str}`; `GET /ws/simple/showElementaryResults` → `{"tests_passed": int, "tests_failed": int, "failing": [str], "report_url": str}`.
- `HARM - Run Harmonization` calls, in order (Branch step, sequential): Inbound Shopify, Inbound AWS Marketplace, Outbound Push, Export Golden to Postgres, then `POST /run` on the runner; a 409 from the runner becomes `"status": "in_progress"`.

- [ ] **Step 1: Build and push** the three processes; deploy them and every process they call with `bash $BI/boomi-deploy.sh <file>`.
- [ ] **Step 2: Verify run.** `bash $BI/boomi-wss-test.sh --path /ws/simple/runHarmonization --data '{}'`. Expected: `"status":"ok"` and `tests_failed` of 5 (3 price plus 2 unmatched, on seed data).
- [ ] **Step 3: Verify price change.** `--path /ws/simple/changeShopifyPrice --data '{"gtin":"<seeded gtin>","price":"9.99"}'`. Expected: 200, and `python3 seed/shopify_seed.py check` reports the changed price. Then send prices `0`, `-1`, `abc`, `1.234`. Expected: each 400 and the store unchanged.
- [ ] **Step 4: Verify results.** `--path /ws/simple/showElementaryResults --method GET`. Expected: counts matching the last run.
- [ ] **Step 5: Verify concurrency.** Fire two `runHarmonization` calls at once. Expected: one `ok`, one `in_progress`.
- [ ] **Step 6: Register with Muse.** Using the entry point recorded in Task 0, register the three endpoints and ask Muse for each request in plain language; confirm each returns the expected result. If `Muse entry point` is still `UNCONFIRMED`, stop and ask the presenter.
- [ ] **Step 7: Commit.**

### Task 14: Reset, end-to-end walkthrough and runbook

**Files:**
- Create: `scripts/reset.sh`, `docs/runbook.md`

**Interfaces:**
- Produces: `scripts/reset.sh` that restarts `awsmp` (`docker-compose restart awsmp`), runs `python3 seed/shopify_seed.py reset`, truncates `public.harm_source_products` and `public.harm_golden_products`, and exits non-zero on any failure. DataHub golden records are not reset.

- [ ] **Step 1: Write** `scripts/reset.sh` and run it; expected exit 0.
- [ ] **Step 2: Walk the spec's flow from Muse:** reset; run harmonization; show matched and quarantined products; change one Shopify price; run again; confirm the AWS Marketplace price follows; show Elementary results; open the MetaHub terms.
- [ ] **Step 3: Write** `docs/runbook.md`: start commands, ports, the reset command, the three Muse requests, the known quirks from Global Constraints, and a short "Adding a vertical" section (new folder under `seed/packs/` with `products.json` and `glossary.json`, a new DataHub model, new dbt tests; containers and Boomi export pattern are reused).
- [ ] **Step 4: Update memory** note `project_sku_price_harmonization_demo.md` with built component names and IDs.
- [ ] **Step 5: Commit.**
