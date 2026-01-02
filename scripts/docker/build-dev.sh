#!/bin/bash
# Docker Build Script for Development

set -e

echo "🐳 Building NoobBook Docker Images (Development)"

# Build backend development image
echo "🔨 Building backend development image..."
docker build -f backend/Dockerfile --target development -t noobbook-backend:dev .

# Build frontend development image
echo "🔨 Building frontend development image..."
docker build -f frontend/Dockerfile --target development -t noobbook-frontend:dev .

echo "✅ Development images built successfully!"
echo ""
echo "To start development containers:"
echo "  make docker-dev"
