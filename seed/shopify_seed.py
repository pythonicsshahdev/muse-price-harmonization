#!/usr/bin/env python3
"""Seed, reset and inspect the POC products in the Shopify development store.

Auth is the Dev Dashboard client-credentials grant (24-hour token). The store may be
shared, so every product this code creates carries TAG and every read-modify path
ignores products without it.

    python3 seed/shopify_seed.py seed|reset|check
"""
from __future__ import annotations

import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import requests

if __package__ in (None, ""):  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed.dataset import Product, load_products
from seed.envfile import load_env, require

TAG = "harmonization-poc"
TOKEN_MARGIN_SECONDS = 60
MAX_ATTEMPTS = 5

_TOKEN: Dict[str, Any] = {"value": None, "expires_at": 0.0}


class ShopifyError(RuntimeError):
    pass


def _reset_token_cache() -> None:
    _TOKEN.update(value=None, expires_at=0.0)


def _config() -> Dict[str, str]:
    env = load_env()
    return {
        "domain": require(env, "SHOPIFY_STORE_DOMAIN"),
        "client_id": require(env, "SHOPIFY_CLIENT_ID"),
        "client_secret": require(env, "SHOPIFY_CLIENT_SECRET"),
        "version": require(env, "SHOPIFY_API_VERSION"),
    }


def get_token() -> str:
    cfg = _config()
    now = time.time()
    if _TOKEN["value"] and now < _TOKEN["expires_at"] - TOKEN_MARGIN_SECONDS:
        return _TOKEN["value"]
    resp = requests.post(
        "https://%s/admin/oauth/access_token" % cfg["domain"],
        data={"grant_type": "client_credentials",
              "client_id": cfg["client_id"],
              "client_secret": cfg["client_secret"]},
        timeout=30,
    )
    if resp.status_code != 200:
        raise ShopifyError("Token request failed: HTTP %d %s" % (resp.status_code, resp.text[:200]))
    body = resp.json()
    _TOKEN["value"] = body["access_token"]
    _TOKEN["expires_at"] = now + float(body["expires_in"])
    return _TOKEN["value"]


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    for _ in range(MAX_ATTEMPTS):
        resp = requests.request(method, url, headers={"X-Shopify-Access-Token": get_token()},
                                timeout=30, **kwargs)
        if resp.status_code == 429:
            time.sleep(float(resp.headers.get("Retry-After", "2")))
            continue
        if resp.status_code >= 400:
            raise ShopifyError("%s %s -> HTTP %d %s" % (method, url, resp.status_code, resp.text[:200]))
        return resp
    raise ShopifyError("Gave up after %d rate-limited attempts: %s %s" % (MAX_ATTEMPTS, method, url))


def _base() -> str:
    cfg = _config()
    return "https://%s/admin/api/%s" % (cfg["domain"], cfg["version"])


def _all_products() -> Iterator[Dict[str, Any]]:
    url: Optional[str] = _base() + "/products.json?limit=250&fields=id,title,tags,variants"
    while url:
        resp = _request("GET", url)
        for product in resp.json()["products"]:
            yield product
        url = resp.links.get("next", {}).get("url")


def _is_ours(product: Dict[str, Any]) -> bool:
    return TAG in [t.strip() for t in product.get("tags", "").split(",")]


def _ours_by_barcode() -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for product in _all_products():
        if not _is_ours(product):
            continue
        for variant in product["variants"]:
            if variant.get("barcode"):
                found[variant["barcode"]] = {"product": product, "variant": variant}
    return found


def _money(price: Decimal) -> str:
    return "%.2f" % price


def seed_store(products: List[Product]) -> int:
    """Create any missing POC product (matched by barcode among tagged products)."""
    existing = _ours_by_barcode()
    for p in products:
        if p.gtin in existing:
            continue
        _request("POST", _base() + "/products.json", json={"product": {
            "title": p.name,
            "vendor": p.brand,
            "product_type": "CPG",
            "tags": TAG,
            "status": "active",
            "variants": [{"sku": p.shopify_sku, "barcode": p.gtin, "price": _money(p.shopify_price)}],
        }})
    return len(products)


def reset_store(products: List[Product]) -> None:
    """Restore seeded name and price on tagged products. Never creates or touches others."""
    existing = _ours_by_barcode()
    for p in products:
        found = existing.get(p.gtin)
        if not found:
            continue
        if found["variant"]["price"] != _money(p.shopify_price):
            _request("PUT", _base() + "/variants/%d.json" % found["variant"]["id"],
                     json={"variant": {"id": found["variant"]["id"], "price": _money(p.shopify_price)}})
        if found["product"]["title"] != p.name:
            _request("PUT", _base() + "/products/%d.json" % found["product"]["id"],
                     json={"product": {"id": found["product"]["id"], "title": p.name}})


def set_price(gtin: str, price: Decimal) -> None:
    try:
        value = Decimal(str(price))
    except InvalidOperation:
        raise ValueError("price must be a number")
    if not value.is_finite() or value <= 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("price must be positive with at most 2 decimals")
    found = _ours_by_barcode().get(gtin)
    if not found:
        raise LookupError("No POC product with barcode %s" % gtin)
    _request("PUT", _base() + "/variants/%d.json" % found["variant"]["id"],
             json={"variant": {"id": found["variant"]["id"], "price": _money(value)}})


def check_store(products: List[Product]) -> Dict[str, Any]:
    existing = _ours_by_barcode()
    present = [p for p in products if p.gtin in existing]
    matches = all(existing[p.gtin]["variant"]["price"] == _money(p.shopify_price) for p in present)
    return {"count": len(present), "prices_match_seed": matches}


def main(argv: List[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("seed", "reset", "check"):
        print(__doc__)
        return 2
    products = load_products()
    if argv[1] == "seed":
        print("seeded:", seed_store(products))
    elif argv[1] == "reset":
        reset_store(products)
        print("reset done")
    else:
        result = check_store(products)
        print(result)
        return 0 if result["count"] == len(products) and result["prices_match_seed"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
