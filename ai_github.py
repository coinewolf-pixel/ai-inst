#!/usr/bin/env python3
"""
ai_github.py — скачать репозиторий с GitHub и добавить его в базу знаний ai.py.

  python3 ai_github.py https://github.com/владелец/репозиторий   скачать или обновить и загрузить
  python3 ai_github.py user имя_на_github                         скачать ВСЕ репозитории пользователя
  python3 ai_github.py list                                       какие репозитории уже скачаны
  python3 ai_github.py update                                     обновить все скачанные

Закрытые (private) репозитории: создайте токен на github.com/settings/tokens
(classic, галочка repo) и запускайте так:
  GITHUB_TOKEN=ваш_токен python3 ai_github.py user имя_на_github

Нужен git:  sudo apt install -y git
Файл ai.py должен лежать в той же папке.
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai  # noqa: E402

REPO_DIR = os.path.expanduser("~/znaniya/github")
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "__pycache__",
             ".venv", "venv", "target", ".next", ".idea", ".vscode"}
MAX_FILE_BYTES = 300 * 1024   # файлы больше 300 КБ пропускаются (обычно это сгенерированный мусор)
MAX_FILES = 2000              # защита от огромных репозиториев


def parse_url(url):
    m = re.match(r"^(?:https?://)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url.strip())
    if not m:
        sys.exit("Нужна ссылка вида https://github.com/владелец/репозиторий")
    return m.group(1), m.group(2)


def git(*args, cwd=None):
    auth = []
    if TOKEN:  # токен передаётся только в заголовке, на диск не сохраняется
        cred = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
        auth = ["-c", f"http.https://github.com/.extraHeader=Authorization: Basic {cred}"]
    try:
        r = subprocess.run(["git", *auth, *args], cwd=cwd, capture_output=True, text=True, timeout=900,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except FileNotFoundError:
        sys.exit("Не установлен git: sudo apt install -y git")
    if r.returncode != 0:
        sys.exit("Ошибка git: " + (r.stderr.strip() or r.stdout.strip()))
    return r.stdout


def fetch(owner, name):
    path = os.path.join(REPO_DIR, f"{owner}__{name}")
    if os.path.isdir(os.path.join(path, ".git")):
        print(f"Обновляю {owner}/{name}...", file=sys.stderr)
        git("pull", "--ff-only", "-q", cwd=path)
    else:
        os.makedirs(REPO_DIR, exist_ok=True)
        print(f"Скачиваю {owner}/{name}...", file=sys.stderr)
        git("clone", "--depth", "1", "-q", f"https://github.com/{owner}/{name}.git", path)
    return path


def learn_repo(path):
    files = []
    for root, dirs, fs in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(fs):
            p = os.path.join(root, f)
            if os.path.splitext(f)[1].lower() in ai.TEXT_EXT | {".pdf"} and os.path.getsize(p) <= MAX_FILE_BYTES:
                files.append(p)
    if len(files) > MAX_FILES:
        print(f"В репозитории {len(files)} файлов, загружаю первые {MAX_FILES}.", file=sys.stderr)
        files = files[:MAX_FILES]
    print(f"Файлов для загрузки: {len(files)}. На процессоре это может занять долго.", file=sys.stderr)

    con = ai.db()
    con.execute("DELETE FROM docs WHERE path LIKE ?", (path + os.sep + "%",))  # убрать старую версию репо
    con.commit()
    added = 0
    for n, p in enumerate(files, 1):
        text = ai.read_file(p)
        if not text or not text.strip():
            continue
        rel = os.path.relpath(p, path)
        parts = list(ai.chunks(text))
        for i, part in enumerate(parts):
            # имя файла в начале куска помогает поиску понять, откуда код
            con.execute("INSERT INTO docs (path, part, text, embedding) VALUES (?, ?, ?, ?)",
                        (p, i, part, ai.json.dumps(ai.embed(f"{rel}\n{part}"))))
        con.commit()
        added += 1
        print(f"  [{n}/{len(files)}] {rel}  ({len(parts)} частей)", file=sys.stderr)
    con.close()
    print(f"Готово: в базу добавлено файлов: {added}")


def user_repos(user):
    """Список репозиториев пользователя (с токеном — включая закрытые)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai_github"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
        base = "https://api.github.com/user/repos?affiliation=owner&per_page=100&page="
    else:
        base = f"https://api.github.com/users/{user}/repos?type=owner&per_page=100&page="
    repos, page = [], 1
    while True:
        req = urllib.request.Request(base + str(page), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                batch = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                sys.exit(f"Пользователь {user} не найден на GitHub")
            if e.code == 401:
                sys.exit("Неверный GITHUB_TOKEN")
            sys.exit(f"Ошибка GitHub ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}")
        except urllib.error.URLError as e:
            sys.exit(f"Нет связи с GitHub: {e.reason}")
        if not batch:
            break
        repos += [(r["owner"]["login"], r["name"]) for r in batch
                  if not r.get("fork") and not r.get("archived")]
        page += 1
    return repos


def cmd_user(user):
    repos = user_repos(user)
    if not repos:
        sys.exit("Репозиториев не найдено (форки и архивные пропускаются).")
    print(f"Найдено репозиториев: {len(repos)}", file=sys.stderr)
    for n, (owner, name) in enumerate(repos, 1):
        print(f"\n=== [{n}/{len(repos)}] {owner}/{name} ===", file=sys.stderr)
        learn_repo(fetch(owner, name))


def cmd_list():
    if not os.path.isdir(REPO_DIR):
        print("Репозитории пока не скачаны.")
        return
    for d in sorted(os.listdir(REPO_DIR)):
        print(d.replace("__", "/", 1))


def main():
    a = sys.argv[1:]
    if len(a) == 1 and a[0] == "list":
        cmd_list()
    elif len(a) == 2 and a[0] == "user":
        cmd_user(a[1])
    elif len(a) == 1 and a[0] == "update":
        if not os.path.isdir(REPO_DIR):
            sys.exit("Репозитории пока не скачаны.")
        for d in sorted(os.listdir(REPO_DIR)):
            owner, name = d.split("__", 1)
            learn_repo(fetch(owner, name))
    elif len(a) == 1:
        learn_repo(fetch(*parse_url(a[0])))
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except ai.AIError as e:
        sys.exit(str(e))
