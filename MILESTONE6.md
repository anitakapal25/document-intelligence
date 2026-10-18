# Milestone 6: private upload API and deployment package

The API serves `GET /health`, `POST /extract`, and an upload page at `/`. The page calls the same extraction endpoint that future agents can call. `POST /extract` returns the five Pydantic fields with status, value, and quotations; each PDF quotation carries a parser-reported page. A completed run returns HTTP 200; malformed and out-of-scope files, parser errors, refusal, extraction failure, and exhausted estimated budget return explicit status codes and error bodies.

The pilot accepts one PDF up to 10 MiB, checks its extension, content type, `%PDF-` header, and exact SHA-256 against `configs/allowed_pdfs.json`. That allowlist contains the 20 selected development CUAD PDFs and one synthetic PDF. It does not accept arbitrary customer contracts yet. Raw uploads live in a temporary directory only during processing and are deleted before the response. No cloud input or result retention is enabled, so object storage is not required for this pilot; add Cloud Storage before introducing retention. Logs contain the PDF hash, status, timing, and token counts, never contract text or quotations. Local benchmark DuckDB is not used by the Cloud Run app.

The estimated $5/month OpenAI guard reserves $0.325 before each call, then settles to the measured token estimate for a completed run. Unknown usage keeps the full reservation. The estimate uses the [official GPT-6 Luna Standard short-context rates](https://developers.openai.com/api/docs/models/gpt-6-luna) of $0.10/M input and $0.50/M output tokens. On Cloud Run, `BUDGET_BACKEND=firestore` uses Firestore transactions so concurrent instances share the same ledger. Local development uses a single-process in-memory ledger. This controls an **estimated application allowance**, not total cloud/provider billing; set Google Cloud and provider billing alerts separately. Firestore integration cannot be live-tested without a project.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` for the upload page or `http://127.0.0.1:8080/docs` for API documentation. Upload `data/synthetic/sample_agreement.pdf` or a development PDF from `data/raw/cuad_pdfs/development/`. Keep `OPENAI_API_KEY` in the Git-ignored `.env` file. The UI shows and lets you download the JSON; it may take a few minutes because Docling and the model run synchronously. The synthetic PDF passed a real API upload: HTTP 200, status `completed`; the name, parties, and agreement date had page-1 evidence, the ambiguous effective date and governing law had page-2 evidence. The saved result is ignored `outputs/api_smoke.json`.

The first measured real development PDF took roughly 92 seconds to parse and 55 seconds for model calls on this machine. The later held-out PDF benchmark reached 1,216 seconds locally, exceeding the proposed 900-second Cloud Run timeout. The current synchronous setup is not validated for that broader workload. Add durable asynchronous jobs before claiming broad PDF support in the cloud, or independently validate a narrower bounded input scope on the hosted service. Local timing includes model loading and possible first-use downloads; it is not a Cloud Run latency result.

## Container

The `Dockerfile` installs only runtime dependencies, CPU PyTorch, and Docling PDF models; `.dockerignore` excludes secrets, raw data, outputs, and Git history. When Docker Desktop's engine is running:

```powershell
docker build -t document-intelligence-pilot .
docker run --rm -p 8080:8080 --env-file .env document-intelligence-pilot
```

Then check `http://127.0.0.1:8080/health` and upload the synthetic PDF. The Docker CLI is present here, but the Docker engine was not running, so image build and container smoke test remain unverified.

## Private Cloud Run deployment

Readiness check (2026-10-18): confirmed project `tidal-anvil-286512` (My First Project). The console displays a linked billing account, but opening it redirects to signup and the billing-account list asks to add an account. Active billing needs owner verification. Cloud Shell remained blank after a reload; local `gcloud` is unavailable. No cloud resources were created.

Added `.gcloudignore` with a runtime-only upload allowlist; verify with `gcloud meta list-files-for-upload` when the CLI is available. API error logs now omit exception contents and tracebacks. All 27 local tests pass, and `python -m scripts.freeze_pilot` verifies the unchanged extraction freeze.

Cloud Run deployment is **pending** a Google Cloud project with billing, the Google Cloud CLI or Cloud Shell, a default Firestore Native database, a service account with Firestore access, and an OpenAI key in Secret Manager. The CLI is not installed in this Windows environment. The deployment script checks Firestore and Secret Manager prerequisites before deploying; it does not create them silently. Region is `asia-south1` (Mumbai).

Prepare the Google Cloud project:

1. Enable Cloud Run, Cloud Build, Artifact Registry, Firestore, and Secret Manager APIs. Create the default Firestore Native database in Mumbai. Its location choice persists, so check the project before creating it.
2. Create a dedicated Cloud Run service account. Grant it Firestore `roles/datastore.user` and Secret Manager Secret Accessor on the OpenAI secret. Store the key as secret `openai-api-key`, version 1; do not put it in a shell command, repository, or image.
3. With `gcloud` authenticated to the intended project, run:

```powershell
.\scripts\deploy_cloud_run.ps1 -ProjectId YOUR_PROJECT_ID -ServiceAccount document-intelligence-run@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

The script deploys from the Dockerfile with 2 CPU, 4 GiB memory, one concurrent request per instance, at most two instances, a 900-second timeout, and IAM authentication required. The deployed app uses Firestore for the shared usage ledger and Secret Manager for the key. [Cloud Run source deployment](https://docs.cloud.google.com/run/docs/deploying-source-code), [service secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets), and [Firestore transactions](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions) describe those mechanisms.

For a browser page at the Cloud Run URL, enable [IAP directly on the Cloud Run service](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run) and grant only your Google account access. Initial IAP setup for a personal project may require the Cloud Console. Alternatively, use the authenticated [Cloud Run proxy](https://docs.cloud.google.com/run/docs/authenticating/developers) from Cloud Shell or WSL and open its local URL. Plain browser login to Google does not itself authenticate to a private Cloud Run IAM endpoint. Portfolio visitors should use a recorded demo rather than this private service.

Before calling Milestone 6 deployed, build the image, verify `/health` and one controlled upload in the private service, and confirm the Firestore ledger is written. These checks need the project and running Docker or Cloud Build access.

Python/PHP/JS comparison: FastAPI's `UploadFile` is like a PHP uploaded-file object or a JS multipart `File`. Pydantic validates the response shape; exact evidence checks still happen in the frozen extractor. The Firestore transaction is like an atomic database transaction protecting a shared monthly counter across API workers.
