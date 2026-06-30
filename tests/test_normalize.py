"""Tests for issue #5: vendor-specific JSON key normalization (_normalize_json).

Some 3drp files use 'Theta_Tilt' (NGMN whitepaper naming) instead of the
schema-canonical 'Theta_Electrical_Tilt', which broke report generation. The
parser normalizes known variants on load via the module-level ALTERNATIVES map.
"""

from __future__ import annotations

from eas_3d_pattern import AntennaPattern


def _normalize(data: dict) -> dict:
    """Call ``_normalize_json`` in isolation.

    The method does not use ``self``, so it can be invoked unbound for a fast,
    construction-free unit test of the mapping logic.
    """
    return AntennaPattern._normalize_json(None, data)  # type: ignore[arg-type]


def test_canonical_key_passes_through_unchanged():
    """A file already using the canonical key is left untouched."""
    data = {"Theta_Electrical_Tilt": 6.0, "Gain": 1}
    assert _normalize(dict(data)) == data


def test_variant_key_is_renamed_to_canonical():
    """'Theta_Tilt' is renamed to 'Theta_Electrical_Tilt' with its value kept."""
    out = _normalize({"Theta_Tilt": 6.0})
    assert out == {"Theta_Electrical_Tilt": 6.0}
    assert "Theta_Tilt" not in out


def test_existing_canonical_is_not_overwritten_when_both_present():
    """When both keys coexist, the canonical value must not be overwritten."""
    out = _normalize({"Theta_Tilt": 1.0, "Theta_Electrical_Tilt": 2.0})
    assert out["Theta_Electrical_Tilt"] == 2.0


def test_no_variant_leaves_data_untouched():
    """Data without any known variant is returned unchanged (no spurious keys)."""
    data = {"Gain": 1, "Phi_HPBW": 65.0}
    assert _normalize(dict(data)) == data


def test_construction_normalizes_theta_tilt(pattern_path):
    """End-to-end: a file using 'Theta_Tilt' is normalized during init (issue #5)."""
    path = pattern_path(extra={"Theta_Tilt": 6.0})
    pattern = AntennaPattern(path, validate=False)
    assert pattern.raw_data["Theta_Electrical_Tilt"] == 6.0
    assert "Theta_Tilt" not in pattern.raw_data
