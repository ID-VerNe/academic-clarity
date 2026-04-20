@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo    Academic Clarity - Automated Tests
echo ==========================================
echo.

:: 1. PNPM Lint (TSC Check)
echo [Phase 1] Frontend Lint (TypeScript check)...
call pnpm lint
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend lint failed!
    pause
    exit /b 1
)
echo [INFO] Frontend lint passed.
echo.

:: 2. Python Tests (Backend)
echo [Phase 2] Backend Tests (Python)...
if not exist "python_embed\python.exe" (
    echo [ERROR] python_embed\python.exe not found!
    pause
    exit /b 1
)

:: Run all backend tests through the summary script
".\python_embed\python.exe" "backend\run_all_tests.py"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] One or more backend tests failed!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] All tests passed (Frontend Lint + Backend Python Tests).
pause
