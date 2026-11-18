import pytest
import responses
from fastapi.testclient import TestClient

import app as runner
import glossary

ACCOUNT = "acct-1"
JWT_URL = "https://api.boomi.com/auth/jwt/generate/" + ACCOUNT
ASSOC_URL = "https://metahub.boomi.com/metahub/api/accounts/%s/associations" % ACCOUNT


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("BOOMI_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("BOOMI_USERNAME", "user@example.com")
    monkeypatch.setenv("BOOMI_API_TOKEN", "tok")
    monkeypatch.setenv("METAHUB_UNIVERSE_ID", "uni-1")
    monkeypatch.setattr(glossary, "_token", {"value": None, "at": 0.0})


GLOSSARY_URL = "https://metahub.boomi.com/metahub/api/accounts/%s/glossaries/" % ACCOUNT


def _assoc(name, endorsement="ENDORSED", purpose="why"):
    # The real association list has no term text (content is null); it comes from GET /glossaries/{id}.
    return {
        "id": "a-" + name,
        "glossarySummary": {"id": "g-" + name, "name": name, "purpose": purpose,
                            "endorsementStatus": endorsement, "status": "PUBLISHED", "content": None},
        "assetSummary": {"title": "CPG Product", "type": "DATAHUB_MODEL", "externalId": "uni-1"},
    }


def test_glossary_returns_the_terms_for_the_model():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, JWT_URL, body="jwt-1")
        rsps.add(responses.GET, ASSOC_URL, json={"associations": [
            _assoc("Price Authority"),
            _assoc("Harmonized SKU", endorsement="DRAFT"),
        ]})
        rsps.add(responses.GET, GLOSSARY_URL + "g-Price Authority",
                 json={"content": "<p>Shopify is the <strong>price authority</strong>.</p>"})
        rsps.add(responses.GET, GLOSSARY_URL + "g-Harmonized SKU", json={"content": "<p>CPG- plus 8 digits.</p>"})
        body = TestClient(runner.app).get("/glossary").json()
        assert rsps.calls[1].request.params["assetExternalId"] == "uni-1"
        assert rsps.calls[1].request.params["assetType"] == "DATAHUB_MODEL"
        assert rsps.calls[2].request.params["includeContent"] == "true"
    assert body["model"] == "CPG Product"
    assert body["term_count"] == 2
    first = body["terms"][0]
    assert first == {"name": "Price Authority", "endorsement": "ENDORSED", "purpose": "why",
                     "definition": "Shopify is the price authority."}
    assert body["terms"][1]["endorsement"] == "DRAFT"
    assert body["terms"][1]["definition"] == "CPG- plus 8 digits."


def test_html_becomes_plain_text():
    html = "<p>A <code>gtin</code> &mdash; the key &amp; more.</p><p>Second line.</p>"
    assert glossary.plain_text(html) == "A gtin — the key & more. Second line."
    assert glossary.plain_text(None) == ""


def test_token_request_sends_no_accept_header():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, JWT_URL, body="jwt-1")
        rsps.add(responses.GET, ASSOC_URL, json={"associations": []})
        TestClient(runner.app).get("/glossary")
        assert rsps.calls[0].request.headers.get("Accept") is None


def test_not_configured_says_which_setting_is_missing(monkeypatch):
    monkeypatch.delenv("BOOMI_API_TOKEN")
    response = TestClient(runner.app).get("/glossary")
    assert response.status_code == 503
    assert "BOOMI_API_TOKEN" in response.json()["message"]


def test_metahub_failure_is_reported_not_a_stack_trace():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, JWT_URL, body="jwt-1")
        rsps.add(responses.GET, ASSOC_URL, status=500, body="boom")
        response = TestClient(runner.app).get("/glossary")
    assert response.status_code == 502
    assert "MetaHub" in response.json()["message"]
