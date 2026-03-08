@echo off
cd /d %~dp0

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv is not installed or not in PATH.
    echo Please install uv first.
    pause
    exit /b 1
)

echo [INFO] Syncing environment...
uv sync
if errorlevel 1 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)

echo [INFO] Running solver...
uv run relic_solver.py
if errorlevel 1 (
    echo [ERROR] Solver failed.
    pause
    exit /b 1
)

echo [DONE] Check solutions_img folder.
pause