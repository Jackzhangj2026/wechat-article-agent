# WeChat Article Agent - DEMO Launcher
# Usage: .\start.ps1

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$backend = Join-Path $projectRoot "backend"
$frontend = Join-Path $projectRoot "frontend"

Write-Host "========================================" -ForegroundColor Green
Write-Host "  WeChat Article Agent - DEMO Launcher" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# DeepSeek API Key is auto-loaded from backend/.env
$envFile = Join-Path $backend ".env"
if (Test-Path $envFile) {
    Write-Host "[OK] DeepSeek API Key loaded from backend/.env" -ForegroundColor Green
} else {
    Write-Host "[WARN] backend/.env not found. Create it with DEEPSEEK_API_KEY=sk-..." -ForegroundColor Yellow
}

# Check ComfyUI workflow
$workflowPath = Join-Path $backend "workflows\z-image-api.json"
if (Test-Path $workflowPath) {
    $content = Get-Content $workflowPath -Raw
    if ($content -match "_") {
        Write-Host "[WARN] z-image-api.json is still a placeholder. Export real workflow from ComfyUI." -ForegroundColor Yellow
    } else {
        Write-Host "[OK] ComfyUI workflow configured" -ForegroundColor Green
    }
}

# Start backend
Write-Host ""
Write-Host "[1/2] Starting backend (http://localhost:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backend'; uvicorn main:app --reload --port 8000"

# Start frontend
Write-Host "[2/2] Starting frontend (http://localhost:5173)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontend'; npx http-server . -p 5173 -c-1 --cors"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Started!" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
