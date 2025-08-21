@echo off
REM ===================================
REM Intelligent Setup Script: Backend & Frontend
REM ===================================
setlocal EnableDelayedExpansion

REM Function to compare Node.js version
set "NODE_MIN_VERSION=20.3.6"

REM Get current directory name
for %%I in ("%CD%") do set "CURDIR=%%~nxI"

REM -----------------------------------
REM Check if inside backend or frontend folder
REM -----------------------------------
if not exist "requirements.txt" if not exist "package.json" (
    echo ❌ No requirements.txt or package.json found in this folder.
    echo Please run this script inside your project's backend or frontend directory.
    pause
    exit /B
)

REM -----------------------------------
REM BACKEND SETUP
REM -----------------------------------
if exist "requirements.txt" (
    echo 🔹 Backend detected...

    REM --- Check for Python ---
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Python not found. Please install Python before proceeding.
        pause
        exit /B
    ) else (
        for /f "tokens=2 delims= " %%A in ('python --version') do set PY_VERSION=%%A
        echo ✅ Python detected: %PY_VERSION%
    )

    REM --- Setup virtualenv ---
    if not exist ".venv" (
        echo Creating virtual environment...
        python -m venv .venv
    ) else (
        echo Virtual environment already exists.
    )

    echo Activating virtual environment...
    call .venv\Scripts\activate.bat

    echo Installing Python dependencies from requirements.txt...
    pip install -r requirements.txt

    echo ✅ Backend setup complete.
    echo.
    echo To start your backend, activate your environment and run the relevant entry script (e.g., uvicorn main:app).
    goto end
)

REM -----------------------------------
REM FRONTEND SETUP
REM -----------------------------------
if exist "package.json" (
    echo 🔹 Frontend detected...

    REM --- Check for Node.js ---
    node --version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Node.js not found. Please install Node.js v%NODE_MIN_VERSION% or higher before proceeding.
        pause
        exit /B
    ) else (
        for /f "tokens=1,2 delims=v " %%A in ('node --version') do set NODE_VERSION=%%B
        echo ✅ Node.js detected: v!NODE_VERSION!
        REM Compare Node.js version
        REM NOT robust for all versioning, simple compare
        if "!NODE_VERSION!" LSS "%NODE_MIN_VERSION%" (
            echo ❌ Node.js version is too low. Please upgrade to v%NODE_MIN_VERSION% or higher.
            pause
            exit /B
        )
    )

    echo Installing npm packages...
    npm install

    echo ✅ Frontend setup complete!
    echo.
    echo To build your frontend, run: npm run build
    echo To start the development server, run: npm run dev
    goto end
)

:end
echo.
echo Please make sure you are running this script inside your project folder:
echo - For backend: run inside your 'backend' folder.
echo - For frontend: run inside your 'frontend' folder.
pause
