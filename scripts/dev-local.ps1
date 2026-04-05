param(
  [switch]$SkipTrainingDashboard
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "apps\\backend"
$pythonVenv = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$pythonCmd = if (Test-Path $pythonVenv) { $pythonVenv } else { "python" }

$backendCommand = @"
`$env:DATABASE_URL = 'sqlite:///./data/training.db'
`$env:TRAINING_DB_URL = 'sqlite:///./data/training.db'
`$env:REDIS_URL = 'redis://localhost:6379/0'
& '$pythonCmd' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"@

Start-Process powershell -WorkingDirectory $backendDir -ArgumentList @("-NoExit", "-Command", $backendCommand) | Out-Null
Start-Process powershell -WorkingDirectory $repoRoot -ArgumentList @("-NoExit", "-Command", "pnpm --filter web dev") | Out-Null

if (-not $SkipTrainingDashboard) {
  Start-Process powershell -WorkingDirectory $repoRoot -ArgumentList @("-NoExit", "-Command", "pnpm --filter training-dashboard dev") | Out-Null
}

Write-Host "Local dev processes started."
Write-Host "Web: http://localhost:5173/"
if (-not $SkipTrainingDashboard) {
  Write-Host "Training dashboard: http://localhost:5174/"
}
Write-Host "API: http://localhost:8000/api/v1/health"
