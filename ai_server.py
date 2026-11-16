#!/usr/bin/env python3
"""
ai_server.py — веб-интерфейс и API для ai.py.

Запуск:
  AI_SERVER_KEY="придумайте-длинный-пароль" python3 ai_server.py

Открыть в браузере:  http://IP-сервера:8000
Файл ai.py должен лежать в той же папке. Фронтенд — static/index.html.
"""
import base64
import collections
import hmac
import json
import mimetypes
import os
import sys
import threading
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai  # noqa: E402

HOST = os.environ.get("AI_SERVER_HOST", "0.0.0.0")
PORT = int(os.environ.get("AI_SERVER_PORT", "8000"))
KEY = os.environ.get("AI_SERVER_KEY", "")
MAX_BODY = 256 * 1024 * 1024          # JSON-запросы (чат, команды)
MAX_UPLOAD = 4 * 1024 * 1024 * 1024   # сырые загрузки файлов: стрим на диск, без RAM-лимита
UPLOAD_DIR = os.path.expanduser("~/znaniya/uploads")
GENERATED_DIR = os.path.expanduser("~/znaniya/generated")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
JOBS_MAX = 200

ASK_SEM = threading.Semaphore(4)       # параллельные чат-запросы (Ollama сам выстроит очередь)
GEN_SEM = threading.Semaphore(2)       # параллельная генерация медиа
JOBS = collections.deque(maxlen=JOBS_MAX)
JOBS_LOCK = threading.Lock()
UPLOAD_LOCKS = {}                       # блокировка на файл: повторная загрузка не дублирует работу
UPLOAD_LOCKS_LOCK = threading.Lock()


def set_job(job, status):
    with JOBS_LOCK:
        job["status"] = status


def run_generation(kind, payload, job):
    try:
        import ai_image
        log = lambda m: set_job(job, "обрабатывается: " + m.strip()[:80])
        with GEN_SEM:
            set_job(job, "обрабатывается")
            if kind == "image":
                paths = ai_image.generate([payload], log)
                if not paths:
                    return set_job(job, "ошибка: картинка не получилась")
                path = paths[0]
            else:
                path = ai_image.make_video(payload, log)
        set_job(job, "готово")
        job["url"] = "/files/" + os.path.basename(path)
    except Exception as e:
        set_job(job, f"ошибка: {e}")


def upload_lock(path):
    with UPLOAD_LOCKS_LOCK:
        lock = UPLOAD_LOCKS.setdefault(path, threading.Lock())
    return lock


def process_upload(path, job):
    import tempfile
    ext = os.path.splitext(path)[1].lower()
    try:
        with upload_lock(path):
            set_job(job, "обрабатывается")
            if ext in ai.TEXT_EXT or ext == ".pdf":
                text = ai.read_file(path) or ""
                kind = None
            else:
                import ai_media
                with tempfile.TemporaryDirectory() as tmp:
                    if ext in ai_media.IMG_EXT:
                        text = ai_media.process_image(path, tmp)
                    elif ext in ai_media.VID_EXT:
                        text = ai_media.process_video(path, tmp)
                    else:
                        text = ai_media.process_audio(path, tmp)
                kind = "media"
            if not text.strip():
                return set_job(job, "ошибка: не удалось извлечь содержимое")
            con = ai.db()
            con.execute("DELETE FROM docs WHERE path = ?", (path,))
            parts = list(ai.chunks(text))
            name = os.path.basename(path)
            embs = ai.embed_batch([f"{name}\n{part}" if kind else part for part in parts])
            con.executemany("INSERT INTO docs (path, part, text, embedding) VALUES (?, ?, ?, ?)",
                            [(path, i, part, json.dumps(e)) for i, (part, e) in enumerate(zip(parts, embs))])
            con.commit()
            con.close()
            ai.invalidate_cache()
        set_job(job, f"готово, частей: {len(parts)}")
    except Exception as e:
        set_job(job, f"ошибка: {e}")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # keep-alive: быстрее, нет переподключений

    def log_message(self, fmt, *args):
        sys.stderr.write("%s  %s\n" % (self.address_string(), fmt % args))

    def send(self, code, obj=None, html=None, ctype=None):
        data = html.encode("utf-8") if html is not None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype or ("text/html; charset=utf-8" if html is not None
                                                   else "application/json; charset=utf-8"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if not KEY:
            return False
        got = self.headers.get("Authorization", "")
        if got.startswith("Bearer "):
            token = got[7:]
            variants = {token, urllib.parse.unquote(token)}
            try:
                variants.add(token.encode("latin-1").decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            if any(hmac.compare_digest(v.encode(), KEY.encode()) for v in variants):
                return True
        try:
            c = SimpleCookie(self.headers.get("Cookie", ""))
            val = urllib.parse.unquote(c["aikey"].value) if "aikey" in c else ""
        except Exception:
            val = ""
        return hmac.compare_digest(val.encode(), KEY.encode()) if val else False

    # ---------- GET ----------
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            page = os.path.join(STATIC_DIR, "index.html")
            if os.path.isfile(page):
                with open(page, encoding="utf-8") as f:
                    return self.send(200, html=f.read())
            return self.send(200, html="<h1>Мой AI</h1><p>Не найден static/index.html</p>")
        if path == "/api/health":
            return self.send(200, {"ok": True})
        if not self.authorized():
            return self.send(401, {"error": "Неверный ключ"})
        if path == "/api/jobs":
            with JOBS_LOCK:
                return self.send(200, {"jobs": list(JOBS)})
        if path == "/api/files":
            files = []
            for folder, kind in [(UPLOAD_DIR, "загружено"), (GENERATED_DIR, "создано")]:
                if not os.path.isdir(folder):
                    continue
                for name in sorted(os.listdir(folder), reverse=True):
                    p = os.path.join(folder, name)
                    if os.path.isfile(p):
                        files.append({"name": name, "url": "/files/" + name,
                                      "size": os.path.getsize(p), "kind": kind})
            return self.send(200, {"files": files})
        if path.startswith("/files/"):
            name = os.path.basename(urllib.parse.unquote(path[7:]))
            for folder in [UPLOAD_DIR, GENERATED_DIR]:
                p = os.path.join(folder, name)
                if os.path.isfile(p):
                    ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
                    data = open(p, "rb").read()
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("X-Content-Type-Options", "nosniff")
                    if "download=1" in self.path:
                        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                    self.end_headers()
                    self.wfile.write(data)
                    return
            return self.send(404, {"error": "Файл не найден"})
        return self.send(404, {"error": "Не найдено"})

    # ---------- POST ----------
    def do_POST(self):
        if not self.authorized():
            return self.send(401, {"error": "Неверный ключ: введите пароль в верхнее поле"})

        if self.path == "/api/upload_raw":
            return self.handle_upload_raw()

        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            return self.send(413, {"error": "Слишком большой запрос"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            return self.send(400, {"error": "Неверный JSON"})

        if self.path == "/api/ask":
            task = body.get("task", "").strip()
            if not task:
                return self.send(400, {"error": "Пустой запрос"})
            with ASK_SEM:
                result = ai.solve(task)
            return self.send(200, result)

        if self.path == "/api/save":
            task = body.get("task", "").strip()
            solution = body.get("solution", "").strip()
            if not task or not solution:
                return self.send(400, {"error": "Нужны task и solution"})
            ai.save(task, solution, "web")
            return self.send(200, {"ok": True})

        if self.path == "/api/upload":
            name = os.path.basename(body.get("name", "file"))
            data = body.get("data", "")
            if not data:
                return self.send(400, {"error": "Нет данных файла"})
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            path = os.path.join(UPLOAD_DIR, name)
            try:
                raw = base64.b64decode(data)
            except Exception:
                return self.send(400, {"error": "Битые base64-данные"})
            with open(path, "wb") as f:
                f.write(raw)
            job = {"file": name, "status": "в очереди"}
            with JOBS_LOCK:
                JOBS.append(job)
            threading.Thread(target=process_upload, args=(path, job), daemon=True).start()
            return self.send(200, {"ok": True, "file": name})

        if self.path == "/api/image":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                return self.send(400, {"error": "Нужен prompt"})
            job = {"file": "image", "status": "в очереди"}
            with JOBS_LOCK:
                JOBS.append(job)
            threading.Thread(target=run_generation, args=("image", prompt, job), daemon=True).start()
            return self.send(200, {"ok": True})

        if self.path == "/api/video":
            scenes = body.get("scenes", [])
            if not scenes:
                return self.send(400, {"error": "Нужны scenes"})
            job = {"file": "video", "status": "в очереди"}
            with JOBS_LOCK:
                JOBS.append(job)
            threading.Thread(target=run_generation, args=("video", scenes, job), daemon=True).start()
            return self.send(200, {"ok": True})

        return self.send(404, {"error": "Неизвестный API"})

    def handle_upload_raw(self):
        """Потоковая загрузка: тело = base64, имя в X-File-Name. Не грузит RAM."""
        name = os.path.basename(self.headers.get("X-File-Name", "file")) or "file"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        path = os.path.join(UPLOAD_DIR, name)
        leftover = b""
        total = 0
        try:
            with open(path, "wb") as f:
                while True:
                    chunk = self.rfile.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_UPLOAD:
                        f.close()
                        os.unlink(path)
                        return self.send(413, {"error": "Файл больше 4 ГБ"})
                    data = leftover + chunk
                    n = len(data) - (len(data) % 4)
                    leftover = data[n:]
                    if n:
                        f.write(base64.b64decode(data[:n]))
                if leftover:
                    pad = (-len(leftover)) % 4
                    f.write(base64.b64decode(leftover + b"=" * pad))
        except (OSError, ValueError) as e:
            try:
                os.unlink(path)
            except OSError:
                pass
            return self.send(400, {"error": f"Ошибка загрузки: {e}"})
        job = {"file": name, "status": "в очереди"}
        with JOBS_LOCK:
            JOBS.append(job)
        threading.Thread(target=process_upload, args=(path, job), daemon=True).start()
        return self.send(200, {"ok": True, "file": name})


def main():
    if not KEY or len(KEY) < 12:
        print("Задайте ключ доступа длиной от 12 символов:")
        print('  AI_SERVER_KEY="придумайте-длинный-пароль" python3 ai_server.py')
        sys.exit(1)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(GENERATED_DIR, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Сервер запущен: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
