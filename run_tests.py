"""
Test script - runs every test_* function in every matcher/tests/test_*.py file.

    python run_tests.py

Each test runs with its own empty data folder, so the real data/ folder is
never touched, and no test calls the real AI.
"""

import functools
import importlib
import logging
import os
import pkgutil
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


def test_modules():
    """Every test_*.py module in matcher/tests, in name order."""
    from matcher import tests

    names = sorted(
        module.name for module in pkgutil.iter_modules(tests.__path__)
        if module.name.startswith("test_")
    )
    return [importlib.import_module(f"matcher.tests.{name}") for name in names]


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from django.test.utils import setup_test_environment

    setup_test_environment()
    logging.disable(logging.CRITICAL)  # expected warnings would clutter the output

    suite = unittest.TestSuite(
        unittest.FunctionTestCase(in_temp_data_dir(test))
        for module in test_modules()
        for name, test in vars(module).items()
        if name.startswith("test_") and callable(test)
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
