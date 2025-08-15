@echo off
REM ===================================
REM Setup Backend or Frontend in One Click
REM ===================================

setlocal enabledelayedexpansion

REM Check if we are in backend folder
if exist "requirements.txt" (
    echo 🔹 Backend detected...
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
    goto end
)

REM Check if we are in frontend folder
if exist "package.json" (
    echo 🔹 Frontend detected...
    echo Installing npm packages...
    npm install
    echo ✅ Frontend setup complete.
    goto end
)

echo ❌ No requirements.txt or package.json found in this folder.
echo Please run this script inside backend or frontend directory.

:end
pause
