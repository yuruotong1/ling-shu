@echo off
chcp 65001 >nul
echo ========================================
echo   Ling Shu Development Environment Startup Script
echo ========================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check virtual environment
if not exist "backend\venv\Scripts\activate.bat" (
    echo Error: Backend virtual environment not found!
    echo Please create a virtual environment and install dependencies first:
    echo   cd backend ^&^& python -m venv venv ^&^& venv\Scripts\activate.bat ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check frontend dependencies
if not exist "frontend\node_modules" (
    echo Error: Frontend dependencies not installed!
    echo Please run: cd frontend ^&^& npm install
    pause
    exit /b 1
)

echo Starting backend service (http://localhost:8000)...
start "Ling Shu - Backend" cmd /k "cd /d "%~dp0backend" && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"

echo Starting frontend service (http://localhost:5173)...
start "Ling Shu - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo   Services started!
echo ========================================
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173
echo.
echo   To stop services: simply close the corresponding terminal windows
echo ========================================

timeout /t 3 >nul
