"""Automated test runner executing all Phase 1-5 unit and integration test suites."""

import sys
import pytest


def run_full_verification_suite() -> int:
    """Runs pytest across all test modules in tests/unit/ and returns system exit code."""
    print("=" * 80)
    print("      THE GOLD PANICLES QR ATTENDANCE SYSTEM - FULL VERIFICATION SUITE")
    print("=" * 80)

    # Passing 'tests/unit/' dynamically discovers all test_*.py files in the folder
    pytest_args = [
        "-v",
        "--tb=short",
        "tests/unit/",
    ]

    exit_code = pytest.main(pytest_args)

    if exit_code == 0:
        print("\n[SUCCESS] All verification tests passed cleanly.")
    else:
        print(f"\n[FAILURE] Verification suite failed with exit code: {exit_code}")

    return exit_code


if __name__ == "__main__":
    sys.exit(run_full_verification_suite())