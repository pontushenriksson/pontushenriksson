"""Build the README header as self-contained SVGs (light and dark).

Text is converted to outlines with Archivo (the font from pontushenriksson.com),
so the banner renders the same everywhere, including GitHub's image proxy.

    pip install fonttools brotli uharfbuzz pillow
    python scripts/banner.py --font path/to/archivo-latin-wdth-normal.woff2

The font ships with @fontsource-variable/archivo (personal-portfolio/node_modules).
"""

import argparse
import base64
import io
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent

W, H = 1280, 440
PAD = 64
RADIUS = 6
PHOTO = (900, 32, 348, 376)  # x, y, w, h

SIGNAL = "#FF5A1F"
THEMES = {
    "light": {"bg": "#E9E8E3", "fg": "#141517", "line": "#D3D1CA"},
    "dark": {"bg": "#141517", "fg": "#F5F3EE", "line": "#2A2C2F"},
}


class Face:
    """One static instance of the variable font, shaped with HarfBuzz."""

    def __init__(self, src: Path, wght: int, wdth: int):
        font = instantiateVariableFont(TTFont(src), {"wght": wght, "wdth": wdth})
        buf = io.BytesIO()
        font.flavor = None
        font.save(buf)
        self.glyphs = font.getGlyphSet()
        self.order = font.getGlyphOrder()
        self.upm = font["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(buf.getvalue()))

    def shape(self, text: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text: str, size: float) -> float:
        _, pos = self.shape(text)
        return sum(p.x_advance for p in pos) * size / self.upm

    def path(self, text: str, x: float, baseline: float, size: float) -> str:
        infos, pos = self.shape(text)
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs)
        cursor = 0
        for info, p in zip(infos, pos):
            name = self.order[info.codepoint]
            # Flip y: font units grow upwards, SVG grows downwards.
            t = (scale, 0, 0, -scale, x + (cursor + p.x_offset) * scale, baseline - p.y_offset * scale)
            self.glyphs[name].draw(TransformPen(pen, t))
            cursor += p.x_advance
        return pen.getCommands()


def photo_data_uri(src: Path) -> str:
    _, _, w, h = PHOTO
    im = Image.open(src).convert("RGB")
    # Crop around the face, keeping the logo wall as context.
    im = im.crop((int(im.width * 0.25), int(im.height * 0.09), int(im.width * 0.95), int(im.height * 0.85)))
    im = ImageOps.fit(im, (w * 2, h * 2), Image.LANCZOS, centering=(0.5, 0.2))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=80, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def build(theme: dict, display: Face, label: Face, photo: str) -> str:
    px, py, pw, ph = PHOTO
    text_w = px - PAD - 48

    # Size the name so "Henriksson." always fits next to the photo.
    size = min(150, text_w / (display.width("Henriksson.", 1)))
    lead = size * 0.9
    base1 = 92 + size * 0.74
    base2 = base1 + lead

    dot_x = PAD + display.width("Henriksson", size)
    henriksson = display.path("Henriksson", PAD, base2, size)
    dot = display.path(".", dot_x, base2, size)

    # Large enough to stay readable when GitHub scales the banner to phone width.
    kicker_size = 40
    kicker_base = H - 60
    kicker = label.path("Co-founder and CEO of Walldy", PAD + 32, kicker_base, kicker_size)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">Pontus Henriksson. Co-founder and CEO of Walldy, Sundsvall, Sweden.</title>
<defs><clipPath id="p"><rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="{RADIUS}"/></clipPath></defs>
<rect width="{W}" height="{H}" rx="{RADIUS}" fill="{theme['bg']}"/>
<path fill="{theme['fg']}" d="{display.path('Pontus', PAD, base1, size)}"/>
<path fill="{theme['fg']}" d="{henriksson}"/>
<path fill="{SIGNAL}" d="{dot}"/>
<line x1="{PAD}" x2="{px - 48}" y1="{kicker_base - 62}" y2="{kicker_base - 62}" stroke="{theme['line']}" stroke-width="1.5"/>
<circle cx="{PAD + 9}" cy="{kicker_base - 13}" r="9" fill="{SIGNAL}"/>
<path fill="{theme['fg']}" d="{kicker}"/>
<image href="{photo}" x="{px}" y="{py}" width="{pw}" height="{ph}" clip-path="url(#p)" preserveAspectRatio="xMidYMid slice"/>
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, type=Path, help="Archivo variable font with wght and wdth axes")
    ap.add_argument("--photo", type=Path, default=ROOT / "assets" / "pontus.jpg")
    args = ap.parse_args()

    display = Face(args.font, wght=900, wdth=125)
    label = Face(args.font, wght=600, wdth=100)
    photo = photo_data_uri(args.photo)

    for name, theme in THEMES.items():
        out = ROOT / "assets" / f"header-{name}.svg"
        out.write_text(build(theme, display, label, photo))
        print(out.relative_to(ROOT), f"{out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
