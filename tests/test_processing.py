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

The ``else`` branch raising "No uniform or nonuniform sampling detected" is
covered by ``TestUnreachableSamplingBranch`` below, which documents why it cannot
be triggered rather than fabricating the state.
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


class TestUnreachableSamplingBranch:
    """The 'No uniform or nonuniform sampling detected' branch cannot be reached.

    The dispatch is::

        if is_uniform_sampling and theta_sampling is not None and phi_sampling is not None:
        elif not is_uniform_sampling:
        else:  # <- unreachable

    ``is_uniform_sampling`` is ``bool(Theta_Sampling and Phi_Sampling)`` and
    ``theta_sampling`` returns ``None`` exactly when ``Theta_Sampling`` is falsy, so a
    true ``is_uniform_sampling`` guarantees both accessors are non-``None``. The
    ``elif`` then absorbs every remaining case. Malformed triples raise from
    ``np.arange`` or indexing rather than yielding ``None``.

    This test documents the invariant instead of fabricating an impossible object;
    the branch is left in place pending a decision on removing it as dead code.
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
