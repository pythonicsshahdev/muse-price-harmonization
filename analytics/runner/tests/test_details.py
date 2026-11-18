from decimal import Decimal

import details


class FakeCursor:
    def __init__(self, results):
        self.results = results
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append(sql)

    def fetchall(self):
        return self.results.pop(0)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, results):
        self.cursor_obj = FakeCursor(results)

    def cursor(self):
        return self.cursor_obj

    def close(self):
        pass


def test_rows_are_turned_into_plain_text_values(monkeypatch):
    drift = [("0812345001020", "Sparkling Water Berry 12-Pack", "aws_marketplace", Decimal("6.49"), Decimal("5.99"), Decimal("8.35"))]
    unmatched = [("AWSMP-PF-0001", None, "Protein Bar Chocolate 12-Count", Decimal("15.49"))]
    conn = FakeConnection([drift, unmatched])
    monkeypatch.setattr(details, "_connect", lambda: conn)
    out = details.fetch_details()
    assert out["price_drift"] == [{"gtin": "0812345001020", "name": "Sparkling Water Berry 12-Pack",
                                   "channel": "aws_marketplace", "channel_price": "6.49",
                                   "golden_price": "5.99", "variance_pct": "8.35"}]
    assert out["unmatched_listings"] == [{"aws_sku": "AWSMP-PF-0001", "gtin": None,
                                          "name": "Protein Bar Chocolate 12-Count", "price": "15.49"}]


def test_drift_query_uses_the_same_tolerance_as_the_dbt_test():
    assert details.TOLERANCE_PCT == 1
    assert "harm.fct_price_variance" in details.DRIFT_SQL
    assert "harm.fct_unmatched_products" in details.UNMATCHED_SQL


def test_missing_warehouse_settings_say_which_one(monkeypatch):
    monkeypatch.delenv("WAREHOUSE_HOST", raising=False)
    try:
        details._connect()
    except details.NotConfigured as exc:
        assert "WAREHOUSE_HOST" in str(exc)
    else:
        raise AssertionError("expected NotConfigured")
