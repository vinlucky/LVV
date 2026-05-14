@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
set "ROOT=%CD%"
set "CLI_DIR=%ROOT%\cli"
set "AI_CORE_DIR=%ROOT%\ai-core"
set "WEB_DIR=%ROOT%\web"
set "PYTHON_EXE="

if "%~1"=="" goto :run
set "CMD=%~1"

if /i "%CMD%"=="install" goto :install
if /i "%CMD%"=="start" goto :run
if /i "%CMD%"=="backend" goto :backend
if /i "%CMD%"=="stop" goto :stop
if /i "%CMD%"=="status" goto :status
if /i "%CMD%"=="help" goto :help
if /i "%CMD%"=="--help" goto :help
if /i "%CMD%"=="-h" goto :help

:run
if not exist "%CLI_DIR%\node_modules" (
    echo Installing CLI dependencies...
    pushd "%CLI_DIR%"
    call npm install
    if %errorlevel% neq 0 (
        echo ERROR: CLI npm install failed
        popd
        pause
        goto :eof
    )
    popd
)
if not exist "%CLI_DIR%\dist\index.js" (
    echo Building CLI...
    pushd "%CLI_DIR%"
    call npm run build
    if %errorlevel% neq 0 (
        echo ERROR: CLI build failed
        popd
        pause
        goto :eof
    )
    popd
)
if "%~1"=="" (
    node "%CLI_DIR%\dist\index.js" start
) else (
    node "%CLI_DIR%\dist\index.js" %*
)
if %errorlevel% neq 0 (
    echo.
    echo ERROR: CLI runtime error
    pause
)
goto :eof

:install
echo.
echo ============================================
echo   LVV Office Assistant - Install
echo ============================================
echo.

echo [1/6] Checking environment...

where py >nul 2>&1
if %errorlevel% equ 0 (
    py --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=py"
    )
)

if "%PYTHON_EXE%"=="" (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        python --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=python"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        python3 --version >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=python3"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    )
)

if "%PYTHON_EXE%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

if "%PYTHON_EXE%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    )
)

if "%PYTHON_EXE%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    )
)

if "%PYTHON_EXE%"=="" (
    if exist "C:\Python313\python.exe" set "PYTHON_EXE=C:\Python313\python.exe"
)

if "%PYTHON_EXE%"=="" (
    if exist "C:\Python312\python.exe" set "PYTHON_EXE=C:\Python312\python.exe"
)

if "%PYTHON_EXE%"=="" (
    if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
)

if "%PYTHON_EXE%"=="" (
    if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found! Install Python 3.10+
    echo   https://www.python.org/downloads/
    pause
    goto :eof
)

"%PYTHON_EXE%" --version
echo [OK] Python ready

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found! Install Node.js 18+
    echo   https://nodejs.org/
    pause
    goto :eof
)
echo [OK] Node.js ready
echo.

echo [2/6] Installing Python backend dependencies...
cd /d "%AI_CORE_DIR%"
if not exist ".venv" (
    echo    Creating virtual environment...
    "%PYTHON_EXE%" -m venv .venv
    if !errorlevel! neq 0 (
        echo    ERROR: Failed to create venv
        pause
        goto :eof
    )
    echo    Virtual environment created
)
echo    Installing packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo    ERROR: Python pip install failed
    echo    Check network connection and retry
    pause
    goto :eof
)
echo [OK] Python dependencies installed
echo.

echo [3/6] Verifying backend dependencies...
".venv\Scripts\python.exe" -c "import fastapi, openai, uvicorn; print('   Core deps OK')"
if %errorlevel% neq 0 (
    echo    WARN: Verification failed, may still work
) else (
    echo [OK] Backend dependencies verified
)
echo.

echo [3.5/6] Installing AI Core Node.js renderers (pptx, docx)...
cd /d "%AI_CORE_DIR%\pptx-renderer"
if not exist "node_modules" (
    echo    Installing pptxgenjs...
    call npm install
    if !errorlevel! neq 0 (
        echo    WARN: pptx-renderer install failed, PPT generation may not work
    )
) else (
    echo    pptx-renderer already installed
)
cd /d "%AI_CORE_DIR%\docx-renderer"
if not exist "node_modules" (
    echo    Installing docx-js...
    call npm install
    if !errorlevel! neq 0 (
        echo    WARN: docx-renderer install failed, DOCX generation may not work
    )
) else (
    echo    docx-renderer already installed
)
echo [OK] Node.js renderers ready
echo.

echo [4/6] Installing Web frontend dependencies...
cd /d "%WEB_DIR%"
if not exist "node_modules" (
    echo    Installing packages - may take a few minutes...
    call npm install
    if !errorlevel! neq 0 (
        echo    ERROR: Web frontend npm install failed
        pause
        goto :eof
    )
)
echo [OK] Web frontend dependencies ready
echo.

echo [5/6] Installing and building CLI...
cd /d "%CLI_DIR%"
if not exist "node_modules" (
    echo    Installing packages...
    call npm install
    if !errorlevel! neq 0 (
        echo    ERROR: CLI npm install failed
        pause
        goto :eof
    )
)
echo    Compiling TypeScript...
call npm run build
if !errorlevel! neq 0 (
    echo    ERROR: CLI build failed
    pause
    goto :eof
)
echo [OK] CLI ready
echo.

echo [6/6] Configuring environment...
if not exist "%ROOT%\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\.env" >nul
        echo    .env created from .env.example
    ) else (
        echo QWEN_API_KEY=sk-your-qwen-api-key-here> "%ROOT%\.env"
        echo TENCENT_API_KEY=sk-your-tencent-api-key-here>> "%ROOT%\.env"
        echo DEFAULT_PROVIDER=qwen>> "%ROOT%\.env"
        echo AI_CORE_HOST=127.0.0.1>> "%ROOT%\.env"
        echo AI_CORE_PORT=8000>> "%ROOT%\.env"
        echo    .env created
    )
    echo    IMPORTANT: Edit %ROOT%\.env and fill in your API Key!
    start notepad "%ROOT%\.env"
) else (
    echo    .env already exists
)
echo [OK] Environment configured
echo.

echo ============================================
echo   Install complete!
echo.
echo   Start: lvv
echo   IMPORTANT: Edit .env and fill in QWEN_API_KEY
echo ============================================
echo.
pause
goto :eof

:backend
echo.
echo Starting AI Core backend - port 8000...
cd /d "%AI_CORE_DIR%"
if not exist ".venv" (
    echo ERROR: Virtual environment not found! Run: lvv install
    pause
    goto :eof
)
start "LVV-AICore" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul
echo [OK] Backend started
echo API docs: http://localhost:8000/docs
echo.
start http://localhost:8000/docs
goto :eof

:stop
echo.
echo Stopping all services...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [OK] All services stopped
echo.
goto :eof

:status
echo.
echo ============================================
echo   Service Status
echo ============================================
echo.
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo [RUNNING] AI Core  - port 8000
) else (
    echo [STOPPED] AI Core  - port 8000
)
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo [RUNNING] Web UI   - port 5173
) else (
    echo [STOPPED] Web UI   - port 5173
)
echo.
echo Web:  http://localhost:5173
echo API:  http://localhost:8000/docs
echo.
goto :eof

:help
echo.
echo LVV Office Assistant - Command Reference
echo ================================================
echo.
echo   lvv                   Start CLI - auto build and run
echo   lvv install           Install all dependencies
echo   lvv backend           Start backend only
echo   lvv stop              Stop all services
echo   lvv status            Check service status
echo   lvv help              Show this help
echo   lvv [any CLI args]    Pass through to CLI
echo.
echo   First time? Run: lvv install
echo   Then edit .env and fill in QWEN_API_KEY
echo.
goto :eof