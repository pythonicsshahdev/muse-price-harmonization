import json
import subprocess

import pytest
from fastapi.testclient import TestClient

import app as runner


def _result(unique_id, status, failures=0):
    return {"unique_id": unique_id, "status": status, "failures": failures}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUN_RESULTS", tmp_path / "run_results.json")
    monkeypatch.setattr(runner, "REPORT", tmp_path / "elementary_report.html")
    monkeypatch.setattr(runner, "_latest", None)
    monkeypatch.setattr(runner.details, "fetch_details", lambda: {"price_drift": [], "unmatched_listings": []})
    return TestClient(runner.app)


def _fake_dbt(run_results, report_html="<html>report</html>"):
    def fake(cmd, **kwargs):
        if cmd[0] == "dbt" and cmd[1] == "test":
            runner.RUN_RESULTS.write_text(json.dumps({"results": run_results}))
        if cmd[0] == "edr":
            runner.REPORT.write_text(report_html)
        # dbt test exits non-zero when tests fail; the runner must not treat that as a crash
        code = 1 if cmd[:2] == ["dbt", "test"] and any(r["status"] == "fail" for r in run_results) else 0
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="")
    return fake


def test_run_returns_counts_from_dbt_output(client, monkeypatch):
    results = [
        _result("test.harm.not_null_golden_gtin", "pass"),
        _result("test.harm.unique_golden_gtin", "pass"),
        _result("test.harm.price_within_tolerance_shopify", "fail", 3),
        _result("test.harm.unmatched_aws_products", "fail", 2),
    ]
    monkeypatch.setattr(runner.subprocess, "run", _fake_dbt(results))
    body = client.post("/run").json()
    assert body["status"] == "ok"
    assert body["tests_passed"] == 2
    assert body["tests_failed"] == 5  # failing rows: 3 price drifts + 2 unmatched
    assert body["report_url"].endswith("/report")
    assert client.get("/results").json()["failing"] == [
        "price_within_tolerance_shopify",
        "unmatched_aws_products",
    ]


def test_second_run_while_active_returns_409(client):
    assert runner._lock.acquire(blocking=False)
    try:
        response = client.post("/run")
    finally:
        runner._lock.release()
    assert response.status_code == 409
    assert response.json() == {"status": "in_progress"}


def test_results_before_any_run_is_404_with_message(client):
    response = client.get("/results")
    assert response.status_code == 404
    assert "no run" in response.json()["message"].lower()


def test_report_serves_html_when_present(client, monkeypatch):
    assert client.get("/report").status_code == 404
    monkeypatch.setattr(runner.subprocess, "run", _fake_dbt([_result("test.harm.t", "pass")]))
    client.post("/run")
    response = client.get("/report")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "report" in response.text


def test_dbt_run_crash_reports_failed(client, monkeypatch):
    def boom(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="connection refused")
    monkeypatch.setattr(runner.subprocess, "run", boom)
    body = client.post("/run").json()
    assert body["status"] == "failed"
    assert "connection refused" in body["error"]


def test_run_includes_the_flagged_rows(client, monkeypatch):
    flagged = {
        "price_drift": [{"gtin": "0812345001020", "name": "Sparkling Water Berry 12-Pack", "channel": "aws_marketplace",
                         "channel_price": "6.49", "golden_price": "5.99", "variance_pct": "8.35"}],
        "unmatched_listings": [{"aws_sku": "AWSMP-PF-0001", "name": "Protein Bar", "gtin": None, "price": "15.49"}],
    }
    monkeypatch.setattr(runner.details, "fetch_details", lambda: flagged)
    monkeypatch.setattr(runner.subprocess, "run", _fake_dbt([_result("test.harm.t", "pass")]))
    body = client.post("/run").json()
    assert body["details"] == flagged
    assert client.get("/results").json()["details"] == flagged


def test_a_details_problem_does_not_fail_the_run(client, monkeypatch):
    def boom():
        raise RuntimeError("database unreachable")
    monkeypatch.setattr(runner.details, "fetch_details", boom)
    monkeypatch.setattr(runner.subprocess, "run", _fake_dbt([_result("test.harm.t", "pass")]))
    body = client.post("/run").json()
    assert body["status"] == "ok"
    assert body["details"] is None
    assert "database unreachable" in body["details_error"]
