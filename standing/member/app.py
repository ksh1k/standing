"""Member agent FastAPI service — healthz + evaluate stub (Phase 2).

Bind intent: localhost only (constraint 6). Example:
  uvicorn standing.member.app:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from standing.negotiation.member_eval import evaluate

app = FastAPI(title="Standing Member Agent", version="0.2.0")

# Process-local bitmap for demo evaluate route only (never sent to coordinator DB).
_LOCAL_AVAILABILITY: str | None = None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "member"}


class SetAvailabilityRequest(BaseModel):
    availability: str = Field(..., min_length=224, max_length=224)


class EvaluateRequest(BaseModel):
    start_slot: int
    # Optional one-shot bitmap; otherwise uses process-local store.
    availability: str | None = Field(default=None, min_length=224, max_length=224)


@app.post("/availability")
def set_availability(body: SetAvailabilityRequest) -> dict[str, str]:
    global _LOCAL_AVAILABILITY
    _LOCAL_AVAILABILITY = body.availability
    return {"status": "ok"}


@app.post("/evaluate")
def evaluate_slot(body: EvaluateRequest) -> dict[str, Any]:
    bitmap = body.availability if body.availability is not None else _LOCAL_AVAILABILITY
    if bitmap is None:
        return {"error": "no availability set"}
    verdict = evaluate(body.start_slot, bitmap)
    return {"verdict": verdict.as_dict()}
