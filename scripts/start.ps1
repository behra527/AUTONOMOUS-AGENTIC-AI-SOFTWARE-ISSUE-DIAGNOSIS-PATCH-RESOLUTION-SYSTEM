$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = 'apps/api'
if (!(Test-Path '.venv/Scripts/python.exe')) { throw 'Run scripts/setup.ps1 first.' }
if (!(Test-Path 'apps/web/dist/index.html')) { throw 'Build the web portal first: cd apps/web; npm run build' }
& .venv/Scripts/python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
$worker = Start-Process -FilePath '.venv/Scripts/python.exe' -ArgumentList '-m','app.worker' -WindowStyle Hidden -PassThru
try {
    Write-Host 'BugHound-Ai: http://127.0.0.1:8000 | API docs: http://127.0.0.1:8000/docs'
    & .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally {
    if (!$worker.HasExited) { Stop-Process -Id $worker.Id }
}
