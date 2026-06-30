"""Smoke tests verifying the test harness and synthetic pattern factory work."""

from __future__ import annotations

from eas_3d_pattern import AntennaPattern


def test_import_and_construct(pattern_path):
    """A synthetic pattern can be loaded into AntennaPattern offline."""
    path = pattern_path()
    pattern = AntennaPattern(path, validate=False)
    assert pattern.Pattern_3D is not None
    assert "P_tp_lin" in pattern.Pattern_3D.data_vars
