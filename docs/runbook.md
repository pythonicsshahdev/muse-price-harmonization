# Runbook: SKU and price harmonization POC

A reusable pattern for harmonizing product SKUs and prices across channels. CPG is the first
vertical. Shopify (a real dev store) and AWS Marketplace (a mock) are harmonized in Boomi Data Hub
by Boomi Integration processes, checked by dbt and Elementary, and driven from Muse.

Boomi Companion built this. It is not part of the running system. At run time: **Muse -> API
gateway -> Boomi Atom -> Shopify / AWS mock / Data Hub / Postgres (RDS) -> dbt + Elementary**.

## Start of day (about 5 minutes)

1. Start Docker Desktop. Containers restart on their own (`restart: unless-stopped`). Check:
   `cd mock-sources && docker-compose --env-file ../.env ps` shows `awsmp`, `elementary`, `postgres` up.
   If not: `docker-compose --env-file ../.env up -d` (never `--remove-orphans`; another project shares the folder name).
2. The Atom is the container `Boomi_Runtime`; the API gateway is `Boomi_Prod_Gateway`. Both must be up (`docker ps`).
3. Tunnel for Muse: `ngrok http 8078 --domain=shahapigateway.ngrok.devsecops-prod.boomi.com` must be running
   (it forwards to the gateway). Check: `curl -s -o /dev/null -w '%{http_code}\n' https://shahapigateway.ngrok.devsecops-prod.boomi.com/ws/rest/muse/harmonization/showElementaryResults` prints **401** (up and protected).
4. `bash scripts/reset.sh` (see below).

## The four requests Muse can make

The Muse connector is "Boomi Harmonization", built from `docs/muse/openapi.yaml`. Every call sends the
API Management key in the `x-api-key` header (`HARM_MUSE_API_KEY` in `.env`; never paste or commit it).

| Say to Muse | Endpoint | What happens |
|---|---|---|
| "Run the harmonization" | `POST /ws/rest/muse/harmonization/runHarmonization` | Loads Shopify and AWS into Data Hub, pushes the golden price and SKU back, exports to Postgres, runs the dbt/Elementary checks. 60 to 70 seconds. A second run at the same time answers `in_progress`. |
| "Change the price of <product> to 9.99" | `POST .../changeShopifyPrice` `{"gtin","price"}` | Sets the Shopify price by GTIN. 400 for a price that is not a positive number with at most 2 decimals; 404 for an unknown GTIN. Only products tagged `harmonization-poc` are touched. |
| "What did the data-quality checks find?" | `GET .../showElementaryResults` | The latest summary: checks passed, records flagged, which checks failed. |
| "What does Price Authority mean?" | `GET .../showGlossary` | The four endorsed MetaHub terms with plain-text definitions, read live from MetaHub (via the runner's `/glossary`). |

Demo beat: reset, run (5 flagged: 3 price drifts + 2 unmatched listings), change one Shopify price,
run again (the AWS listing follows Shopify; drift for that product shows once), show the results.

## Reset between runs

`bash scripts/reset.sh` (about 6 seconds, exits non-zero on failure). It restarts the AWS mock (seed
prices and GTINs), restores the POC products' seed prices in Shopify, empties the two `harm_*`
warehouse tables, and restarts the Elementary runner so "show results" says no run yet. It does not
touch Data Hub (the next run recomputes it) or any other table in the shared database.

## Where to look

| What | Where |
|---|---|
| **Elementary report (visual)** | open `http://localhost:4121/report` in a browser, after at least one run. Lineage, test results, anomalies. |
| Latest summary as JSON | `curl localhost:4121/results` |
| Golden records and quarantine | Boomi Data Hub UI, model `cpgproduct`, repository `enterprise-data-hub`; or `bash $DH/datahub-quarantine.sh query --universe df443425-d048-44ab-9482-a7cc903b3b3c` (after `source scripts/skill-paths.sh`) |
| Harmonized SKU and price terms | MetaHub UI (Glossaries page), four endorsed terms associated to the CPG Product model; Muse reads them with `showGlossary`; `curl localhost:4121/glossary` |
| Warehouse tables | RDS database `postgresdemo`, `public.harm_source_products` (one row per channel listing), `public.harm_golden_products`; Elementary in schema `harm_elementary`, dbt models in `harm` |
| Boomi components | folder `boomi_shah_abdullah/Sku Harmonization POC`, all named `HARM - ...`; IDs in `docs/platform-ids.md` |

## Ports and names

| Port | What |
|---|---|
| 4120 | AWS Marketplace mock (`awsmp`) |
| 4121 | dbt + Elementary runner (`elementary`): `/run`, `/results`, `/report`, `/health` |
| 5442 | local Postgres (development and tests only; the demo uses RDS) |
| 8078 | Boomi API gateway (public via ngrok) |
| 9092 | the Atom's own web server (needs Basic credentials; used for debugging) |

Ports 4020, 4040, 4041, 5433 and 5434 are used by other things on this Mac (SSH tunnel, ngrok).

## Known quirks (learned the hard way)

- **Positional binding:** the Database V2 connector binds `?` by position. A missing field shifts the
  parameters, so the "no GTIN" and "no AWS SKU" cases use separate 4- and 6-field operations. Never re-sort a request profile.
- **Initial load:** each Data Hub source needs enable, load, finish, one source at a time. Never re-run an
  inbound process while a source is mid-load (creates POSSIBLE_DUPLICATE entries).
- **Quarantine:** a missing or malformed GTIN is sent without a GTIN so Data Hub quarantines it as REQUIRED_FIELD.
  Data Hub rules have no length or regex test, so the 13-digit check lives in the AWS process.
- **Source ranking:** Shopify is ranked first for price (Data Hub model, Sources tab, Rank Sources). Keep `<mdm:sourceRankings>` if the model is ever updated through the API.
- **QUERY steps parse their input document as a filter.** A process called as a subprocess gets an empty
  document first (`Start with an empty document`); do not remove those Message steps.
- **Routes:** the show-results route must be GET; the other two are POST. Listener and API component
  must both be deployed. After changing a listener, redeploy `HARM - Muse API` too.
- **Shopify:** the dev store is shared. Only products tagged `harmonization-poc` are changed. The native
  connector's token comes from the OAuth tab (Generate); if it expires, Regenerate on `HARM - Shopify Connection`.
- **After a run the AWS mock matches Shopify,** so price drift only reappears after a reset or a new Shopify price change.
- **`report_url` in responses is a localhost address;** Muse, being hosted, cannot open it.
- The golden-record export, source rows and Elementary tests run against the shared RDS database. Tables are
  prefixed `harm_`. Never alter other tables there.

## Adding a vertical (manufacturing, finance, ...)

1. Copy `seed/packs/cpg/` to `seed/packs/<vertical>/` and edit `products.json` (the canonical dataset with deliberate
   mismatches) and `glossary.json` (MetaHub terms).
2. Create a new Data Hub model for the vertical (new model and source IDs; keep one match rule on the business key).
3. Add dbt tests for that vertical's rules in `analytics/` (the generic `price_within_tolerance` and `no_rows` tests are reusable).
4. Reuse as they are: the Docker mocks and runner, the Postgres export pattern, the inbound/outbound process shapes
   (clone the `HARM - ...` processes and swap the profiles and maps), the Muse API pattern and `scripts/reset.sh`.
5. Run `python3 seed/metahub_seed.py --pack <vertical> --universe <model id>` for the glossary.
