"""One real local upload through the same FastAPI route as the browser page."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import app


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    path = ROOT / "data/synthetic/sample_agreement.pdf"
    with TestClient(app) as client, path.open("rb") as source:
        response = client.post("/extract", files={"file": (path.name, source, "application/pdf")})
    output = ROOT / "outputs/api_smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(response.json(), indent=2) + "\n", encoding="utf-8")
    print(f"HTTP {response.status_code}; saved {output}")
    if response.status_code != 200:
        raise SystemExit(1)
    print(f"Run status: {response.json()['status']}")


if __name__ == "__main__":
    main()
