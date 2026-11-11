"""Brand-card image generation for HeyMariner (Pillow, local only).

Navy background (#0B2C4A), teal accent (#14919B), white text,
"HEYMARINER" header, wrapped title, a teal wave line and a footer.
No external API is involved.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Pillow is required for brand-card generation: "
        "pip install Pillow==10.4.0 (see requirements.txt)"
    ) from exc

NAVY = "#0B2C4A"
TEAL = "#14919B"
WHITE = "#FFFFFF"

DEFAULT_BRAND: dict[str, Any] = {
    "name": "HeyMariner",
    "colors": {"navy": NAVY, "teal": TEAL, "white": WHITE},
    "tagline": "Trusted maritime updates for seafarers and shipping professionals",
}


def _title_and_subtitle(item_or_title: Any) -> tuple[str, str]:
    """Accept a ResearchItem, a dict, or a plain title string."""
    if isinstance(item_or_title, str):
        return item_or_title, ""
    if isinstance(item_or_title, dict):
        title = str(
            item_or_title.get("title")
            or item_or_title.get("headline")
            or ""
        )
        subtitle = str(
            item_or_title.get("subtitle")
            or item_or_title.get("summary")
            or item_or_title.get("description")
            or ""
        )
        return title, subtitle
    # ResearchItem or any object with attributes (duck-typed so this
    # module works before/after Part A lands).
    title = str(getattr(item_or_title, "title", "") or "")
    subtitle = str(
        getattr(item_or_title, "subtitle", "")
        or getattr(item_or_title, "summary", "")
        or getattr(item_or_title, "description", "")
        or ""
    )
    return title, subtitle


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        # Rough wrap by characters, then refine by pixel width.
        for chunk in textwrap.wrap(paragraph, width=40) or [""]:
            while draw.textlength(chunk, font=font) > max_width and len(chunk) > 1:
                # Split the chunk at the last space that fits.
                cut = chunk.rfind(" ", 0, max(1, len(chunk) - 1))
                if cut <= 0:
                    cut = len(chunk) // 2
                lines.append(chunk[:cut])
                chunk = chunk[cut:].lstrip()
            lines.append(chunk)
    return lines


def generate_brand_card(
    item_or_title: Any,
    subtitle: str = "",
    brand: dict | None = None,
    output_path: Path | str | None = None,
    size: tuple[int, int] = (1080, 1080),
) -> Path:
    """Generate a HeyMariner brand card and save it to *output_path*.

    *item_or_title* may be a ResearchItem, a dict, or a title string.
    Returns the output :class:`pathlib.Path`. Raises a clear
    :class:`ImportError` if Pillow is missing.
    """
    if output_path is None:
        raise ValueError("output_path is required")
    brand = brand or DEFAULT_BRAND
    colors = brand.get("colors", {}) if isinstance(brand, dict) else {}
    navy = str(colors.get("navy", NAVY))
    teal = str(colors.get("teal", TEAL))
    white = str(colors.get("white", WHITE))
    brand_name = str(brand.get("name", "HeyMariner")) if isinstance(brand, dict) else "HeyMariner"

    title, item_subtitle = _title_and_subtitle(item_or_title)
    subtitle = subtitle or item_subtitle
    title = title.strip() or brand_name
    subtitle = subtitle.strip()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    width, height = size
    image = Image.new("RGB", (width, height), navy)
    draw = ImageDraw.Draw(image)

    try:
        header_font = ImageFont.load_default(size=64)
        title_font = ImageFont.load_default(size=72)
        subtitle_font = ImageFont.load_default(size=36)
        footer_font = ImageFont.load_default(size=32)
    except TypeError:  # very old Pillow without size kwarg
        header_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()

    margin = 80
    # Header: HEYMARINER top-left, with a teal underline.
    header = brand_name.upper()
    draw.text((margin, 70), header, font=header_font, fill=white)
    draw.line(
        [(margin, 170), (margin + 220, 170)], fill=teal, width=8
    )

    # Title, wrapped to fit.
    title_lines = _wrap(draw, title, title_font, width - 2 * margin)
    y = 240
    line_height = 95
    for line in title_lines[:6]:
        draw.text((margin, y), line, font=title_font, fill=white)
        y += line_height

    # Subtitle, wrapped, below the title.
    if subtitle:
        sub_lines = _wrap(draw, subtitle, subtitle_font, width - 2 * margin)
        y += 30
        for line in sub_lines[:4]:
            draw.text((margin, y), line, font=subtitle_font, fill=white)
            y += 50

    # Teal wave line: a series of arcs/ellipses across the lower third.
    wave_y = height - 260
    for x in range(0, width, 120):
        draw.arc(
            [x, wave_y, x + 180, wave_y + 120],
            start=180,
            end=360,
            fill=teal,
            width=10,
        )
    draw.ellipse([width - 220, wave_y - 40, width - 100, wave_y + 80], fill=teal)

    # Footer.
    draw.text(
        (margin, height - 110),
        "heymariner \u2022 Trusted maritime updates",
        font=footer_font,
        fill=white,
    )

    suffix = out.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        image.save(out, format="JPEG", quality=92)
    else:
        image.save(out, format="PNG")
    return out
