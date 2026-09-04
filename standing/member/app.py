"""Member agent FastAPI stub — healthz only in Phase 1.

Bind intent: localhost only (constraint 6). Example:
  uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Standing Member Agent", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "member"}
