"""Regenerate the small, neutral offline image placeholders."""
from pathlib import Path

from PIL import Image, ImageDraw

static = Path(__file__).resolve().parent.parent / "movie_app" / "static"


def clapper(draw, x, y, size, color):
    width = max(2, size // 18)
    draw.rounded_rectangle((x, y, x + size, y + size * .72), radius=size * .08, outline=color, width=width)
    draw.rectangle((x, y + size * .2, x + size, y + size * .25), fill=color)
    for offset in (.2, .48, .76):
        draw.line((x + size * offset, y, x + size * (offset - .12), y + size * .22), fill=color, width=width)
    draw.line((x + size * .23, y + size * .47, x + size * .7, y + size * .47), fill=color, width=width)


image = Image.new("RGB", (400, 600), "#e5e9ec")
draw = ImageDraw.Draw(image)
clapper(draw, 159, 239, 82, "#a6b0ba")
image.save(static / "poster-placeholder.png", optimize=True)
icon = Image.new("RGB", (64, 64), "#ad3046")
clapper(ImageDraw.Draw(icon), 13, 17, 38, "#ffffff")
icon.save(static / "favicon.png", optimize=True)
