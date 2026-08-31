"""Tests for ``calculate_directivity()`` and ``calculate_losses()``.

These are *correctness* tests, not characterization tests. Directivity has exact
closed-form values for simple radiation patterns, so the implementation is checked against
analysis rather than against whatever it happens to return today.

For a pattern whose radiation intensity depends only on theta, directivity is::

    D = U_max / <U>,    <U> = (1 / 4pi) * integral U sin(theta) dtheta dphi

giving these reference values:

===================  ==================  ===========  ==============
Pattern              <U>                 D            D [dBi]
===================  ==================  ===========  ==============
isotropic, U = 1     1                   1            0.0000
U = sin^2(theta)     2/3                 3/2          1.7609
U = sin^4(theta)     8/15                15/8         2.7300
U = cos^2(theta)     1/3                 3            4.7712
===================  ==================  ===========  ==============

Note that ``sin^2`` and ``cos^2`` are *not* symmetric on a sphere: the ``sin(theta)``
Jacobian weights the equator more heavily than the poles, so a pole-peaked ``cos^2``
pattern is twice as directive as an equator-peaked ``sin^2`` one. Asserting they are equal
is a mistake this suite exists to catch.

Nothing off the shelf can test this for us. numpy has no spherical-geometry or solid-angle
support, and scipy — despite providing quadrature, spherical harmonics and Lebedev rules —
has no notion of antenna directivity. What scipy *can* do is compute the underlying
integral independently, so ``TestReferenceValuesAreThemselvesCorrect`` uses it to verify
the hardcoded constants above rather than trusting hand algebra.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import lebedev_rule, quad

from eas_3d_pattern import AntennaPattern

# Attenuation stand-in for a true pattern null, where -10*log10(0) is undefined.
# Points at theta = 0 and 180 carry zero solid angle, so their value is irrelevant to the
# integral; this exists only to keep the JSON finite.
NULL_ATTENUATION_DB = 120.0

# Order for scipy's Lebedev spherical quadrature, used only to cross-check the reference
# constants below. High enough to be exact for these low-order patterns.
LEBEDEV_ORDER = 35

# Grid step for the analytic patterns. At 5 degrees the quadrature error stays under
# 0.003 dB for every case below, which the tolerance accommodates.
GRID_STEP_DEG = 5.0

# Tolerance in dB. Comfortably above the observed 5-degree quadrature error (0.003 dB) and
# far below the 3 dB gap between the correct answer and a missing sin(theta) weight.
DIRECTIVITY_TOL_DB = 0.01

ISOTROPIC_DBI = 0.0
SIN_SQUARED_DBI = 10 * np.log10(1.5)
SIN_FOURTH_DBI = 10 * np.log10(15 / 8)
COS_SQUARED_DBI = 10 * np.log10(3.0)

DECLARED_GAIN_DBI = 12.0


def build_analytic_pattern(
    tmp_path: Path,
    intensity: Callable[[float], float],
    gain_dbi: float = DECLARED_GAIN_DBI,
    step: float = GRID_STEP_DEG,
) -> AntennaPattern:
    """Write a pattern whose linear radiation intensity follows ``intensity(theta_deg)``.

    Parameters
    ----------
    tmp_path
        Directory to write the pattern JSON into.
    intensity
        Maps theta in degrees to linear radiation intensity, normalized so the peak is 1.
    gain_dbi
        Declared header gain, used by ``calculate_losses()``.
    step
        Grid step in degrees for both theta and phi.

    Returns:
    -------
    AntennaPattern
        The loaded pattern, ready for directivity calculation.
    """
    thetas = np.arange(0.0, 180.0 + 1e-9, step)
    phis = np.arange(-180.0, 180.0 - step + 1e-9, step)

    rows: list[list[float]] = []
    for theta in thetas:
        u = float(intensity(float(theta)))
        attenuation = (
            NULL_ATTENUATION_DB
            if u <= 0.0
            else min(-10.0 * float(np.log10(u)), NULL_ATTENUATION_DB)
        )
        rows.extend([attenuation, attenuation, attenuation + 20.0] for _ in phis)

    pattern = {
        "Coordinate_System": "SPCS_Ericsson",
        "Gain": {"value": gain_dbi, "unit": "dBi"},
        "Phi_HPBW": 65.0,
        "Theta_HPBW": 7.0,
        "Front_to_Back": 30.0,
        "Theta_Sampling": [0.0, step, 180.0],
        "Phi_Sampling": [-180.0, step, 180.0 - step],
        "Data_Set_Row_Structure": [
            "MagAttenuationTP",
            "MagAttenuationCo",
            "MagAttenuationCr",
        ],
        "Data_Set": rows,
    }
    file_path = tmp_path / "analytic_pattern.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(pattern), encoding="utf-8")
    return AntennaPattern(str(file_path), validate=False)


def sin_squared(theta_deg: float) -> float:
    """Hertzian-dipole intensity, peaking at the equator."""
    return float(np.sin(np.radians(theta_deg)) ** 2)


def sin_fourth(theta_deg: float) -> float:
    """A narrower equator-peaked pattern."""
    return float(np.sin(np.radians(theta_deg)) ** 4)


def cos_squared(theta_deg: float) -> float:
    """A pole-peaked pattern."""
    return float(np.cos(np.radians(theta_deg)) ** 2)


def isotropic(theta_deg: float) -> float:
    """Uniform radiation in every direction."""
    return 1.0


class TestDirectivityAgainstClosedForm:
    """``calculate_directivity()`` versus analytically exact values."""

    @pytest.mark.parametrize(
        ("intensity", "expected_dbi", "description"),
        [
            (isotropic, ISOTROPIC_DBI, "isotropic"),
            (sin_squared, SIN_SQUARED_DBI, "U = sin^2, D = 3/2"),
            (sin_fourth, SIN_FOURTH_DBI, "U = sin^4, D = 15/8"),
            (cos_squared, COS_SQUARED_DBI, "U = cos^2, D = 3"),
        ],
    )
    def test_matches_analytic_directivity(
        self, tmp_path, intensity, expected_dbi, description
    ):
        pattern = build_analytic_pattern(tmp_path, intensity)
        assert pattern.calculate_directivity() == pytest.approx(
            expected_dbi, abs=DIRECTIVITY_TOL_DB
        ), description

    def test_pole_peaked_is_more_directive_than_equator_peaked(self, tmp_path):
        """The sin(theta) Jacobian must not be dropped.

        ``cos^2`` and ``sin^2`` differ only by where they point. If the solid-angle
        weighting were omitted, the two would come out equal; correctly weighted they
        differ by 10*log10(2) ~= 3.01 dB.
        """
        equator = build_analytic_pattern(tmp_path / "a", sin_squared)
        pole = build_analytic_pattern(tmp_path / "b", cos_squared)

        difference = pole.calculate_directivity() - equator.calculate_directivity()
        assert difference == pytest.approx(10 * np.log10(2.0), abs=DIRECTIVITY_TOL_DB)

    def test_quadrature_error_shrinks_on_a_finer_grid(self, tmp_path):
        """Remaining error must be discretization, which refinement reduces."""
        coarse = build_analytic_pattern(tmp_path / "c", sin_squared, step=10.0)
        fine = build_analytic_pattern(tmp_path / "f", sin_squared, step=2.0)

        coarse_err = abs(coarse.calculate_directivity() - SIN_SQUARED_DBI)
        fine_err = abs(fine.calculate_directivity() - SIN_SQUARED_DBI)
        assert fine_err < coarse_err

    def test_directivity_is_at_least_isotropic(self, tmp_path):
        """No passive pattern can be less directive than an isotropic radiator."""
        for intensity in (isotropic, sin_squared, sin_fourth, cos_squared):
            pattern = build_analytic_pattern(tmp_path / intensity.__name__, intensity)
            assert pattern.calculate_directivity() >= -DIRECTIVITY_TOL_DB


class TestReferenceValuesAreThemselvesCorrect:
    """Validate the hardcoded reference constants against independent quadrature.

    The constants above are exact rationals derived by hand, and hand-derived references
    are exactly the kind of thing that is confidently wrong: the first draft of this suite
    asserted ``cos^2`` had the same directivity as ``sin^2``, forgetting that the
    ``sin(theta)`` Jacobian breaks that symmetry. The implementation disagreed, and the
    implementation was right.

    scipy has no notion of antenna directivity, so it cannot check ``calculate_directivity``
    for us. What it can do is compute the underlying integral independently, which pins the
    reference values and removes the algebra as a source of error.

    These tests exercise no library code. They guard the rest of this file.
    """

    @pytest.mark.parametrize(
        ("intensity", "expected_dbi"),
        [
            (isotropic, ISOTROPIC_DBI),
            (sin_squared, SIN_SQUARED_DBI),
            (sin_fourth, SIN_FOURTH_DBI),
            (cos_squared, COS_SQUARED_DBI),
        ],
    )
    def test_constant_matches_scipy_quadrature(self, intensity, expected_dbi):
        """``<U> = 1/2 * integral U(theta) sin(theta) dtheta`` over [0, pi]."""
        mean_intensity = (
            0.5 * quad(lambda t: intensity(np.degrees(t)) * np.sin(t), 0.0, np.pi)[0]
        )
        directivity_dbi = 10 * np.log10(1.0 / mean_intensity)
        assert directivity_dbi == pytest.approx(expected_dbi, abs=1e-9)

    @pytest.mark.parametrize(
        ("intensity", "expected_dbi"),
        [
            (isotropic, ISOTROPIC_DBI),
            (sin_squared, SIN_SQUARED_DBI),
            (sin_fourth, SIN_FOURTH_DBI),
            (cos_squared, COS_SQUARED_DBI),
        ],
    )
    def test_constant_matches_lebedev_spherical_quadrature(
        self, intensity, expected_dbi
    ):
        """Second, structurally different check: quadrature over the sphere itself.

        Lebedev integrates on the sphere directly rather than reducing to a 1-D theta
        integral, so it does not share the ``sin(theta)`` factor that the quad-based check
        writes out by hand.
        """
        points, weights = lebedev_rule(LEBEDEV_ORDER)
        theta_deg = np.degrees(np.arccos(np.clip(points[2], -1.0, 1.0)))
        values = np.array([intensity(t) for t in theta_deg])

        mean_intensity = float(np.sum(weights * values) / np.sum(weights))
        directivity_dbi = 10 * np.log10(1.0 / mean_intensity)
        assert directivity_dbi == pytest.approx(expected_dbi, abs=1e-6)


class TestDirectivityCaching:
    """``dOmega`` is injected into ``Pattern_3D`` on first use and then reused."""

    def test_repeated_calls_agree(self, tmp_path):
        """The cached-dOmega path must give the same answer as the first call."""
        pattern = build_analytic_pattern(tmp_path, sin_squared)

        first = pattern.calculate_directivity()
        assert "dOmega" in pattern.Pattern_3D.data_vars
        second = pattern.calculate_directivity()

        assert first == pytest.approx(second, abs=1e-12)

    def test_domega_sums_to_the_full_sphere(self, tmp_path):
        """Total solid angle over a full sphere must be 4*pi steradians."""
        pattern = build_analytic_pattern(tmp_path, sin_squared)
        pattern.calculate_directivity()

        total = float(pattern.Pattern_3D["dOmega"].sum())
        assert total == pytest.approx(4 * np.pi, rel=0.01)


class TestLosses:
    """``calculate_losses()`` is declared gain minus computed directivity."""

    def test_losses_are_gain_minus_directivity(self, tmp_path):
        pattern = build_analytic_pattern(tmp_path, sin_squared, gain_dbi=1.0)
        expected = 1.0 - pattern.calculate_directivity()
        assert pattern.calculate_losses() == pytest.approx(expected, abs=1e-9)

    def test_lossless_pattern_reports_zero_loss(self, tmp_path):
        """Declaring gain equal to the theoretical directivity implies no loss."""
        pattern = build_analytic_pattern(
            tmp_path, sin_squared, gain_dbi=SIN_SQUARED_DBI
        )
        assert pattern.calculate_losses() == pytest.approx(0.0, abs=DIRECTIVITY_TOL_DB)

    def test_missing_gain_raises(self, tmp_path):
        """Loss is undefined without a declared gain, and must not be guessed."""
        pattern = build_analytic_pattern(tmp_path, sin_squared)
        del pattern.raw_data["Gain"]

        with pytest.raises(ValueError, match="(?i)gain"):
            pattern.calculate_losses()
