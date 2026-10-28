"""Automates full test verification and PyInstaller standalone compilation."""

import os
import subprocess
import sys


def build_standalone_executable() -> None:
    """Executes verification tests first, then invokes PyInstaller to build the Windows executable."""
    print("[1/2] Executing Verification Test Suite...")
    test_result = subprocess.run([sys.executable, "run_tests.py"])

    if test_result.returncode != 0:
        print("\n[ERROR] Build aborted: Verification tests failed.")
        sys.exit(1)

    print("\n[2/2] Compiling Windows Executable via PyInstaller...")
    build_result = subprocess.run(["pyinstaller", "--clean", "tgp_attendance.spec"])

    if build_result.returncode == 0:
        print("\n" + "=" * 80)
        print(" BUILD SUCCESSFUL!")
        print(" Standalone Executable Location: dist/TGP_Attendance_System.exe")
        print("=" * 80)
    else:
        print("\n[ERROR] PyInstaller compilation failed.")
        sys.exit(build_result.returncode)


if __name__ == "__main__":
    build_standalone_executable()