#!/bin/bash
set -e

REGISTRY="${DOCKER_REGISTRY:-nexorum}"
VERSION="${VERSION:-latest}"

echo "Building NEXORUM images version: $VERSION"

docker build -t $REGISTRY/frontend:$VERSION ./frontend
docker build -t $REGISTRY/ai-orchestrator:$VERSION ./backend/ai-orchestrator
docker build -t $REGISTRY/exchange-connector:$VERSION ./backend/exchange-connector
docker build -t $REGISTRY/risk-engine:$VERSION ./backend/risk-engine
docker build -t $REGISTRY/auth-service:$VERSION ./backend/auth-service
docker build -t $REGISTRY/market-data:$VERSION ./backend/market-data

echo "Pushing to registry..."
docker push $REGISTRY/frontend:$VERSION
docker push $REGISTRY/ai-orchestrator:$VERSION
docker push $REGISTRY/exchange-connector:$VERSION
docker push $REGISTRY/risk-engine:$VERSION
docker push $REGISTRY/auth-service:$VERSION
docker push $REGISTRY/market-data:$VERSION

echo "All images built and pushed!"
