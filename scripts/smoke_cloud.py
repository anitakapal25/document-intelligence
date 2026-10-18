"""Validate the four demo PDFs on private Cloud Run (uses authenticated gcloud).

Run before enabling IAP; tokens stay in memory, never in files or printed output.
This performs paid extraction calls and saves results under ignored outputs/.
"""

import argparse
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent


def request(url, token=None, data=None, content_type=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=920) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    if not base.startswith("https://") or not base.endswith(".run.app"):
        raise ValueError("Expected an HTTPS Cloud Run service URL")
    output = ROOT / "outputs/cloud_smoke"
    output.mkdir(parents=True, exist_ok=True)
    token = subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()
    unauth, _ = request(base + "/health")
    assert unauth in (401, 403), f"Unexpected unauthenticated status: {unauth}"
    code, body = request(base + "/health", token)
    assert code == 200 and json.loads(body)["status"] == "ok"
    code, body = request(base + "/scope", token)
    assert code == 200 and json.loads(body)["scope"] == "demo"
    contracts = json.loads((ROOT / "configs/allowed_demo_pdfs.json").read_text())["contracts"]
    assert set(json.loads(body)["documents"]) == {item["document_id"] for item in contracts}
    api = "https://huggingface.co/api/datasets/theatticusproject/cuad/tree/main/CUAD_v1/full_contract_pdf?recursive=true&limit=1000"
    code, body = request(api)
    assert code == 200
    paths = {Path(item["path"]).stem.casefold(): item["path"] for item in json.loads(body)}
    summary = {"url": base, "unauthenticated_status": unauth, "runs": []}
    for item in contracts:
        document_id = item["document_id"]
        if document_id == "synthetic-sample-agreement":
            code, pdf = request(base + "/sample.pdf", token)
        else:
            path = paths[document_id.casefold()]
            code, pdf = request("https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/" + quote(path, safe="/"))
        assert code == 200 and hashlib.sha256(pdf).hexdigest() == item["sha256"]
        boundary = uuid.uuid4().hex
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo.pdf"\r\n'
                   'Content-Type: application/pdf\r\n\r\n').encode() + pdf + f"\r\n--{boundary}--\r\n".encode()
        started = time.perf_counter()
        code, body = request(base + "/extract", token, payload, f"multipart/form-data; boundary={boundary}")
        seconds = round(time.perf_counter() - started, 2)
        result = json.loads(body)
        (output / f"{item['sha256']}.json").write_text(json.dumps(result, indent=2) + "\n")
        summary["runs"].append({"document_id": document_id, "http_status": code,
                                "status": result.get("status"), "elapsed_seconds": seconds,
                                "metadata": result.get("metadata"), "error_code": result.get("error_code")})
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"{document_id}: HTTP {code}, {result.get('status')}, {seconds}s", flush=True)
    assert all(row["http_status"] == 200 and row["status"] == "completed" for row in summary["runs"])
    print("All four demo PDFs completed; unauthenticated access rejected.")


if __name__ == "__main__":
    main()
