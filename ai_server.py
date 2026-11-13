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
MAX_BODY = 20 * 1024 * 1024  # 20 МБ на запрос
UPLOAD_DIR = os.path.expanduser("~/znaniya/uploads")

# Процессор тянет один запрос за раз: остальные ждут в очереди, а не тормозят друг друга.
MODEL_LOCK = threading.Lock()

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
 <p>Текстовые файлы: .txt, .md, код, .csv. PDF загружайте через команду learn на сервере.</p>
 <input id="file" type="file" multiple><div class="row"><button id="up" class="grey">Загрузить</button></div>
 <div id="upinfo" class="meta"></div>
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
  $("up").disabled=true;
  for(const f of files){
    $("upinfo").textContent="Загружаю "+f.name+"...";
    try{ const j=await api("/api/learn",{name:f.name,text:await f.text()}); $("upinfo").textContent=f.name+": "+j.parts+" частей добавлено"; }
    catch(e){ $("upinfo").textContent=f.name+": "+e.message; }
  }
  $("up").disabled=false;
};
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

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("Слишком большой запрос (больше 20 МБ)")
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except json.JSONDecodeError:
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
        self.send(404, {"error": "Нет такого адреса"})

    def do_POST(self):
        if not self.authorized():
            return self.send(401, {"error": "Неверный ключ"})
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
