@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo    Academic Clarity - Ultra Parallel Tests
echo ==========================================
echo.

:: 直接调用全量并行调度器
if not exist "python_embed\python.exe" (
    echo [ERROR] python_embed\python.exe not found!
    exit /b 1
)

".\python_embed\python.exe" "backend\run_all_tests.py"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [FAILURE] Some tasks failed. Check logs above.
    exit /b 1
)

echo.
echo [SUCCESS] All tasks (TSC Lint + Backend Tests) finished successfully!
