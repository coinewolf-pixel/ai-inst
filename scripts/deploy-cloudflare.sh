#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     NEXORUM — Cloudflare Deployment                        ║"
echo "╚════════════════════════════════════════════════════════════╝"

echo ""
echo "⚠️  IMPORTANT: Frontend deploys via Cloudflare Pages Git Integration"
echo "   It reads wrangler.toml from REPO ROOT automatically."
echo "   No manual deploy needed if Git Integration is connected."
echo ""

# ── 1. Deploy API Gateway Worker (via GH Actions or manual) ──
echo "[1/1] Deploying API Gateway Worker..."
cd cloudflare/workers/api-gateway
npm install
npx wrangler deploy
cd ../../..

echo ""
echo "✅ Worker deployed!"
echo ""
echo "📋 For Frontend (Pages):"
echo "   1. Go to Cloudflare Dashboard → Pages"
echo "   2. Create project → Connect Git repository"
echo "   3. Build command: npm run build"
echo "   4. Build output: frontend/dist"
echo "   5. Root wrangler.toml will be auto-detected"
