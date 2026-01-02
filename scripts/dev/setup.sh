#!/bin/bash
# Local Development Setup Script

set -e

echo "🔧 Setting up NoobBook for Local Development"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed"
    exit 1
fi

# Check npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm is required but not installed"
    exit 1
fi

echo "✅ All prerequisites satisfied"

# Make scripts executable
chmod +x scripts/dev/*.sh

echo "🎉 Local development setup complete!"
echo ""
echo "To start development:"
echo "  Backend:  make dev-backend"
echo "  Frontend: make dev-frontend"
echo "  Both:     make dev-local"
