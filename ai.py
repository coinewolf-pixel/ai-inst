#!/usr/bin/env python3
"""
ai.py — локальный AI с памятью решённых задач.

Команды:
  python3 ai.py ask "задача"               спросить модель (она увидит похожие задачи из памяти)
  python3 ai.py add "задача" файл.txt      сохранить готовое решение из файла в память
  python3 ai.py list                       показать, что лежит в памяти
  python3 ai.py learn папка_или_файл       загрузить ваши файлы в базу знаний
  python3 ai.py docs                       показать, какие файлы загружены

Нужен только Python 3 и запущенный Ollama. Для PDF нужен pdftotext:
  sudo apt install -y poppler-utils
"""
import json
import math
import os
import sqlite3
import subprocess
import sys
import urllib.request

TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv",
            ".sh", ".c", ".cpp", ".h", ".java", ".go", ".rs", ".php", ".sql",
            ".yaml", ".yml", ".xml", ".ini", ".cfg", ".log"}
CHUNK_CHARS = 1500  # размер куска текста, на которые режутся файлы

# ---------- НАСТРОЙКИ ----------
# Чтобы перейти на другую модель или другой сервер, меняются только эти строки.
BASE_URL = os.environ.get("AI_BASE_URL", "http://localhost:11434/v1")  # Ollama на этом ПК
API_KEY = os.environ.get("AI_API_KEY", "ollama")                       # для Ollama любой текст
CHAT_MODEL = os.environ.get("AI_CHAT_MODEL", "qwen2.5-coder:7b")       # модель, которая отвечает
EMBED_MODEL = os.environ.get("AI_EMBED_MODEL", "nomic-embed-text")     # модель для поиска в памяти
DB_PATH = os.environ.get("AI_DB", os.path.expanduser("~/ai_memory.db"))
TOP_K = 3            # сколько похожих задач показывать модели
MIN_SIMILARITY = 0.5  # ниже этого порога задача считается непохожей
MAX_EXAMPLE_CHARS = 3000  # обрезка длинных решений, чтобы не переполнить модель
# -------------------------------


def _post(path, payload, timeout=1800):
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise AIError(f"Ошибка модели ({e.code}): {body}\nПроверьте, что модель скачана: ollama list")
    except urllib.error.URLError as e:
        raise AIError(f"Не удалось подключиться к {BASE_URL}: {e.reason}\nПроверьте, что Ollama запущен: systemctl status ollama")


class AIError(Exception):
    pass


def embed(text):
    data = _post("/embeddings", {"model": EMBED_MODEL, "input": text})
    return data["data"][0]["embedding"]


def chat(messages):
    data = _post("/chat/completions", {"model": CHAT_MODEL, "messages": messages})
    return data["choices"][0]["message"]["content"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS memory (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               created TEXT DEFAULT CURRENT_TIMESTAMP,
               task TEXT NOT NULL,
               solution TEXT NOT NULL,
               source TEXT NOT NULL,
               embedding TEXT NOT NULL
           )"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS docs (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               path TEXT NOT NULL,
               part INTEGER NOT NULL,
               text TEXT NOT NULL,
               embedding TEXT NOT NULL
           )"""
    )
    return con


def read_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            out = subprocess.run(["pdftotext", "-layout", path, "-"],
                                 capture_output=True, text=True, timeout=300)
            return out.stdout
        except FileNotFoundError:
            print("  пропущен PDF (нет pdftotext): sudo apt install -y poppler-utils", file=sys.stderr)
            return ""
    if ext in TEXT_EXT:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    return None  # неподдерживаемый тип


def chunks(text):
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    buf = ""
    for p in paras:
        while len(p) > CHUNK_CHARS:
            if buf:
                yield buf
                buf = ""
            yield p[:CHUNK_CHARS]
            p = p[CHUNK_CHARS:]
        if len(buf) + len(p) + 2 > CHUNK_CHARS:
            yield buf
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf:
        yield buf


def cmd_learn(target):
    if os.path.isdir(target):
        files = [os.path.join(r, f) for r, _, fs in os.walk(target) for f in sorted(fs)]
    elif os.path.isfile(target):
        files = [target]
    else:
        sys.exit(f"Не найдено: {target}")
    con = db()
    added = 0
    for path in files:
        path = os.path.abspath(path)
        text = read_file(path)
        if text is None:
            continue
        if not text.strip():
            continue
        con.execute("DELETE FROM docs WHERE path = ?", (path,))  # повторная загрузка обновляет файл
        parts = list(chunks(text))
        print(f"  {path}  ({len(parts)} частей)", file=sys.stderr)
        for i, part in enumerate(parts):
            con.execute("INSERT INTO docs (path, part, text, embedding) VALUES (?, ?, ?, ?)",
                        (path, i, part, json.dumps(embed(part))))
        con.commit()
        added += 1
    con.close()
    print(f"Загружено файлов: {added}")


def cmd_docs():
    con = db()
    rows = con.execute("SELECT path, COUNT(*) FROM docs GROUP BY path ORDER BY path").fetchall()
    con.close()
    if not rows:
        print("Файлы пока не загружены.")
    for path, n in rows:
        print(f"{n:5} частей  {path}")


def search_docs(q_emb):
    con = db()
    rows = con.execute("SELECT path, text, embedding FROM docs").fetchall()
    con.close()
    scored = [(cosine(q_emb, json.loads(e)), p, t) for p, t, e in rows]
    scored.sort(key=lambda r: r[0], reverse=True)
    return [r for r in scored[:TOP_K] if r[0] >= MIN_SIMILARITY]


def save(task, solution, source):
    con = db()
    con.execute(
        "INSERT INTO memory (task, solution, source, embedding) VALUES (?, ?, ?, ?)",
        (task, solution, source, json.dumps(embed(task))),
    )
    con.commit()
    con.close()


def search(task):
    con = db()
    rows = con.execute("SELECT task, solution, embedding FROM memory").fetchall()
    con.close()
    if not rows:
        return []
    q = embed(task)
    scored = [(cosine(q, json.loads(e)), t, s) for t, s, e in rows]
    scored.sort(key=lambda r: r[0], reverse=True)
    return [r for r in scored[:TOP_K] if r[0] >= MIN_SIMILARITY]


def solve(task):
    """Ответ на задачу с учётом памяти и файлов. Возвращает словарь (используется и сервером)."""
    found = search(task)
    system = "Ты опытный разработчик. Отвечай точно и по делу, код давай целиком."
    if found:
        examples = "\n\n".join(
            f"--- Задача ---\n{t}\n--- Решение ---\n{s[:MAX_EXAMPLE_CHARS]}" for _, t, s in found
        )
        system += (
            "\n\nНиже решения похожих задач, которые уже сработали. "
            "Используй их как образец, если они подходят.\n\n" + examples
        )
    docs = search_docs(embed(task))
    if docs:
        ctx = "\n\n".join(f"--- Из файла {os.path.basename(p)} ---\n{t}" for _, p, t in docs)
        system += "\n\nСведения из файлов пользователя, опирайся на них:\n\n" + ctx
    answer = chat([{"role": "system", "content": system}, {"role": "user", "content": task}])
    return {
        "answer": answer,
        "memory": [{"score": round(s, 2), "task": t[:200]} for s, t, _ in found],
        "files": [{"score": round(s, 2), "file": os.path.basename(p)} for s, p, _ in docs],
    }


def cmd_ask(task):
    print(f"[модель] {CHAT_MODEL} думает, это может занять несколько минут...", file=sys.stderr)
    r = solve(task)
    for m in r["memory"]:
        print(f"[память] {m['score']:.2f}  {m['task'][:70]}", file=sys.stderr)
    for f in r["files"]:
        print(f"[файлы]  {f['score']:.2f}  {f['file']}", file=sys.stderr)
    if not r["memory"] and not r["files"]:
        print("[память] похожего ничего нет, модель решала с нуля", file=sys.stderr)
    answer = r["answer"]
    print("\n" + answer + "\n")

    if sys.stdin.isatty():
        if input("Решение сработало? Сохранить в память? (y/n): ").strip().lower() in ("y", "д"):
            save(task, answer, "local:" + CHAT_MODEL)
            print("Сохранено.")


def cmd_add(task, path):
    with open(path, encoding="utf-8") as f:
        solution = f.read().strip()
    if not solution:
        sys.exit("Файл пустой, сохранять нечего.")
    save(task, solution, "file:" + os.path.basename(path))
    print("Сохранено в память.")


def cmd_list():
    con = db()
    rows = con.execute("SELECT id, created, source, task FROM memory ORDER BY id").fetchall()
    con.close()
    if not rows:
        print("Память пока пустая.")
    for i, created, source, task in rows:
        print(f"{i:4}  {created}  [{source}]  {task[:80]}")
    print(f"\nВсего записей: {len(rows)}. Файл базы: {DB_PATH}")


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "ask":
        cmd_ask(a[1])
    elif len(a) == 3 and a[0] == "add":
        cmd_add(a[1], a[2])
    elif len(a) == 1 and a[0] == "list":
        cmd_list()
    elif len(a) == 2 and a[0] == "learn":
        cmd_learn(a[1])
    elif len(a) == 1 and a[0] == "docs":
        cmd_docs()
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except AIError as e:
        sys.exit(str(e))
