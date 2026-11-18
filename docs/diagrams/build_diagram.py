#!/usr/bin/env python3
"""Build the SKU/price harmonization use-case diagram.

Imports the boomi-usecase-diagram generator and icon libraries from the skill
and writes the HTML next to this file, so the skill stays untouched.
Run:  python3 build_diagram.py
"""
import sys
from pathlib import Path

SKILL = Path.home() / ".claude/skills/boomi-usecase-diagram/assets"
sys.path.insert(0, str(SKILL))
import gen_usecase_diagram as g  # noqa: E402

HERE = Path(__file__).resolve().parent

DIAGRAM = {
    "client": "Consumer Packaged Goods POC",
    "useCase": "Use Case 1: SKU & Price Harmonization",
    "breadcrumb": ["Shopify", ".", "AWS Marketplace", ">", "Boomi", ">",
                   "DataHub", ">", "Channels", ".", "Elementary"],
    "footer": ["CPG POC", "Boomi Integration + DataHub + MetaHub + Elementary",
               "Use Case 1: SKU & Price Harmonization"],
    # Spacer columns (.) carry the arrows and pills so labels clear the cards.
    "grid": {
        "cols": "1fr 0.45fr 1.05fr 0.45fr 1.2fr 0.45fr 1.05fr",
        "areas": ('"muse muse meta meta meta meta meta" '
                  '"shop . inbs . dh . exp" '
                  '"aws . inba . dh . exp" '
                  '"out . . . . . ela"'),
    },
    "arrowColours": {"navy": "#0B2A4A", "blue": "#1273E6",
                     "teal": "#0FA69A", "green": "#127C3F",
                     "purple": "#6B3FA0"},
    "groups": [{"title": "Sales Channels", "members": ["shop", "aws"],
                "colour": "#1273E6", "pad": 14}],
    "cards": [
        {"id": "muse", "n": 0, "area": "muse", "tone": "slate",
         "icon": "process_call",
         "eyebrow": "Front end", "eyebrowPlain": True,
         "title": "Muse",
         "lines": ["The interface people use to run the POC", "Triggers a Boomi API to start a run"]},

        {"id": "shop", "n": 1, "area": "shop", "tone": "blue",
         "connector": "shopify",
         "eyebrow": "Sales channel", "eyebrowPlain": True,
         "title": "Shopify Store",
         "lines": ["Real development store", "Admin API via native connector"],
         "chips": [{"text": "Price authority", "colour": "#127C3F"}]},

        {"id": "aws", "n": 2, "area": "aws", "tone": "blue",
         "connector": "http",
         "eyebrow": "Sales channel", "eyebrowPlain": True,
         "title": "AWS Marketplace",
         "lines": ["Mock API in Docker", "Real payload shapes"],
         "note": "Swap for a real account by editing the connection"},

        {"id": "inbs", "n": 3, "area": "inbs", "tone": "navy", "icon": "map",
         "eyebrow": "Boomi Integration", "title": "Inbound: Shopify",
         "lines": ["Pull products, SKUs, prices", "Map to DataHub batch XML"],
         "note": "Source: shopify"},

        {"id": "inba", "n": 4, "area": "inba", "tone": "navy", "icon": "map",
         "eyebrow": "Boomi Integration", "title": "Inbound: AWS Marketplace",
         "lines": ["Pull listings, SKUs, prices", "Map to DataHub batch XML"],
         "note": "Source: aws_marketplace"},

        {"id": "dh", "n": 5, "area": "dh", "tone": "teal", "icon": "connector",
         "eyebrow": "Boomi DataHub", "eyebrowPlain": True,
         "title": "CPG Product Model",
         "lines": ["Match on GTIN", "Shopify wins on price",
                   "Harmonized SKU generated"],
         "chips": [{"text": "Golden record", "colour": "#127C3F"},
                   {"text": "Quarantine", "colour": "#B45309"}]},

        {"id": "exp", "n": 6, "area": "exp", "tone": "slate",
         "connector": "database",
         "eyebrow": "Warehouse", "eyebrowPlain": True,
         "title": "Postgres (Docker)",
         "lines": ["Golden rows", "Source rows"],
         "note": "Written by a Boomi export process"},

        {"id": "out", "n": 7, "area": "out", "tone": "navy", "icon": "notify",
         "eyebrow": "Boomi Integration", "title": "Outbound Processes",
         "lines": ["Push golden price and harmonized SKU to each channel",
                   "Native channel SKU left untouched"]},

        {"id": "ela", "n": 8, "area": "ela", "tone": "amber", "icon": "exception",
         "eyebrow": "Observability", "eyebrowPlain": True,
         "title": "dbt + Elementary",
         "lines": ["Price drift", "Unmatched SKU", "Freshness and nulls"],
         "chips": [{"text": "Observability report", "colour": "#B45309"}]},

        {"id": "meta", "n": 9, "area": "meta", "tone": "purple",
         "icon": "document_cache",
         "eyebrow": "Governance", "eyebrowPlain": True,
         "title": "Boomi MetaHub Business Glossary",
         "lines": ["Harmonized SKU  ·  Price Authority  ·  "
                   "Channel Price Variance  ·  Canonical Product ID"],
         "note": "Terms associated to the DataHub CPG Product model"},
    ],
    "arrows": [
        {"from": "muse", "to": "inbs", "fs": "b", "ts": "t", "dash": True,
         "pill": "triggers run via API", "px": 620, "py": 286},
        {"from": "shop", "to": "inbs", "ci": "blue", "colour": "#1273E6",
         "pill": "catalog + prices"},
        {"from": "aws", "to": "inba", "ci": "blue", "colour": "#1273E6",
         "pill": "listings + prices"},
        {"from": "inbs", "to": "dh", "pill": "batch load"},
        {"from": "inba", "to": "dh", "pill": "batch load"},
        {"from": "dh", "to": "exp", "ci": "teal", "colour": "#0FA69A",
         "pill": "golden + source rows"},
        {"from": "exp", "to": "ela", "fs": "b", "ts": "t", "pill": "tables"},
        # bowed return: leaves DataHub's bottom, enters Outbound's right side
        {"from": "dh", "to": "out", "fs": "b", "ts": "r", "curve": 112,
         "ci": "teal", "colour": "#0FA69A", "pill": "golden record"},
        {"from": "out", "to": "aws", "fs": "t", "ts": "b",
         "ci": "green", "colour": "#127C3F",
         "pill": "price + SKU to both channels"},
        {"from": "meta", "to": "dh", "fs": "b", "ts": "t",
         "dash": True, "ci": "purple", "colour": "#6B3FA0",
         "pill": "associated to model"},
    ],
    "details": [
        {"title": "Match & Survivorship", "tone": "teal", "bullets": [
            "One model, one source per channel",
            "Match rule on canonical product ID (GTIN)",
            "Shopify is the price authority; AWS price aligned to it"]},
        {"title": "Runtime", "tone": "navy", "bullets": [
            "Local Atom reaches Docker via host.docker.internal",
            "AWS Marketplace mock, Postgres, dbt + Elementary in Docker",
            "Credentials in .env, never committed",
            "Built with Boomi Companion (build helper only)"]},
        {"title": "Reusable Pattern", "tone": "purple", "bullets": [
            "Pull the same entity from several systems",
            "Harmonize, govern, monitor, push back",
            "CPG first, then Manufacturing and Finance"]},
    ],
}

if __name__ == "__main__":
    out = HERE / "sku_harmonization.html"
    out.write_text(g.render(DIAGRAM))
    print("wrote %s (%.0f KB)" % (out.name, out.stat().st_size / 1024))
