""""Icon utility helper for loading and runtime-tinting Lucide SVG icon assets."""

import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)

_RENDER_SCALE = 2  # render at 2x physical pixels, report via devicePixelRatio, for crisp HiDPI icons


class IconHelper:
    """Loads Lucide SVG icons from assets/icons/lucide/ and tints them at runtime
    to any color the active theme needs, with per-(name, color, size) caching.

    Lucide icons (https://lucide.dev) are MIT-licensed single-color outline SVGs
    distributed as individual files named in kebab-case (e.g. "chevron-left.svg",
    "check-circle.svg"). This helper expects those exact files to exist under
    assets/icons/lucide/<name>.svg. If a requested icon file is missing, a blank
    (fully transparent) icon/pixmap is returned and a one-time warning is logged
    -- callers must never crash just because an icon asset hasn't been placed yet.
    """

    _icon_cache: dict = {}
    _pixmap_cache: dict = {}
    _missing_warned: set = set()

    @classmethod
    def get_base_dir(cls) -> Path:
        """Returns application base directory, supporting both source and PyInstaller frozen execution."""
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parent.parent.parent

    @classmethod
    def _icon_dir(cls) -> Path:
        return cls.get_base_dir() / "assets" / "icons" / "lucide"

    @classmethod
    def _resolve_svg_path(cls, name: str) -> Path:
        filename = name if name.endswith(".svg") else f"{name}.svg"
        return cls._icon_dir() / filename

    @classmethod
    def get_pixmap(cls, name: str, color: str = "#F4EFEA", size: int = 20) -> QPixmap:
        """Returns a tinted, cached QPixmap for the given Lucide icon name."""
        cache_key = (name, color, size)
        if cache_key in cls._pixmap_cache:
            return cls._pixmap_cache[cache_key]

        svg_path = cls._resolve_svg_path(name)
        if not svg_path.exists():
            if name not in cls._missing_warned:
                logger.warning(
                    "IconHelper: Lucide icon '%s' not found at %s -- rendering "
                    "blank. Place the real Lucide SVG file there to fix this.",
                    name, svg_path,
                )
                cls._missing_warned.add(name)
            blank = QPixmap(size, size)
            blank.fill(Qt.GlobalColor.transparent)
            cls._pixmap_cache[cache_key] = blank
            return blank

        pixmap = cls._render_tinted(svg_path, color, size)
        cls._pixmap_cache[cache_key] = pixmap
        return pixmap

    @classmethod
    def get_icon(
        cls,
        name: str,
        color: str = "#F4EFEA",
        size: int = 20,
        fallback_pixmap: Optional[object] = None,  # kept for backward-compat call sites; unused
    ) -> QIcon:
        """Returns a tinted, cached QIcon for the given Lucide icon name."""
        cache_key = (name, color, size)
        if cache_key in cls._icon_cache:
            return cls._icon_cache[cache_key]

        pixmap = cls.get_pixmap(name, color=color, size=size)
        icon = QIcon(pixmap)
        cls._icon_cache[cache_key] = icon
        return icon

    @staticmethod
    def _render_tinted(svg_path: Path, color: str, size: int) -> QPixmap:
        """Rasterizes an SVG at 2x and tints every opaque pixel to `color`."""
        renderer = QSvgRenderer(str(svg_path))
        physical_size = size * _RENDER_SCALE

        pixmap = QPixmap(physical_size, physical_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()

        pixmap.setDevicePixelRatio(float(_RENDER_SCALE))
        return pixmap

    @classmethod
    def clear_cache(cls) -> None:
        """Clears all cached icons/pixmaps. Call this if a theme color change needs a full re-tint."""
        cls._icon_cache.clear()
        cls._pixmap_cache.clear()