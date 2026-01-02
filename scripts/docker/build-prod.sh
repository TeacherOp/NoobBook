#!/bin/bash
# Docker Build Script for Production

set -e

echo "🐳 Building NoobBook Docker Images (Production)"

# Build backend production image
echo "🔨 Building backend production image..."
docker build -f backend/Dockerfile --target production -t noobbook-backend:latest .

# Build frontend production image
echo "🔨 Building frontend production image..."
docker build -f frontend/Dockerfile --target production -t noobbook-frontend:latest .

echo "✅ Production images built successfully!"
echo ""
echo "Images created:"
echo "  noobbook-backend:latest"
echo "  noobbook-frontend:latest"
echo ""
echo "To start production containers:"
echo "  make docker-prod"
