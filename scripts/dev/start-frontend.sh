#!/bin/bash
# Local Frontend Development Script

set -e

echo "🚀 Starting NoobBook Frontend (Local Development)"

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Start the development server
echo "🎯 Starting Vite development server..."
export VITE_API_URL=http://localhost:5000/api/v1
npm run dev
