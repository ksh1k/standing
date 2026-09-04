"""Coordinator FastAPI stub — healthz only in Phase 1.

Bind intent: localhost only (constraint 6). Example:
  uvicorn standing.coordinator.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Standing Coordinator", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "coordinator"}
