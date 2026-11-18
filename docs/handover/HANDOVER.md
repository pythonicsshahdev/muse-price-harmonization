# Handover: SKU and Price Harmonization POC

Status as of 2026-11-18. Built between 2026-10-28 and 2026-11-18 by Shah Abdullah with Boomi
Companion (Claude Code). All 15 plan tasks are done and verified; the work is committed on branch
`sku-price-harmonization-poc` (not pushed, no pull request).

This document explains what the POC is, how it works, why it was built the way it was, what is
known to be fragile, and how to run it. For rebuilding it on another machine see
`REPLICATION_GUIDE.md`. For day-to-day operation see `../runbook.md`. Boomi component IDs are in
`../platform-ids.md`.

---

## 1. What this is

A proof of concept for a **reusable harmonization pattern**: pull the same business entity from
several systems, match and merge it in Boomi Data Hub into one golden record, push the harmonized
result back to every system, explain what the fields mean in MetaHub, and watch data quality with
dbt and Elementary. A person drives the whole thing in plain language from **Muse** (an AI
assistant app).

The first use case is **consumer packaged goods (CPG): product SKU and price across two sales
channels**.

- **Shopify** is a real development store (the demo store is shared with other people).
- **AWS Marketplace** is a mock (a small FastAPI service) that follows the real Marketplace
  Catalog API shapes, so a real account could replace it by editing one Boomi connection.

Boomi Companion (Claude Code) *built* this. It is **not part of the running system**. At run time
the chain is:

```
Muse  ->  public tunnel  ->  Boomi API Gateway  ->  Boomi Atom (local, Docker)
                                                      |-> Shopify dev store (native Boomi connector)
                                                      |-> AWS Marketplace mock (REST)
                                                      |-> Boomi Data Hub (golden records)
                                                      |-> Postgres warehouse (RDS)  -> dbt + Elementary
```

### The demo story (what you show)

1. "Run the harmonization." Boomi loads both catalogs into Data Hub. Products match on GTIN into one
   golden record each. The harmonized SKU (`CPG-` + last 8 digits of the GTIN) and the winning price
   (Shopify wins) are pushed back to both channels. Two AWS listings have a missing or malformed
   GTIN, so Data Hub quarantines them. dbt and Elementary then flag **5 things**: 3 price drifts
   between channels and 2 unmatched AWS listings.
2. "Change the price of the Cold Brew Coffee to 9.99." Only Shopify changes.
3. "Run the harmonization" again. The new price flows through Data Hub and the AWS listing follows.
4. "What did the data-quality checks find?" Muse reads the Elementary summary. The visual report
   is at `http://localhost:4121/report`.
5. In MetaHub, four endorsed glossary terms explain Harmonized SKU, Price Authority, Channel Price
   Variance and Canonical Product ID.

---

## 2. Architecture and where everything lives

| Piece | What it is | Where / port |
|---|---|---|
| Boomi Atom | Local runtime in Docker, container `Boomi_Runtime` (boomi/atom) | web server 9092 on the Mac |
| Boomi API Gateway | Container `Boomi_Prod_Gateway` (boomi/gateway) | 8078 |
| Public tunnel for Muse | ngrok, forwards a reserved domain to the gateway | `ngrok http 8078 --domain=<your reserved domain>` |
| AWS Marketplace mock | FastAPI, container `harmonization-poc-awsmp-1` | 4120 (container 4020) |
| dbt + Elementary runner | FastAPI + dbt + Elementary 0.26.1, container `harmonization-poc-elementary-1` | 4121 (container 4021) |
| Local Postgres | Development and tests only | 5442 |
| Warehouse (demo) | A shared cloud Postgres 16 (RDS); tables in `public` prefixed `harm_` | env `RDS_POSTGRES_*` |
| Shopify | Development store `boomi-demo-store` (shared); POC products tagged `harmonization-poc` | Dev Dashboard app "SKU Harmonization POC" |
| Data Hub | Model `cpgproduct` deployed to repository `enterprise-data-hub` | universe id = model id (see `platform-ids.md`) |
| MetaHub | Four endorsed glossary terms associated to the model | `seed/metahub_seed.py` |
| Boomi folder | `boomi_shah_abdullah/Sku Harmonization POC`, every component named `HARM - ...` | |

Docker Compose project name is `harmonization-poc`. Never use `--remove-orphans` (another project
has a folder with the same name and Compose would treat its containers as orphans).

### Repository map

```
active-development/    Boomi component XML (processes, connections, operations, profiles, maps,
                       the API Service Component, Data Hub model and source XML)
analytics/             dbt project, Elementary config, FastAPI runner, Dockerfile, entrypoint
docs/                  spec, plan, runbook, platform-ids, handover, diagrams, OpenAPI for Muse
mock-sources/          docker-compose.yml, AWS mock (awsmp), Postgres init SQL
scripts/               reset.sh, skill-paths.sh (locates the Boomi skill scripts)
seed/                  canonical dataset (packs/cpg), Shopify seed, MetaHub seed, tests
```

56 automated tests pass (`python3 -m pytest`): the dataset oracle, the Shopify seed, the AWS mock,
the runner, and the MetaHub seed.

---

## 3. The data model and rules

**Data Hub model `cpgproduct`** (display name "CPG Product"; the API rejected a name with a space, so it
was created as `CPGProduct` and the platform lowercases it).

| Field | Type | Notes |
|---|---|---|
| `gtin` | string(13), required | the only match key (one match rule) |
| `harmonized_sku` | string | `CPG-` + last 8 digits of the GTIN |
| `name`, `brand` | string | |
| `price` | float | Shopify ranked first (source ranking, per field) |
| `shopify_sku`, `aws_sku` | string | each channel's native SKU is never overwritten |

Sources: `shopify` (default) and `aws_marketplace`. Source ranking puts Shopify first for price, name
and `aws_sku`; the ranking lives in the model XML as `<mdm:sourceRankings>`.

**Quarantine rule.** Data Hub business rules have no length or regex test, so the "exactly 13 digits"
check lives in the AWS process. A missing or malformed GTIN is sent **without** a GTIN, so Data Hub
quarantines the record with cause `REQUIRED_FIELD`. On the seed data that is exactly two entries
(`AWSMP-PF-0001` has no GTIN; `AWSMP-PF-0002` has a 12-digit one).

**Harmonized SKU** is computed in a user-defined function (`HARM - Harmonized SKU`: Left Character
Trim to 8, then String Concat with `CPG-`). No Groovy anywhere.

**Warehouse tables** (`public`, shared database, prefix `harm_`):

- `harm_source_products(source, source_key, gtin, name, price, loaded_at)` primary key (source, source_key);
  one row per channel listing, written by the two inbound processes.
- `harm_golden_products(golden_id, gtin, harmonized_sku, name, price, shopify_sku, aws_sku, updated_at)`;
  one row per golden record, written by the export process.

**dbt and Elementary** (`analytics/`): staging views over the two tables; marts `fct_price_variance`
(each channel listing against the golden price) and `fct_unmatched_products` (AWS listings no golden
record claims). Tests: `price_within_tolerance` (named `price_drift_between_channels`, 1 percent),
`no_rows` (named `unmatched_aws_listings`), `not_null` and `unique` on the golden GTIN, and an
Elementary freshness check. The runner reports `tests_failed` as the **number of flagged rows**, not
the number of failed tests, so seed data gives 5 (3 drifts + 2 unmatched). dbt models are in schema
`harm`, Elementary in `harm_elementary`.

**MetaHub terms** (`seed/packs/cpg/glossary.json`): Harmonized SKU, Price Authority, Channel Price
Variance, Canonical Product ID. `seed/metahub_seed.py` is idempotent.

---

## 4. The Boomi processes

All in folder `Sku Harmonization POC`. Seven processes:

| Process | What it does |
|---|---|
| `HARM - Inbound Shopify` | Queries Shopify (31 products in the shared store), keeps the 12 tagged `harmonization-poc`, then branches: (1) map to a Data Hub batch and POST it, (2) upsert a row in `harm_source_products`. |
| `HARM - Inbound AWS Marketplace` | Loops over `ListEntities` (5 per page, so 5+5+2) using a loop-back decision on the next-page token; describes each entity; if the GTIN is 13 digits sends a full batch, otherwise a batch without GTIN; upserts the source row (a separate 4-field operation when there is no GTIN). |
| `HARM - Outbound Push` | Two paths. AWS: for each golden record with an AWS listing, `StartChangeSet` with the golden price and harmonized SKU. Shopify: for each tagged product, look up the golden record by GTIN and write the product metafield `harmonization.harmonized_sku`. Native SKUs and prices are never changed. |
| `HARM - Export Golden to Postgres` | Upserts each golden record into `harm_golden_products` (6-field operation when there is no AWS SKU). |
| `HARM - Run Harmonization` | Listener. Runs the four processes above in order (Branch, sequential), then `POST /run` on the Elementary runner. A 409 from the runner becomes `status: in_progress`. |
| `HARM - Change Shopify Price API` | Listener. Validates the price (positive, at most 2 decimals), checks the GTIN exists in Data Hub, finds the product in Shopify, updates the variant price. 400 for a bad price, 404 for an unknown GTIN. |
| `HARM - Show Elementary Results API` | Listener. Returns the runner's latest summary. |

Plus the API Service Component `HARM - Muse API` (base path `muse`) that publishes the three listeners at
`/ws/rest/muse/harmonization/runHarmonization` (POST), `.../changeShopifyPrice` (POST) and
`.../showElementaryResults` (GET).

Other components: five connections (Shopify native, AWS mock, DataHub REST, Postgres on RDS, Elementary
runner), REST/DB V2/native operations, JSON and XML profiles, maps, the UDF. See `platform-ids.md`.

---

## 5. How Muse is connected

- Muse has a connector named **Boomi Harmonization**, created from `docs/muse/openapi.yaml`.
- The API is registered in Boomi **API Management** on Local_Runtime under a plan ("APIM Unlimited").
  Callers send the plan's API key in the **`x-api-key`** header. The key is stored as
  `HARM_MUSE_API_KEY` in `.env`; it must never be pasted into chat or committed.
- The public path is an ngrok reserved domain forwarding to the gateway container (port 8078). Without the
  key the gateway answers 401.
- Direct access to the Atom's own web server (port 9092) needs Basic credentials instead and is used
  for debugging only.
- Muse asks the user to allow access to the site for each action ("Allow once" or "Always allow this
  site"; "always" covers every subdomain of the domain).

---

## 6. Decisions and why

| Decision | Reason |
|---|---|
| Model named "CPG Product" (created as `CPGProduct`) | A model named `Product` already existed in the shared repository (earlier project, 300 records); never touched. |
| Warehouse = shared RDS Postgres, tables `harm_*` in `public` | The user supplied it; reachable by the Atom without Docker networking tricks; more convincing than a laptop container. The local Postgres remains for development and tests. A cloud MySQL idea was raised and withdrawn. |
| Postgres, not Snowflake | Elementary supports Postgres (verified); no extra account needed. |
| Shopify wins on price | Real store is the system of record; AWS is aligned to it. Implemented with Data Hub source ranking. |
| Harmonized SKU is a separate field | Never overwrites a channel's native SKU. In Shopify it is a metafield. |
| Shopify metafield written via Product UPDATE | The native connector has no Metafield object, but Product UPDATE accepts a `metafields` array. |
| Outbound Shopify path starts from the Shopify product | The golden record has no Shopify product id; the Shopify product does. Avoids changing the deployed model. |
| Two Postgres operations for missing GTIN / AWS SKU | The Database V2 connector binds `?` positionally; a missing field shifts the parameters. |
| Native Shopify connector with OAuth authorization code | Legacy custom apps can no longer be created. The Dev Dashboard app's App URL host had to be set to `platform.boomi.com` and the Boomi callback added as a redirect URL. |
| API Management key via gateway for Muse | Muse is a hosted client and needs a public, authenticated door. |
| Runbook, reset script, 56 tests | The POC must be repeatable; resetting must be easy. |

---

## 7. Verification evidence (2026-11-18)

- Data Hub: 12 golden records, 10 with an `aws_sku`, quarantine exactly 2 (both `REQUIRED_FIELD`), no
  `POSSIBLE_DUPLICATE`; for the 3 drift GTINs the golden price equals the Shopify price.
- Postgres: 12 `shopify` + 12 `aws_marketplace` source rows and 12 golden rows, all matching the oracle in
  `seed/dataset.py`; every process is idempotent (re-run keeps the counts).
- Shopify: all 12 tagged products carry the metafield; SKUs, prices and tags unchanged.
- AWS mock: after a run, the 10 matched listings carry the golden price and harmonized SKU.
- API through the public gateway: `runHarmonization` 200 in about 65 seconds, `ok`, 5 flagged; two
  simultaneous runs gave one `ok` and one `in_progress`; `changeShopifyPrice` valid price changes
  Shopify, prices `0`, `-1`, `abc`, `1.234`, empty and `0.00` return 400, an unknown GTIN returns 404;
  results 200; no key returns 401.
- Full walkthrough from `scripts/reset.sh`: run (5 flagged), price to 9.99, run (AWS follows, 3 flagged),
  results.
- Muse verified the connector by calling the results action and then asked to run the harmonization.

---

## 8. Known fragile points and lessons

- **Database V2 positional binding.** Never re-sort a request profile; field order must match the SQL `?` order.
- **QUERY steps parse their input document as a filter.** Subprocesses get an empty document first
  (Message steps named "Start with an empty document"). Removing them breaks the Shopify query with
  "Could not unmarshall query filter".
- **Initial load.** Each Data Hub source: enable, load once, finish, one source at a time. Re-running an
  inbound process mid-load creates duplicates.
- **Shopify native operation import.** The import omits product `title`, `vendor` and `status` from the
  response; they were switched on by editing the operation field list (selectable and selected).
- **API Service Component.** The show-results route must be explicitly GET (otherwise it registers as POST and
  returns 404). After changing a listener process, redeploy the API component too. The Atom's API tier
  must be `advanced`.
- **`.env` password quoting.** A password containing shell characters must be single-quoted, or `source .env` breaks.
- **Concurrency guard** is only at the final step (the runner returns 409 while a test run is active). Two
  runs at once both execute the earlier idempotent steps.
- **Shared resources.** The Shopify store, the Data Hub repository and the RDS database are shared with
  other people. Only `harmonization-poc` products, the `cpgproduct` model and `harm_*` tables are ours.
- **`report_url`** in responses is a `localhost` address; hosted Muse cannot open it.
- **After a run the AWS mock matches Shopify**, so the drift only reappears after `scripts/reset.sh` or a new
  Shopify price change.

---

## 9. Open items and next steps

1. Delete the leftover probe processes in the Boomi UI (`HARM - Probe Shopify Query`; the probe
   Shopify operation was renamed and is in use).
2. Decide whether to push the branch and open a pull request; nothing has been pushed.
3. Optional: expose the Elementary report through the gateway so Muse can link to it.
4. Optional: a dedicated web-server user for direct Atom access; rotate the API key if it was ever shared.
5. Replace the AWS mock with a real Marketplace account (needs SigV4 signing on the connection).
6. Add the second vertical (manufacturing): see "Adding a vertical" in the runbook.

---

## 10. Security notes

- Credentials live only in `.env` (git-ignored): Boomi API token, Data Hub repository token, Shopify client
  secret, RDS password, the API Management key. None of them appears in the repository; a scan for the
  current values was run before each commit.
- The Muse endpoints can change a Shopify price and trigger runs. They are protected by the API key at the
  gateway. Treat the key like a password and rotate it if exposed.
- The ngrok tunnel is public. Stop it when not demonstrating.
- The shared Shopify store and RDS database are touched only in the ways listed above.
