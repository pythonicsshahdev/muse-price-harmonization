import json

import pytest
import responses

from seed import metahub_seed as mh

ACCOUNT = "acct-1"
BASE = "https://metahub.boomi.com/metahub/api/accounts/" + ACCOUNT
JWT_URL = "https://api.boomi.com/auth/jwt/generate/" + ACCOUNT


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    # Never read the real .env in tests.
    monkeypatch.setenv("ENV_FILE", str(tmp_path / "empty.env"))
    monkeypatch.setenv("BOOMI_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("BOOMI_USERNAME", "user@example.com")
    monkeypatch.setenv("BOOMI_API_TOKEN", "tok")
    monkeypatch.setattr(mh, "_token", {"value": None, "at": 0.0})
    monkeypatch.setattr(mh, "_now", lambda: 1000.0)


def _jwt(rsps, body="jwt-1"):
    rsps.add(responses.GET, JWT_URL, body=body)


def _posts(rsps, suffix):
    return [c for c in rsps.calls if c.request.method == "POST" and c.request.url.endswith(suffix)]


def test_token_request_sends_no_accept_header():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        assert mh.get_token() == "jwt-1"
        assert rsps.calls[0].request.headers.get("Accept") is None
        assert rsps.calls[0].request.headers["Authorization"].startswith("Basic ")


def test_token_refreshes_after_four_minutes(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(mh, "_now", lambda: clock["t"])
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, JWT_URL, body="jwt-1")
        rsps.add(responses.GET, JWT_URL, body="jwt-2")
        assert mh.get_token() == "jwt-1"
        clock["t"] += 239
        assert mh.get_token() == "jwt-1"  # still cached
        clock["t"] += 2
        assert mh.get_token() == "jwt-2"  # past the 4-minute clock


def test_ensure_glossary_reuses_existing_name():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        rsps.add(responses.GET, BASE + "/glossaries/search",
                 json={"data": [{"id": "g-9", "name": "Price Authority"},
                                {"id": "g-8", "name": "Price Authority (old)"}]})
        rsps.add(responses.POST, BASE + "/glossaries/g-9/endorsement-status", status=409)
        gid = mh.ensure_glossary("Price Authority", "why", "<p>x</p>", endorse=True)
        assert gid == "g-9"
        assert _posts(rsps, "/glossaries") == []  # nothing created


def test_ensure_glossary_creates_then_endorses_when_absent():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        rsps.add(responses.GET, BASE + "/glossaries/search", json={"data": []})
        rsps.add(responses.POST, BASE + "/glossaries", json={"id": "g-new"}, status=201)
        rsps.add(responses.POST, BASE + "/glossaries/g-new/endorsement-status", json={})
        assert mh.ensure_glossary("Harmonized SKU", "why", "<p>x</p>", endorse=True) == "g-new"
        created = json.loads(_posts(rsps, "/glossaries")[0].request.body)
        assert created["name"] == "Harmonized SKU"
        assert created["type"] == "BUSINESS_GLOSSARY"
        assert created["status"] == "PUBLISHED"
        endorsed = json.loads(_posts(rsps, "/endorsement-status")[0].request.body)
        assert endorsed["endorsementStatus"] == "ENDORSED"


def test_re_endorse_409_is_ignored():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        rsps.add(responses.GET, BASE + "/glossaries/search", json={"data": [{"id": "g-1", "name": "T"}]})
        rsps.add(responses.POST, BASE + "/glossaries/g-1/endorsement-status", status=409, body="already")
        assert mh.ensure_glossary("T", "p", "<p/>", endorse=True) == "g-1"  # no exception


def test_ensure_glossary_without_endorse_skips_endorsement():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        rsps.add(responses.GET, BASE + "/glossaries/search", json={"data": []})
        rsps.add(responses.POST, BASE + "/glossaries", json={"id": "g-2"}, status=201)
        mh.ensure_glossary("T", "p", "<p/>", endorse=False)
        assert _posts(rsps, "/endorsement-status") == []


def test_associate_posts_datahub_model_association_once():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        rsps.add(responses.GET, BASE + "/associations", json={"data": []})
        rsps.add(responses.POST, BASE + "/associations", json={"id": "a-1"}, status=201)
        assert mh.associate("g-1", "uni-1") is True
        body = json.loads(_posts(rsps, "/associations")[0].request.body)
        assert body["assetType"] == "DATAHUB_MODEL"
        assert body["assetExternalId"] == "uni-1"
        assert body["glossaryId"] == "g-1"


def test_associate_skips_when_already_associated():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        # MetaHub's real list response keys the rows under "associations".
        rsps.add(responses.GET, BASE + "/associations", json={"associations": [{"id": "a-1"}]})
        assert mh.associate("g-1", "uni-1") is False
        assert _posts(rsps, "/associations") == []


def test_failed_create_raises_with_status():
    with responses.RequestsMock() as rsps:
        _jwt(rsps)
        rsps.add(responses.GET, BASE + "/glossaries/search", json={"data": []})
        rsps.add(responses.POST, BASE + "/glossaries", status=400, body="bad name")
        with pytest.raises(mh.MetaHubError, match="400"):
            mh.ensure_glossary("T", "p", "<p/>", endorse=False)
