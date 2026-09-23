"""Smoke tests verifying the test harness and synthetic pattern factory work."""

from __future__ import annotations

from eas_3d_pattern import AntennaPattern


def test_import_and_construct(pattern_path):
    """A synthetic pattern can be loaded into AntennaPattern offline."""
    path = pattern_path()
    pattern = AntennaPattern(path, validate=False)
    assert pattern.pattern is not None
    assert "P_tp_lin" in pattern.pattern.data_vars
