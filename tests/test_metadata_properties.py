"""Tests for ``AntennaPattern`` metadata properties.

Scope is deliberately narrow: the properties that contain *logic* — unit
conversion — plus the required/optional key split. Properties that are a bare
``str(self.raw_data[key])`` pass-through are not individually tested; there is
nothing to break in them short of a typo in the key name, and the parser cannot
construct without the required keys anyway.

These pin behaviour ahead of the planned god-class decomposition.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from eas_3d_pattern import AntennaPattern


def load(pattern_path, **extra) -> AntennaPattern:
    """Build a synthetic pattern with ``extra`` metadata merged in, and load it."""
    return AntennaPattern(pattern_path(extra=extra), validate=False)


class TestFrequencyConversion:
    """``frequency_hz`` normalizes any declared unit to Hz."""

    @pytest.mark.parametrize(
        ("value", "unit", "expected_hz"),
        [
            (2_100_000_000.0, "Hz", 2_100_000_000.0),
            (2_100_000.0, "kHz", 2_100_000_000.0),
            (2100.0, "MHz", 2_100_000_000.0),
            (2.1, "GHz", 2_100_000_000.0),
            (0.0021, "THz", 2_100_000_000.0),
        ],
    )
    def test_units_normalize_to_hz(self, pattern_path, value, unit, expected_hz):
        pattern = load(pattern_path, Frequency={"value": value, "unit": unit})
        assert pattern.frequency_hz == pytest.approx(expected_hz)

    def test_unknown_unit_passes_value_through(self, pattern_path):
        """An unrecognized unit is returned unscaled rather than raising."""
        pattern = load(pattern_path, Frequency={"value": 42.0, "unit": "furlongs"})
        assert pattern.frequency_hz == pytest.approx(42.0)


class TestFrequencyRange:
    """``frequency_range`` converts both bounds, or returns None when absent."""

    def test_absent_returns_none(self, pattern_path):
        pattern = load(pattern_path)
        assert pattern.frequency_range is None

    def test_bounds_are_converted(self, pattern_path):
        pattern = load(
            pattern_path,
            Frequency_Range={"lower": 1.8, "upper": 2.2, "unit": "GHz"},
        )
        assert pattern.frequency_range == pytest.approx([1.8e9, 2.2e9])


class TestGainConversion:
    """``gain_dbi`` converts dBd to dBi; dBi passes through."""

    @pytest.mark.parametrize(
        ("value", "unit", "expected"),
        [
            (15.0, "dBi", 15.0),
            (15.0, "dBd", 17.15),
        ],
    )
    def test_units(self, pattern_path, value, unit, expected):
        pattern = load(pattern_path, Gain={"value": value, "unit": unit})
        assert pattern.gain_dbi == pytest.approx(expected)


class TestEirpConversion:
    """``eirp_dbm`` normalizes power units to dBm."""

    @pytest.mark.parametrize(
        ("value", "unit", "expected_dbm"),
        [
            (43.0, "dBm", 43.0),
            (13.0, "dBW", 43.0),
            (1000.0, "mW", 30.0),
            (1.0, "W", 30.0),
        ],
    )
    def test_units(self, pattern_path, value, unit, expected_dbm):
        pattern = load(pattern_path, EIRP={"value": value, "unit": unit})
        assert pattern.eirp_dbm == pytest.approx(expected_dbm)

    def test_absent_returns_none(self, pattern_path):
        pattern = load(pattern_path)
        assert pattern.eirp_dbm is None


class TestOutputPowerConversion:
    """``output_power_watt`` normalizes power units to watts."""

    @pytest.mark.parametrize(
        ("value", "unit", "expected_watt"),
        [
            (40.0, "W", 40.0),
            (40_000.0, "mW", 40.0),
            (10.0, "dBW", 10.0),
            (40.0, "dBm", 10.0),
        ],
    )
    def test_units(self, pattern_path, value, unit, expected_watt):
        pattern = load(
            pattern_path, Configured_Output_Power={"value": value, "unit": unit}
        )
        assert pattern.output_power_watt == pytest.approx(expected_watt)

    def test_absent_returns_none(self, pattern_path):
        pattern = load(pattern_path)
        assert pattern.output_power_watt is None


class TestElectricalPanAndTilt:
    """The two properties renamed from the ``eletrical`` misspelling.

    Guards the 2026-08-31 rename: these names are the public contract now, and
    the old misspelled ones must be gone.
    """

    def test_values_are_read(self, pattern_path):
        pattern = load(pattern_path, Phi_Electrical_Pan=12.5, Theta_Electrical_Tilt=6.0)
        assert pattern.phi_electrical_pan == pytest.approx(12.5)
        assert pattern.theta_electrical_tilt == pytest.approx(6.0)

    def test_absent_returns_none(self, pattern_path):
        pattern = load(pattern_path)
        assert pattern.phi_electrical_pan is None
        assert pattern.theta_electrical_tilt is None

    def test_misspelled_names_are_gone(self, pattern_path):
        """The pre-rename names must not linger as aliases."""
        pattern = load(pattern_path)
        assert not hasattr(pattern, "phi_eletrical_pan")
        assert not hasattr(pattern, "theta_eletrical_tilt")


class TestOptionalMetadata:
    """Optional string metadata returns None rather than raising when absent."""

    @pytest.mark.parametrize(
        "prop",
        [
            "pattern_name",
            "beam_id",
            "configuration",
            "rf_port",
            "array_id",
            "array_position",
        ],
    )
    def test_absent_returns_none(self, pattern_path, prop):
        pattern = load(pattern_path)
        assert getattr(pattern, prop) is None

    def test_present_value_is_returned(self, pattern_path):
        pattern = load(pattern_path, Beam_ID="B12", RF_Port="RFp01")
        assert pattern.beam_id == "B12"
        assert pattern.rf_port == "RFp01"


class TestRequiredMetadata:
    """Required keys raise when missing — they are not silently defaulted."""

    def test_missing_required_key_raises(self, pattern_path):
        pattern = load(pattern_path)
        with pytest.raises(KeyError):
            _ = pattern.supplier

    def test_present_required_key_is_returned(self, pattern_path):
        pattern = load(pattern_path, Supplier="VENDOR")
        assert pattern.supplier == "VENDOR"


class TestPassThroughMetadata:
    """Verbatim string/scalar pass-throughs return exactly what is in the JSON.

    These accessors were moved to ``eas_3d_pattern.ngmn.Metadata`` in the Phase 2a
    decomposition. Several were previously only *executed* via ``__str__`` without
    their return value being asserted, and two (``BASTA_AA_WP_version``,
    ``coordinate_system``) had no coverage at all. This pins the value contract so
    a wrong JSON key or a botched future move is caught.
    """

    # (property name, JSON key, stored value)
    STRING_PASS_THROUGHS: ClassVar = [
        ("BASTA_AA_WP_version", "BASTA_AA_WP_version", "WP3.0"),
        ("supplier", "Supplier", "VENDOR"),
        ("antenna_model", "Antenna_Model", "ANTMODEL1"),
        ("antenna_type", "Antenna_Type", "Massive MIMO"),
        ("revision_version", "Revision_Version", "R2"),
        ("released_date", "Released_Date", "2026-01-01"),
        ("coordinate_system", "Coordinate_System", "SPCS_Ericsson"),
        ("pattern_type", "Pattern_Type", "3D"),
        ("nominal_polarization", "Nominal_Polarization", "+45/-45"),
        ("optional_comments", "Optional_Comments", "sample comment"),
    ]

    @pytest.mark.parametrize(
        ("prop", "key", "value"),
        STRING_PASS_THROUGHS,
        ids=[row[0] for row in STRING_PASS_THROUGHS],
    )
    def test_string_pass_through_returns_stored_value(
        self, pattern_path, prop, key, value
    ):
        pattern = load(pattern_path, **{key: value})
        assert getattr(pattern, prop) == value

    # (property name, JSON key, stored value, expected float)
    SCALAR_PASS_THROUGHS: ClassVar = [
        ("phi_hpbw", "Phi_HPBW", 65.0, 65.0),
        ("theta_hpbw", "Theta_HPBW", 7.0, 7.0),
        ("front_to_back", "Front_to_Back", 30.0, 30.0),
    ]

    @pytest.mark.parametrize(
        ("prop", "key", "value", "expected"),
        SCALAR_PASS_THROUGHS,
        ids=[row[0] for row in SCALAR_PASS_THROUGHS],
    )
    def test_scalar_pass_through_is_float(
        self, pattern_path, prop, key, value, expected
    ):
        pattern = load(pattern_path, **{key: value})
        result = getattr(pattern, prop)
        assert isinstance(result, float)
        assert result == pytest.approx(expected)

    def test_optional_string_present_value_is_returned(self, pattern_path):
        pattern = load(
            pattern_path,
            Configuration="cfgA",
            Array_ID="A1",
            Array_Position="top",
        )
        assert pattern.configuration == "cfgA"
        assert pattern.array_id == "A1"
        assert pattern.array_position == "top"
