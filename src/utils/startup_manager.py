"""Manage automatic startup for the packaged Gold Panicles application.

Startup is registered for the current Windows user only. No administrator
privileges are required.

The application must be packaged before startup can be enabled. This prevents
the development environment's Python interpreter from being registered
instead of the actual Gold Panicles executable.
"""

import sys
import subprocess
from pathlib import Path
from typing import Optional


APP_REGISTRY_NAME = "GoldPaniclesAttendance"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


class StartupManager:
    """Manage Gold Panicles automatic launch when the user logs into Windows."""

    @staticmethod
    def is_supported() -> bool:
        """Return whether the current operating system supports this manager."""
        return sys.platform == "win32"

    @staticmethod
    def _get_executable_path() -> Path:
        """Return the path of the packaged application executable."""
        if not getattr(sys, "frozen", False):
            raise RuntimeError(
                "Automatic startup can only be configured from the packaged "
                "Gold Panicles executable."
            )

        executable = Path(sys.executable).resolve()

        if not executable.is_file():
            raise FileNotFoundError(
                f"Gold Panicles executable was not found: {executable}"
            )

        return executable

    @classmethod
    def _get_startup_command(cls) -> str:
        """Return the correctly quoted executable command."""
        executable = cls._get_executable_path()
        return subprocess.list2cmdline([str(executable)])

    @classmethod
    def is_enabled(cls) -> bool:
        """Check whether Gold Panicles is registered for Windows startup."""
        if not cls.is_supported():
            return False

        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                winreg.KEY_READ,
            ) as registry_key:
                value, _ = winreg.QueryValueEx(
                    registry_key,
                    APP_REGISTRY_NAME,
                )

            return value == cls._get_startup_command()

        except (FileNotFoundError, OSError, RuntimeError):
            return False

    @classmethod
    def enable_startup(cls) -> None:
        """Register Gold Panicles to launch when the current user logs in."""
        if not cls.is_supported():
            raise OSError(
                "Automatic startup is only supported on Windows."
            )

        import winreg

        command = cls._get_startup_command()

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as registry_key:
            winreg.SetValueEx(
                registry_key,
                APP_REGISTRY_NAME,
                0,
                winreg.REG_SZ,
                command,
            )

    @classmethod
    def disable_startup(cls) -> None:
        """Remove Gold Panicles from the current user's startup applications."""
        if not cls.is_supported():
            raise OSError(
                "Automatic startup is only supported on Windows."
            )

        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                winreg.KEY_SET_VALUE,
            ) as registry_key:
                winreg.DeleteValue(
                    registry_key,
                    APP_REGISTRY_NAME,
                )

        except FileNotFoundError:
            # The setting is already disabled.
            pass