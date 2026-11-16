# Cloudflare Edge Deployment

## Структура

```
cloudflare/
├── workers/
│   └── api-gateway/          # Cloudflare Worker (serverless API Gateway)
│       ├── src/index.ts      # Edge-логика: rate limit, JWT, routing
│       ├── wrangler.toml     # Конфиг Worker (main = src/index.ts)
│       └── package.json      # wrangler deploy
│
└── pages/
    ├── wrangler.toml         # Конфиг Pages (без main, только vars)
    └── package.json          # wrangler pages deploy
```

## Разница Workers vs Pages

| | Workers | Pages |
|-|---------|-------|
| Тип | Serverless функции | Static hosting + Functions |
| Команда деплоя | `wrangler deploy` | `wrangler pages deploy <dir>` |
| Entry point | `main = "src/index.ts"` | Статические файлы из папки |
| Назначение | API Gateway, edge logic | Next.js frontend |

## Локальный деплой

```bash
# 1. Worker (API Gateway)
cd cloudflare/workers/api-gateway
npm install
npx wrangler deploy

# 2. Frontend → Pages
cd frontend
npm install
npm run build          # Создаёт frontend/dist (static export)
cd ../cloudflare/pages
npm install
npx wrangler pages deploy ../../frontend/dist --project-name nexorum-frontend
```

## GitHub Actions

Секреты:
- `CLOUDFLARE_API_TOKEN` — Token с правами Cloudflare Workers + Pages
- `KUBECONFIG` — Base64-encoded kubeconfig для Kubernetes

## Troubleshooting

**Ошибка: "Could not detect a directory containing static files"**
→ Вы используете `wrangler deploy` вместо `wrangler pages deploy`. Workers и Pages — разные команды.

**Ошибка: "No build output detected"**
→ Убедитесь, что `frontend/next.config.ts` содержит `output: 'export'` и `distDir: 'dist'`.
