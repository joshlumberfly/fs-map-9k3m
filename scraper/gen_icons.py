"""Generate PWA app icons. Run once after edits; commit the PNGs.

Outputs:
- web/icon-192.png       (Android/PWA)
- web/icon-512.png       (Android/PWA, large)
- web/apple-touch-icon.png  (iOS home screen, 180x180)
- web/favicon-32.png     (browser tab)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

YELLOW = (250, 204, 21)        # warning yellow
DARK = (24, 24, 27)             # near-black foreground
RED_BG = (220, 38, 38)          # red disc background
WHITE = (255, 255, 255)


def draw_icon(size: int, *, padded: bool) -> Image.Image:
    """Yellow warning triangle with `!` on a red disc.

    `padded=True` adds breathing room so iOS can crop the corners into a
    rounded square without clipping the symbol.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = int(size * 0.06) if padded else 0
    disc = (margin, margin, size - margin, size - margin)
    d.ellipse(disc, fill=RED_BG)

    cx = size // 2
    tri_top_y = int(size * 0.22)
    tri_bot_y = int(size * 0.78)
    tri_half_w = int(size * 0.30)
    top = (cx, tri_top_y)
    left = (cx - tri_half_w, tri_bot_y)
    right = (cx + tri_half_w, tri_bot_y)
    d.polygon([top, left, right], fill=YELLOW, outline=DARK, width=max(2, size // 80))

    bar_w = max(3, size // 22)
    bar_top = tri_top_y + int(size * 0.18)
    bar_bot = tri_bot_y - int(size * 0.18)
    d.rectangle((cx - bar_w // 2, bar_top, cx + bar_w // 2, bar_bot), fill=DARK)

    dot_r = max(3, size // 28)
    dot_cy = tri_bot_y - int(size * 0.08)
    d.ellipse(
        (cx - dot_r, dot_cy - dot_r, cx + dot_r, dot_cy + dot_r),
        fill=DARK,
    )

    return img


def main() -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    targets = [
        (192, "icon-192.png", True),
        (512, "icon-512.png", True),
        (180, "apple-touch-icon.png", True),
        (32, "favicon-32.png", False),
    ]
    for size, filename, padded in targets:
        img = draw_icon(size, padded=padded)
        img.save(WEB_DIR / filename, optimize=True)
        print(f"  wrote {filename} ({size}x{size})")


if __name__ == "__main__":
    main()
