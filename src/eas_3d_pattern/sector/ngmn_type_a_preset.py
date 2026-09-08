# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""The NGMN BASTA V13 Type A sector preset."""

from __future__ import annotations

import logging
from typing import Any

from eas_3d_pattern.sector.definitions import Sector
from eas_3d_pattern.sector.presets import SectorPreset

logger = logging.getLogger(__name__)

NGMN_TYPE_A_THETA_HPBW_MIN: float = 0.5
NGMN_TYPE_A_THETA_HPBW_MAX: float = 25.0
NGMN_TYPE_A_SECTOR_PHI_MIN: float = 50.0
NGMN_TYPE_A_SECTOR_PHI_MAX: float = 130.0
NGMN_TYPE_A_THETA3: float = 165.0
NGMN_TYPE_A_THETA4: float = 180.0


class NgmnTypeAPreset(SectorPreset):
    """NGMN BASTA V13.0 Type A (Macro BS Beam) sector layout."""

    name = "ngmn-v13-type-a"

    def load(
        self,
        theta_beam_peak: float,
        theta_hpbw: float,
        phi_nominal_direction: float = 0.0,
        nominal_sector_phi: float = 120.0,
        **_kwargs: Any,
    ) -> Sector:
        """Build the NGMN BASTA V13 Type A sector layout.

        Computes AR boundaries per NGMN BASTA V13.0, Section 7.2.4, Table 7-1,
        Type A: Macro BS Beam.

        The Interference AR (non-rectangular) is decomposed into 3 rectangular
        sub-regions: left, right, and upper strips around the Service AR.

        Args:
            theta_beam_peak (float): Beam peak theta in degrees (internal coord system).
            theta_hpbw (float): Elevation half-power beamwidth in degrees.
            phi_nominal_direction (float): Nominal azimuth direction in degrees. Defaults to 0.
            nominal_sector_phi (float): Nominal sector width in degrees. Defaults to 120.
            **_kwargs: Unused, absorbed for the preset interface.

        Returns:
            Sector: Six sectors: Service, Interference_Left, Interference_Right,
            Interference_Upper, Upper, Lower.

        Raises:
            ValueError: If parameters fall outside NGMN Type A applicability constraints.
        """
        if not (NGMN_TYPE_A_THETA_HPBW_MIN <= theta_hpbw <= NGMN_TYPE_A_THETA_HPBW_MAX):
            raise ValueError(
                f"SectorDefinition: NGMN Type A requires HPBW_θ in "
                f"[{NGMN_TYPE_A_THETA_HPBW_MIN}°, {NGMN_TYPE_A_THETA_HPBW_MAX}°], "
                f"got {theta_hpbw}°."
            )
        if not (
            NGMN_TYPE_A_SECTOR_PHI_MIN <= nominal_sector_phi <= NGMN_TYPE_A_SECTOR_PHI_MAX
        ):
            raise ValueError(
                f"SectorDefinition: NGMN Type A requires NominalSector_φ in "
                f"[{NGMN_TYPE_A_SECTOR_PHI_MIN}°, {NGMN_TYPE_A_SECTOR_PHI_MAX}°], "
                f"got {nominal_sector_phi}°."
            )

        # Table 7-1 boundary formulas
        theta_1 = min(90.0, theta_beam_peak - theta_hpbw)
        theta_2 = theta_beam_peak - theta_hpbw / 2.0
        theta_3 = NGMN_TYPE_A_THETA3
        theta_4 = NGMN_TYPE_A_THETA4
        phi_1 = phi_nominal_direction - nominal_sector_phi / 2.0
        phi_2 = phi_nominal_direction + nominal_sector_phi / 2.0

        sector = Sector()

        # Service AR: [theta_2, theta_3] x [phi_1, phi_2]
        sector.add_sector(
            name="Service",
            theta_min=(theta_2, "<="),
            theta_max=(theta_3, "<="),
            phi_min=(phi_1, "<="),
            phi_max=(phi_2, "<="),
        )

        # Interference AR decomposed into 3 rectangles:
        # Left strip: [theta_1, theta_3] x [-180, phi_1)
        sector.add_sector(
            name="Interference_Left",
            theta_min=(theta_1, "<="),
            theta_max=(theta_3, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(phi_1, "<"),
        )

        # Right strip: [theta_1, theta_3] x (phi_2, 180)
        sector.add_sector(
            name="Interference_Right",
            theta_min=(theta_1, "<="),
            theta_max=(theta_3, "<="),
            phi_min=(phi_2, "<"),
            phi_max=(180.0, "<"),
        )

        # Upper strip: [theta_1, theta_2) x [phi_1, phi_2]
        sector.add_sector(
            name="Interference_Upper",
            theta_min=(theta_1, "<="),
            theta_max=(theta_2, "<"),
            phi_min=(phi_1, "<="),
            phi_max=(phi_2, "<="),
        )

        # Upper AR: [0, theta_1) x [-180, 180)
        sector.add_sector(
            name="Upper",
            theta_min=(0.0, "<="),
            theta_max=(theta_1, "<"),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )

        # Lower AR: (theta_3, 180] x [-180, 180)
        sector.add_sector(
            name="Lower",
            theta_min=(theta_3, "<"),
            theta_max=(theta_4, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )

        logger.debug(
            f"NgmnTypeAPreset: Loaded with ϑ₁={theta_1:.1f}°, "
            f"ϑ₂={theta_2:.1f}°, ϑ₃={theta_3:.1f}°, φ₁={phi_1:.1f}°, φ₂={phi_2:.1f}°."
        )
        return sector
