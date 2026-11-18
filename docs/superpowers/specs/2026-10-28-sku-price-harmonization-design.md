# SKU and Price Harmonization POC — Design

Date: 2026-10-28
Status: Approved by the presenter on 2026-11-08 ("for now"; may be revised).
Nothing built yet.

## Intent and why

Build a proof of concept (POC) in which one product catalog, sold through two channels, is
harmonized into a single trusted record. The channels are Shopify and the AWS
Marketplace. Over time each channel drifts: the same product ends up with
different SKUs, names and prices. Boomi Integration processes pull both
catalogs into Boomi DataHub, which matches them and produces one golden record
per product. The harmonized SKU and price flow back out to both channels.

The demo also shows what surrounds the data. MetaHub explains what the
harmonized fields mean. Elementary Data watches the harmonized data and flags
price drift and unmatched SKUs.

Boomi Companion is only the helper that builds the POC. Muse is the front end
people use to run it: it triggers a Boomi process or API that runs the
harmonization.

This is a POC of a reusable pattern, not a one-off demo. The underlying idea
is deep: pull the same entity from several systems, harmonize it through
DataHub, push the result back, govern its meaning in MetaHub, and monitor
its quality with Elementary. Product SKU and price across sales channels is
simply where it starts. The first use case is consumer packaged goods (CPG).
Manufacturing, finance and others follow, so the project is structured to
take new use cases without rework.

## Goals

- A repeatable CPG demo that runs on the presenter's machine in Docker with
  the local Atom, plus a real Shopify development store.
- One DataHub `CPG Product` model with one source per channel and one golden
  record per product.
- A visible detect-reconcile-explain beat: change a price in one channel,
  run the process, and watch it flow through DataHub, get flagged by
  Elementary, and be explained by MetaHub.
- MetaHub glossary terms associated to the DataHub model.
- Elementary reports on the harmonized data in a warehouse.
- A structure where a second vertical (manufacturing) is a new data pack plus
  a model, not a rebuild.

## Non-goals

- A real AWS Marketplace account in this iteration. The mock must be
  swappable for a real one later (see Decisions).
- Production hardening, scale, or security beyond demo level.
- Custom connectors built with the Java SDK.
- Manufacturing and finance verticals in this iteration. Only the structure
  that allows them is in scope.
- Snowflake or any cloud warehouse.

## Anti-goals

- A POC that works only once. Resetting to a clean, known state must be easy.
- A POC that depends on corporate network conditions (Zscaler) for anything
  except the calls to Boomi itself.
- Hand-rolled calls to the DataHub REST API. The `bc-datahub` skill scripts
  are the only route (see Constraints).

## Constraints

- Everything except Shopify runs in Docker. The Atom is local and already
  proven; it reaches containers at `host.docker.internal:<port>` and the
  Shopify store over the internet.
- `docker compose` (v2) is not installed. Use the hyphenated `docker-compose`.
- Mock data loads at container start. Editing it needs a service restart.
- DataHub is enabled on the account. The native DataHub connector needs hub
  credentials from the hub Configure screen, not the Boomi API token. This
  account uses the USA East hub cloud.
- Never hand-roll curl against the Hub REST API: it ignores unknown trailing
  path segments, so an undeploy call can become a repository delete.
- DataHub match rules: one rule, on a unique system ID. Initial load runs one
  source at a time and must be marked finished before any re-run.
- MetaHub is Early Access. API: JWT bearer from the Boomi auth endpoint, no
  `Accept` header on the token call, token expires in 5 minutes.
- Elementary is dbt-native: it needs a dbt project on a warehouse. DataHub is
  not a warehouse, so a Boomi export to Postgres is required.
- Boomi Map limits apply (no function chaining in a cell, no standalone map
  preview, DB V2 returns no generated keys).
- Credentials stay in `.env`, which is gitignored.

## Decisions made with the presenter

- Containers and Docker for everything.
- Local Atom, proven.
- Postgres as the warehouse (not Snowflake): the shared RDS demo database, tables in `public` prefixed `harm_` (decided 2026-11-17). A local Postgres container mirrors the tables for development and tests.
- Shopify is a real store, not a mock. The presenter can get access. It
  is a development store with sample products (confirmed by the presenter
  on 2026-11-08), which matters because the outbound step writes prices
  into it.
  The Shopify side uses a Dev Dashboard app (legacy custom apps can no
  longer be created), authenticated with its client ID and secret in `.env`
  and a 24-hour Admin API token. The Boomi connection uses the native
  Shopify connector if it supports that token, otherwise an HTTP Client
  with OAuth 2.0 client credentials. All POC products are tagged
  `harmonization-poc` so nothing else in the store is touched. Reset means re-seeding the store's products
  and prices through its API.
- AWS Marketplace is a mock for now. If the presenter gets a real account,
  swapping it in should be plug and play: the mock mirrors the real
  payload shapes, and the Boomi connection holds the base URL and auth, so
  the change is a connection edit, not a process rebuild.
- CPG is the first vertical, then manufacturing and finance.
- Boomi Companion is only the build helper. It is not part of the running
  POC.
- Muse is the runtime front end. The presenter interacts through Muse, and
  Muse triggers a Boomi process or API that runs the harmonization through
  Shopify and the rest of the flow. So the POC needs a trigger surface on
  the local Atom that Muse can call.

## My calls (to be checked)

- The AWS Marketplace mock is a small FastAPI service, in the style of the
  `credentialing` mock in the Children's project, with a seeded dataset
  containing deliberate SKU and price mismatches against the Shopify store's
  seeded products. Its endpoints and payloads follow the real AWS
  Marketplace shapes as closely as the builder can verify, so the swap to a
  real account stays small.
- The `CPG Product` model is matched on a SKU key. Because the channels use
  different SKUs, the match key is a shared canonical product identifier
  carried by both mocks (for example a GTIN/UPC), and the harmonized SKU is
  a DataHub output field. The builder should confirm this against what
  DataHub matching supports.
- Elementary runs in its own container (dbt + Elementary CLI) against the
  Postgres container and produces the HTML observability report.
- The Boomi export writes golden-record rows and source rows to Postgres
  tables that the dbt models and tests read.
- Outbound processes push the harmonized SKU and price back to each mock.
- Postgres support in Elementary is believed but not verified. Verify against
  the Elementary quickstart before building on it.
- MetaHub glossary terms for CPG: Harmonized SKU, Price Authority, Channel
  Price Variance, Canonical Product ID, and similar. The seed approach reuses
  the idempotent-by-name pattern from `metahub_seed.py` in the Children's
  project.

## Settled after review (my calls, to be checked)

- **Unmatched products.** SKUs always differ between channels. A product is
  unmatched only when one channel's GTIN is missing or malformed, so the
  seed data includes a few such products. They land in DataHub quarantine
  and Elementary flags them. If DataHub cannot match on a GTIN field, the
  fallback is a Boomi pre-match step that assigns a canonical ID.
- **Harmonized SKU.** A newly generated canonical SKU (DataHub or Boomi
  side), not either channel's existing value. The exact format is left to
  the builder.
- **Repeat runs.** One initial load per source at setup, then incremental
  updates for the demo beat. Reset covers the mocks and Postgres only.
  DataHub golden records persist. A full hub reset is a rare, separate
  operation done only through the `bc-datahub` scripts.
- **Elementary tests.** Explicit dbt tests on the seeded rows (price
  variance above a threshold between channel and golden rows, unmatched
  records, freshness, nulls). Anomaly detection with back-filled history is
  optional. If Elementary does not support Postgres, stop and ask the
  presenter rather than switching warehouse.
- **Outbound.** Pushes the golden price and a separate harmonized-SKU field
  to each mock. It does not overwrite the channel's native SKU, so the next
  inbound run cannot change match behavior. Mocks are simplified but shaped
  like the real Shopify and AWS Marketplace payloads, with a generic HTTP
  Client connector and no auth.
- **MetaHub association.** Supported. The Children's project created
  associations with `assetType: DATAHUB_MODEL`. Terms attach to the model
  as a whole.
- **Platform setup.** The plan starts with a discovery step: confirm the
  hub repository attached to the local Atom, check that no `CPG Product` model
  already exists, and build in one new folder under the target folder.

## Decided by the presenter (after review)

- **Price Authority.** Shopify wins when the channels disagree on price, as
  the merchant's system of record. The AWS Marketplace price is aligned to
  the Shopify price. DataHub source ranking puts Shopify first for price.

## Muse as the trigger (my calls, to be checked)

- A Boomi process exposed as an API on the local Atom (web services
  listener) is the single entry point Muse calls to start a run. A run
  executes inbound, DataHub load, outbound push and the Postgres export in
  order.
- Whether Muse calls that API directly or through Boomi's platform
  execute-process API is left to the builder, based on what Muse can reach.
- How Muse connects to this workspace is unconfirmed. The template has no
  mention of Muse. The builder must confirm what Muse can call and whether
  it reads this project's skills and `.env`.
- Muse supports three requests (decided by the presenter, who wants room
  to grow beyond them): run harmonization, change a Shopify price, and show
  Elementary results. Each needs a Boomi-reachable entry point. Changing a
  Shopify price is a Boomi process that updates the development store.
  Showing Elementary results returns the report location or a summary of
  the latest test results. The exact API shape is left to the builder.

## Architecture

```
Shopify mock ──┐                                  ┌─► Shopify mock (harmonized SKU/price)
               ├─► Boomi (local Atom) ─► DataHub ─┤
AWS Mkt mock ──┘        golden record per product └─► AWS Marketplace mock
                                  │
                                  └─► Boomi export ─► Postgres ─► dbt + Elementary
                                                      (golden +        (price drift,
                                                       source rows)     unmatched SKU,
                                                                        freshness, nulls)
MetaHub glossary ── associated to the DataHub CPG Product model
```

Shopify is a real development store (not a container). Containers: awsmp-mock,
postgres, elementary (dbt + CLI). In the diagram, read "Shopify mock" as the
real Shopify store.

## POC walkthrough

1. Reset to the seeded state.
2. Run inbound processes; DataHub produces golden records.
3. Show matched products and any quarantined or unmatched ones.
4. Change a price in one mock.
5. Re-run; show the new golden price pushed back to both channels.
6. Show Elementary flagging the drift or unmatched SKU.
7. Show MetaHub terms explaining Harmonized SKU and Price Authority.

## Vertical extensibility

Each vertical is a pack: seeded source data, a DataHub model, glossary terms,
and dbt tests. CPG is the first pack. The containers, Boomi export pattern,
and Elementary setup are shared. Manufacturing and finance packs are future
work and are not specified here.

## Left to the builder

- Container ports, image choices, directory layout.
- Exact Boomi process, connection, profile and map decomposition.
- The precise seeded dataset (counts, which products drift and how).
- dbt model and Elementary test selection.
- Reset mechanism (script versus compose commands).
- Names of Boomi components, within a single target folder.
