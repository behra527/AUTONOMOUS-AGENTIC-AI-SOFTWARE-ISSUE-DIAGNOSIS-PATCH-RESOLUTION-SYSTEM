$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (!(Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv }
& .venv/Scripts/python -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$env:PYTHONPATH = 'apps/api'
& .venv/Scripts/python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& .venv/Scripts/python -m app.seed
if ($LASTEXITCODE -ne 0) { throw 'Demo seeding failed' }
Push-Location apps/web
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Web build failed' }
} finally { Pop-Location }
Write-Host 'Ready. Run ./scripts/start.ps1'
