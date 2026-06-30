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


def test_report_uses_module_logger():
    """Bug 8: report.py must log via a module logger, not the root logger.

    Direct ``logging.info``/``logging.error`` calls bypass the user's logging
    configuration. The module must define ``logger = logging.getLogger(__name__)``
    and route all log calls through it.
    """
    assert hasattr(report_mod, "logger")
    assert report_mod.logger.name == "eas_3d_pattern.util_func.report"

    source = Path(report_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    log_methods = {
        "debug",
        "info",
        "warning",
        "error",
        "critical",
        "exception",
        "log",
    }
    root_logger_calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in log_methods
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logging"
    ]
    assert root_logger_calls == [], root_logger_calls


def test_generate_excel_report_handles_no_matching_subband(tmp_path):
    """Bug 47: empty avg_df_list must not crash pd.concat.

    When no antenna frequency falls in any configured subband, ``avg_df_list``
    is empty and ``pd.concat([])`` raised ``ValueError: No objects to
    concatenate``. The report must still be generated.
    """
    import pandas as pd

    df = pd.DataFrame(
        {
            "Supplier": ["S"],
            "Antenna_Model": ["M"],
            "Revision_Version": ["R"],
            "Array_ID": ["A"],
            "Cell": [50.0],
            "Theta_Electrical_Tilt": [0.0],
            "Frequency_value": [100.0],  # below every SUBBANDS_DEFAULT range
        }
    )
    report_name = tmp_path / "BEreport.xlsx"
    report_mod._generate_excel_report(df, report_name, report_mod.SUBBANDS_DEFAULT)
    assert report_name.is_file()


def test_generate_report_surfaces_skipped_files(tmp_path, make_pattern_dict, caplog):
    """Bug 48: files that fail processing must be surfaced, not silently dropped.

    One valid pattern and one invalid file are placed in the input directory.
    The report must be generated from the valid file while logging a warning
    that reports the number of skipped files.
    """
    import json
    import logging

    input_dir = tmp_path / "in"
    input_dir.mkdir()
    output_dir = tmp_path / "out"

    good = make_pattern_dict(
        coordinate_system="SPCS_Ericsson",
        peak_theta=90.0,
        peak_phi=0.0,
        extra={
            "Supplier": "S",
            "Antenna_Model": "M",
            "Revision_Version": "R",
            "Array_ID": "A",
            "Theta_Electrical_Tilt": 0.0,
            "Frequency": {"value": 2100.0, "unit": "MHz"},
        },
    )
    (input_dir / "good.json").write_text(json.dumps(good), encoding="utf-8")
    (input_dir / "bad.json").write_text("{}", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="eas_3d_pattern.util_func.report"):
        df = report_mod.generate_report_eas(input_dir, output_dir)

    assert len(df) == 1
    assert "skipped" in caplog.text.lower()
