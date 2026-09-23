# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""The traditional EAS sector preset."""

from __future__ import annotations

from typing import Any

from eas_3d_pattern.sector.definitions import Sector
from eas_3d_pattern.sector.presets import SectorPreset

EAS_THETA_WASTED_BORDER: float = 70.0
EAS_THETA_EMF_BORDER: float = 165.0
EAS_THETA_LOWER: float = 180.0
EAS_SECTOR_PHI_HALF: float = 60.0


class EasPreset(SectorPreset):
    """The traditional EAS six-sector layout (Cell, Int1-3, EMF, Wasted)."""

    name = "eas"

    def load(self, top_border: float, **_kwargs: Any) -> Sector:
        """Build the EAS sector layout.

        Args:
            top_border (float): Upper theta boundary in degrees (typically from
                the -3 dB point).
            **_kwargs: Unused, absorbed for the preset interface.

        Returns:
            Sector: The six EAS sectors.
        """
        sector = Sector()
        sector.add_sector(
            name="Cell",
            theta_min=(top_border, "<="),
            theta_max=(EAS_THETA_EMF_BORDER, "<="),
            phi_min=(-EAS_SECTOR_PHI_HALF, "<="),
            phi_max=(EAS_SECTOR_PHI_HALF, "<="),
        )
        sector.add_sector(
            name="Int1",
            theta_min=(top_border, "<="),
            theta_max=(EAS_THETA_EMF_BORDER, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(-EAS_SECTOR_PHI_HALF, "<"),
        )
        sector.add_sector(
            name="Int2",
            theta_min=(top_border, "<="),
            theta_max=(EAS_THETA_EMF_BORDER, "<="),
            phi_min=(EAS_SECTOR_PHI_HALF, "<"),
            phi_max=(180.0, "<"),
        )
        sector.add_sector(
            name="Int3",
            theta_min=(EAS_THETA_WASTED_BORDER, "<="),
            theta_max=(top_border, "<"),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        sector.add_sector(
            name="EMF",
            theta_min=(EAS_THETA_EMF_BORDER, "<"),
            theta_max=(EAS_THETA_LOWER, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        sector.add_sector(
            name="Wasted",
            theta_min=(0.0, "<="),
            theta_max=(EAS_THETA_WASTED_BORDER, "<"),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        return sector
