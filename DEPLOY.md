# NEXORUM — Deploy Guide

## Frontend (Cloudflare Pages) — ТОЛЬКО через GitHub Actions

**НЕ используй Cloudflare Pages Git Integration!**

### Шаг 1: Залей код на GitHub

```bash
# Распакуй ZIP, зайди в папку
cd nexorum

# Инициализируй git
git init
git add .
git commit -m "init"
git remote add origin https://github.com/TVOY_USERNAME/nexorum.git
git push -u origin main
```

### Шаг 2: Добавь 2 секрета в GitHub

Зайди в свой репозиторий на GitHub:
**Settings → Secrets and variables → Actions → New repository secret**

Добавь 2 секрета:

| Название | Значение | Где взять |
|----------|----------|-----------|
| `CLOUDFLARE_API_TOKEN` | Токен | Cloudflare Dashboard → My Profile → API Tokens → Create Token → Use template "Edit Cloudflare Workers" |
| `CLOUDFLARE_ACCOUNT_ID` | ID аккаунта | Cloudflare Dashboard → любая страница → правый сайдбар, раздел "Account ID" |

### Шаг 3: Готово

Push в `main` — GitHub Actions автоматически:
1. Соберёт Next.js в `frontend/dist`
2. Задеплоит в Cloudflare Pages
3. Задеплоит Worker (если менялся)
4. Задеплоит Kubernetes (если менялся backend)

Смотри прогресс здесь: **GitHub → Actions**

---

## Backend (Kubernetes / Hetzner)

См. `scripts/deploy-k8s.sh` и `terraform/`

## Worker (API Gateway)

Автоматически деплоится через GitHub Actions при изменении `cloudflare/workers/**`
