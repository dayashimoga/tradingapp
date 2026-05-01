#!/bin/bash

echo "======================================================="
echo "    TradingBot Autonomous System - Startup Script"
echo "======================================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "[ERROR] Docker is not running or not installed."
  echo "Please start Docker and try again."
  exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
  echo "[WARNING] No .env file found!"
  echo "Creating a default .env file for Paper Trading..."
  echo "# Alpaca Paper Trading Keys" > .env
  echo "ALPACA_API_KEY=your_key_here" >> .env
  echo "ALPACA_SECRET_KEY=your_secret_here" >> .env
  echo "ALPACA_PAPER=true" >> .env
  echo "Please edit the .env file with your real keys later."
  echo ""
fi

echo "[1/3] Stopping any old containers..."
docker-compose down

echo ""
echo "[2/3] Building and starting the full stack..."
docker-compose up -d --build

echo ""
echo "[3/3] System is booting up! Please wait 10 seconds..."
sleep 10

echo ""
echo "======================================================="
echo "✅ SYSTEM IS LIVE!"
echo "======================================================="
echo ""
echo "Your dashboard is now running in the background."
echo ""
echo "📊 Trading Dashboard: http://localhost:3000"
echo "🔌 Backend API:       http://localhost:8000/docs"
echo "📈 Grafana Metrics:   http://localhost:3001"
echo ""

# Attempt to open browser automatically
if which xdg-open > /dev/null
then
  xdg-open http://localhost:3000
elif which open > /dev/null
then
  open http://localhost:3000
fi
