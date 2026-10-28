"""Automated PyInstaller build script compiling executable distribution folder."""

import subprocess
import sys


def build_executable():
    print("==========================================================")
    print("Building The Gold Panicles Local QR Attendance System Exe")
    print("==========================================================")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "tgp_qr_app.spec",
    ]

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n[SUCCESS] Compilation finished. Executable bundle is located in 'dist/TGP_QR_Attendance_System/'.")
    else:
        print("\n[ERROR] PyInstaller compilation failed. Review output logs above.")


if __name__ == "__main__":
    build_executable()