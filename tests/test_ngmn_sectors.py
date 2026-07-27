"""Tests for NGMN BASTA V13 Type A sector preset.

Validates the sector boundaries, constraint checks, integration with
AntennaPattern.calculate_beam_efficiency(), and the sector_preset property.

Reference: NGMN BASTA V13.0, Section 7.2.4, Table 7-1, Type A.
"""

from __future__ import annotations

import pytest

from eas_3d_pattern import AntennaPattern, SectorDefinition


class TestNgmnTypeABoundaries:
    """Verify computed sector boundaries match Table 7-1 formulas."""

    def test_boundaries_standard_beam(self, pattern_path):
        """Standard macro beam: peak=96°, HPBW_θ=7°, sector=120°.

        Expected per Table 7-1:
          ϑ₁ = min(90, 96 - 7) = 89°
          ϑ₂ = 96 - 7/2 = 92.5°
          ϑ₃ = 165°
          φ₁ = 0 - 120/2 = -60°
          φ₂ = 0 + 120/2 = 60°
        """
        path = pattern_path(
            peak_theta=96.0,
            peak_phi=0.0,
            extra={
                "Theta_HPBW": 7.0,
                "Phi_HPBW": 65.0,
            },
        )
        _ = AntennaPattern(path, validate=False)  # ensure pattern is loadable
        sectors = SectorDefinition.from_preset(
            "ngmn-v13-type-a",
            theta_beam_peak=96.0,
            theta_hpbw=7.0,
            phi_nominal_direction=0.0,
            nominal_sector_phi=120.0,
        )

        service = sectors.sectors["Service"]
        assert service.theta_min[0] == pytest.approx(92.5)
        assert service.theta_max[0] == pytest.approx(165.0)
        assert service.phi_min[0] == pytest.approx(-60.0)
        assert service.phi_max[0] == pytest.approx(60.0)

        upper = sectors.sectors["Upper"]
        assert upper.theta_min[0] == pytest.approx(0.0)
        assert upper.theta_max[0] == pytest.approx(89.0)

        lower = sectors.sectors["Lower"]
        assert lower.theta_min[0] == pytest.approx(165.0)
        assert lower.theta_max[0] == pytest.approx(180.0)

    def test_theta1_capped_at_90(self, pattern_path):
        """When peak - HPBW > 90, ϑ₁ = min(90, peak - HPBW) = 90."""
        sectors = SectorDefinition.from_preset(
            "ngmn-v13-type-a",
            theta_beam_peak=100.0,
            theta_hpbw=7.0,
            phi_nominal_direction=0.0,
            nominal_sector_phi=120.0,
        )
        upper = sectors.sectors["Upper"]
        assert upper.theta_max[0] == pytest.approx(90.0)

    def test_phi_offset_shifts_service(self):
        """Non-zero phi_nominal_direction shifts φ₁ and φ₂."""
        sectors = SectorDefinition.from_preset(
            "ngmn-v13-type-a",
            theta_beam_peak=96.0,
            theta_hpbw=7.0,
            phi_nominal_direction=-30.0,
            nominal_sector_phi=120.0,
        )
        service = sectors.sectors["Service"]
        assert service.phi_min[0] == pytest.approx(-90.0)
        assert service.phi_max[0] == pytest.approx(30.0)


class TestNgmnTypeAConstraints:
    """NGMN Type A applicability constraints must be enforced."""

    def test_theta_hpbw_below_minimum_raises(self):
        """HPBW_θ < 0.5° is outside Type A applicability."""
        with pytest.raises(ValueError, match="HPBW"):
            SectorDefinition.from_preset(
                "ngmn-v13-type-a",
                theta_beam_peak=96.0,
                theta_hpbw=0.3,
                phi_nominal_direction=0.0,
                nominal_sector_phi=120.0,
            )

    def test_theta_hpbw_above_maximum_raises(self):
        """HPBW_θ > 25° is outside Type A applicability."""
        with pytest.raises(ValueError, match="HPBW"):
            SectorDefinition.from_preset(
                "ngmn-v13-type-a",
                theta_beam_peak=96.0,
                theta_hpbw=30.0,
                phi_nominal_direction=0.0,
                nominal_sector_phi=120.0,
            )

    def test_sector_phi_below_minimum_raises(self):
        """NominalSector_φ < 50° is outside Type A applicability."""
        with pytest.raises(ValueError, match="[Ss]ector"):
            SectorDefinition.from_preset(
                "ngmn-v13-type-a",
                theta_beam_peak=96.0,
                theta_hpbw=7.0,
                phi_nominal_direction=0.0,
                nominal_sector_phi=40.0,
            )

    def test_sector_phi_above_maximum_raises(self):
        """NominalSector_φ > 130° is outside Type A applicability."""
        with pytest.raises(ValueError, match="[Ss]ector"):
            SectorDefinition.from_preset(
                "ngmn-v13-type-a",
                theta_beam_peak=96.0,
                theta_hpbw=7.0,
                phi_nominal_direction=0.0,
                nominal_sector_phi=140.0,
            )


class TestNgmnTypeAPartition:
    """All sectors together must partition the full sphere."""

    def test_sectors_sum_to_unity(self, pattern_path):
        """Sum of all sector efficiencies must be ~1.0."""
        path = pattern_path(peak_theta=96.0, peak_phi=0.0)
        pattern = AntennaPattern(path, validate=False)
        sectors = SectorDefinition.from_preset(
            "ngmn-v13-type-a",
            theta_beam_peak=96.0,
            theta_hpbw=7.0,
            phi_nominal_direction=0.0,
            nominal_sector_phi=120.0,
        )
        eff = pattern.calculate_beam_efficiency(sector_definitions=sectors)
        total = sum(eff.values())
        assert total == pytest.approx(1.0, abs=0.02)


class TestSectorPresetProperty:
    """The sector_preset property on AntennaPattern."""

    def test_default_preset_is_eas(self, pattern_path):
        """New patterns default to 'eas' preset."""
        path = pattern_path()
        pattern = AntennaPattern(path, validate=False)
        assert pattern.sector_preset == "eas"

    def test_set_preset_to_ngmn(self, pattern_path):
        """Setting preset to ngmn-v13-type-a is accepted."""
        path = pattern_path()
        pattern = AntennaPattern(path, validate=False)
        pattern.sector_preset = "ngmn-v13-type-a"
        assert pattern.sector_preset == "ngmn-v13-type-a"

    def test_set_invalid_preset_raises(self, pattern_path):
        """Setting an unknown preset name raises ValueError."""
        path = pattern_path()
        pattern = AntennaPattern(path, validate=False)
        with pytest.raises(ValueError, match="[Pp]reset"):
            pattern.sector_preset = "nonexistent"

    def test_available_presets_returns_list(self, pattern_path):
        """available_sector_presets() returns a list containing known names."""
        presets = AntennaPattern.available_sector_presets()
        assert "eas" in presets
        assert "ngmn-v13-type-a" in presets

    def test_ngmn_preset_used_by_calculate_beam_efficiency(self, pattern_path):
        """When preset is ngmn, calculate_beam_efficiency uses NGMN sectors."""
        path = pattern_path(
            peak_theta=96.0,
            peak_phi=0.0,
            extra={"Theta_HPBW": 7.0, "Phi_HPBW": 65.0},
        )
        pattern = AntennaPattern(path, validate=False)
        pattern.sector_preset = "ngmn-v13-type-a"
        eff = pattern.calculate_beam_efficiency()
        # NGMN sectors use "Service", not "Cell"
        assert "Service" in eff
        assert "Cell" not in eff

    def test_explicit_sector_definitions_bypasses_preset(self, pattern_path):
        """Passing sector_definitions= ignores the preset entirely."""
        path = pattern_path(peak_theta=96.0, peak_phi=0.0)
        pattern = AntennaPattern(path, validate=False)
        pattern.sector_preset = "ngmn-v13-type-a"
        custom = SectorDefinition(load_default=False)
        custom.add_sector(
            name="MyRegion",
            theta_min=(0.0, "<="),
            theta_max=(180.0, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<="),
        )
        eff = pattern.calculate_beam_efficiency(sector_definitions=custom)
        assert "MyRegion" in eff
        assert "Service" not in eff


class TestPresetRegistry:
    """The from_preset classmethod and preset discovery."""

    def test_from_preset_eas(self, pattern_path):
        """'eas' preset loads the traditional EAS sectors."""
        sectors = SectorDefinition.from_preset("eas", top_border=85.0)
        assert "Cell" in sectors.sectors
        assert "Int1" in sectors.sectors

    def test_from_preset_unknown_raises(self):
        """Unknown preset name raises ValueError."""
        with pytest.raises(ValueError, match="[Pp]reset"):
            SectorDefinition.from_preset("unknown-preset")

    def test_presets_returns_known_names(self):
        """SectorDefinition.presets() returns available preset names."""
        names = SectorDefinition.presets()
        assert "eas" in names
        assert "ngmn-v13-type-a" in names
