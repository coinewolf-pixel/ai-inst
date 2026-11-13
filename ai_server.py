#!/usr/bin/env python3
"""
ai_server.py — сервер для ai.py: страница чата в браузере + API для ваших сервисов.

Запуск:
  AI_SERVER_KEY="придумайте-длинный-пароль" python3 ai_server.py

Открыть в браузере:  http://IP-сервера:8000
Файл ai.py должен лежать в той же папке.

API (ключ передаётся в заголовке  Authorization: Bearer ВАШ_КЛЮЧ):
  POST /api/ask      {"task": "..."}                      -> {"answer", "memory", "files"}
  POST /api/save     {"task": "...", "solution": "..."}   -> сохранить рабочее решение в память
  POST /api/learn    {"name": "файл.txt", "text": "..."}  -> добавить текст в базу знаний
  POST /api/upload   {"name": "фото.jpg", "data": "base64"} -> любой файл: текст, PDF, фото, видео, аудио
  GET  /api/jobs                                          -> что сейчас обрабатывается в фоне
  GET  /api/docs                                          -> список загруженных файлов
  GET  /api/health                                        -> проверка, что сервер жив (без ключа)
"""
import hmac
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai  # noqa: E402

HOST = os.environ.get("AI_SERVER_HOST", "0.0.0.0")
PORT = int(os.environ.get("AI_SERVER_PORT", "8000"))
KEY = os.environ.get("AI_SERVER_KEY", "")
MAX_BODY = 700 * 1024 * 1024  # до ~500 МБ файла (base64 раздувает размер на треть)
UPLOAD_DIR = os.path.expanduser("~/znaniya/uploads")

# Процессор тянет один запрос за раз: остальные ждут в очереди, а не тормозят друг друга.
MODEL_LOCK = threading.Lock()

# Фоновая обработка фото и видео: она долгая, поэтому браузер не ждёт её окончания.
JOBS = []          # [{"file": ..., "status": "в очереди" / "обрабатывается" / "готово" / "ошибка: ..."}]
JOBS_LOCK = threading.Lock()


def set_job(job, status):
    with JOBS_LOCK:
        job["status"] = status


def process_upload(path, job):
    """Обрабатывает сохранённый файл: текст и PDF через ai.py, медиа через ai_media.py."""
    import tempfile
    ext = os.path.splitext(path)[1].lower()
    try:
        with MODEL_LOCK:
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
            for i, part in enumerate(parts):
                emb = ai.embed(f"{name}\n{part}" if kind else part)
                con.execute("INSERT INTO docs (path, part, text, embedding) VALUES (?, ?, ?, ?)",
                            (path, i, part, json.dumps(emb)))
            con.commit()
            con.close()
        set_job(job, f"готово, частей: {len(parts)}")
    except SystemExit as e:  # ai_media сообщает об отсутствии ffmpeg через sys.exit
        set_job(job, f"ошибка: {e}")
    except Exception as e:
        set_job(job, f"ошибка: {e}")

PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мой AI</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px;background:#f6f6f4;color:#222}
 h1{font-size:20px} .row{display:flex;gap:8px;margin:8px 0;flex-wrap:wrap}
 textarea,input{width:100%;box-sizing:border-box;padding:10px;font:inherit;border:1px solid #ccc;border-radius:8px}
 textarea{min-height:90px} button{padding:10px 16px;border:0;border-radius:8px;background:#2d5be3;color:#fff;font:inherit;cursor:pointer}
 button.grey{background:#777} button:disabled{opacity:.5}
 .msg{background:#fff;border-radius:10px;padding:12px;margin:10px 0;white-space:pre-wrap;box-shadow:0 1px 2px #0001}
 .me{background:#e8eefc} .meta{font-size:12px;color:#666;margin-top:6px}
 details{margin:14px 0;background:#fff;border-radius:10px;padding:10px}
</style></head><body>
<h1>Мой AI</h1>
<input id="key" type="password" placeholder="Ключ доступа (AI_SERVER_KEY)">
<div id="chat"></div>
<textarea id="task" placeholder="Напишите задачу..."></textarea>
<div class="row"><button id="send">Отправить</button></div>
<details><summary>Добавить файл в базу знаний</summary>
 <p>Можно: тексты, код, PDF, фото (jpg, png, webp), видео (mp4, mov, mkv), аудио (mp3, wav, m4a).
 Фото и видео обрабатываются в фоне: на процессоре фото занимает минуты, видео дольше.</p>
 <input id="file" type="file" multiple><div class="row"><button id="up" class="grey">Загрузить</button></div>
 <div id="upinfo" class="meta" style="white-space:pre-wrap"></div>
 <div id="jobs" class="meta" style="white-space:pre-wrap"></div>
</details>
<script>
const $=id=>document.getElementById(id);
try{ $("key").value=localStorage.getItem("aikey")||""; }catch(e){}
$("key").onchange=()=>{ try{localStorage.setItem("aikey",$("key").value)}catch(e){} };
function hdr(){return {"Content-Type":"application/json","Authorization":"Bearer "+$("key").value};}
function add(text,cls){const d=document.createElement("div");d.className="msg "+(cls||"");d.textContent=text;$("chat").appendChild(d);d.scrollIntoView();return d;}
async function api(path,body){
  const r=await fetch(path,{method:"POST",headers:hdr(),body:JSON.stringify(body)});
  const j=await r.json().catch(()=>({error:"Сервер вернул не JSON"}));
  if(!r.ok) throw new Error(j.error||("Ошибка "+r.status)); return j;
}
$("send").onclick=async()=>{
  const task=$("task").value.trim(); if(!task) return;
  add(task,"me"); $("task").value=""; $("send").disabled=true;
  const wait=add("Думаю... на процессоре это может занять несколько минут.");
  try{
    const j=await api("/api/ask",{task});
    wait.textContent=j.answer;
    const m=document.createElement("div"); m.className="meta";
    const src=[...j.memory.map(x=>"память: "+x.task.slice(0,40)),...j.files.map(x=>"файл: "+x.file)];
    m.textContent=src.length?("Опирался на: "+src.join("; ")):"Решал с нуля";
    const b=document.createElement("button"); b.className="grey"; b.textContent="Сработало, сохранить в память";
    b.onclick=async()=>{b.disabled=true;try{await api("/api/save",{task,solution:j.answer});b.textContent="Сохранено";}catch(e){b.textContent=e.message;}};
    wait.appendChild(m); wait.appendChild(document.createElement("br")); wait.appendChild(b);
  }catch(e){ wait.textContent="Ошибка: "+e.message; }
  $("send").disabled=false;
};
$("up").onclick=async()=>{
  const files=[...$("file").files]; if(!files.length) return;
  if(!$("key").value.trim()){ $("upinfo").textContent="Сначала введите пароль в верхнее поле"; return; }
  $("up").disabled=true;
  const log=[]; const show=()=>{$("upinfo").textContent=log.join("\n");};
  let okN=0, badN=0;
  for(const [i,f] of files.entries()){
    log.push(f.name+": отправляю..."); show();
    try{
      const data=await new Promise((ok,bad)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(",")[1]||"");r.onerror=()=>bad(new Error("не удалось прочитать файл"));r.readAsDataURL(f);});
      await api("/api/upload",{name:f.name,data});
      log[log.length-1]=f.name+": принят"; okN++;
    }catch(e){ log[log.length-1]=f.name+": пропущен — "+e.message; badN++; }
    show();
  }
  log.push("Итого: принято "+okN+", пропущено "+badN); show();
  $("up").disabled=false; jobs();
};
async function jobs(){
  try{
    const r=await fetch("/api/jobs",{headers:hdr()}); if(!r.ok) return;
    const j=await r.json();
    $("jobs").textContent=j.jobs.slice(-10).reverse().map(x=>x.file+" — "+x.status).join("\\n");
    if(j.jobs.some(x=>x.status==="в очереди"||x.status==="обрабатывается")) setTimeout(jobs,5000);
  }catch(e){}
}
jobs();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s  %s\n" % (self.address_string(), fmt % args))

    def send(self, code, obj=None, html=None):
        data = html.encode("utf-8") if html is not None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html is not None else "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        got = self.headers.get("Authorization", "")
        return bool(KEY) and hmac.compare_digest(got.encode(), ("Bearer " + KEY).encode())

    def read_raw(self):
        """Всегда дочитываем запрос до конца, иначе браузер увидит обрыв связи вместо ошибки."""
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            self.close_connection = True
            return None
        return self.rfile.read(n)

    def body(self):
        try:
            return json.loads(self._raw.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Тело запроса должно быть JSON")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, html=PAGE)
        if self.path == "/api/health":
            return self.send(200, {"ok": True, "model": ai.CHAT_MODEL})
        if self.path == "/api/docs":
            if not self.authorized():
                return self.send(401, {"error": "Неверный ключ"})
            con = ai.db()
            rows = con.execute("SELECT path, COUNT(*) FROM docs GROUP BY path ORDER BY path").fetchall()
            con.close()
            return self.send(200, {"docs": [{"file": p, "parts": n} for p, n in rows]})
        if self.path == "/api/jobs":
            if not self.authorized():
                return self.send(401, {"error": "Неверный ключ"})
            with JOBS_LOCK:
                return self.send(200, {"jobs": [dict(j) for j in JOBS[-50:]]})
        self.send(404, {"error": "Нет такого адреса"})

    def do_POST(self):
        self._raw = self.read_raw()
        if self._raw is None:
            return self.send(413, {"error": "Файл слишком большой (больше 500 МБ)"})
        if not self.authorized():
            return self.send(401, {"error": "Неверный ключ: введите пароль в верхнее поле"})
        try:
            b = self.body()
            if self.path == "/api/ask":
                task = str(b.get("task", "")).strip()
                if not task:
                    return self.send(400, {"error": "Пустая задача"})
                with MODEL_LOCK:
                    return self.send(200, ai.solve(task))
            if self.path == "/api/save":
                task, sol = str(b.get("task", "")).strip(), str(b.get("solution", "")).strip()
                if not task or not sol:
                    return self.send(400, {"error": "Нужны task и solution"})
                with MODEL_LOCK:
                    ai.save(task, sol, str(b.get("source", "api")))
                return self.send(200, {"ok": True})
            if self.path == "/api/learn":
                name = os.path.basename(str(b.get("name", "")).strip()) or "text.txt"
                text = str(b.get("text", ""))
                if not text.strip():
                    return self.send(400, {"error": "Пустой текст"})
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                path = os.path.join(UPLOAD_DIR, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                parts = list(ai.chunks(text))
                with MODEL_LOCK:
                    con = ai.db()
                    con.execute("DELETE FROM docs WHERE path = ?", (path,))
                    for i, part in enumerate(parts):
                        con.execute("INSERT INTO docs (path, part, text, embedding) VALUES (?, ?, ?, ?)",
                                    (path, i, part, json.dumps(ai.embed(part))))
                    con.commit()
                    con.close()
                return self.send(200, {"ok": True, "parts": len(parts)})
            if self.path == "/api/upload":
                import base64
                import binascii
                name = os.path.basename(str(b.get("name", "")).strip())
                if not name:
                    return self.send(400, {"error": "Нет имени файла"})
                ext = os.path.splitext(name)[1].lower()
                allowed = ai.TEXT_EXT | {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif",
                                         ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v",
                                         ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus"}
                if ext not in allowed:
                    return self.send(400, {"error": f"Тип {ext or 'без расширения'} не поддерживается"})
                try:
                    raw = base64.b64decode(str(b.get("data", "")), validate=True)
                except (binascii.Error, ValueError):
                    return self.send(400, {"error": "Файл повреждён при передаче"})
                if not raw:
                    return self.send(400, {"error": "Пустой файл"})
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                path = os.path.join(UPLOAD_DIR, name)
                with open(path, "wb") as f:
                    f.write(raw)
                job = {"file": name, "status": "в очереди"}
                with JOBS_LOCK:
                    JOBS.append(job)
                threading.Thread(target=process_upload, args=(path, job), daemon=True).start()
                return self.send(200, {"ok": True, "queued": name})
            self.send(404, {"error": "Нет такого адреса"})
        except ValueError as e:
            self.send(400, {"error": str(e)})
        except ai.AIError as e:
            self.send(502, {"error": str(e)})
        except Exception as e:  # чтобы одна ошибка не роняла сервер
            self.send(500, {"error": "Внутренняя ошибка: %s" % e})


def main():
    if len(KEY) < 12:
        sys.exit('Задайте ключ доступа длиной от 12 символов:\n'
                 '  AI_SERVER_KEY="придумайте-длинный-пароль" python3 ai_server.py')
    print(f"Сервер запущен: http://{HOST}:{PORT}  (модель {ai.CHAT_MODEL})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
