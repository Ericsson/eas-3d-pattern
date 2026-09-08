# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Beam efficiency over sector definitions.

Solid-angle-weighted power fraction falling inside each declared sector. Pure
function over the processed pattern dataset and a
:class:`~eas_3d_pattern.sector.SectorDefinition`.

Preset *dispatch* deliberately stays on ``AntennaPattern``: choosing a preset
requires pattern-derived inputs (the measured 3 dB border, the beam peak) that
are produced by side-effecting methods, and threading those through a pure
function would change which dataset attributes end up published.

Split out of ``parser.py`` (Phase 3c of the god-class decomposition, plan
section 2.1.3).
"""

from __future__ import annotations

import logging
import operator
from collections.abc import Callable
from types import MappingProxyType

import xarray as xr

from eas_3d_pattern.metrics.quadrature import DOMEGA, ensure_domega
from eas_3d_pattern.sector import BoundaryBox, Sector
from eas_3d_pattern.util_func.guards import verify

logger = logging.getLogger(__name__)

#: Component holding the linear total-power pattern.
POWER_COMPONENT_LIN = "P_tp_lin"
#: Component holding the linear co-polar pattern.
COPOLAR_COMPONENT_LIN = "P_co_lin"

#: Comparison operators a sector boundary may declare. Read-only lookup table.
BOUNDARY_OPERATORS: MappingProxyType[str, Callable[[float, float], bool]] = (
    MappingProxyType(
        {
            "<": operator.lt,
            "<=": operator.le,
            ">": operator.gt,
            ">=": operator.ge,
        }
    )
)


def beam_efficiency(
    pattern: xr.Dataset,
    sectors: Sector,
    powersum: bool = True,
) -> dict[str, float]:
    """Calculate the beam efficiency of the antenna pattern data.

    Beam efficiency is the ratio of the solid-angle-weighted power inside each
    sector to the overall weighted power. Calculations are based only on the
    summation method for now.

    Args:
        pattern (xr.Dataset): Processed pattern dataset. Gains a ``dOmega``
            data variable as a side effect if it is not already present.
        sectors (Sector): Sector boundaries to integrate over.
        powersum (bool, optional): If True, efficiency is calculated on total
            power. If False, on the co-polar pattern. Defaults to True.

    Raises:
        ValueError: If the overall power sums to zero, which would make every
            efficiency nan or inf.
        TypeError: If any sector is not a ``BoundaryBox``.

    Returns:
        dict[str, float]: Sector name to efficiency fraction.
    """
    logger.debug("AntennaPattern: Calculating beam efficiency of antenna pattern data.")
    component = POWER_COMPONENT_LIN if powersum else COPOLAR_COMPONENT_LIN
    field_values = pattern[component]

    ensure_domega(pattern)

    weighted_field_values = pattern[DOMEGA] * field_values
    Sp_overall = float(weighted_field_values.sum())
    verify(Sp_overall != 0, "Overall power is zero; cannot compute beam efficiency.")

    efficiency = {}
    for sector_name, box in sectors.sectors.items():
        verify(isinstance(box, BoundaryBox),
               f"Sector Definitions need to be class 'BoundaryBox' but is class {type(box)}.",
               TypeError)
        efficiency[sector_name] = float(
            _sector_sum(weighted_field_values, box) / Sp_overall
        )

    return efficiency


def _sector_sum(
    weighted_field_values: xr.DataArray, box: BoundaryBox
) -> xr.DataArray:
    """Sum the weighted field inside one rectangular sector.

    Args:
        weighted_field_values (xr.DataArray): Field already multiplied by ``dOmega``.
        box (BoundaryBox): Theta/Phi bounds, each paired with the comparison
            operator to apply.

    Returns:
        xr.DataArray: Zero-dimensional array holding the weighted power inside the sector.
    """
    theta = weighted_field_values.Theta
    phi = weighted_field_values.Phi
    return (
        weighted_field_values.where(
            BOUNDARY_OPERATORS[box.theta_min[1]](box.theta_min[0], theta), drop=True
        )
        .where(BOUNDARY_OPERATORS[box.theta_max[1]](theta, box.theta_max[0]), drop=True)
        .where(BOUNDARY_OPERATORS[box.phi_min[1]](box.phi_min[0], phi), drop=True)
        .where(BOUNDARY_OPERATORS[box.phi_max[1]](phi, box.phi_max[0]), drop=True)
        .sum()
    )
