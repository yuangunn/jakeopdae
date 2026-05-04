"""Generate ``packaging/jakeopdae.ico`` and ``packaging/splash.png``.

Run once whenever the brand changes. The ``.ico`` ships in the
PyInstaller spec via ``icon=`` and shows up as the exe's icon + the
desktop shortcut's icon. The ``.png`` is the splash that fills the
5-10 second one-file extraction window.

Both assets are pure-PIL drawings so we don't need a designer round
trip — change the colours / glyph here and rebuild.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "keymacro" / "ui" / "assets" / "fonts"
BOLD = FONTS / "NotoSansKR-Bold.ttf"
REGULAR = FONTS / "NotoSansKR-Regular.ttf"

# Brand palette from DESIGN.md
SURFACE = (19, 17, 14, 255)        # #13110E
BRASS = (232, 178, 106, 255)       # #E8B26A
ON_SURFACE = (242, 235, 218, 255)  # #F2EBDA
DIMMED = (163, 155, 133, 255)      # #A39B85
HINT = (120, 115, 102, 255)


def make_icon(size: int) -> Image.Image:
    """Square icon with the 작 character in brass on warm-graphite."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded background — slight padding so the rounded corner doesn't
    # look squashed when Windows shows the icon at small sizes.
    pad = max(1, size // 24)
    radius = max(2, size // 8)
    draw.rounded_rectangle(
        [(pad, pad), (size - pad - 1, size - pad - 1)],
        radius=radius,
        fill=SURFACE,
        outline=BRASS,
        width=max(1, size // 32),
    )

    # 작 character — only at sizes large enough to render it.
    if size >= 24:
        font_size = int(size * 0.62)
        font = ImageFont.truetype(str(BOLD), font_size)
        draw.text(
            (size // 2, size // 2 + size // 28),
            "작",
            fill=BRASS,
            anchor="mm",
            font=font,
        )
    else:
        # At 16x16 the 작 character is illegible; draw a small brass dot
        # so the icon is at least recognisably *something*.
        cx = size // 2
        r = max(2, size // 4)
        draw.ellipse(
            [(cx - r, cx - r), (cx + r, cx + r)],
            fill=BRASS,
        )
    return img


def write_ico(path: Path) -> None:
    """Save a multi-size ICO. PIL resamples the source image to each
    requested size internally, which is fine for our 작 glyph since
    rounding artefacts at small sizes are barely visible.

    We *also* hand-render the 16×16 and 24×24 versions (where the
    glyph would otherwise be illegible) and embed them via
    ``append_images``, but the heavy lifting is the 256×256 master."""
    master = make_icon(256)
    extras = [make_icon(s) for s in (16, 24, 32, 48)]
    sizes = [(s, s) for s in (256, 128, 64, 48, 32, 24, 16)]
    master.save(
        path,
        format="ICO",
        sizes=sizes,
        append_images=extras,
    )
    print(f"wrote {path}  ({len(sizes)} sizes, {path.stat().st_size} bytes)")


def write_splash(path: Path) -> None:
    W, H = 560, 300
    img = Image.new("RGB", (W, H), SURFACE[:3])
    draw = ImageDraw.Draw(img)

    # Top brass bar — 4px stripe (mirrors the trigger-stripe motif).
    draw.rectangle([(0, 0), (W, 4)], fill=BRASS[:3])

    # Hero glyph — 작
    title_font = ImageFont.truetype(str(BOLD), 72)
    draw.text((W // 2, 130), "작업대", fill=ON_SURFACE[:3], anchor="mm", font=title_font)

    # Subtitle
    sub_font = ImageFont.truetype(str(REGULAR), 18)
    draw.text(
        (W // 2, 200),
        "매크로 자동화 데스크탑 도구",
        fill=DIMMED[:3],
        anchor="mm",
        font=sub_font,
    )

    # Loading hint
    hint_font = ImageFont.truetype(str(REGULAR), 12)
    draw.text(
        (W // 2, 270),
        "처음 실행은 5~10초 걸려요…",
        fill=HINT[:3],
        anchor="mm",
        font=hint_font,
    )
    img.save(path)
    print(f"wrote {path}  ({W}x{H})")


if __name__ == "__main__":
    write_ico(HERE / "jakeopdae.ico")
    write_splash(HERE / "splash.png")
