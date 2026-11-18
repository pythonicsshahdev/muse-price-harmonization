"""Canonical product dataset for a vertical pack, plus the expected-outcome oracle.

A vertical is a folder under seed/packs/. The oracle functions describe what the
harmonization should produce, so the same data drives the mocks, the Shopify
seed, and the checks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

PACKS_DIR = Path(__file__).resolve().parent / "packs"


@dataclass(frozen=True)
class Product:
    gtin: str
    name: str
    brand: str
    shopify_sku: str
    shopify_price: Decimal
    aws_sku: str
    aws_name: str
    aws_price: Decimal
    aws_gtin: Optional[str]


def load_products(pack: str = "cpg") -> List[Product]:
    path = PACKS_DIR / pack / "products.json"
    with open(path) as f:
        raw = json.load(f, parse_float=Decimal)
    return [
        Product(
            gtin=r["gtin"],
            name=r["name"],
            brand=r["brand"],
            shopify_sku=r["shopify_sku"],
            shopify_price=Decimal(r["shopify_price"]),
            aws_sku=r["aws_sku"],
            aws_name=r["aws_name"],
            aws_price=Decimal(r["aws_price"]),
            aws_gtin=r["aws_gtin"],
        )
        for r in raw["products"]
    ]


def canonical_sku(gtin: str, prefix: str = "CPG") -> str:
    return "%s-%s" % (prefix, gtin[-8:])


def _is_matched(p: Product) -> bool:
    return p.aws_gtin == p.gtin


def expected_matched(products: List[Product]) -> List[str]:
    """GTINs whose AWS listing carries the same GTIN as the Shopify product."""
    return [p.gtin for p in products if _is_matched(p)]


def expected_unmatched(products: List[Product]) -> List[str]:
    """AWS SKUs whose listing GTIN is missing or does not match."""
    return [p.aws_sku for p in products if not _is_matched(p)]


def expected_price_drift(products: List[Product]) -> List[str]:
    """GTINs of matched products whose channel prices differ."""
    return [p.gtin for p in products if _is_matched(p) and p.aws_price != p.shopify_price]
