"""Regression tests for AntennaPattern parser bugs (v0.2.0 bug table)."""

from __future__ import annotations

import numpy as np

from eas_3d_pattern import AntennaPattern


def test_top_3db_point_no_crossing_does_not_raise(pattern_path):
    """Bug 1: a beam peaking at the top of the cut must not raise UnboundLocalError.

    When the peak sits at theta=0, the upward vertical cut contains no point at
    or below -3 dB, so the search loop never assigns ``top_border``. The method
    must return a finite float fallback instead of crashing.
    """
    path = pattern_path(peak_theta=0.0, peak_phi=0.0)
    pattern = AntennaPattern(path, validate=False)
    top = pattern.calculate_top_3db_point(power=False)
    assert isinstance(top, float)
    assert np.isfinite(top)
