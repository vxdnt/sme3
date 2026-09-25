from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import STATIC_DIR


def ensure_event_images() -> None:
    image_dir = STATIC_DIR / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    jpg = image_dir / "BFISS.jpg"
    png = image_dir / "BFISS2.png"
    if jpg.exists() and png.exists():
        return

    img = Image.new("RGB", (800, 1200), (10, 10, 10))
    draw = ImageDraw.Draw(img)
    draw.rectangle([36, 36, 764, 1164], outline=(227, 84, 74), width=6)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        small = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
        small = font
    draw.text((80, 480), "Big Fat Indian Scam Sangeet", fill=(255, 255, 255), font=font)
    draw.text((80, 540), "27 Sep 2026  ·  6:00 PM", fill=(154, 160, 166), font=small)
    draw.text((80, 580), "Eumsik Garden Restaurant", fill=(154, 160, 166), font=small)
    if not jpg.exists():
        img.save(jpg, format="JPEG", quality=85)
    if not png.exists():
        img.save(png, format="PNG")
