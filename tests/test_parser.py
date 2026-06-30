"""Regression tests for AntennaPattern parser bugs (v0.2.0 bug table)."""

from __future__ import annotations

import numpy as np
import pytest

from eas_3d_pattern import AntennaPattern, SectorDefinition


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


def test_unknown_coordinate_system_raises(pattern_path):
    """Bug 2: an unrecognized coordinate system must not silently no-op.

    Previously ``_change_coordinate_system`` matched no branch for an unknown
    system yet still stamped the attrs as converted. It must raise instead.
    """
    path = pattern_path(coordinate_system="SPCS_Unknown")
    with pytest.raises(ValueError, match="coordinate system"):
        AntennaPattern(path, validate=False)


def test_substring_coordinate_system_not_treated_as_internal(pattern_path):
    """Bug 3: substring check must be equality.

    ``"SPCS_Eri"`` is a substring of ``"SPCS_Ericsson"``. The old
    ``not in DEFAULT_INTERNAL_COORD_SYSTEM`` check treated it as already-internal
    and skipped conversion. With ``!=`` it is correctly recognized as a distinct
    (here unsupported) system and rejected.
    """
    path = pattern_path(coordinate_system="SPCS_Eri")
    with pytest.raises(ValueError, match="coordinate system"):
        AntennaPattern(path, validate=False)


def test_beam_efficiency_zero_overall_power_raises(pattern_path):
    """Bug 5: zero overall power must not silently produce inf/nan efficiencies.

    A pattern whose linear power underflows to exactly 0 everywhere makes
    ``Sp_overall == 0``. The division ``Sp_region / Sp_overall`` then yields
    nan/inf silently. The method must instead raise a clear error.
    """
    thetas = np.arange(0.0, 180.0 + 1e-6, 5.0)
    phis = np.arange(-180.0, 175.0 + 1e-6, 5.0)
    n = len(thetas) * len(phis)
    # 4000 dB attenuation -> 10**(-400) underflows to 0.0 for all components.
    data_set = [[4000.0, 4000.0, 4000.0] for _ in range(n)]
    path = pattern_path(
        data_set=data_set,
        row_structure=["MagAttenuationTP", "MagAttenuationCo", "MagAttenuationCr"],
    )
    pattern = AntennaPattern(path, validate=False)
    sectors = SectorDefinition(load_default=False)
    sectors.add_sector(
        name="all",
        theta_min=(0.0, "<="),
        theta_max=(180.0, "<="),
        phi_min=(-180.0, "<="),
        phi_max=(180.0, "<="),
    )
    with pytest.raises(ValueError, match="(?i)overall power"):
        pattern.calculate_beam_efficiency(sector_definitions=sectors)


def test_empty_data_set_raises_clear_error(pattern_path):
    """Bug 6: an empty Data_Set must raise a clear error early in __init__.

    Previously an empty Data_Set surfaced only as a confusing downstream error
    (sampling-count mismatch) or silently produced an empty dataset.
    """
    path = pattern_path(
        data_set=[],
        row_structure=["MagAttenuationTP", "MagAttenuationCo", "MagAttenuationCr"],
    )
    with pytest.raises(ValueError, match="(?i)data_set"):
        AntennaPattern(path, validate=False)


def test_top_3db_point_uses_grid_step_not_hardcoded_one(pattern_path):
    """Bug 43: the 3 dB border must advance by the grid step, not a fixed +1.

    On a 5 deg grid with the beam peaking at theta=90, the -3 dB crossing falls
    on theta=80 (atten 5 dB), so the top border should be 80 + 5 = 85, not the
    hardcoded 80 + 1 = 81.
    """
    path = pattern_path(peak_theta=90.0, peak_phi=0.0)  # default 5 deg grid
    pattern = AntennaPattern(path, validate=False)
    top = pattern.calculate_top_3db_point(power=False)
    assert top == 85.0


def test_validate_true_without_schema_raises(pattern_path, monkeypatch):
    """Bug 46: requesting validation with no schema must not silently skip it.

    If the schema failed to load, ``validate=True`` previously did nothing and
    gave no signal. It must raise so the caller knows validation was not done.
    """
    from eas_3d_pattern.schema_manager import NGMNSchema

    monkeypatch.setattr(NGMNSchema, "schema_content", None)
    path = pattern_path()
    with pytest.raises(ValueError, match="(?i)schema"):
        AntennaPattern(path, validate=True)
