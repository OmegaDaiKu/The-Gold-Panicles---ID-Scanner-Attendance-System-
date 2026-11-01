"""
Utility for loading custom application fonts from assets/fonts/ at startup and providing
standard QFont instances for the UI typography hierarchy.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtGui import QFont, QFontDatabase
from src.ui.theme import Typography

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = (".ttf", ".otf")
_LOADED_FAMILIES: List[str] = []


def load_application_fonts(base_dir: Path) -> List[str]:
    """Scans base_dir/assets/fonts/ for .ttf/.otf files and registers each with QFontDatabase."""
    global _LOADED_FAMILIES
    fonts_dir = base_dir / "assets" / "fonts"
    _LOADED_FAMILIES.clear()

    if not fonts_dir.exists() or not fonts_dir.is_dir():
        logger.info(
            "Custom fonts directory not found at %s — using system fallback fonts only.",
            fonts_dir,
        )
        return _LOADED_FAMILIES

    try:
        font_files = sorted(
            f for f in fonts_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
        )
    except OSError:
        logger.exception("Unable to read fonts directory: %s", fonts_dir)
        return _LOADED_FAMILIES

    if not font_files:
        logger.info(
            "No .ttf/.otf font files found in %s — using system fallback fonts only.",
            fonts_dir,
        )
        return _LOADED_FAMILIES

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
            _LOADED_FAMILIES.extend(families)
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

    return _LOADED_FAMILIES


def get_font(
    family: str,
    point_size: int = 11,
    weight: QFont.Weight = QFont.Weight.Normal,
    italic: bool = False,
) -> QFont:
    """Generates a configured QFont object with family fallbacks."""
    font = QFont(family, point_size)
    font.setWeight(weight)
    font.setItalic(italic)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def get_display_font(size: int = Typography.SECTION_HEADER_PT, bold: bool = True) -> QFont:
    """Returns standard display font for headers and hero text."""
    family = Typography.DISPLAY_FAMILY if Typography.DISPLAY_FAMILY in _LOADED_FAMILIES else Typography.BODY_FAMILY
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    return get_font(family, size, weight)


def get_body_font(size: int = Typography.BODY_PT, bold: bool = False) -> QFont:
    """Returns standard body font for labels and inputs."""
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    return get_font(Typography.BODY_FAMILY, size, weight)


def get_mono_font(size: int = Typography.LABEL_PT, bold: bool = False) -> QFont:
    """Returns standard monospace font for IDs, timestamps, and data grids."""
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    return get_font(Typography.MONO_FAMILY, size, weight)