import json

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
CATALOG = {"Catalog": "AWSMarketplace", "EntityType": "SaaSProduct"}


@pytest.fixture(autouse=True)
def _reset():
    client.post("/admin/reset")


def list_all(page_size):
    ids, token, pages = [], None, 0
    while True:
        body = dict(CATALOG, MaxResults=page_size)
        if token:
            body["NextToken"] = token
        data = client.post("/ListEntities", json=body).json()
        ids += [e["EntityId"] for e in data["EntitySummaryList"]]
        pages += 1
        token = data["NextToken"]
        if token is None:
            return ids, pages


def describe(entity_id):
    r = client.get("/DescribeEntity", params={"catalog": "AWSMarketplace", "entityId": entity_id})
    return r


def details_of(entity_id):
    return json.loads(describe(entity_id).json()["Details"])


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_list_returns_all_twelve_with_large_page():
    ids, pages = list_all(50)
    assert len(ids) == 12 and pages == 1


def test_list_pages_of_five_cover_all_without_duplicates():
    ids, pages = list_all(5)
    assert pages == 3
    assert len(ids) == 12 and len(set(ids)) == 12


def test_list_exact_boundary_page_of_twelve_has_no_next_token():
    data = client.post("/ListEntities", json=dict(CATALOG, MaxResults=12)).json()
    assert len(data["EntitySummaryList"]) == 12
    assert data["NextToken"] is None


def test_list_summary_shape():
    first = client.post("/ListEntities", json=dict(CATALOG, MaxResults=1)).json()
    item = first["EntitySummaryList"][0]
    for key in ("EntityId", "EntityType", "EntityArn", "Name", "LastModifiedDate", "Visibility"):
        assert key in item
    assert first["NextToken"] is not None


def test_list_wrong_catalog_is_422():
    r = client.post("/ListEntities", json={"Catalog": "Other", "EntityType": "SaaSProduct"})
    assert r.status_code == 422


def test_describe_returns_sku_gtin_price():
    body = describe("AWSMP-BW-0002").json()
    assert body["EntityIdentifier"] == "AWSMP-BW-0002@1"
    assert body["EntityType"] == "SaaSProduct@1.0"
    d = details_of("AWSMP-BW-0002")
    assert d["Sku"] == "AWSMP-BW-0002"
    assert d["ListPrice"] == "6.49"
    assert len(d["Gtin"]) == 13
    assert d["HarmonizedSku"] is None
    assert body["DetailsDocument"] == d


def test_missing_gtin_product_has_null_gtin():
    assert details_of("AWSMP-PF-0001")["Gtin"] is None


def test_malformed_gtin_product_has_twelve_digits():
    assert len(details_of("AWSMP-PF-0002")["Gtin"]) == 12


def test_start_change_set_updates_price_and_harmonized_sku():
    change = {
        "Catalog": "AWSMarketplace",
        "ChangeSet": [{
            "ChangeType": "UpdateInformation",
            "Entity": {"Identifier": "AWSMP-BW-0002@1", "Type": "SaaSProduct@1.0"},
            "Details": json.dumps({"ListPrice": "5.99", "HarmonizedSku": "CPG-00100200"}),
        }],
    }
    r = client.post("/StartChangeSet", json=change)
    assert r.status_code == 200
    assert set(r.json()) == {"ChangeSetId", "ChangeSetArn"}
    d = details_of("AWSMP-BW-0002")
    assert d["ListPrice"] == "5.99"
    assert d["HarmonizedSku"] == "CPG-00100200"


def test_start_change_set_unknown_entity_is_404_and_changes_nothing():
    change = {
        "Catalog": "AWSMarketplace",
        "ChangeSet": [{
            "ChangeType": "UpdateInformation",
            "Entity": {"Identifier": "nope@1", "Type": "SaaSProduct@1.0"},
            "Details": json.dumps({"ListPrice": "1.00"}),
        }],
    }
    assert client.post("/StartChangeSet", json=change).status_code == 404


def test_start_change_set_rejects_bad_price():
    change = {
        "Catalog": "AWSMarketplace",
        "ChangeSet": [{
            "ChangeType": "UpdateInformation",
            "Entity": {"Identifier": "AWSMP-BW-0002", "Type": "SaaSProduct@1.0"},
            "Details": json.dumps({"ListPrice": "-3"}),
        }],
    }
    assert client.post("/StartChangeSet", json=change).status_code == 422
    assert details_of("AWSMP-BW-0002")["ListPrice"] == "6.49"


def test_describe_unknown_entity_is_404():
    assert describe("does-not-exist").status_code == 404


def test_reset_restores_seed():
    client.post("/StartChangeSet", json={
        "Catalog": "AWSMarketplace",
        "ChangeSet": [{
            "ChangeType": "UpdateInformation",
            "Entity": {"Identifier": "AWSMP-BW-0002", "Type": "SaaSProduct@1.0"},
            "Details": json.dumps({"ListPrice": "1.11", "HarmonizedSku": "X"}),
        }],
    })
    client.post("/admin/reset")
    d = details_of("AWSMP-BW-0002")
    assert d["ListPrice"] == "6.49" and d["HarmonizedSku"] is None
