"""Boot coordinator UI + demo APIs on 127.0.0.1:8000.  python -m standing.demo_server"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("STANDING_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))

from standing.coordinator.app import app  # noqa: E402

__all__ = ["app"]


def main() -> None:
    import uvicorn

    uvicorn.run("standing.demo_server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
