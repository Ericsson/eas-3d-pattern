# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Sector geometry and presets.

Public surface:

- :class:`BoundaryBox` — a single rectangular region.
- :class:`BoundaryBoxSquare` — deprecated alias of :class:`BoundaryBox`.
- :class:`Sector` — a named collection of boxes.
- :class:`SectorDefinition` — deprecated compatibility wrapper over :class:`Sector`.
- :func:`from_preset`, :func:`preset_names` — preset registry helpers.
"""

from __future__ import annotations

from eas_3d_pattern.sector._compat import SectorDefinition
from eas_3d_pattern.sector.definitions import (
    BoundaryBox,
    BoundaryBoxSquare,
    Sector,
)
from eas_3d_pattern.sector.presets import (
    SectorPreset,
    from_preset,
    preset_names,
    validate_preset,
)

__all__ = [
    "BoundaryBox",
    "BoundaryBoxSquare",
    "Sector",
    "SectorDefinition",
    "SectorPreset",
    "from_preset",
    "preset_names",
    "validate_preset",
]
