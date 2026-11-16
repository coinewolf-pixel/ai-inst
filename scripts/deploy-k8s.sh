#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     NEXORUM AI — Kubernetes Cloud Deployment              ║"
echo "╚════════════════════════════════════════════════════════════╝"

NAMESPACE="nexorum"
CONTEXT="${KUBE_CONTEXT:-nexorum-prod}"

echo "[1/8] Switching to context: $CONTEXT"
kubectl config use-context $CONTEXT || { echo "Context not found. Set KUBE_CONTEXT env var."; exit 1; }

echo "[2/8] Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

echo "[3/8] Applying ConfigMap & Secrets..."
kubectl apply -f k8s/01-configmap.yaml -n $NAMESPACE
kubectl apply -f k8s/02-secrets.yaml -n $NAMESPACE

echo "[4/8] Deploying infrastructure (Postgres, Redis, ClickHouse, Kafka)..."
kubectl apply -f k8s/10-postgres.yaml -n $NAMESPACE
kubectl apply -f k8s/11-redis.yaml -n $NAMESPACE
kubectl apply -f k8s/12-clickhouse.yaml -n $NAMESPACE
kubectl apply -f k8s/13-kafka.yaml -n $NAMESPACE

echo "[5/8] Waiting for infrastructure..."
kubectl wait --for=condition=ready pod -l app=nexorum-postgres -n $NAMESPACE --timeout=300s
kubectl wait --for=condition=ready pod -l app=nexorum-redis -n $NAMESPACE --timeout=120s
kubectl wait --for=condition=ready pod -l app=nexorum-clickhouse -n $NAMESPACE --timeout=120s

echo "[6/8] Deploying microservices..."
kubectl apply -f k8s/20-ai-orchestrator.yaml -n $NAMESPACE
kubectl apply -f k8s/21-exchange-connector.yaml -n $NAMESPACE
kubectl apply -f k8s/22-risk-engine.yaml -n $NAMESPACE
kubectl apply -f k8s/23-auth-service.yaml -n $NAMESPACE
kubectl apply -f k8s/24-market-data.yaml -n $NAMESPACE

echo "[7/8] Applying ingress..."
kubectl apply -f k8s/30-ingress.yaml -n $NAMESPACE
kubectl apply -f k8s/40-hpa.yaml -n $NAMESPACE
kubectl apply -f k8s/50-cert-manager.yaml

echo "[8/8] Deployment complete!"
echo ""
echo "Services:"
kubectl get svc -n $NAMESPACE
echo ""
echo "Pods:"
kubectl get pods -n $NAMESPACE
echo ""
echo "Access: https://app.nexorum.ai | https://api.nexorum.ai"
