#!/bin/bash

# Grants Council - Start script

echo "Starting Grants Council..."
echo ""

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Warning: OPENROUTER_API_KEY not set"
    echo "Add it to .env file or set with: export OPENROUTER_API_KEY='your-key'"
    echo ""
fi

# Start backend
echo "Starting backend on http://localhost:8001..."
cd backend
uvicorn main:app --reload --port 8001 &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✓ Grants Council is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8001/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
