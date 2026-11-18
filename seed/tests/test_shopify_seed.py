import json
from decimal import Decimal

import pytest
import responses

from seed import shopify_seed
from seed.dataset import load_products
from seed.envfile import MissingConfig

DOMAIN = "test-shop.myshopify.com"
BASE = "https://%s/admin/api/2026-10" % DOMAIN
TOKEN_URL = "https://%s/admin/oauth/access_token" % DOMAIN
PRODUCTS_URL = BASE + "/products.json"
TAG = "harmonization-poc"


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", DOMAIN)
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("SHOPIFY_API_VERSION", "2026-10")
    shopify_seed._reset_token_cache()


def token_ok():
    responses.add(responses.POST, TOKEN_URL,
                  json={"access_token": "tok", "scope": "write_products", "expires_in": 86399})


def shop_product(i, p, tags=TAG, price=None, title=None):
    return {"id": 1000 + i, "title": title or p.name, "tags": tags,
            "variants": [{"id": 2000 + i, "sku": p.shopify_sku, "barcode": p.gtin,
                          "price": str(price or p.shopify_price)}]}


def listing(items):
    responses.add(responses.GET, PRODUCTS_URL, json={"products": items})


def calls_to(method):
    return [c for c in responses.calls if c.request.method == method and "oauth" not in c.request.url]


@responses.activate
def test_seed_is_idempotent_by_barcode():
    token_ok()
    products = load_products()
    listing([shop_product(i, p) for i, p in enumerate(products)])
    assert shopify_seed.seed_store(products) == 12
    assert calls_to("POST") == []


@responses.activate
def test_seed_creates_missing_products_with_tag():
    token_ok()
    products = load_products()
    listing([shop_product(i, p) for i, p in enumerate(products[:-1])])
    responses.add(responses.POST, PRODUCTS_URL, json={"product": {"id": 1}}, status=201)
    assert shopify_seed.seed_store(products) == 12
    posts = calls_to("POST")
    assert len(posts) == 1
    body = json.loads(posts[0].request.body)["product"]
    last = products[-1]
    assert TAG in body["tags"]
    assert body["variants"][0]["sku"] == last.shopify_sku
    assert body["variants"][0]["barcode"] == last.gtin
    assert body["variants"][0]["price"] == str(last.shopify_price)


@responses.activate
def test_lists_all_pages_via_link_header():
    token_ok()
    products = load_products()
    next_url = PRODUCTS_URL + "?page_info=abc&limit=250"
    responses.add(responses.GET, PRODUCTS_URL, match_querystring=False,
                  json={"products": [shop_product(i, p) for i, p in enumerate(products[:6])]},
                  headers={"Link": '<%s>; rel="next"' % next_url})
    responses.add(responses.GET, next_url,
                  json={"products": [shop_product(i + 6, p) for i, p in enumerate(products[6:])]})
    assert shopify_seed.seed_store(products) == 12
    assert calls_to("POST") == []


@pytest.mark.parametrize("bad", [Decimal("0"), Decimal("-1"), Decimal("1.234"), "abc"])
@responses.activate
def test_set_price_rejects_zero_negative_and_three_decimals(bad):
    with pytest.raises(ValueError):
        shopify_seed.set_price(load_products()[0].gtin, bad)
    assert len(responses.calls) == 0


@responses.activate
def test_set_price_unknown_gtin_raises_lookup_error():
    token_ok()
    listing([])
    with pytest.raises(LookupError):
        shopify_seed.set_price("0000000000000", Decimal("9.99"))


@responses.activate
def test_set_price_updates_the_variant():
    token_ok()
    p = load_products()[1]
    listing([shop_product(1, p)])
    responses.add(responses.PUT, BASE + "/variants/2001.json", json={"variant": {"id": 2001}})
    shopify_seed.set_price(p.gtin, Decimal("9.99"))
    put = calls_to("PUT")[0]
    assert json.loads(put.request.body) == {"variant": {"id": 2001, "price": "9.99"}}


@responses.activate
def test_retries_on_429_honoring_retry_after(monkeypatch):
    token_ok()
    slept = []
    monkeypatch.setattr(shopify_seed.time, "sleep", lambda s: slept.append(s))
    responses.add(responses.GET, PRODUCTS_URL, status=429, headers={"Retry-After": "2.0"})
    responses.add(responses.GET, PRODUCTS_URL, json={"products": []})
    assert shopify_seed.check_store(load_products())["count"] == 0
    assert slept == [2.0]


@pytest.mark.parametrize("key", ["SHOPIFY_CLIENT_SECRET", "SHOPIFY_CLIENT_ID", "SHOPIFY_STORE_DOMAIN"])
def test_missing_env_key_names_the_key(monkeypatch, key):
    monkeypatch.delenv(key)
    with pytest.raises(MissingConfig) as exc:
        shopify_seed.get_token()
    assert key in str(exc.value)


@responses.activate
def test_token_cached_and_refreshed_before_expiry(monkeypatch):
    token_ok()
    clock = {"now": 1000.0}
    monkeypatch.setattr(shopify_seed.time, "time", lambda: clock["now"])
    assert shopify_seed.get_token() == "tok"
    clock["now"] += 100
    shopify_seed.get_token()
    assert len([c for c in responses.calls if "oauth" in c.request.url]) == 1
    clock["now"] = 1000.0 + 86399 - 30  # inside the 60 second safety margin
    shopify_seed.get_token()
    assert len([c for c in responses.calls if "oauth" in c.request.url]) == 2


@responses.activate
def test_never_modifies_untagged_products():
    token_ok()
    p = load_products()[2]
    listing([shop_product(2, p, tags="someone-elses", price=Decimal("99.00"), title="Not ours")])
    shopify_seed.reset_store([p])
    with pytest.raises(LookupError):
        shopify_seed.set_price(p.gtin, Decimal("1.00"))
    assert calls_to("PUT") == []
    assert calls_to("POST") == []


@responses.activate
def test_reset_restores_seed_price_and_name():
    token_ok()
    p = load_products()[3]
    listing([shop_product(3, p, price=Decimal("1.11"), title="Renamed by someone")])
    responses.add(responses.PUT, BASE + "/variants/2003.json", json={})
    responses.add(responses.PUT, BASE + "/products/1003.json", json={})
    shopify_seed.reset_store([p])
    bodies = {c.request.url.rsplit("/", 2)[-2]: json.loads(c.request.body) for c in calls_to("PUT")}
    assert bodies["variants"] == {"variant": {"id": 2003, "price": str(p.shopify_price)}}
    assert bodies["products"] == {"product": {"id": 1003, "title": p.name}}


@responses.activate
def test_check_store_reports_count_and_price_match():
    token_ok()
    products = load_products()
    items = [shop_product(i, p) for i, p in enumerate(products)]
    items[0]["variants"][0]["price"] = "0.01"
    listing(items)
    result = shopify_seed.check_store(products)
    assert result == {"count": 12, "prices_match_seed": False}
