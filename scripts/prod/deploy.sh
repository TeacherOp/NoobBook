#!/bin/bash
# Production Deployment Script

set -e

echo "🚀 Deploying NoobBook to Production"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is required but not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is required but not installed"
    exit 1
fi

# Build production images
echo "🔨 Building production images..."
./scripts/docker/build-prod.sh

# Start production services
echo "🎯 Starting production services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service health
echo "🏥 Checking service health..."
docker-compose -f docker-compose.prod.yml ps

echo "✅ Production deployment complete!"
echo ""
echo "Application is running at: http://localhost"
echo ""
echo "To view logs: make logs-prod"
echo "To stop: make stop-prod"
