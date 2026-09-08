# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for beam efficiency and sector-preset construction.

Written ahead of the Phase 3c move of this code into
``eas_3d_pattern.metrics.efficiency`` (plan section 2.1.3), pinning the branches
that were previously uncovered:

* the default ``eas`` preset path, which existing tests bypassed by always
  passing explicit sector definitions,
* the NGMN Type A guard for missing HPBW metadata,
* the fallback path for externally registered presets,
* ``powersum=False``, which integrates the co-polar component,
* the type guard rejecting non-``BoundaryBoxSquare`` sectors.

NGMN Type A sector *geometry* is covered in ``test_ngmn_sectors.py``; this module
covers the efficiency computation and preset dispatch around it.
"""

from __future__ import annotations

import pytest

from eas_3d_pattern import AntennaPattern, SectorDefinition
from eas_3d_pattern.sector import presets as presets_module


def full_sphere_sectors() -> SectorDefinition:
    """A single sector spanning the whole sphere, so efficiency must be 1.0."""
    sectors = SectorDefinition(load_default=False)
    sectors.add_sector(
        name="all",
        theta_min=(0.0, "<="),
        theta_max=(180.0, "<="),
        phi_min=(-180.0, "<="),
        phi_max=(180.0, "<="),
    )
    return sectors


class TestDefaultEasPreset:
    """The default preset path, used when no sector definitions are passed."""

    def test_default_preset_is_eas(self, pattern_path):
        pattern = AntennaPattern(pattern_path(), validate=False)
        assert pattern.sector_preset == "eas"

    def test_beam_efficiency_without_sectors_builds_eas_preset(self, pattern_path):
        """No explicit sectors means the eas preset is built from the pattern itself.

        The preset derives its top border from the measured 3 dB point, so this
        path also exercises the peak search.
        """
        pattern = AntennaPattern(
            pattern_path(peak_theta=90.0, peak_phi=0.0), validate=False
        )
        efficiency = pattern.calculate_beam_efficiency()

        assert isinstance(efficiency, dict)
        assert efficiency
        for name, value in efficiency.items():
            assert isinstance(name, str)
            assert 0.0 <= value <= 1.0


class TestNgmnTypeAMetadataGuard:
    """The Type A preset needs HPBW metadata and must say so."""

    @pytest.mark.parametrize("missing_key", ["Theta_HPBW", "Phi_HPBW"])
    def test_missing_hpbw_raises(self, pattern_path, missing_key):
        pattern = AntennaPattern(pattern_path(), validate=False)
        pattern.sector_preset = "ngmn-v13-type-a"
        del pattern.data[missing_key]

        with pytest.raises(ValueError, match="(?i)hpbw"):
            pattern.calculate_beam_efficiency()


class TestExternallyRegisteredPreset:
    """Presets added to the registry are dispatched through the fallback path."""

    def test_external_preset_is_dispatched(self, pattern_path, monkeypatch):
        """A preset that is neither eas nor Type A falls through to from_preset().

        The fallback takes no pattern-derived arguments, so the preset's load must
        be callable with none.
        """
        class _WholeSpherePreset(presets_module.SectorPreset):
            name = "whole-sphere"

            def load(self, **_kwargs):
                return full_sphere_sectors()

        registry = dict(presets_module._REGISTRY)
        registry["whole-sphere"] = _WholeSpherePreset()
        monkeypatch.setattr(presets_module, "_REGISTRY", registry, raising=True)

        pattern = AntennaPattern(pattern_path(), validate=False)
        pattern.sector_preset = "whole-sphere"
        efficiency = pattern.calculate_beam_efficiency()

        assert efficiency["all"] == pytest.approx(1.0, abs=1e-9)


class TestPowersumSelectsComponent:
    """``powersum`` chooses which field component is integrated."""

    def test_powersum_false_uses_copolar(self, pattern_path):
        """The co-polar branch must run and still produce a valid fraction."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        efficiency = pattern.calculate_beam_efficiency(
            sector_definitions=full_sphere_sectors(), powersum=False
        )
        assert efficiency["all"] == pytest.approx(1.0, abs=1e-9)

    def test_full_sphere_is_unity_for_both_components(self, pattern_path):
        """Whole-sphere efficiency is 1.0 regardless of the component chosen."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        on_power = pattern.calculate_beam_efficiency(
            sector_definitions=full_sphere_sectors(), powersum=True
        )
        on_copolar = pattern.calculate_beam_efficiency(
            sector_definitions=full_sphere_sectors(), powersum=False
        )
        assert on_power["all"] == pytest.approx(1.0, abs=1e-9)
        assert on_copolar["all"] == pytest.approx(1.0, abs=1e-9)


class TestSectorTypeGuard:
    """Only rectangular boundary boxes are supported."""

    def test_non_boundary_box_sector_raises(self, pattern_path):
        pattern = AntennaPattern(pattern_path(), validate=False)
        sectors = full_sphere_sectors()
        sectors.sectors["not-a-box"] = object()

        with pytest.raises(TypeError, match="BoundaryBoxSquare"):
            pattern.calculate_beam_efficiency(sector_definitions=sectors)
