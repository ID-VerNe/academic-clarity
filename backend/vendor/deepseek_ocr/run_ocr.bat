@echo off
setlocal
cd /d "%~dp0"

if not exist "python_embed\python.exe" (
    echo [ERROR] Python embedded environment not found.
    pause
    exit /b 1
)

echo Starting DeepSeek-OCR LiteLLM Script...
".\python_embed\python.exe" "run_dpsk_ocr_litellm.py"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    pause
)
