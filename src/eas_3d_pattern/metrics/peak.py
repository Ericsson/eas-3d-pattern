# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Beam peak location and the top 3 dB border.

Pure functions over the processed pattern dataset. Neither reads nor mutates
``AntennaPattern`` state: the dataset attributes that ``util_func/report.py``
depends on (``peak_coordinates``, ``top_3db_point``) are published by the
``AntennaPattern`` wrappers, which own that side effect.

``top_3db_border`` takes the peak as an argument rather than locating it itself,
so the caller decides whether locating the peak should also publish it.

Split out of ``parser.py`` (Phase 3b of the god-class decomposition, plan
section 2.1.3).
"""

from __future__ import annotations

import logging

import numpy as np
import xarray as xr

from eas_3d_pattern.util_func.guards import verify

logger = logging.getLogger(__name__)

#: Component holding the total-power pattern in dB.
POWER_COMPONENT = "P_tp_dB"
#: Component holding the co-polar pattern in dB.
COPOLAR_COMPONENT = "P_co_dB"
#: Half-power level relative to the beam peak, in dB.
HALF_POWER_DB = -3.0
#: Grid step assumed when the theta axis has too few points to measure one.
FALLBACK_GRID_STEP_DEG = 1.0


def component_name(power: bool) -> str:
    """Return the dataset component to search for a given ``power`` flag.

    Args:
        power (bool): Whether to use the total-power component instead of co-polar.

    Returns:
        str: Name of the data variable to read.
    """
    return POWER_COMPONENT if power else COPOLAR_COMPONENT


def find_peak(pattern: xr.Dataset, power: bool = False) -> tuple[float, float]:
    """Find the Theta/Phi coordinates of the pattern peak.

    Searches for the maximum value within the pattern data array. If two points
    represent a maximum value, the first one is returned.

    Args:
        pattern (xr.Dataset): Processed pattern dataset.
        power (bool, optional): Whether to search the power component instead of
            the co-polarized one. Defaults to False.

    Raises:
        ValueError: If the component yields no peak coordinate pair, which happens
            when the dataset is not indexed by both Theta and Phi.

    Returns:
        tuple[float, float]: (theta, phi) coordinates of the peak in degrees.
    """
    component = component_name(power)
    logger.debug(f"AntennaPattern: Searching for peak of component {component}")
    peak_tuple = (
        pattern.stack(pt=("Theta", "Phi")).idxmax("pt")[component].values.item()
    )
    verify(isinstance(peak_tuple, tuple),
           "AntennaPattern: Failed to find peak coordinates for the component. Make sure to select a component with data.")
    theta_val_peak, phi_val_peak = peak_tuple
    logger.debug(f"AntennaPattern: Peak coordinates found: {peak_tuple}")
    return theta_val_peak, phi_val_peak


def top_3db_border(
    pattern: xr.Dataset,
    theta_peak: float,
    phi_peak: float,
    power: bool = False,
) -> float:
    """Find the Theta border where the beam falls 3 dB below its peak.

    No interpolation is done; this is a simplistic search for the last point
    reported above -3 dB, advanced by one theta grid step.

    Args:
        pattern (xr.Dataset): Processed pattern dataset.
        theta_peak (float): Theta coordinate of the beam peak, in degrees.
        phi_peak (float): Phi coordinate of the beam peak, in degrees.
        power (bool, optional): Whether to cut the power component instead of the
            co-polarized one. Defaults to False, which complies with the NGMN standard.

    Returns:
        float: Theta border for the top 3 dB point in degrees.
    """
    vertical_cut = pattern.sel(Phi=phi_peak)
    vertical_cut_normed = vertical_cut[component_name(power)]

    # Fallback: if no point at/below -3 dB exists above the peak (e.g. a very
    # narrow beam peaking at the top of the cut), the 3 dB border collapses to
    # the peak theta itself instead of leaving ``top_border`` unbound.
    top_border = float(theta_peak)

    # Advance the border by the actual theta grid step rather than a hardcoded
    # 1 deg, so the result is correct for any sampling resolution.
    theta_axis = np.sort(vertical_cut_normed["Theta"].values)
    if theta_axis.size > 1:
        grid_step = float(np.median(np.diff(theta_axis)))
    else:
        grid_step = FALLBACK_GRID_STEP_DEG

    for theta_val in np.flip(
        vertical_cut_normed.sel(Theta=slice(0, theta_peak))["Theta"]
    ):
        if vertical_cut_normed.sel(Theta=theta_val) <= HALF_POWER_DB:
            top_border = float(theta_val.values) + grid_step
            break
    else:
        logger.warning(
            "AntennaPattern: No -3 dB crossing found above the peak; using peak theta as top 3 dB border."
        )
    return top_border
