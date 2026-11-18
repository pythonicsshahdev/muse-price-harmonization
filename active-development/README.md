# active-development

The Boomi component definitions for the SKU and price harmonization POC, as XML. Boomi Companion
(Claude Code) creates and pushes them with the `boomi-integration` and `bc-datahub` skill scripts.

**These files belong to one Boomi account.** They carry that account's folder, connection, profile and map
IDs, and the Data Hub universe id inside two REST operation paths. Do not push them to another account as they
are. Use them as reference templates and rebuild with Boomi Companion; the steps are in
[`docs/handover/REPLICATION_GUIDE.md`](../docs/handover/REPLICATION_GUIDE.md). The account's component names and
IDs are listed in [`docs/platform-ids.md`](../docs/platform-ids.md).

Everything lives in the Boomi folder `Sku Harmonization POC`, and every component name starts with `HARM - `.

## Folders

The folder names are the Boomi component types, which is how the skill scripts lay out pulled and created files.

| Folder | Component type | What is in it |
|---|---|---|
| `process/` | process | 8 processes: `HARM - Inbound Shopify`, `Inbound AWS Marketplace`, `Outbound Push`, `Export Golden to Postgres`, and the four listeners Muse calls (`Run Harmonization`, `Change Shopify Price API`, `Show Elementary Results API`, `Show Glossary API`) |
| `webservice/` | API Service Component | `HARM - Muse API`: publishes the four listeners at `/ws/rest/muse/harmonization/...` |
| `connector-settings/` | connections | AWS mock, Elementary runner, Postgres. The Data Hub REST connection was created by the `bc-datahub` script and the Shopify connection in the Boomi UI (OAuth), so neither is stored here |
| `connector-action/` | connector operations | REST operations (AWS mock, Data Hub, Elementary runner), Database V2 upserts, the web-service listener operations, and the two native Shopify operations (query and update, imported in the UI and then pulled) |
| `profile.json/`, `profile.xml/` | profiles | request and response shapes, including the Data Hub batch and the golden-record query response |
| `transform.map/` | maps | field mappings between those profiles |
| `transform.function/` | user-defined function | `HARM - Harmonized SKU` (`CPG-` plus the last 8 digits of the GTIN) |
| `mdm.model/`, `mdm.source/` | Data Hub | the `cpgproduct` model and the `shopify` and `aws_marketplace` sources, created with the `bc-datahub` scripts, not the component API |
| `feedback/queries/` | Data Hub query files | `all-products.xml`, used to read the golden records |

## Rules worth knowing before editing

- **Database V2 request profiles are order-sensitive.** The connector binds `?` by position, so the field order must
  match the SQL. Never re-sort them. Missing fields shift the parameters, which is why the "no GTIN" and "no AWS SKU"
  cases have their own operations and profiles.
- **Subprocesses start with an empty document** (the Message steps called "Start with an empty document"). Query steps
  read their input document as a filter and fail on anything else.
- **Remove `branchId` from pulled XML before deploying**, and redeploy the API Service Component after changing a listener.
- The files named `HARM - Shopify ... Products` and `Shopify Product ...` were pulled from the platform after a UI import,
  so they still carry platform metadata (creator, branch, folder path). The Query operation was edited to also return
  `title`, `vendor` and `status`; the import leaves them out.

Working output (account listings, execution logs, the sync state) is git-ignored and regenerated on demand.
