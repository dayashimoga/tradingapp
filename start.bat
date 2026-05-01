@echo off
setlocal

echo =======================================================
echo     TradingBot Autonomous System - Startup Script
echo =======================================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running or not installed.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

:: Check if .env exists
if not exist ".env" (
    echo [WARNING] No .env file found!
    echo Creating a default .env file for Paper Trading...
    echo # Alpaca Paper Trading Keys > .env
    echo ALPACA_API_KEY=your_key_here >> .env
    echo ALPACA_SECRET_KEY=your_secret_here >> .env
    echo ALPACA_PAPER=true >> .env
    echo Please edit the .env file with your real keys later.
    echo.
)

echo [1/3] Stopping any old containers...
docker-compose down

echo.
echo [2/3] Building and starting the full stack...
docker-compose up -d --build

echo.
echo [3/3] System is booting up! Please wait 10 seconds...
timeout /t 10 /nobreak >nul

echo.
echo =======================================================
echo ✅ SYSTEM IS LIVE!
echo =======================================================
echo.
echo Your dashboard is now running in the background.
echo.
echo 📊 Trading Dashboard: http://localhost:3000
echo 🔌 Backend API:       http://localhost:8000/docs
echo 📈 Grafana Metrics:   http://localhost:3001
echo.
echo Press any key to open the dashboard in your browser...
pause >nul

start http://localhost:3000
