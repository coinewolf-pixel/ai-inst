#!/usr/bin/env bash
# deploy.sh — обновить NEXORUM AI на сервере до последней версии из GitHub
set -euo pipefail
cd "$(dirname "$0")"

echo "==> git pull"
git pull --ff-only

echo "==> Python-зависимости (aienv)"
if [ -x "$HOME/aienv/bin/pip" ]; then
  "$HOME/aienv/bin/pip" install -q -r requirements.txt || echo "  (пропущено — requirements не обязательны для ядра)"
fi

echo "==> systemd"
if [ -f nexorum-ai.service ]; then
  sudo cp nexorum-ai.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now nexorum-ai
  sudo systemctl restart nexorum-ai
  echo "==> Служба перезапущена"
else
  echo "  nexorum-ai.service не найден — запустите вручную: AI_SERVER_KEY=... python3 ai_server.py"
fi
echo "==> Готово: http://$(hostname -I | awk '{print $1}'):8000"
