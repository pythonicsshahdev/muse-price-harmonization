"""Resolve the warehouse connection, then start the runner.

WAREHOUSE=rds (default) reads the RDS_POSTGRES_* keys from .env; WAREHOUSE=local
reads the local container's POSTGRES_* keys. The JDBC URL is parsed so the host,
port and database are kept in one place.
"""
import os
import re
import sys


def resolve(env):
    if env.get("WAREHOUSE", "rds") == "local":
        return {
            "WAREHOUSE_HOST": env.get("LOCAL_POSTGRES_HOST", "postgres"),
            "WAREHOUSE_PORT": "5432",
            "WAREHOUSE_DB": env["POSTGRES_DB"],
            "WAREHOUSE_USER": env["POSTGRES_USER"],
            "WAREHOUSE_PASSWORD": env["POSTGRES_PASSWORD"],
        }
    match = re.match(r"jdbc:postgresql://([^:/]+)(?::(\d+))?/([^?]+)", env["RDS_POSTGRES_JDBC_URL"])
    if not match:
        sys.exit("RDS_POSTGRES_JDBC_URL is not a jdbc:postgresql:// URL")
    return {
        "WAREHOUSE_HOST": match.group(1),
        "WAREHOUSE_PORT": match.group(2) or "5432",
        "WAREHOUSE_DB": match.group(3),
        "WAREHOUSE_USER": env["RDS_POSTGRES_USERNAME"],
        "WAREHOUSE_PASSWORD": env["RDS_POSTGRES_PASSWORD"],
    }


if __name__ == "__main__":
    os.environ.update(resolve(os.environ))
    os.execvp("uvicorn", ["uvicorn", "app:app", "--app-dir", "runner", "--host", "0.0.0.0", "--port", "4021"])
