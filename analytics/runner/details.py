"""The rows behind the data-quality counts: which products drifted, by how much, and which
AWS Marketplace listings no golden record claims.

Reads the dbt marts the runner has just built (schema `harm`). Read-only. A failure here must never
fail a run: the caller treats it as "no details".
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

# Keep in step with tolerance_pct in analytics/models/schema.yml (price_drift_between_channels).
TOLERANCE_PCT = 1

DRIFT_SQL = """
select v.gtin, g.name, v.source, v.channel_price, v.golden_price, v.variance_pct
from harm.fct_price_variance v
join harm.stg_golden_products g on g.gtin = v.gtin
where abs(v.channel_price - v.golden_price) > v.golden_price * %s / 100.0
order by abs(v.variance_pct) desc, v.gtin
"""

UNMATCHED_SQL = """
select source_key, gtin, name, price
from harm.fct_unmatched_products
order by source_key
"""


class NotConfigured(RuntimeError):
    pass


def _connect():
    settings = {}
    for name in ("WAREHOUSE_HOST", "WAREHOUSE_PORT", "WAREHOUSE_DB", "WAREHOUSE_USER", "WAREHOUSE_PASSWORD"):
        value = os.environ.get(name, "")
        if not value:
            raise NotConfigured("%s is not set in the runner's environment." % name)
        settings[name] = value
    import psycopg2  # installed with dbt-postgres; imported here so the unit tests need not have it

    return psycopg2.connect(
        host=settings["WAREHOUSE_HOST"], port=int(settings["WAREHOUSE_PORT"]), dbname=settings["WAREHOUSE_DB"],
        user=settings["WAREHOUSE_USER"], password=settings["WAREHOUSE_PASSWORD"], connect_timeout=10,
    )


def _text(value) -> Optional[str]:
    return None if value is None else str(value)


def fetch_details() -> Dict[str, List[Dict]]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(DRIFT_SQL, (TOLERANCE_PCT,))
        drift = [
            {"gtin": _text(r[0]), "name": _text(r[1]), "channel": _text(r[2]), "channel_price": _text(r[3]),
             "golden_price": _text(r[4]), "variance_pct": _text(r[5])}
            for r in cur.fetchall()
        ]
        cur.execute(UNMATCHED_SQL)
        unmatched = [
            {"aws_sku": _text(r[0]), "gtin": _text(r[1]), "name": _text(r[2]), "price": _text(r[3])}
            for r in cur.fetchall()
        ]
        cur.close()
        return {"price_drift": drift, "unmatched_listings": unmatched}
    finally:
        conn.close()
