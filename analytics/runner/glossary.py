"""Reads the MetaHub business glossary terms associated with the CPG Product model.

Muse reaches this through the Boomi process `HARM - Show Glossary API`, so the person can ask
what a term such as "Price Authority" means. Read-only: it never writes to MetaHub.

The JWT request must carry no Accept header (it answers 406 otherwise) and the token lasts five
minutes, so it is refreshed on a four-minute clock.
"""
from __future__ import annotations

import base64
import html
import os
import re
import time
from typing import Dict, List

import requests

METAHUB = "https://metahub.boomi.com/metahub"
# Universe id of the deployed CPG Product model (docs/platform-ids.md).
DEFAULT_UNIVERSE = "df443425-d048-44ab-9482-a7cc903b3b3c"
TOKEN_TTL_SECONDS = 240
_token = {"value": None, "at": 0.0}


class NotConfigured(RuntimeError):
    pass


class MetaHubError(RuntimeError):
    pass


def _need(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise NotConfigured("MetaHub is not configured: %s is not set in the runner's environment." % name)
    return value


def plain_text(content) -> str:
    """Turn a glossary term's HTML into one line of plain text."""
    if not content:
        return ""
    text = re.sub(r"</p>\s*<p>", " ", content)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _jwt(account: str) -> str:
    if _token["value"] and time.time() - _token["at"] < TOKEN_TTL_SECONDS:
        return _token["value"]
    cred = base64.b64encode(("BOOMI_TOKEN.%s:%s" % (_need("BOOMI_USERNAME"), _need("BOOMI_API_TOKEN"))).encode()).decode()
    resp = requests.get(
        "https://api.boomi.com/auth/jwt/generate/%s" % account,
        # A None value removes requests' default Accept header.
        headers={"Authorization": "Basic " + cred, "Accept": None},
        timeout=30,
    )
    if resp.status_code != 200:
        raise MetaHubError("MetaHub sign-in failed (HTTP %s)." % resp.status_code)
    _token["value"] = resp.text.strip()
    _token["at"] = time.time()
    return _token["value"]


def _content(account: str, token: str, glossary_id) -> str:
    if not glossary_id:
        return ""
    resp = requests.get(
        "%s/api/accounts/%s/glossaries/%s" % (METAHUB, account, glossary_id),
        params={"includeContent": "true"},
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise MetaHubError("MetaHub could not read a glossary term (HTTP %s)." % resp.status_code)
    return resp.json().get("content") or ""


def fetch_terms() -> Dict:
    account = _need("BOOMI_ACCOUNT_ID")
    universe = os.environ.get("METAHUB_UNIVERSE_ID") or DEFAULT_UNIVERSE
    token = _jwt(account)
    resp = requests.get(
        "%s/api/accounts/%s/associations" % (METAHUB, account),
        params={"assetType": "DATAHUB_MODEL", "assetExternalId": universe, "limit": 100},
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise MetaHubError("MetaHub could not list the glossary terms (HTTP %s)." % resp.status_code)
    rows = resp.json().get("associations") or []
    terms: List[Dict] = []
    model = "CPG Product"
    for row in rows:
        term = row.get("glossarySummary") or {}
        model = (row.get("assetSummary") or {}).get("title") or model
        terms.append({
            "name": term.get("name", ""),
            "endorsement": term.get("endorsementStatus", ""),
            "purpose": term.get("purpose", ""),
            # The association list carries no term text; fetch each term with its content.
            "definition": plain_text(_content(account, token, term.get("id"))),
        })
    return {"model": model, "term_count": len(terms), "terms": terms}
