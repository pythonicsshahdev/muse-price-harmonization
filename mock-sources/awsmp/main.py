"""AWS Marketplace Catalog API mock (SaaSProduct listings).

Mirrors the operation names and shapes of the real API; see docs/awsmp-api-notes.md
for the exact matches and deviations. State loads at import and on POST /admin/reset,
so editing the products file needs a container restart.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

CATALOG = "AWSMarketplace"
ENTITY_TYPE = "SaaSProduct"
SEED_DATE = "2026-01-01T00:00:00Z"
ARN_PREFIX = "arn:aws:aws-marketplace:us-east-1:000000000000:AWSMarketplace/SaaSProduct/"


def _products_path() -> Path:
    env = os.environ.get("PRODUCTS_PATH")
    if env:
        return Path(env)
    container = Path("/app/data/products.json")
    if container.exists():
        return container
    return Path(__file__).resolve().parents[2] / "seed" / "packs" / "cpg" / "products.json"


STATE: Dict[str, Dict[str, Any]] = {}


def load_state() -> None:
    with open(_products_path()) as f:
        products = json.load(f)["products"]
    STATE.clear()
    for p in products:
        STATE[p["aws_sku"]] = {
            "name": p["aws_name"],
            "modified": SEED_DATE,
            "details": {
                "ProductTitle": p["aws_name"],
                "Sku": p["aws_sku"],
                "Gtin": p["aws_gtin"],
                "ListPrice": p["aws_price"],
                "HarmonizedSku": None,
            },
        }


load_state()
app = FastAPI(title="AWS Marketplace Catalog mock")


def err(status: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bare_id(identifier: str) -> str:
    return identifier.split("@", 1)[0]


def _summary(entity_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "EntityId": entity_id,
        "EntityType": ENTITY_TYPE,
        "EntityArn": ARN_PREFIX + entity_id,
        "Name": entry["name"],
        "LastModifiedDate": entry["modified"],
        "Visibility": "Public",
        "SaaSProductSummary": {"ProductTitle": entry["name"], "Visibility": "Public"},
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/admin/reset")
def reset() -> Dict[str, str]:
    load_state()
    return {"status": "reset"}


@app.post("/ListEntities")
async def list_entities(request: Request):
    body = await request.json()
    if body.get("Catalog") != CATALOG:
        return err(422, "Catalog must be %s" % CATALOG)
    if not body.get("EntityType"):
        return err(422, "EntityType is required")
    max_results = body.get("MaxResults", 20)
    if not isinstance(max_results, int) or not 1 <= max_results <= 50:
        return err(422, "MaxResults must be between 1 and 50")
    offset = 0
    token = body.get("NextToken")
    if token:
        if not token.startswith("offset-") or not token[7:].isdigit():
            return err(422, "Invalid NextToken")
        offset = int(token[7:])
    items: List[Dict[str, Any]] = []
    if body["EntityType"] == ENTITY_TYPE:
        items = [_summary(i, e) for i, e in STATE.items()]
    page = items[offset:offset + max_results]
    nxt = "offset-%d" % (offset + max_results) if offset + max_results < len(items) else None
    return {"EntitySummaryList": page, "NextToken": nxt}


@app.get("/DescribeEntity")
def describe_entity(catalog: str = Query(...), entityId: str = Query(...)):
    if catalog != CATALOG:
        return err(422, "catalog must be %s" % CATALOG)
    entity_id = _bare_id(entityId)
    entry = STATE.get(entity_id)
    if entry is None:
        return err(404, "Entity %s not found" % entity_id)
    return {
        "EntityType": ENTITY_TYPE + "@1.0",
        "EntityIdentifier": entity_id + "@1",
        "EntityArn": ARN_PREFIX + entity_id,
        "LastModifiedDate": entry["modified"],
        "Details": json.dumps(entry["details"]),
        "DetailsDocument": entry["details"],
    }


def _valid_price(value: Any) -> Optional[str]:
    try:
        price = Decimal(str(value))
    except InvalidOperation:
        return None
    if price <= 0 or price != price.quantize(Decimal("0.01")):
        return None
    return "%.2f" % price


@app.post("/StartChangeSet")
async def start_change_set(request: Request):
    body = await request.json()
    if body.get("Catalog") != CATALOG:
        return err(422, "Catalog must be %s" % CATALOG)
    changes = body.get("ChangeSet")
    if not isinstance(changes, list) or not changes:
        return err(422, "ChangeSet must be a non-empty list")
    planned = []
    for change in changes:
        if change.get("ChangeType") != "UpdateInformation":
            return err(422, "Only ChangeType UpdateInformation is supported")
        entity_id = _bare_id((change.get("Entity") or {}).get("Identifier", ""))
        if entity_id not in STATE:
            return err(404, "Entity %s not found" % entity_id)
        try:
            details = json.loads(change.get("Details") or "{}")
        except ValueError:
            return err(422, "Details must be a JSON string")
        updates: Dict[str, Any] = {}
        if "ListPrice" in details:
            price = _valid_price(details["ListPrice"])
            if price is None:
                return err(422, "ListPrice must be a positive number with at most 2 decimals")
            updates["ListPrice"] = price
        if "HarmonizedSku" in details:
            updates["HarmonizedSku"] = details["HarmonizedSku"]
        planned.append((entity_id, updates))
    for entity_id, updates in planned:
        STATE[entity_id]["details"].update(updates)
        STATE[entity_id]["modified"] = _now()
    change_set_id = str(uuid.uuid4())
    return {
        "ChangeSetId": change_set_id,
        "ChangeSetArn": "arn:aws:aws-marketplace:us-east-1:000000000000:AWSMarketplace/ChangeSet/" + change_set_id,
    }
