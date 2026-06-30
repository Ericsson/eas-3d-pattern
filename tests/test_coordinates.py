"""Regression tests for coordinate-system transforms (Bugs 41-44).

Empirical note: spec-valid SPCS_CW data uses theta in [-90, 90] and phi in
[0, 359] (verified against the bundled ANTMODEL2 sample). ``theta + 90`` then
correctly maps to [0, 180]. The real defect is the absence of a post-condition
check: out-of-spec input silently produces theta/phi outside the internal
SPCS_Ericsson ranges, yielding negative solid-angle weights and corrupted
calculations.
"""

from __future__ import annotations

import numpy as np
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


@pytest.mark.parametrize(
    ("system", "theta_sampling"),
    [
        ("SPCS_Polar", [0.0, 5.0, 180.0]),
        ("SPCS_CW", [-90.0, 5.0, 90.0]),
        ("SPCS_CCW", [-90.0, 5.0, 90.0]),
        ("SPCS_Geo", [0.0, 5.0, 180.0]),
    ],
)
def test_phi_boundary_consistent_across_transforms(
    pattern_path, system, theta_sampling
):
    """Bug 42: the phi=180 column maps consistently to -180 in every system.

    The ``phi >= 180`` (Polar/CCW) vs ``phi > 180`` (CW/Geo) difference is not a
    bug: CW/Geo negate the wrapped value, so ``>`` is the correct compensation.
    For spec-valid input all four systems map the phi=180 input column to -180
    and keep phi within the internal [-180, 179] range (no +180, no dropped
    column). This regression test pins that correct behavior.
    """
    path = pattern_path(
        coordinate_system=system,
        theta_sampling=theta_sampling,
        phi_sampling=[0.0, 5.0, 355.0],
        peak_theta=0.0 if system in ("SPCS_CW", "SPCS_CCW") else 90.0,
        peak_phi=0.0,
    )
    pattern = AntennaPattern(path, validate=False)
    phi = pattern.Pattern_3D.coords["Phi"].values
    assert phi.min() >= -180.0
    assert phi.max() <= 179.0
    assert not np.any(np.isclose(phi, 180.0))
    assert np.any(np.isclose(phi, -180.0))
