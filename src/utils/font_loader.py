"""Utility for loading custom application fonts from assets/fonts/ at application startup."""

import logging
from pathlib import Path
from typing import List

from PySide6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = (".ttf", ".otf")


def load_application_fonts(base_dir: Path) -> List[str]:
    """Scans base_dir/assets/fonts/ for .ttf/.otf files and registers each with QFontDatabase."""
    fonts_dir = base_dir / "assets" / "fonts"
    loaded_families: List[str] = []

    if not fonts_dir.exists() or not fonts_dir.is_dir():
        logger.info(
            "Custom fonts directory not found at %s — using system fallback fonts only.",
            fonts_dir,
        )
        return loaded_families

    try:
        font_files = sorted(
            f for f in fonts_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
        )
    except OSError:
        logger.exception("Unable to read fonts directory: %s", fonts_dir)
        return loaded_families

    if not font_files:
        logger.info(
            "No .ttf/.otf font files found in %s — using system fallback fonts only.",
            fonts_dir,
        )
        return loaded_families

    for font_file in font_files:
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id == -1:
            logger.warning(
                "Failed to load font file '%s' (corrupt, unsupported, or invalid format).",
                font_file.name,
            )
            continue

        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded_families.extend(families)
            logger.info("Loaded custom font family '%s' from %s", ", ".join(families), font_file.name)

            for family in families:
                try:
                    styles = QFontDatabase.styles(family)
                except Exception:
                    styles = []
                logger.info(
                    "  → Family '%s' (from %s) reports style(s): %s",
                    family, font_file.name, ", ".join(styles) if styles else "(none reported)",
                )
        else:
            logger.warning(
                "Font file '%s' loaded but reported no usable font family names.",
                font_file.name,
            )

    return loaded_families