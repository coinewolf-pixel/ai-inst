#!/usr/bin/env python3
"""
ai_media.py — добавить фото, видео и аудио в базу знаний ai.py.

  python3 ai_media.py папка_или_файл            обработать новые файлы
  python3 ai_media.py папка_или_файл --force    обработать заново, даже уже загруженные

Фото:  модель зрения составляет подробное описание (что на снимке, текст на нём).
Видео: описываются кадры каждые 30 секунд, речь расшифровывается в текст.
Аудио: речь расшифровывается в текст.
Всё сохраняется как текст, и потом по нему можно задавать вопросы через ai.py.

Подготовка (один раз):
  sudo apt install -y ffmpeg python3-venv
  ollama pull qwen2.5vl:3b
  python3 -m venv ~/aienv && ~/aienv/bin/pip install faster-whisper
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai  # noqa: E402

# ---------- НАСТРОЙКИ ----------
VISION_MODEL = os.environ.get("AI_VISION_MODEL", "qwen2.5vl:3b")   # модель, которая смотрит на картинки
WHISPER_PY = os.environ.get("AI_WHISPER_PY", os.path.expanduser("~/aienv/bin/python"))
WHISPER_SIZE = os.environ.get("AI_WHISPER_SIZE", "small")         # tiny / base / small / medium
FRAME_EVERY = 30      # секунд между кадрами видео
MAX_FRAMES = 12       # не больше стольких кадров на одно видео
IMG_MAX_SIDE = 896    # картинки уменьшаются до этого размера: так быстрее и не хуже
# -------------------------------

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VID_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUD_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus"}

PHOTO_PROMPT = (
    "Опиши это изображение подробно на русском языке: что и кто изображён, обстановка, "
    "предметы, цвета, действия. Если на изображении есть текст, перепиши его дословно. "
    "Если это скриншот программы или код, опиши, что на экране."
)
FRAME_PROMPT = "Кратко опиши на русском, что происходит на этом кадре видео. Если есть текст, перепиши его."

WHISPER_CODE = r"""
import sys
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[2], device="cpu", compute_type="int8")
segs, info = m.transcribe(sys.argv[1], vad_filter=True)
for s in segs:
    t = int(s.start)
    print(f"[{t//3600:02d}:{t%3600//60:02d}:{t%60:02d}] {s.text.strip()}", flush=True)
"""


def native_url(path):
    base = ai.BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base + path


def run(cmd, timeout=600):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        sys.exit(f"Не найдена программа {cmd[0]}: sudo apt install -y ffmpeg")


def to_small_jpeg(src, dst, seek=None):
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if seek is not None:
        cmd += ["-ss", str(seek)]
    cmd += ["-i", src, "-frames:v", "1",
            "-vf", f"scale='if(gt(iw,ih),min({IMG_MAX_SIDE},iw),-2)':'if(gt(iw,ih),-2,min({IMG_MAX_SIDE},ih))'",
            "-q:v", "3", dst]
    r = run(cmd)
    return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0


def look(jpeg_path, prompt):
    with open(jpeg_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {"model": VISION_MODEL, "stream": False,
               "messages": [{"role": "user", "content": prompt, "images": [b64]}]}
    req = urllib.request.Request(native_url("/api/chat"), data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            return json.loads(resp.read().decode())["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        raise ai.AIError(f"Ошибка модели зрения ({e.code}): {e.read().decode('utf-8', 'replace')}\n"
                         f"Скачайте её: ollama pull {VISION_MODEL}")
    except urllib.error.URLError as e:
        raise ai.AIError(f"Ollama не отвечает: {e.reason}", fatal=True)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def transcribe(path):
    if not os.path.exists(WHISPER_PY):
        print("  речь пропущена: не установлен faster-whisper "
              "(python3 -m venv ~/aienv && ~/aienv/bin/pip install faster-whisper)", file=sys.stderr)
        return ""
    print(f"  расшифровываю речь (whisper {WHISPER_SIZE}), это долго...", file=sys.stderr)
    r = run([WHISPER_PY, "-c", WHISPER_CODE, path, WHISPER_SIZE], timeout=6 * 3600)
    if r.returncode != 0:
        print("  ошибка расшифровки: " + r.stderr.strip()[-300:], file=sys.stderr)
        return ""
    return r.stdout.strip()


def ts(sec):
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def process_image(path, tmp):
    small = os.path.join(tmp, "img.jpg")
    if not to_small_jpeg(path, small):
        print("  не удалось открыть картинку, пропускаю", file=sys.stderr)
        return ""
    return f"Фото: {os.path.basename(path)}\n\n{look(small, PHOTO_PROMPT)}"


def process_video(path, tmp):
    dur = duration(path)
    times = [t for t in range(0, int(dur) + 1, FRAME_EVERY)][:MAX_FRAMES] or [0]
    lines = [f"Видео: {os.path.basename(path)}", f"Длительность: {ts(dur)}", "", "Что видно на кадрах:"]
    for n, t in enumerate(times, 1):
        frame = os.path.join(tmp, f"f{n}.jpg")
        if to_small_jpeg(path, frame, seek=t):
            print(f"  кадр {n}/{len(times)} ({ts(t)})", file=sys.stderr)
            lines.append(f"[{ts(t)}] {look(frame, FRAME_PROMPT)}")
    speech = transcribe(path)
    if speech:
        lines += ["", "Речь в видео:", speech]
    return "\n".join(lines)


def process_audio(path, tmp):
    speech = transcribe(path)
    return f"Аудио: {os.path.basename(path)}\n\nРечь:\n{speech}" if speech else ""


def store(path, text):
    con = ai.db()
    con.execute("DELETE FROM docs WHERE path = ?", (path,))
    parts = list(ai.chunks(text))
    name = os.path.basename(path)
    for i, part in enumerate(parts):
        con.execute("INSERT INTO docs (path, part, text, embedding) VALUES (?, ?, ?, ?)",
                    (path, i, part, json.dumps(ai.embed(f"{name}\n{part}"))))
    con.commit()
    con.close()
    return len(parts)


def already_loaded(path):
    con = ai.db()
    row = con.execute("SELECT 1 FROM docs WHERE path = ? LIMIT 1", (path,)).fetchone()
    con.close()
    return row is not None


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]
    if len(args) != 1:
        print(__doc__)
        return
    target = args[0]
    if os.path.isdir(target):
        files = [os.path.join(r, f) for r, _, fs in os.walk(target) for f in sorted(fs)]
    elif os.path.isfile(target):
        files = [target]
    else:
        sys.exit(f"Не найдено: {target}")
    media = [os.path.abspath(f) for f in files
             if os.path.splitext(f)[1].lower() in IMG_EXT | VID_EXT | AUD_EXT]
    if not media:
        sys.exit("Фото, видео или аудио не найдено.")
    print(f"Найдено медиафайлов: {len(media)}", file=sys.stderr)

    other = len(files) - len(media)
    if other:
        print(f"Не медиафайлов пропущено: {other} (их загружает ai.py learn)", file=sys.stderr)

    done = skipped = 0
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, path in enumerate(media, 1):
            if not force and already_loaded(path):
                skipped += 1
                continue
            ext = os.path.splitext(path)[1].lower()
            print(f"[{n}/{len(media)}] {path}", file=sys.stderr)
            try:
                if ext in IMG_EXT:
                    text = process_image(path, tmp)
                elif ext in VID_EXT:
                    text = process_video(path, tmp)
                else:
                    text = process_audio(path, tmp)
                if not text.strip():
                    failed.append((path, "не удалось извлечь содержимое"))
                    continue
                print(f"  сохранено частей: {store(path, text)}", file=sys.stderr)
                done += 1
            except ai.AIError as e:
                if e.fatal:
                    raise
                failed.append((path, str(e).splitlines()[0]))
            except Exception as e:  # один плохой файл не останавливает остальные
                failed.append((path, f"ошибка: {e}"))
    print(f"Готово: обработано {done}, уже были загружены: {skipped}, с ошибкой: {len(failed)}")
    for path, why in failed:
        print(f"  пропущен: {os.path.basename(path)} — {why}")


if __name__ == "__main__":
    try:
        main()
    except ai.AIError as e:
        sys.exit(str(e))
