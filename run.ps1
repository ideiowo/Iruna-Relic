Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] uv is not installed or not in PATH."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[INFO] Syncing environment..."
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] uv sync failed."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[INFO] Running solver..."
uv run relic_solver.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Solver failed."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[DONE] Check solutions_img folder."
Read-Host "Press Enter to exit"