#!/usr/bin/env python3
"""Seed the MetaHub business glossary for a vertical pack and associate it to the
DataHub model.

Idempotent: a glossary that already exists (by name) is reused, and an association
that already exists is skipped, so this is safe to re-run. Credentials come from
the workspace .env and are never printed.

MetaHub JWTs expire after 5 minutes, so the token is refreshed on a 4-minute clock.
The JWT request must carry no Accept header (it answers 406 otherwise).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests

if __package__ in (None, ""):  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed.envfile import load_env, require

BASE = "https://metahub.boomi.com/metahub"
PACKS_DIR = Path(__file__).resolve().parent / "packs"
# Universe id of the deployed CPG Product model (docs/platform-ids.md).
DEFAULT_UNIVERSE = "df443425-d048-44ab-9482-a7cc903b3b3c"
TOKEN_TTL_SECONDS = 240

_token = {"value": None, "at": 0.0}


class MetaHubError(RuntimeError):
    pass


def _now() -> float:
    return time.time()


def _account(env=None) -> str:
    return require(env or load_env(), "BOOMI_ACCOUNT_ID")


def get_token() -> str:
    if _token["value"] and _now() - _token["at"] < TOKEN_TTL_SECONDS:
        return _token["value"]
    env = load_env()
    cred = base64.b64encode(
        ("BOOMI_TOKEN.%s:%s" % (require(env, "BOOMI_USERNAME"), require(env, "BOOMI_API_TOKEN"))).encode()
    ).decode()
    resp = requests.get(
        "https://api.boomi.com/auth/jwt/generate/%s" % _account(env),
        # A None value removes requests' default Accept header.
        headers={"Authorization": "Basic " + cred, "Accept": None},
        timeout=30,
    )
    if resp.status_code != 200:
        raise MetaHubError("token request failed: %s" % resp.status_code)
    _token["value"] = resp.text.strip()
    _token["at"] = _now()
    return _token["value"]


def _call(method: str, path: str, body=None, params=None, ok=(200, 201)):
    resp = requests.request(
        method,
        "%s/api/accounts/%s%s" % (BASE, _account(), path),
        json=body,
        params=params,
        headers={"Authorization": "Bearer " + get_token(), "Accept": "application/json"},
        timeout=45,
    )
    if resp.status_code not in ok:
        raise MetaHubError("%s %s -> %s %s" % (method, path, resp.status_code, resp.text[:200]))
    # Accepted non-2xx answers (e.g. a 409 on re-endorse) carry a plain-text body.
    return resp.json() if resp.ok and resp.text.strip() else None


def _rows(payload) -> list:
    # Lists answer {"data": [...]} for glossaries and {"associations": [...]} for associations.
    if isinstance(payload, dict):
        return payload.get("data") or payload.get("associations") or []
    return payload or []


def ensure_glossary(name: str, purpose: str, content_html: str, endorse: bool) -> str:
    """Return the id of the glossary called `name`, creating it if absent."""
    found = [g for g in _rows(_call("GET", "/glossaries/search", params={"key": name, "limit": 100}))
             if g.get("name") == name]
    if found:
        gid = found[0]["id"]
    else:
        created = _call("POST", "/glossaries", {
            "name": name,
            "type": "BUSINESS_GLOSSARY",
            "purpose": purpose,
            "content": content_html,
            "status": "PUBLISHED",
        })
        gid = created.get("id") or (created.get("data") or {}).get("id")
    if endorse:
        # Endorsement is a separate call. Re-endorsing an already ENDORSED term is a 409: fine.
        _call("POST", "/glossaries/%s/endorsement-status" % gid,
              {"endorsementStatus": "ENDORSED", "comment": "Harmonization POC baseline"},
              ok=(200, 201, 409))
    return gid


def associate(glossary_id: str, universe_id: str, title: str = "CPG Product") -> bool:
    """Link a glossary to the DataHub model. Returns True if created, False if it existed."""
    existing = _rows(_call("GET", "/associations", params={
        "glossaryId": glossary_id, "assetType": "DATAHUB_MODEL", "assetExternalId": universe_id, "limit": 1}))
    if existing:
        return False
    _call("POST", "/associations", {
        "assetType": "DATAHUB_MODEL",
        "assetExternalId": universe_id,
        "glossaryId": glossary_id,
        "title": title,
    })
    return True


def load_terms(pack: str) -> List[dict]:
    with open(PACKS_DIR / pack / "glossary.json") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", default="cpg")
    parser.add_argument("--universe", default=DEFAULT_UNIVERSE, help="DataHub model/universe id")
    parser.add_argument("--no-endorse", action="store_true")
    args = parser.parse_args(argv)

    created = linked = 0
    for term in load_terms(args.pack):
        gid = ensure_glossary(term["name"], term["purpose"], term["content_html"], not args.no_endorse)
        newly = associate(gid, args.universe)
        linked += newly
        print("  %-24s %s %s" % (term["name"], gid, "linked" if newly else "already linked"))
    print("%d new association(s)" % linked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
