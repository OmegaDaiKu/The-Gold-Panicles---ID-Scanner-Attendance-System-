"""Runs the Gold Panicles automated test suite."""

import sys

try:
    import pytest
except ImportError:
    print("ERROR: pytest is not installed.")
    print("Install dependencies using:")
    print("python -m pip install -r requirements-test.txt")
    raise SystemExit(2)


def main() -> int:
    return int(pytest.main(["-v", "tests"]))


if __name__ == "__main__":
    raise SystemExit(main())