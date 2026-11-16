# NEXORUM AI INSTITU

AI-Native Institutional Trading Operating System

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/YOUR_USER/nexorum.git
cd nexorum

# 2. Local development
docker-compose up -d

# 3. Frontend
cd frontend
npm install
npm run dev
```

## Cloud Deploy

See [DEPLOY.md](DEPLOY.md)

## Architecture

- **Frontend**: Next.js 15 + Tailwind + Recharts
- **Backend**: 5 microservices (FastAPI + Python)
- **Database**: PostgreSQL + TimescaleDB, ClickHouse, Redis
- **Message Queue**: Kafka
- **Cloud**: Hetzner k3s + Cloudflare Edge
