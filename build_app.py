
"""Builds the Gold Panicles standalone Windows executable.

Runs automated tests first. PyInstaller is invoked only if all tests pass.
"""

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
MAIN_SCRIPT = ROOT_DIR / "main.py"
SPEC_FILE = ROOT_DIR / "tgp_attendance.spec"


def run_command(command: list[str], description: str) -> bool:
    print(f"\n{'=' * 60}")
    print(description)
    print("=" * 60)

    result = subprocess.run(command, cwd=ROOT_DIR)
    return result.returncode == 0


def main() -> int:
    if not MAIN_SCRIPT.is_file():
        print("ERROR: main.py was not found.")
        return 1

    if not SPEC_FILE.is_file():
        print("ERROR: GoldPanicles.spec was not found.")
        print("Create the PyInstaller specification before building.")
        return 1

    # 1. Run automated tests.
    tests_passed = run_command(
        [sys.executable, "run_tests.py"],
        "[1/2] Running automated test suite",
    )

    if not tests_passed:
        print("\nBUILD ABORTED: Automated tests failed.")
        return 1

    # 2. Build standalone executable.
    build_passed = run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            str(SPEC_FILE),
        ],
        "[2/2] Building standalone executable",
    )

    if not build_passed:
        print("\nBUILD FAILED: PyInstaller encountered an error.")
        return 1

    print("\nBUILD COMPLETED SUCCESSFULLY.")
    print(f"Output directory: {ROOT_DIR / 'dist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
