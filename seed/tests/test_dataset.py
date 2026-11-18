from decimal import Decimal

from seed.dataset import (
    canonical_sku,
    expected_matched,
    expected_price_drift,
    expected_unmatched,
    load_products,
)


def test_twelve_products_unique_gtins():
    products = load_products()
    assert len(products) == 12
    gtins = [p.gtin for p in products]
    assert len(set(gtins)) == 12
    assert all(len(g) == 13 and g.isdigit() for g in gtins)
    shopify_skus = [p.shopify_sku for p in products]
    assert len(set(shopify_skus)) == 12


def test_canonical_sku_rule():
    assert canonical_sku("0012345678905") == "CPG-45678905"
    assert canonical_sku("0012345678905", prefix="MFG") == "MFG-45678905"


def test_canonical_sku_unique_across_products():
    skus = [canonical_sku(p.gtin) for p in load_products()]
    assert len(set(skus)) == 12


def test_expected_matched_is_ten():
    products = load_products()
    matched = expected_matched(products)
    assert len(matched) == 10
    assert set(matched) <= {p.gtin for p in products}


def test_expected_unmatched_is_two_aws_skus():
    products = load_products()
    unmatched = expected_unmatched(products)
    assert len(unmatched) == 2
    by_sku = {p.aws_sku: p for p in products}
    kinds = sorted(
        "missing" if by_sku[s].aws_gtin is None else "malformed" for s in unmatched
    )
    assert kinds == ["malformed", "missing"]
    malformed = next(by_sku[s] for s in unmatched if by_sku[s].aws_gtin is not None)
    assert len(malformed.aws_gtin) == 12


def test_expected_price_drift_is_three():
    products = load_products()
    drift = expected_price_drift(products)
    assert len(drift) == 3
    by_gtin = {p.gtin: p for p in products}
    for g in drift:
        assert by_gtin[g].aws_price != by_gtin[g].shopify_price
    assert set(drift) <= set(expected_matched(products))


def test_unmatched_products_also_differ_in_price_but_are_not_drift():
    products = load_products()
    unmatched = set(expected_unmatched(products))
    differing = [p for p in products if p.aws_sku in unmatched and p.aws_price != p.shopify_price]
    assert len(differing) == 2
    assert not set(expected_price_drift(products)) & {p.gtin for p in differing}


def test_two_products_have_name_variants():
    variants = [p for p in load_products() if p.aws_name != p.name]
    assert len(variants) == 2


def test_prices_are_two_decimal_decimals():
    for p in load_products():
        for price in (p.shopify_price, p.aws_price):
            assert isinstance(price, Decimal)
            assert price == price.quantize(Decimal("0.01"))
            assert price > 0
