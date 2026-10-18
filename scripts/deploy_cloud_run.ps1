param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [Parameter(Mandatory = $true)][string]$ServiceAccount,
    [string]$Service = 'document-intelligence-pilot',
    [string]$Region = 'asia-south1',
    [string]$SecretName = 'openai-api-key',
    [string]$SecretVersion = '1'
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw 'Google Cloud CLI is required. Use Cloud Shell or install gcloud first.'
}

# Prerequisites are intentionally checked instead of silently creating billable resources.
& gcloud firestore databases describe '--database=(default)' "--project=$ProjectId" '--format=value(name)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Create the default Firestore Native database first.' }
& gcloud secrets describe $SecretName "--project=$ProjectId" '--format=value(name)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Create the OpenAI key in Secret Manager first.' }

$deployArgs = @(
    'run', 'deploy', $Service,
    '--source=.', "--project=$ProjectId", "--region=$Region",
    '--no-allow-unauthenticated',
    '--memory=4Gi', '--cpu=2', '--timeout=900', '--concurrency=1',
    '--min-instances=0', '--max-instances=2',
    '--set-env-vars=BUDGET_BACKEND=firestore,PILOT_SCOPE=demo',
    "--set-secrets=OPENAI_API_KEY=${SecretName}:${SecretVersion}",
    "--service-account=$ServiceAccount"
)
& gcloud @deployArgs
if ($LASTEXITCODE -ne 0) { throw 'Cloud Run deployment failed.' }
& gcloud run services describe $Service "--project=$ProjectId" "--region=$Region" '--format=value(status.url)'
