# Replication guide: rebuild the SKU and price harmonization POC on your own machine

For someone who has the repository but not the original Boomi account, Shopify store or machine.
Read `HANDOVER.md` first for what the POC is. Budget one to two working days the first time,
mostly for account set-up and the few steps that can only be done in the Boomi and Shopify screens.

**Method.** The repository holds the Boomi component XML as a working reference, but those files
contain IDs that belong to the original Boomi account (folder, connections, profiles, maps,
universe). Do **not** push them as they are. Rebuild the components in your account with Boomi
Companion (Claude Code), using the XML as templates. Where a step is UI-only, this guide says so.

---

## 0. What you need

**Accounts and products**

| Need | Why | Notes |
|---|---|---|
| Boomi Integration account | build and run the processes | API token (Settings > AtomSphere API Tokens) |
| A Local Runtime (Atom) in Docker | runs the processes | the original uses the `boomi/atom` image, container `Boomi_Runtime`, web server port 9092 published |
| Boomi Data Hub with a repository | golden records | note the repository URL, username and token from the hub Configure screen |
| Boomi MetaHub access | business glossary | Early Access feature; ask your Boomi contact |
| Boomi API Management plus a gateway | key-protected public API for Muse | the original runs the `boomi/gateway` container on 8078. Alternative without it: expose the Atom (port 9092) through a tunnel and use Basic auth (steps 8 and 9) |
| Shopify Partner organisation | a development store and a Dev Dashboard app | legacy custom apps can no longer be created |
| Muse | the front end | the AI assistant app; it must be able to import an OpenAPI file or add an API connector |
| ngrok account | a reserved domain for the public tunnel | free plans give one static domain |
| A Postgres 16 database | warehouse | a cloud one or the local container (step 3) |

**On your machine:** Docker Desktop with `docker-compose` (hyphenated, v1 syntax), Python 3.9 or newer, Git,
ngrok, a text editor, and **Claude Code with the Boomi Companion plugins** (`bc-integration`, `bc-datahub`;
optional `bc-marketplace`). Boomi Companion's own set-up guide (`/bc-integration:env-setup-guide`) walks through
the Boomi part of `.env`.

---

## 1. Get the code and configure `.env`

```bash
git clone <repo-url> harmonization-poc && cd harmonization-poc
git checkout sku-price-harmonization-poc
cp .env.example .env              # then fill it in as you go; .env is git-ignored
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q              # expect 66 passed (all offline, no accounts needed)
```

Fill `.env` in the order of this guide. Check what Boomi Companion can see with
`source scripts/skill-paths.sh && bash $BI/boomi-env-check.sh` (prints which keys are set, never their values).
Never paste secrets into a chat, and single-quote any value containing shell characters.

---

## 2. Local services in Docker

```bash
cd mock-sources
docker-compose --env-file ../.env up -d --build
docker-compose --env-file ../.env ps         # awsmp, elementary, postgres up
curl localhost:4120/health                   # {"status":"ok"}
```

- Compose project name is `harmonization-poc`. Never use `--remove-orphans`.
- `elementary` needs a warehouse. Until step 3 is done it will start but fail on `POST /run`.
- Ports used: 4120 (AWS mock), 4121 (runner), 5442 (local Postgres). If a port is taken, change the left side of
  the mapping in `mock-sources/docker-compose.yml` and everything that mentions it (connections, docs).

---

## 3. Warehouse

Pick one.

**A. Cloud Postgres (what the original uses).** Create a database and a user that can create tables and schemas.
Set `WAREHOUSE=rds` and `RDS_POSTGRES_JDBC_URL`, `RDS_POSTGRES_USERNAME`, `RDS_POSTGRES_PASSWORD`. The Atom must be
able to reach it. Create the two tables:

```bash
# any Postgres client works; this one needs only Docker
docker run --rm -v "$PWD/mock-sources/postgres/init:/sql:ro" -e PGPASSWORD='<password>' postgres:16 \
  psql -h <host> -U <user> -d <db> -f /sql/01_schema.sql
```

If the database is shared, keep the `harm_` prefix and touch nothing else in it.

**B. Local container only.** Set `WAREHOUSE=local` and `POSTGRES_PASSWORD`. `docker-compose up` creates the tables
from `mock-sources/postgres/init/01_schema.sql`. In Boomi (step 6) point the Postgres connection at
`jdbc:postgresql://host.docker.internal:5442/harmonization` so the Atom container can reach it.

Check the analytics side: restart the runner (`docker-compose --env-file ../.env up -d elementary`), then
`curl -X POST localhost:4121/run`. With empty tables it should answer `status ok` with all tests passed, and
`http://localhost:4121/report` should open the Elementary dashboard.

---

## 4. Shopify development store

1. In your Partner organisation create a **development store** (any name; the original is `boomi-demo-store`).
2. Open the **Dev Dashboard** (dev.shopify.com), create an app named **SKU Harmonization POC**, scope
   `write_products` (add `read_products` if offered), custom distribution, and install it on the store. The
   app and the store must be in the same organisation so the client-credentials grant works.
3. Put `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET` and `SHOPIFY_API_VERSION` in `.env`.
4. Seed and check:

```bash
python3 seed/shopify_seed.py seed     # creates the 12 CPG products, all tagged harmonization-poc
python3 seed/shopify_seed.py check    # {'count': 12, 'prices_match_seed': True}
```

If the store is shared, the code only ever creates or changes products carrying the tag. A second `seed` creates nothing.

The Boomi Shopify connection (step 6) uses the native connector and the **OAuth authorization code** flow, which
needs two more app settings later: App URL host `platform.boomi.com` and the Boomi callback as a redirect URL.

---

## 5. Data Hub model, sources and MetaHub

Use the `bc-datahub` skill scripts, never hand-written calls (`source scripts/skill-paths.sh` sets `$DH`).

```bash
bash $DH/datahub-env-check.sh                                   # both API surfaces reachable
bash $DH/datahub-source.sh create active-development/mdm.source/shopify.xml
bash $DH/datahub-source.sh create active-development/mdm.source/aws_marketplace.xml
bash $DH/datahub-model.sh create active-development/mdm.model/cpg_product.xml   # prints the model id
```

Then, in the Data Hub UI on the new model's **Sources** tab, click **Rank Sources** and put **Shopify first**
for `price`, `name` and `aws_sku` (ranking can also be saved through the API once you have pulled the draft; keep
`<mdm:sourceRankings>` on any later update). Save as draft, then:

```bash
bash $DH/datahub-model.sh publish <model-id> --notes "initial"
bash $DH/datahub-deployment.sh deploy <model-id> <repository-id> --version <v>   # or deploy from the UI
```

The **universe id equals the model id**. Write it down. Notes: the model name may not contain a space (create as
`CPGProduct`); if a model named `Product` already exists in a shared repository, never touch it.

Initial loads come later (step 7). MetaHub glossary (needs MetaHub access and the Boomi API token in `.env`):

```bash
python3 seed/metahub_seed.py --universe <model-id>     # run twice; the second run creates nothing
```

---

## 6. Boomi connections and components

Create the folder **Sku Harmonization POC** (`bash $BI/boomi-folder-create.sh "Sku Harmonization POC"`), set
`BOOMI_TARGET_FOLDER`, and name everything `HARM - ...`.

Open Claude Code in the repository and give it this task (adapt the quotes):

> "Rebuild the Boomi components for this POC in my account's folder `Sku Harmonization POC`, using the XML under
> `active-development/` as templates and `docs/handover/HANDOVER.md` as the design. Follow the build order in
> `docs/handover/REPLICATION_GUIDE.md` section 6. Replace every account-specific ID (folder, connections, profiles,
> maps, the Data Hub universe id inside the Data Hub REST operations' paths). Push as you go and record the new IDs
> in `docs/platform-ids.md`. Stop and tell me at every step marked UI."

### Build order

| # | Component | How |
|---|---|---|
| 1 | Connection `HARM - DataHub REST Connection` | `bash $DH/datahub-connection.sh bootstrap rest "HARM - DataHub REST Connection" <folder-id>` |
| 2 | Connections `HARM - AWSMP Connection` (REST, no auth, `http://host.docker.internal:4120`) and `HARM - Elementary Runner Connection` (REST, no auth, `http://host.docker.internal:4121`) | Companion, from `active-development/connector-settings/` |
| 3 | Connection `HARM - Postgres Connection` (Database V2, driver `org.postgresql.Driver`, your JDBC URL) | Companion creates it with an **empty password**. **UI:** open it, type the password, Save, Test Connection |
| 4 | Connection `HARM - Shopify Connection` (native Shopify connector) | **UI.** In the Shopify app set App URL to `https://platform.boomi.com` and add redirect URL `https://platform.boomi.com/account/<your-account-id>/oauth2/callback`; create a new app version and release it. In Boomi create the connection, OAuth 2.0 tab: client id and secret, authorization URL `https://<store>.myshopify.com/admin/oauth/authorize`, access-token URL `.../admin/oauth/access_token`, scope `write_products`, then **Generate** and Save. Test it |
| 5 | Operation `HARM - Shopify Query Products` (Shopify, QUERY, Product) | **UI import.** Afterwards, ask Companion to pull it and set `title`, `vendor`, `status` to selectable and selected (the import omits them), then push |
| 6 | Operation `HARM - Shopify Update Product` (Shopify, UPDATE, Product, tick "Return Application Error Responses") | **UI import.** Its request profile includes `metafields` |
| 7 | Profiles, REST operations, maps, the UDF `HARM - Harmonized SKU` | Companion, from `active-development/` (profile.xml, profile.json, connector-action, transform.map, transform.function). **Never re-sort the Postgres request profiles** |
| 8 | Processes: `HARM - Inbound Shopify`, `HARM - Inbound AWS Marketplace`, `HARM - Outbound Push`, `HARM - Export Golden to Postgres` | Companion. Starts must be `passthroughaction` (they are called as subprocesses) |
| 9 | Listener processes and WSS operations: `HARM - Run Harmonization`, `HARM - Change Shopify Price API`, `HARM - Show Elementary Results API` | Companion |
| 10 | API Service Component `HARM - Muse API` (base path `muse`; the show-results route has `httpMethod="GET"`) | Companion. Needs an Atom whose shared web server `apiType` is `advanced` (`bash $BI/boomi-shared-server-info.sh`) |

Deploy every process and the API component to your environment (`bash $BI/boomi-deploy.sh <file>`; listeners and
the component separately). **Remove `branchId` from any pulled XML before deploying.**

---

## 7. First load, in this exact order

1. Enable the initial load for Shopify, run `HARM - Inbound Shopify` once, finish the load:
   ```bash
   bash $DH/datahub-source.sh enable-initial-load --repository <repo-id> --universe <model-id> shopify
   bash $BI/boomi-test-execute.sh --process-id <inbound-shopify-id>
   bash $DH/datahub-source.sh finish-initial-load --repository <repo-id> --universe <model-id> shopify
   ```
   Verify: 12 golden records, 0 quarantine entries (`datahub-golden-record.sh query`, `datahub-quarantine.sh query`).
2. Same three commands for `aws_marketplace` with `HARM - Inbound AWS Marketplace`. Verify: still 12 golden records,
   10 with an `aws_sku`, **exactly 2** quarantine entries (both `REQUIRED_FIELD`), none `POSSIBLE_DUPLICATE`.
3. Run `HARM - Outbound Push`, then `HARM - Export Golden to Postgres`. Verify in the AWS mock that the 10 matched
   listings carry the Shopify price and a `CPG-` SKU, in Shopify that the 12 products carry the
   `harmonization.harmonized_sku` metafield, and that `harm_golden_products` has 12 rows.

Do not re-run an inbound process while its source is mid initial load. One source at a time.

---

## 8. Make the API reachable for Muse

**With API Management and a gateway (original design).**
1. In Boomi **API Management**, register the deployed `HARM - Muse API` on your environment, create a plan, and
   issue an API key for it. Put the key in `.env` as `HARM_MUSE_API_KEY`.
2. Start a tunnel to the gateway: `ngrok http 8078 --domain=<your-reserved-domain>`.
3. Test: no key gives 401; with the key it works:
   ```bash
   curl -s -H "x-api-key: $KEY" https://<your-domain>/ws/rest/muse/harmonization/showElementaryResults
   ```

**Without a gateway.** Create a user and token in the Atom's Shared Web Server settings, tunnel the Atom's port with
`ngrok http 9092`, and call with HTTP Basic. Edit `docs/muse/openapi.yaml` accordingly (security scheme `http`/`basic`).

Check the five behaviours before involving Muse (replace the host; key from `.env`):

| Call | Expected |
|---|---|
| `POST .../runHarmonization` (body `{}`) | 200, `status: ok`, `tests_failed: 5` on a fresh reset, about 60 to 70 seconds |
| two of them at once | one `ok`, one `in_progress` |
| `POST .../changeShopifyPrice {"gtin":"0812345002010","price":"9.99"}` | 200, the Shopify price changes |
| same with price `0`, `-1`, `abc`, `1.234` | 400 each, store unchanged |
| unknown GTIN, and `GET .../showElementaryResults` | 404, and 200 with the summary |

---

## 9. Connect Muse

1. Set the `servers` URL and security scheme in `docs/muse/openapi.yaml` to your own domain (the file in the repository
   points at the original domain).
2. In Muse, add a connector from that OpenAPI file. When asked for credentials, give it the API key as the `x-api-key`
   header. Name the connector for what it does (the original is "Boomi Harmonization").
3. Ask Muse for "the latest data-quality results" first (a read-only call), then "run the harmonization", then change a
   price and run again. Muse asks permission to reach the site for each action.

Muse can only reach a public address; it cannot open `http://localhost:4121/report`. View the Elementary dashboard in
your own browser.

---

## 10. Operate, reset, extend

- Between runs: `bash scripts/reset.sh` (about 6 seconds; restores the AWS mock, the Shopify seed prices, empties the two
  warehouse tables, restarts the runner). Everything else is in `docs/runbook.md`.
- Add a vertical (manufacturing, finance): `docs/runbook.md`, section "Adding a vertical".

---

## 11. Verification checklist (all should be true)

- [ ] `python3 -m pytest -q` passes (66 tests)
- [ ] `curl localhost:4120/health` and `localhost:4121/health` return ok
- [ ] `python3 seed/shopify_seed.py check` reports 12 products with seed prices
- [ ] Data Hub: model deployed, 12 golden records, 2 quarantine entries (`REQUIRED_FIELD`)
- [ ] `harm_source_products` has 24 rows (12 per channel), `harm_golden_products` has 12
- [ ] MetaHub: 4 endorsed terms associated to the model
- [ ] Gateway: 401 without the key, 200 with it
- [ ] First run after a reset reports 5 flagged records; the Elementary report opens at `localhost:4121/report`
- [ ] Muse can run the harmonization, change a price and read the results

---

## 12. Troubleshooting (symptom, cause, fix)

| Symptom | Cause | Fix |
|---|---|---|
| `Could not unmarshall query filter` from a listener | a QUERY step received the caller's document | put an empty Message step in front of the Shopify query and in front of each subprocess call |
| Route returns 404 "Unknown operation for the given URL path" | method mismatch, or listener not deployed | the show-results route must be GET; deploy every listener and then the API component; check the Atom log |
| 404 "No context-path matches the request URI" | wrong port (not the Atom or gateway) | use the gateway port, or the Atom's published web-server port |
| 401 at the gateway | missing or wrong `x-api-key` | send the API Management key for your plan |
| `No value specified for parameter 5` (or wrong columns written) | Database V2 binds `?` by position and a field is missing | use the separate no-GTIN / no-AWS-SKU operations; keep request profile order equal to the SQL |
| Duplicate or `POSSIBLE_DUPLICATE` quarantine entries | an inbound process re-ran mid initial load | finish the initial load first; resend after |
| Shopify query lacks `title`/`vendor` | the import hides them | mark them selectable and selected in the operation XML and push |
| Shopify OAuth "redirect_uri and application url must have matching hosts" | the app's App URL host differs from the callback host | set App URL host to `platform.boomi.com`, add the callback, release a new app version |
| API component deploys but nothing answers | Atom `apiType` is not `advanced`, or listener not deployed | check `boomi-shared-server-info.sh`; deploy listeners and component |
| `source .env` fails | unquoted password with shell characters | single-quote the value |
| `price_drift` check never flags | the AWS mock already matches Shopify after a run | `bash scripts/reset.sh` |
| Elementary run fails to connect | wrong `WAREHOUSE` setting or credentials | set `WAREHOUSE=rds` or `local` and recreate the `elementary` container |
| Shopify redirect or token errors after a day | tokens expire (the seed uses a 24-hour client-credentials token; the connector token may need Regenerate) | rerun the seed (it fetches a fresh token) or Regenerate on the connection |

---

## 13. Security checklist

- `.env` is git-ignored; run `git status` before every commit and never add it. Rotate any key that was shared.
- The public tunnel exposes an API that can change prices and trigger runs. Keep the API key on, and stop the tunnel when not demonstrating.
- On shared resources (Shopify store, Data Hub repository, database) only touch what carries your tag, model name or prefix.
