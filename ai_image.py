#!/usr/bin/env python3
"""
ai_image.py — создать картинку по описанию или видео по сценарию.

  python3 ai_image.py image "кот в космосе, мультяшный стиль"
  python3 ai_image.py video сценарий.txt

Сценарий для видео: обычный текстовый файл, каждая непустая строка — одна сцена.
Для каждой сцены создаётся картинка с плавным приближением и подписью внизу,
сцены склеиваются в один mp4. Это видео-слайдшоу: полноценное «живое» видео
на процессоре без видеокарты сделать нельзя.

Готовые файлы складываются в ~/znaniya/generated.

Подготовка (один раз, скачается около 2-3 ГБ):
  sudo apt install -y ffmpeg fonts-dejavu-core python3-venv
  python3 -m venv ~/aienv
  ~/aienv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
  ~/aienv/bin/pip install diffusers transformers accelerate
Модель (около 2,5 ГБ) скачается сама при первом запуске.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai  # noqa: E402

# ---------- НАСТРОЙКИ ----------
IMAGE_MODEL = os.environ.get("AI_IMAGE_MODEL", "stabilityai/sd-turbo")
IMAGE_PY = os.environ.get("AI_IMAGE_PY", os.path.expanduser("~/aienv/bin/python"))
OUT_DIR = os.environ.get("AI_IMAGE_DIR", os.path.expanduser("~/znaniya/generated"))
STEPS = int(os.environ.get("AI_IMAGE_STEPS", "2"))   # 1 — быстрее, 4 — качественнее
SIZE = 512                                           # родной размер SD-Turbo
SCENE_SECONDS = 4                                    # длительность одной сцены видео
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
# -------------------------------

# Этот код выполняется в ~/aienv, где стоят torch и diffusers.
# Модель загружается один раз, потом создаются все картинки по списку.
GEN_CODE = r"""
import json, os, sys
import torch
from diffusers import AutoPipelineForText2Image
torch.set_num_threads(os.cpu_count() or 4)
job = json.loads(sys.stdin.read())
pipe = AutoPipelineForText2Image.from_pretrained(job["model"], torch_dtype=torch.float32)
pipe.set_progress_bar_config(disable=True)
for item in job["items"]:
    g = torch.Generator().manual_seed(item["seed"])
    img = pipe(prompt=item["prompt"], num_inference_steps=job["steps"], guidance_scale=0.0,
               width=job["size"], height=job["size"], generator=g).images[0]
    img.save(item["out"])
    print(item["out"], flush=True)
"""

TRANSLATE_SYSTEM = (
    "Ты переводишь описания картинок для генератора изображений. Переведи описание на английский "
    "и сделай из него короткий промпт: перечисли через запятую объект, действие, обстановку, стиль, "
    "освещение. Ответь только промптом, без пояснений и кавычек."
)


class ImageError(Exception):
    pass


def to_english(text):
    """Модель для картинок понимает английский лучше, поэтому переводим локальной моделью."""
    if all(ord(c) < 128 for c in text):
        return text
    try:
        out = ai.chat([{"role": "system", "content": TRANSLATE_SYSTEM},
                       {"role": "user", "content": text}]).strip().strip('"').splitlines()
        out = next((line for line in out if line.strip()), "")
        return out[:400] or text
    except ai.AIError:
        return text  # без перевода тоже сработает, просто хуже


def generate(prompts, log=print):
    """Создаёт картинки по списку описаний. Возвращает пути к файлам."""
    if not os.path.exists(IMAGE_PY):
        raise ImageError("Не установлен генератор картинок. Выполните подготовку из начала ai_image.py")
    os.makedirs(OUT_DIR, exist_ok=True)
    items = []
    for p in prompts:
        en = to_english(p)
        log(f"  промпт: {en}")
        items.append({"prompt": en, "seed": int.from_bytes(os.urandom(4), "big"),
                      "out": os.path.join(OUT_DIR, f"img_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.png")})
    job = {"model": IMAGE_MODEL, "steps": STEPS, "size": SIZE, "items": items}
    log(f"  рисую {len(items)} шт. (первый запуск дольше: скачивается модель)...")
    try:
        r = subprocess.run([IMAGE_PY, "-c", GEN_CODE], input=json.dumps(job), capture_output=True,
                           text=True, timeout=6 * 3600)
    except subprocess.TimeoutExpired:
        raise ImageError("Генерация не уложилась в 6 часов")
    done = [i["out"] for i in items if os.path.exists(i["out"])]
    if r.returncode != 0 and not done:
        tail = (r.stderr.strip().splitlines() or ["неизвестная ошибка"])[-1]
        raise ImageError("Ошибка генератора: " + tail[-300:])
    return done


def make_video(scenes, log=print):
    """Сценарий -> картинка на каждую сцену -> слайдшоу mp4 с подписями."""
    scenes = [s.strip() for s in scenes if s.strip()]
    if not scenes:
        raise ImageError("В сценарии нет сцен")
    if len(scenes) > 60:
        raise ImageError("Слишком много сцен (больше 60)")
    images = generate(scenes, log)
    if len(images) != len(scenes):
        log(f"  внимание: получилось картинок {len(images)} из {len(scenes)}")
    fps = 25
    frames = SCENE_SECONDS * fps
    out = os.path.join(OUT_DIR, f"video_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for n, (img, text) in enumerate(zip(images, scenes), 1):
            log(f"  сцена {n}/{len(images)}")
            txt = os.path.join(tmp, f"t{n}.txt")
            with open(txt, "w", encoding="utf-8") as f:
                f.write("\n".join(textwrap.wrap(text, 42)[:3]))
            vf = (f"scale={SIZE * 2}:{SIZE * 2},"
                  f"zoompan=z='min(zoom+0.0012,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={frames}:s={SIZE}x{SIZE}:fps={fps}")
            if os.path.exists(FONT):
                vf += (f",drawtext=fontfile={FONT}:textfile={txt}:fontcolor=white:fontsize=20"
                       f":line_spacing=6:box=1:boxcolor=black@0.55:boxborderw=10"
                       f":x=(w-text_w)/2:y=h-text_h-24")
            part = os.path.join(tmp, f"p{n}.mp4")
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", img, "-vf", vf,
                                "-t", str(SCENE_SECONDS), "-r", str(fps), "-c:v", "libx264",
                                "-preset", "veryfast", "-pix_fmt", "yuv420p", part],
                               capture_output=True, text=True)
            if r.returncode == 0:
                parts.append(part)
            else:
                log("  сцена пропущена: " + r.stderr.strip()[-200:])
        if not parts:
            raise ImageError("Не удалось собрать ни одной сцены (установлен ли ffmpeg?)")
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            f.writelines(f"file '{p}'\n" for p in parts)
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                            "-c", "copy", "-movflags", "+faststart", out], capture_output=True, text=True)
        if r.returncode != 0:
            raise ImageError("Не удалось склеить видео: " + r.stderr.strip()[-200:])
    return out


def main():
    a = sys.argv[1:]
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    try:
        if len(a) == 2 and a[0] == "image":
            for p in generate([a[1]], log):
                print(f"Готово: {p}")
        elif len(a) == 2 and a[0] == "video":
            with open(a[1], encoding="utf-8") as f:
                print(f"Готово: {make_video(f.read().splitlines(), log)}")
        else:
            print(__doc__)
    except (ImageError, OSError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
