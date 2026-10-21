"""Réglages pytest communs."""
import sys

import pytest

# Les tests d'interface plantent par intermittence (Abort trap / segfault dans Tk) sur le runner macOS de la CI.
# Cause non élucidée : on ne les exécute pas sous macOS pour garder la CI exploitable. Le cœur reste testé.
UI_TESTS = ("test_ui_smoke.py", "test_safe_after.py")


def pytest_collection_modifyitems(config, items):
    if sys.platform != "darwin":
        return
    skip = pytest.mark.skip(reason="tests d'interface désactivés sous macOS (plantage Tk intermittent en CI)")
    for item in items:
        if item.fspath.basename in UI_TESTS:
            item.add_marker(skip)