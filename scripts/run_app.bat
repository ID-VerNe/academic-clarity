@echo off
setlocal
cd /d "%~dp0"

title Academic Clarity - One Click Starter

echo ==========================================
echo    Academic Clarity - AI Researcher
echo ==========================================
echo.

:: 1. 检查 node_modules 是否存在
if not exist "node_modules\" (
    echo [SYS] Node modules missing. Installing dependencies...
    call pnpm install
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] pnpm install failed. Please ensure Node.js and pnpm are installed.
        exit /b 1
    )
)

:: 2. 检查 Python 嵌入环境
if not exist "python_embed\python.exe" (
    echo [ERROR] Embedded Python environment not found in 'python_embed' folder.
    echo Please ensure the python_embed directory is correctly set up.
    exit /b 1
)

echo [SYS] Environment check passed.
echo [SYS] Launching Electron (Backend will auto-start)...
echo.

:: 3. 启动开发模式 (包含 Vite + Electron)
call pnpm dev

if %ERRORLEVEL% neq 0 (
    echo.
    echo [INFO] Application exited with code %ERRORLEVEL%.
)
