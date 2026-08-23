"""Generate PWA icons (dark rounded square + gold LB monogram)."""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "static", "icons")
os.makedirs(ICON_DIR, exist_ok=True)

DARK = (15, 17, 21, 255)      # #0f1115
GOLD = (229, 184, 66, 255)    # #e5b842


def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=DARK,
                        outline=GOLD, width=max(2, size // 48))
    font = None
    for cand in ("arialbd.ttf", "Arial Bold.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(cand, int(size * 0.52))
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    text = "LB"
    bbox = d.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    d.text((x, y), text, font=font, fill=GOLD)
    return img


for s in (192, 512):
    p = os.path.join(ICON_DIR, "icon-%d.png" % s)
    make_icon(s).save(p, "PNG")
    print("saved", p)
