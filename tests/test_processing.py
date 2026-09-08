# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for turning raw pattern rows into the processed dataset.

Written ahead of the Phase 4c move of ``_process_pattern_data`` into its own
module (plan section 2.1.3), pinning its remaining uncovered branches: the
sampling/row count mismatch, duplicate coordinate pairs, and the irregular-grid
warnings.

The uniform-sampling grid guards (``verify(..., AssertionError)``) protect an
internal invariant that no input can violate; ``TestUniformSamplingInvariant``
below documents why rather than fabricating the impossible state.
"""

from __future__ import annotations

import logging

import pytest

from eas_3d_pattern import AntennaPattern

ROW_STRUCTURE = [
    "Theta",
    "Phi",
    "MagAttenuationTP",
    "MagAttenuationCo",
    "MagAttenuationCr",
]


class TestSamplingRowCountMismatch:
    """Declared sampling triples must agree with the number of data rows."""

    def test_fewer_rows_than_sampling_points_raises(self, pattern_path):
        """A truncated Data_Set cannot be laid onto the declared grid."""
        path = pattern_path(
            data_set=[[1.0, 1.0, 21.0] for _ in range(10)],
            row_structure=["MagAttenuationTP", "MagAttenuationCo", "MagAttenuationCr"],
        )
        with pytest.raises(ValueError, match="(?i)does not equal pattern data"):
            AntennaPattern(path, validate=False)

    def test_error_names_both_counts(self, pattern_path):
        """The message must state the expected and actual counts, for diagnosis."""
        path = pattern_path(
            data_set=[[1.0, 1.0, 21.0] for _ in range(10)],
            row_structure=["MagAttenuationTP", "MagAttenuationCo", "MagAttenuationCr"],
        )
        with pytest.raises(
            ValueError, match="(?i)does not equal pattern data"
        ) as excinfo:
            AntennaPattern(path, validate=False)

        message = str(excinfo.value)
        assert "n=2664" in message
        assert "m=10" in message


class TestDuplicateCoordinates:
    """Each (Theta, Phi) pair may appear only once."""

    def test_repeated_pair_raises(self, nonuniform_pattern_path):
        """Duplicated coordinates would silently collapse during reshaping."""
        path = nonuniform_pattern_path(
            extra={
                "Data_Set": [
                    [90.0, 0.0, 0.0, 0.0, 20.0],
                    [90.0, 0.0, 3.0, 3.0, 23.0],
                ],
                "Data_Set_Row_Structure": ROW_STRUCTURE,
            }
        )
        with pytest.raises(ValueError, match="(?i)duplicate"):
            AntennaPattern(path, validate=False)


class TestIrregularGridWarnings:
    """Uneven Theta/Phi spacing is allowed but must be reported."""

    def test_irregular_phi_spacing_warns(self, nonuniform_pattern_path, caplog):
        """Phi spacing of 1 then 4 degrees is uneven and must warn."""
        rows = [
            [theta, phi, 0.0, 0.0, 20.0]
            for theta in (0.0, 90.0)
            for phi in (0.0, 1.0, 5.0)
        ]
        path = nonuniform_pattern_path(
            extra={"Data_Set": rows, "Data_Set_Row_Structure": ROW_STRUCTURE}
        )

        with caplog.at_level(logging.WARNING, logger="eas_3d_pattern._processing"):
            AntennaPattern(path, validate=False)

        assert any("gridded data detected in Phi" in r.message for r in caplog.records)

    def test_regular_grid_does_not_warn(self, nonuniform_pattern_path, caplog):
        """The default regular grid must not produce spurious warnings."""
        with caplog.at_level(logging.WARNING, logger="eas_3d_pattern._processing"):
            AntennaPattern(nonuniform_pattern_path(), validate=False)

        assert not [r for r in caplog.records if "gridded data detected" in r.message]


class TestUniformSamplingInvariant:
    """The uniform-sampling grid guards cannot fire in practice.

    The dispatch is now::

        if is_uniform_sampling:
            verify(theta_sampling is not None, ..., AssertionError)
            verify(phi_sampling is not None, ..., AssertionError)
            ...  # build the meshgrid
        else:
            ...  # non-uniform: coordinates carried on each row

    ``is_uniform_sampling`` is ``bool(Theta_Sampling and Phi_Sampling)`` and
    ``theta_sampling`` returns ``None`` exactly when ``Theta_Sampling`` is falsy, so a
    true ``is_uniform_sampling`` guarantees both accessors are non-``None``. The two
    ``verify(..., AssertionError)`` guards therefore protect an internal invariant that
    cannot be violated through any input; malformed triples raise from ``np.arange`` or
    indexing rather than yielding ``None``.

    These tests document the invariant instead of fabricating an impossible object; the
    guards are kept for the type narrowing they express and as executable documentation.
    """

    def test_uniform_sampling_implies_both_accessors_present(self, pattern_path):
        pattern = AntennaPattern(pattern_path(), validate=False)
        assert pattern.is_uniform_sampling is True
        assert pattern.theta_sampling is not None
        assert pattern.phi_sampling is not None

    def test_absent_triples_take_the_nonuniform_branch(self, nonuniform_pattern_path):
        pattern = AntennaPattern(nonuniform_pattern_path(), validate=False)
        assert pattern.is_uniform_sampling is False
        assert pattern.theta_sampling is None
        assert pattern.phi_sampling is None
