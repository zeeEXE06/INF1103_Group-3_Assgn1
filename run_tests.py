"""
Test script - runs every test_* function in matcher/tests.py.

    python run_tests.py

Each test runs with its own empty data folder, so the real data/ folder is
never touched, and no test calls the real AI.
"""

import functools
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

import django


def in_temp_data_dir(test):
    """Run a test with DATA_DIR pointing at a new empty folder."""
    from django.test.utils import override_settings

    @functools.wraps(test)
    def run():
        with tempfile.TemporaryDirectory() as tmp, override_settings(DATA_DIR=Path(tmp)):
            test()

    return run


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from django.test.utils import setup_test_environment

    from matcher import tests

    setup_test_environment()
    logging.disable(logging.CRITICAL)  # expected warnings would clutter the output

    suite = unittest.TestSuite(
        unittest.FunctionTestCase(in_temp_data_dir(test))
        for name, test in vars(tests).items()
        if name.startswith("test_") and callable(test)
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
