import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import entrypoint  # noqa: E402


def test_rds_url_is_parsed_into_host_port_db():
    env = {
        "RDS_POSTGRES_JDBC_URL": "jdbc:postgresql://db.example.com:5432/demo?tcpKeepAlive=true",
        "RDS_POSTGRES_USERNAME": "u",
        "RDS_POSTGRES_PASSWORD": "p",
    }
    out = entrypoint.resolve(env)
    assert (out["WAREHOUSE_HOST"], out["WAREHOUSE_PORT"], out["WAREHOUSE_DB"]) == ("db.example.com", "5432", "demo")
    assert (out["WAREHOUSE_USER"], out["WAREHOUSE_PASSWORD"]) == ("u", "p")


def test_local_mode_uses_the_container_keys():
    env = {"WAREHOUSE": "local", "POSTGRES_DB": "d", "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p"}
    out = entrypoint.resolve(env)
    assert out["WAREHOUSE_HOST"] == "postgres" and out["WAREHOUSE_DB"] == "d"
