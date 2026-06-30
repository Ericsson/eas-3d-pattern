"""Regression tests for coordinate-system transforms (Bugs 41-44).

Empirical note: spec-valid SPCS_CW data uses theta in [-90, 90] and phi in
[0, 359] (verified against the bundled ANTMODEL2 sample). ``theta + 90`` then
correctly maps to [0, 180]. The real defect is the absence of a post-condition
check: out-of-spec input silently produces theta/phi outside the internal
SPCS_Ericsson ranges, yielding negative solid-angle weights and corrupted
calculations.
"""

from __future__ import annotations

import pytest

from eas_3d_pattern import AntennaPattern


def test_cw_out_of_spec_theta_is_rejected(pattern_path):
    """Bug 41: CW theta outside spec must not silently yield negative dOmega.

    Feeding CW data with theta in [0, 180] (out of CW's [-90, 90] spec) makes
    ``theta + 90`` land in [90, 270]; ``sin`` then goes negative, corrupting
    directivity/beam-efficiency. The transform must reject this instead.
    Phi here is kept in valid CW range [0, 355] so only theta is out of range.
    """
    path = pattern_path(
        coordinate_system="SPCS_CW",
        theta_sampling=[0.0, 5.0, 180.0],
        phi_sampling=[0.0, 5.0, 355.0],
        peak_theta=90.0,
        peak_phi=0.0,
    )
    with pytest.raises(ValueError, match="(?i)theta"):
        AntennaPattern(path, validate=False)


def test_valid_cw_pattern_constructs_with_internal_ranges(pattern_path):
    """Spec-valid CW data (theta in [-90, 90]) must still convert successfully.

    Guards against the post-condition over-rejecting real CW data: after the
    transform theta must be within [0, 180].
    """
    path = pattern_path(
        coordinate_system="SPCS_CW",
        theta_sampling=[-90.0, 5.0, 90.0],
        phi_sampling=[0.0, 5.0, 355.0],
        peak_theta=0.0,
        peak_phi=0.0,
    )
    pattern = AntennaPattern(path, validate=False)
    theta = pattern.Pattern_3D.coords["Theta"].values
    assert theta.min() >= 0.0
    assert theta.max() <= 180.0
