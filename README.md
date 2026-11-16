# NEXORUM AI

Локальный AI-ассистент с памятью, базой знаний и генерацией медиа. Работает полностью на вашем сервере (Ollama), без внешних API и без контентных ограничений.

## Состав

| Файл | Назначение |
|---|---|
| `ai.py` | Ядро: память решённых задач + RAG-база знаний (SQLite + эмбеддинги) |
| `ai_server.py` | Веб-интерфейс и REST API (порт 8000) |
| `static/index.html` | Фронтенд |
| `ai_image.py` | Генерация картинок (SD-Turbo) и видео-слайдшоу (ffmpeg) |
| `ai_media.py` | Фото/видео/аудио → описания и транскрипты в базу знаний |
| `ai_github.py` | Репозитории GitHub → база знаний |

## Быстрый старт (сервер Ubuntu/Debian)

```bash
# 1. Зависимости системы
sudo apt install -y python3 python3-venv ffmpeg fonts-dejavu-core poppler-utils git ollama

# 2. Модели Ollama
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
ollama pull qwen2.5vl:3b

# 3. Python-окружение для генерации медиа
python3 -m venv ~/aienv
~/aienv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
~/aienv/bin/pip install diffusers transformers accelerate faster-whisper

# 4. Клонировать и запустить
git clone https://github.com/coinewolf-pixel/ai-inst.git ~/nexorum
cd ~/nexorum
AI_SERVER_KEY="придумайте-длинный-пароль" python3 ai_server.py
```

Открыть: `http://IP-сервера:8000`

## Установка как служба (автозапуск)

```bash
sudo cp nexorum-ai.service /etc/systemd/system/
sudo systemctl enable --now nexorum-ai
journalctl -u nexorum-ai -f   # логи
```

## Обновление на сервере

```bash
cd ~/nexorum && ./deploy.sh
```

## API

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/ask` | `{task}` → ответ с учётом памяти и базы знаний |
| POST | `/api/upload_raw` | Потоковая загрузка файла (base64, заголовок `X-File-Name`), авто-индексация |
| POST | `/api/upload` | То же через JSON (совместимость) |
| POST | `/api/image` | `{prompt}` → генерация картинки |
| POST | `/api/video` | `{scenes: [...]}` → видео-слайдшоу |
| POST | `/api/save` | Сохранить решение в память |
| GET | `/api/files` | Список файлов |
| GET | `/api/jobs` | Статусы фоновых задач |

Все запросы (кроме `/` и `/api/health`) требуют `Authorization: Bearer <ключ>` или cookie `aikey`.
