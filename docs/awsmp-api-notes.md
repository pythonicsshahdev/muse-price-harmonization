# AWS Marketplace Catalog API: real shapes vs the mock

Source: AWS Marketplace Catalog API reference (`ListEntities`, `DescribeEntity`,
`StartChangeSet`), read 2026-11-12. The mock in `mock-sources/awsmp/` follows these
shapes so a real account can replace it by editing the Boomi connection.

## Matches the real API

| Operation | Real shape | Mock |
|---|---|---|
| `ListEntities` | `POST /ListEntities`, body `Catalog` (`AWSMarketplace`), `EntityType`, `MaxResults` (1 to 50, default 20), `NextToken` | same |
| `ListEntities` response | `EntitySummaryList[]` with `EntityId`, `EntityType`, `EntityArn`, `Name`, `LastModifiedDate`, `Visibility`; `NextToken` is null on the last page | same (plus a `SaaSProductSummary` block) |
| `DescribeEntity` | `GET /DescribeEntity?catalog=AWSMarketplace&entityId=<id>` | same |
| `DescribeEntity` response | `EntityType` (`Type@Version`), `EntityIdentifier` (`EntityId@RevisionId`), `EntityArn`, `LastModifiedDate` (`YYYY-MM-DDTHH:MM:SSZ`), `Details` (stringified JSON), `DetailsDocument` (JSON) | same |
| `StartChangeSet` | `POST /StartChangeSet`, body `Catalog`, `ChangeSet[]` with `ChangeType`, `Entity {Identifier, Type}`, `Details` (stringified JSON), optional `ChangeSetName` | same |
| `StartChangeSet` response | `ChangeSetId`, `ChangeSetArn` | same |
| Errors | 404 not found, 422 validation | same status codes, body `{"message": "..."}` |

## Deviations (mock only)

- The contents of `Details` / `DetailsDocument` are the mock's own, because the real
  document varies by product type and has no price or GTIN fields for these products.
  Mock keys: `ProductTitle`, `Sku`, `Gtin` (null when missing), `ListPrice` (string,
  two decimals), `HarmonizedSku` (null until written).
- `StartChangeSet` accepts one change type, `UpdateInformation`, which sets `ListPrice`
  and/or `HarmonizedSku`. The real API runs change sets asynchronously and locks the
  entity; the mock applies the change immediately.
- `EntityId` equals the listing's AWS SKU (for example `AWSMP-BW-0001`).
- `NextToken` is an opaque string of the form `offset-<n>`.
- Extra endpoints with no real equivalent: `GET /health`, `POST /admin/reset`.
- No authentication. A real account needs SigV4 request signing on the Boomi connection.
