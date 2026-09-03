# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for peak location and the top 3 dB border.

Written ahead of the Phase 3b move of these methods into
``eas_3d_pattern.metrics.peak`` (plan section 2.1.3), which requires the
previously uncovered branches to be pinned first:

* the ``power=True`` path of both methods (the ``P_tp_dB`` component),
* the single-theta-point grid-step fallback,
* the side effects both methods leave on ``Pattern_3D``, which
  ``util_func/report.py`` depends on.
"""

from __future__ import annotations

import pytest

from eas_3d_pattern import AntennaPattern


class TestFindPeakCoordinates:
    """Peak search over the power and co-polar components."""

    def test_copolar_peak_matches_configured_beam(self, pattern_path):
        pattern = AntennaPattern(
            pattern_path(peak_theta=90.0, peak_phi=0.0), validate=False
        )
        theta, phi = pattern.find_peak_coordinates(power=False)
        assert theta == pytest.approx(90.0)
        assert phi == pytest.approx(0.0)

    def test_power_component_peak_is_searched(self, pattern_path):
        """``power=True`` selects the P_tp_dB component rather than P_co_dB."""
        pattern = AntennaPattern(
            pattern_path(peak_theta=90.0, peak_phi=0.0), validate=False
        )
        theta, phi = pattern.find_peak_coordinates(power=True)
        assert theta == pytest.approx(90.0)
        assert phi == pytest.approx(0.0)

    def test_offset_beam_peak_is_found(self, pattern_path):
        """The search must track the beam, not return a fixed coordinate."""
        pattern = AntennaPattern(
            pattern_path(peak_theta=60.0, peak_phi=25.0), validate=False
        )
        theta, phi = pattern.find_peak_coordinates(power=False)
        assert theta == pytest.approx(60.0)
        assert phi == pytest.approx(25.0)

    def test_peak_coordinates_attr_is_published(self, pattern_path):
        """``util_func/report.py`` reads ``Pattern_3D.peak_coordinates``.

        The attribute is a deliberate side effect of the call and part of the
        contract; report generation breaks without it.
        """
        pattern = AntennaPattern(pattern_path(), validate=False)
        assert "peak_coordinates" not in pattern.Pattern_3D.attrs

        theta, phi = pattern.find_peak_coordinates(power=False)

        assert pattern.Pattern_3D.attrs["peak_coordinates"] == (theta, phi)


class TestTopThreeDbPoint:
    """The theta border where the beam falls 3 dB below its peak."""

    def test_power_component_cut_is_used(self, pattern_path):
        """``power=True`` takes the vertical cut from P_tp_dB."""
        pattern = AntennaPattern(
            pattern_path(peak_theta=90.0, peak_phi=0.0), validate=False
        )
        top = pattern.calculate_top_3db_point(power=True)
        assert top == pytest.approx(85.0)

    def test_single_theta_point_uses_unit_grid_step_fallback(self, pattern_path):
        """A one-row theta axis has no spacing to measure, so the step falls back to 1.

        ``np.diff`` on a single-element axis is empty, so the median grid step is
        undefined. The method must not produce nan; with no -3 dB crossing on a
        single-point cut it reports the peak theta itself.
        """
        pattern = AntennaPattern(
            pattern_path(theta_sampling=[90.0, 5.0, 90.0], peak_theta=90.0),
            validate=False,
        )
        top = pattern.calculate_top_3db_point(power=False)
        assert top == pytest.approx(90.0)

    def test_top_3db_point_attr_is_published(self, pattern_path):
        """The border is also recorded on the dataset attrs as a side effect."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        top = pattern.calculate_top_3db_point(power=False)
        assert pattern.Pattern_3D.attrs["top_3db_point"] == pytest.approx(top)

    def test_peak_side_effect_survives_via_top_3db(self, pattern_path):
        """``report.py`` calls only ``calculate_top_3db_point`` then reads the peak.

        The peak attribute must therefore be published transitively, without the
        caller invoking ``find_peak_coordinates`` itself.
        """
        pattern = AntennaPattern(pattern_path(), validate=False)
        pattern.calculate_top_3db_point(power=False)
        assert "peak_coordinates" in pattern.Pattern_3D.attrs


# The ``not isinstance(peak_tuple, tuple)`` guard in ``find_peak`` is NOT covered,
# and cannot be reached: ``stack(pt=("Theta", "Phi"))`` raises ``KeyError`` if either
# dimension is missing, and when both are present the stacked MultiIndex coordinate is
# always a tuple. ``_process_pattern_data`` always produces both dimensions, so no
# input reachable through ``AntennaPattern`` triggers it. Left in place pending a
# decision on removing it as dead code; do not add a test that fabricates the state.
