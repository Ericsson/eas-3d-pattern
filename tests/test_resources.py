"""Regression tests for deprecated importlib.resources usage (Bug 7)."""

from __future__ import annotations

import ast
import importlib
import warnings
from pathlib import Path

import eas_3d_pattern.sample_data as sample_data
from eas_3d_pattern import schema_manager

_DEPRECATED = {
    "importlib.resources.contents",
    "importlib.resources.is_resource",
    "importlib.resources.path",
    "importlib.resources.open_text",
}


def _deprecated_resource_calls(source: str) -> list[str]:
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            dotted = ast.unparse(node.func)
            if dotted in _DEPRECATED:
                found.append(dotted)
    return found


def test_no_deprecated_importlib_resources_apis():
    """Bug 7: neither sample_data nor schema_manager may call deprecated APIs.

    ``contents``/``is_resource``/``path``/``open_text`` are deprecated and
    removed in Python 3.14. They must be replaced by the ``files()`` API.
    """
    for module in (sample_data, schema_manager):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert _deprecated_resource_calls(source) == [], module.__name__


def test_sample_data_no_deprecated_warning_and_finds_samples():
    """Bug 7: reloading sample_data emits no DeprecationWarning and finds samples."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(sample_data)

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deprecations, [str(w.message) for w in deprecations]
    assert len(sample_data.SAMPLE_JSON) >= 1
