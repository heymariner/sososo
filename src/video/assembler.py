"""Slideshow assembly with ffmpeg (optional dependency)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("heymariner")


def assemble_slideshow(
    images: list[Path],
    output_path: Path | str,
    duration_per_image: int = 3,
) -> Path | None:
    """Assemble *images* into a slideshow video at *output_path*.

    Returns the output :class:`Path` on success, or ``None`` when
    ffmpeg is not installed (a warning is logged) or the render fails.
    Uses the ffmpeg concat demuxer with a 120-second timeout.
    """
    images = [Path(p) for p in images]
    out = Path(output_path)
    if not images:
        logger.warning("assemble_slideshow: no images supplied")
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning(
            "assemble_slideshow: ffmpeg not found; skipping video assembly"
        )
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as concat_file:
        for image in images:
            concat_file.write(f"file '{image.resolve()}'\n")
            concat_file.write(f"duration {duration_per_image}\n")
        # The last image needs repeating so its duration is honoured.
        concat_file.write(f"file '{images[-1].resolve()}'\n")
        concat_path = concat_file.name
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_path,
                "-vsync",
                "vfr",
                "-pix_fmt",
                "yuv420p",
                str(out),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        logger.warning("assemble_slideshow: ffmpeg timed out after 120s")
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("assemble_slideshow: ffmpeg failed: %s", exc)
        return None
    finally:
        Path(concat_path).unlink(missing_ok=True)
    if result.returncode != 0:
        logger.warning(
            "assemble_slideshow: ffmpeg exited %s: %s",
            result.returncode,
            (result.stderr or "")[-500:],
        )
        return None
    return out if out.exists() else None
