"""Regression tests for util_func.report bugs (v0.2.0 bug table)."""

from __future__ import annotations

import ast
from pathlib import Path

import eas_3d_pattern.util_func.report as report_mod


def test_report_does_not_import_from_top_level_package():
    """Bug 4: report.py must not import from the top-level package.

    ``from eas_3d_pattern import AntennaPattern, SectorDefinition`` creates a
    circular import that only works because of import ordering in ``__init__``.
    The module must use relative imports of the concrete submodules instead.
    Inspect real import statements via AST so docstring examples are ignored.
    """
    source = Path(report_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    offending = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module == "eas_3d_pattern"
    ]
    assert not offending, "report.py must not absolute-import the top-level package"
    assert report_mod.AntennaPattern is not None
    assert report_mod.SectorDefinition is not None
