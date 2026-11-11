"""Decide the post format for a scored item."""

from __future__ import annotations


def _video_enabled(config) -> bool:
    """Whether video generation is enabled in *config*.

    Defaults to True when *config* is None or does not say otherwise,
    so a high-scoring video-suitable item is not silently downgraded
    by an absent config. An explicit ``False`` anywhere in the
    generation/video settings disables video.
    """
    if config is None:
        return True
    if isinstance(config, dict):
        # Direct flags.
        for key in ("video_enabled", "video"):
            if key in config and isinstance(config[key], bool):
                return config[key]
        gen = config.get("generation")
        if isinstance(gen, dict):
            for key in ("video_enabled", "video"):
                if key in gen and isinstance(gen[key], bool):
                    return gen[key]
            video = gen.get("video")
            if isinstance(video, dict) and isinstance(video.get("enabled"), bool):
                return video["enabled"]
            if isinstance(video, bool):
                return video
        video = config.get("video")
        if isinstance(video, dict) and isinstance(video.get("enabled"), bool):
            return video["enabled"]
    return True


def decide_format(item, score, config: dict | None = None) -> str:
    """Return one of ``IMAGE_POST`` / ``VIDEO`` / ``TEXT_LED`` / ``NO_POST``.

    - ``NO_POST`` when the band is ``reject`` / ``low priority``
      (or the total is below 60).
    - ``VIDEO`` when total >= 85, video_potential >= 75 and video
      generation is enabled in *config*.
    - ``TEXT_LED`` when total >= 60 and visual_potential < 40.
    - ``IMAGE_POST`` when total >= 60 (and the item is visual enough).
    - Otherwise ``NO_POST``.
    """
    total = float(getattr(score, "total", 0) or 0)
    band_label = str(getattr(score, "band", "") or "").lower()
    dimensions = getattr(score, "dimensions", None) or {}
    video_potential = float(dimensions.get("video_potential", 0) or 0)
    visual_potential = float(dimensions.get("visual_potential", 0) or 0)

    if band_label in ("reject", "low priority") or total < 60:
        return "NO_POST"
    if total >= 85 and video_potential >= 75 and _video_enabled(config):
        return "VIDEO"
    if total >= 60 and visual_potential < 40:
        return "TEXT_LED"
    if total >= 60:
        return "IMAGE_POST"
    return "NO_POST"
