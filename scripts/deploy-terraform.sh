#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     NEXORUM AI — Terraform Infrastructure Deploy          ║"
echo "╚════════════════════════════════════════════════════════════╝"

cd terraform

echo "[1/4] Initializing Terraform..."
terraform init

echo "[2/4] Planning..."
terraform plan -out=tfplan

echo "[3/4] Applying..."
terraform apply tfplan

echo "[4/4] Done!"
terraform output

echo ""
echo "Next steps:"
echo "  1. SSH into control node: ssh root@$(terraform output -raw k8s_control_ip)"
echo "  2. Install k3s: curl -sfL https://get.k3s.io | sh -"
echo "  3. Copy kubeconfig and run: ./scripts/deploy-k8s.sh"
