#!/usr/bin/env bash
set -e

# Change to script directory
cd "$(dirname "$0")"

echo "========================================"
echo "  Ling Shu Development Environment Startup Script"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -f "backend/venv/Scripts/activate" ]; then
    echo "Error: Backend virtual environment not found!"
    echo "Please create a virtual environment and install dependencies first:"
    echo "  cd backend && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if frontend dependencies exist
if [ ! -d "frontend/node_modules" ]; then
    echo "Error: Frontend dependencies not installed!"
    echo "Please run: cd frontend && npm install"
    exit 1
fi

echo "Starting backend service (http://localhost:8000)..."
cd backend
source venv/Scripts/activate
start "Ling Shu - Backend" bash -c "uvicorn app.main:app --reload --port 8000; echo ''; read -p 'Press Enter to close...'"
cd ..

echo "Starting frontend service (http://localhost:5173)..."
cd frontend
start "Ling Shu - Frontend" bash -c "npm run dev; echo ''; read -p 'Press Enter to close...'"
cd ..

echo ""
echo "========================================"
echo "  Services started!"
echo "========================================"
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "  To stop services: simply close the corresponding terminal windows"
echo "========================================"
