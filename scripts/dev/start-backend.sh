#!/bin/bash
# Local Backend Development Script

set -e

echo "🚀 Starting NoobBook Backend (Local Development)"

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating Python virtual environment..."
    cd backend
    python3 -m venv venv
    cd ..
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source backend/venv/bin/activate

# Install dependencies
echo "📚 Installing Python dependencies..."
cd backend
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cp .env.template .env
    echo "📝 Please configure your .env file with appropriate values"
fi

# Start the backend server
echo "🎯 Starting Flask development server..."
export FLASK_ENV=development
export FLASK_DEBUG=1
python run.py
