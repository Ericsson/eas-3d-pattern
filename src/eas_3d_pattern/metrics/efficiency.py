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
from types import MappingProxyType
from typing import Literal

import numpy as np
import xarray as xr

from eas_3d_pattern.metrics.quadrature import DOMEGA, ensure_domega
from eas_3d_pattern.sector import BoundaryBox, Sector
from eas_3d_pattern.util_func.guards import verify

logger = logging.getLogger(__name__)

#: Component holding the linear total-power pattern.
POWER_COMPONENT_LIN = "P_tp_lin"
#: Component holding the linear co-polar pattern.
COPOLAR_COMPONENT_LIN = "P_co_lin"

#: searchsorted side realizing each lower-bound operator. "<=" keeps the bound, "<" drops it.
LOWER_BOUND_SIDE: MappingProxyType[str, Literal["left", "right"]] = MappingProxyType({"<=": "left", "<": "right"})
#: searchsorted side realizing each upper-bound operator. "<=" keeps the bound, "<" drops it.
UPPER_BOUND_SIDE: MappingProxyType[str, Literal["left", "right"]] = MappingProxyType({"<=": "right", "<": "left"})


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
    theta = weighted_field_values.Theta.values
    phi = weighted_field_values.Phi.values
    values = weighted_field_values.values

    verify(bool(np.all(np.diff(theta) > 0) and np.all(np.diff(phi) > 0)),
             "beam_efficiency: Theta and Phi coordinates must be sorted ascending.")

    Sp_overall = float(np.nansum(values))
    verify(Sp_overall != 0, "Overall power is zero; cannot compute beam efficiency.")

    efficiency = {}
    for sector_name, box in sectors.sectors.items():
        verify(isinstance(box, BoundaryBox),
               f"Sector Definitions need to be class 'BoundaryBox' but is class {type(box)}.",
               TypeError)
        efficiency[sector_name] = _sector_sum(values, theta, phi, box) / Sp_overall

    return efficiency


def _sector_sum(
    values: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
    box: BoundaryBox
) -> float:
    """Sum the weighted field inside one rectangular sector.

    The sector is axis-aligned, so its bounds are separable: each one maps to an
    index range on a single sorted coordinate axis, found by binary search. The
    two ranges together address the sector as a contiguous block of ``values``,
    which is summed as a view without building a mask or copying the data.

    Each bound carries the comparison operator that decides whether the boundary
    coordinate itself belongs to the sector. That choice is expressed as the
    ``side`` argument of :func:`numpy.searchsorted` via :data:`LOWER_BOUND_SIDE`
    and :data:`UPPER_BOUND_SIDE`; an inverted ``side`` silently shifts a sector
    edge by one grid step rather than raising.

    NaN cells are skipped, matching the overall sum in :func:`beam_efficiency`.
    They arise from components the source file never declared and from incomplete
    grids.

    Args:
        values (np.ndarray): The dOmega-weighted field as a 2D array indexed
            ``[theta, phi]``.
        theta (np.ndarray): Theta coordinates in degrees, sorted ascending. The
            caller guarantees the ordering; it is not re-checked here.
        phi (np.ndarray): Phi coordinates in degrees, sorted ascending. The caller
            guarantees the ordering; it is not re-checked here.
        box (BoundaryBox): Theta/Phi bounds, each paired with the comparison
            operator to apply.

    Returns:
        float: Weighted power inside the sector.
    """
    theta_start = int(np.searchsorted(theta, box.theta_min[0], side=LOWER_BOUND_SIDE[box.theta_min[1]]))
    theta_stop = int(np.searchsorted(theta, box.theta_max[0], side=UPPER_BOUND_SIDE[box.theta_max[1]]))
    phi_start = int(np.searchsorted(phi, box.phi_min[0], side=LOWER_BOUND_SIDE[box.phi_min[1]]))
    phi_stop = int(np.searchsorted(phi, box.phi_max[0], side=UPPER_BOUND_SIDE[box.phi_max[1]]))
    return float(np.nansum(values[theta_start:theta_stop, phi_start:phi_stop]))
