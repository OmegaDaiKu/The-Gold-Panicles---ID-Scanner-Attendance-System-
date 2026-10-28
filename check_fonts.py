"""
check_fonts.py — one-time diagnostic script.

Run this from your project root with your venv active:
    python check_fonts.py

It scans assets/fonts/ and prints, for every .ttf/.otf file found,
the exact family name(s) and style name(s) Qt registers for it.
This does NOT modify your application or touch font_loader.py —
it's a standalone throwaway diagnostic.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase

# QFontDatabase requires a QApplication instance to exist first.
app = QApplication(sys.argv)

base_dir = Path(__file__).resolve().parent
fonts_dir = base_dir / "assets" / "fonts"

if not fonts_dir.exists():
    print(f"ERROR: folder not found: {fonts_dir}")
    print("Make sure assets/fonts/ is a sibling of assets/images/.")
    sys.exit(1)

font_files = sorted(
    f for f in fonts_dir.iterdir()
    if f.is_file() and f.suffix.lower() in (".ttf", ".otf")
)

if not font_files:
    print(f"No .ttf/.otf files found in {fonts_dir}")
    sys.exit(0)

print(f"Found {len(font_files)} font file(s) in {fonts_dir}\n")
print("-" * 70)

for font_file in font_files:
    font_id = QFontDatabase.addApplicationFont(str(font_file))
    if font_id == -1:
        print(f"FILE: {font_file.name}")
        print("  -> FAILED TO LOAD (corrupt, unsupported, or invalid format)")
        print("-" * 70)
        continue

    families = QFontDatabase.applicationFontFamilies(font_id)
    print(f"FILE: {font_file.name}")
    for family in families:
        styles = QFontDatabase.styles(family)
        print(f"  -> Registered family: \"{family}\"")
        print(f"     Available styles under this family: {styles}")
    print("-" * 70)

print("\nDone. Compare the 'Registered family' strings above against")
print("the font-family values used in theme.qss.")