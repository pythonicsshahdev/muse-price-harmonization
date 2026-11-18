#!/usr/bin/env bash
# Put the demo back to its starting state so the next harmonization run shows the
# price drift and the unmatched listings again.
#
#   bash scripts/reset.sh
#
# What it resets:
#   - the AWS Marketplace mock (restart reloads the seeded prices and GTINs)
#   - the POC products in the Shopify dev store (seed names and prices; only products
#     tagged harmonization-poc are touched)
#   - the two warehouse tables public.harm_source_products and public.harm_golden_products
#   - the Elementary runner's cached summary (restart), so "show results" says no run yet
# What it does NOT reset: DataHub golden records and quarantine (the next run
# recomputes them), the other tables in the shared RDS database, MetaHub terms.
#
# Credentials come from .env and are never printed. Exits non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] || { echo "ERROR: .env not found in $ROOT" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${RDS_POSTGRES_JDBC_URL:?set RDS_POSTGRES_JDBC_URL in .env}"
: "${RDS_POSTGRES_USERNAME:?set RDS_POSTGRES_USERNAME in .env}"
: "${RDS_POSTGRES_PASSWORD:?set RDS_POSTGRES_PASSWORD in .env}"

step() { printf '\n== %s\n' "$1"; }

step "1/4 AWS Marketplace mock: restart"
( cd mock-sources && docker-compose --env-file ../.env restart awsmp >/dev/null )
for i in $(seq 1 30); do
  if curl -fsS -m 2 localhost:4120/health >/dev/null 2>&1; then break; fi
  [[ $i -eq 30 ]] && { echo "ERROR: AWS mock did not come back on :4120" >&2; exit 1; }
  sleep 1
done
echo "mock is up"

step "2/4 Shopify: restore the POC products' seed prices and names"
python3 -W ignore seed/shopify_seed.py reset

step "3/4 Warehouse: empty the two harmonization tables"
HOST="$(sed -E 's#^jdbc:postgresql://([^:/]+).*#\1#' <<<"$RDS_POSTGRES_JDBC_URL")"
PORT="$(sed -nE 's#^jdbc:postgresql://[^:/]+:([0-9]+)/.*#\1#p' <<<"$RDS_POSTGRES_JDBC_URL")"
DB="$(sed -E 's#^jdbc:postgresql://[^/]+/([^?]+).*#\1#' <<<"$RDS_POSTGRES_JDBC_URL")"
docker run --rm -e PGPASSWORD="$RDS_POSTGRES_PASSWORD" -e PGCONNECT_TIMEOUT=15 postgres:16 \
  psql -h "$HOST" -p "${PORT:-5432}" -U "$RDS_POSTGRES_USERNAME" -d "$DB" -v ON_ERROR_STOP=1 -q \
  -c "truncate table public.harm_source_products, public.harm_golden_products"
echo "tables emptied"

step "4/4 Elementary runner: restart (clears the cached run summary)"
( cd mock-sources && docker-compose --env-file ../.env restart elementary >/dev/null )
for i in $(seq 1 30); do
  if curl -fsS -m 2 localhost:4121/health >/dev/null 2>&1; then break; fi
  [[ $i -eq 30 ]] && { echo "ERROR: Elementary runner did not come back on :4121" >&2; exit 1; }
  sleep 1
done
echo "runner is up"

step "Check"
python3 -W ignore seed/shopify_seed.py check
curl -fsS localhost:4120/health >/dev/null && echo "aws mock: healthy"
echo
echo "Reset complete. The next 'run the harmonization' should flag 5 records (3 price drifts, 2 unmatched)."
