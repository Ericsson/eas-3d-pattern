# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for loading patterns that declare angles per row (NGMN NonUniformSampling).

Covers the branch of ``_process_pattern_data`` taken when no ``Theta_Sampling`` /
``Phi_Sampling`` triples are present, and the sampling metadata accessors in that
state — the gap left open when those accessors moved in Phase 2c.
"""

from __future__ import annotations

import warnings

import pytest

from eas_3d_pattern import AntennaPattern


class TestNonUniformLoading:
    """A pattern without sampling triples loads through the non-uniform branch."""

    def test_loads_and_builds_dataset(self, nonuniform_pattern_path):
        pattern = AntennaPattern(nonuniform_pattern_path(), validate=False)
        assert pattern.is_uniform_sampling is False
        assert set(pattern.pattern.dims) == {"Theta", "Phi"}
        assert pattern.pattern.sizes["Theta"] == 37
        assert pattern.pattern.sizes["Phi"] == 72

    def test_sampling_accessors_return_none(self, nonuniform_pattern_path):
        """Without triples there is no derived grid to return.

        This is the branch of ``theta_sampling`` / ``phi_sampling`` that the Phase 2c
        tests could not reach, because the uniform fixture always supplies triples.
        """
        pattern = AntennaPattern(nonuniform_pattern_path(), validate=False)
        assert pattern.theta_sampling is None
        assert pattern.phi_sampling is None

    def test_metrics_agree_with_uniform_equivalent(
        self, nonuniform_pattern_path, pattern_path
    ):
        """The same beam declared either way must yield the same directivity.

        Guards the two loading branches against drifting apart: the row-enumerated
        and triple-derived forms describe an identical grid, so every derived metric
        must match.
        """
        nonuniform = AntennaPattern(nonuniform_pattern_path(), validate=False)
        uniform = AntennaPattern(pattern_path(), validate=False)

        assert nonuniform.calculate_directivity() == pytest.approx(
            uniform.calculate_directivity(), abs=1e-9
        )
        assert nonuniform.find_peak_coordinates() == uniform.find_peak_coordinates()


class TestNoSelfInflictedDeprecationWarning:
    """Loading a pattern must not emit the library's own deprecation warnings.

    ``_process_pattern_data`` used to test the non-uniform branch via
    ``is_nonuniform_sampling``, which was deprecated in Phase 2c. That made every
    non-uniform load raise a DeprecationWarning about an API the caller never
    touched. Internal code must use ``not is_uniform_sampling`` instead.
    """

    def test_nonuniform_load_is_warning_free(self, nonuniform_pattern_path):
        path = nonuniform_pattern_path()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            AntennaPattern(path, validate=False)

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert not deprecations, [str(w.message) for w in deprecations]

    def test_uniform_load_is_warning_free(self, pattern_path):
        path = pattern_path()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            AntennaPattern(path, validate=False)

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert not deprecations, [str(w.message) for w in deprecations]
