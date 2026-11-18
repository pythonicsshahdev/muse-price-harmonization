"""Runs dbt + Elementary against the harmonization warehouse and serves the results.

Muse never talks to this directly: the Boomi process `HARM - Run Harmonization`
calls POST /run, and `HARM - Show Elementary Results API` calls GET /results.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

PROJECT_DIR = Path(os.environ.get("DBT_PROJECT_DIR", "/app"))
RUN_RESULTS = PROJECT_DIR / "target" / "run_results.json"
REPORT = PROJECT_DIR / "edr_target" / "elementary_report.html"
REPORT_BASE_URL = os.environ.get("REPORT_BASE_URL", "http://localhost:4121")

app = FastAPI(title="Harmonization analytics runner")
_lock = threading.Lock()
_latest: dict | None = None


def _sh(cmd):
    return subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)


def _tail(proc) -> str:
    return (proc.stderr or proc.stdout or "").strip()[-500:]


def _summarize() -> dict:
    results = json.loads(RUN_RESULTS.read_text())["results"]
    passed = [r for r in results if r["status"] == "pass"]
    failed = [r for r in results if r["status"] in ("fail", "error")]
    return {
        "status": "ok",
        "tests_passed": len(passed),
        # Rows flagged, not test count: one price test failing for 3 GTINs is 3.
        "tests_failed": sum(r.get("failures") or 1 for r in failed),
        "failing": [r["unique_id"].split(".")[2] for r in failed],
        "report_url": f"{REPORT_BASE_URL}/report",
    }


@app.post("/run")
def run():
    global _latest
    if not _lock.acquire(blocking=False):
        return JSONResponse({"status": "in_progress"}, status_code=409)
    try:
        for cmd in (["dbt", "run"], ["dbt", "test"], ["edr", "report", "--file-path", str(REPORT)]):
            proc = _sh(cmd)
            # dbt test exits non-zero when a test fails, which is the point of the demo.
            if proc.returncode != 0 and cmd[:2] != ["dbt", "test"]:
                _latest = {"status": "failed", "error": _tail(proc)}
                return _latest
        try:
            _latest = _summarize()
        except (OSError, KeyError, ValueError) as exc:
            _latest = {"status": "failed", "error": f"no dbt test results: {exc}"}
        return _latest
    finally:
        _lock.release()


@app.get("/results")
def results():
    if _latest is None:
        return JSONResponse({"message": "No run yet. POST /run first."}, status_code=404)
    return _latest


@app.get("/report")
def report():
    if not REPORT.exists():
        return JSONResponse({"message": "No report yet. POST /run first."}, status_code=404)
    return FileResponse(REPORT, media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok"}
