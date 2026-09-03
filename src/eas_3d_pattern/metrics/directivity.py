# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Directivity and ohmic-loss metrics.

Pure functions over the processed pattern dataset: data in, number out. Neither
reads nor mutates ``AntennaPattern`` state, beyond the deliberate ``dOmega``
cache injected by :func:`~eas_3d_pattern.metrics.quadrature.ensure_domega`.

Split out of ``parser.py`` (Phase 3a of the god-class decomposition, plan
section 2.1.3).
"""

from __future__ import annotations

import logging

import numpy as np
import xarray as xr

from eas_3d_pattern.metrics.quadrature import DOMEGA, ensure_domega

logger = logging.getLogger(__name__)


def directivity(pattern_3d: xr.Dataset) -> float:
    """Calculate the directivity of the antenna pattern data.

    Directivity is calculated with the average radiation intensity over the whole
    sphere and the maximum radiation intensity. Can only be calculated if data is
    complete (full sphere). Regular grids are advised.

    Args:
        pattern_3d (xr.Dataset): Processed pattern dataset. Gains a ``dOmega``
            data variable as a side effect if it is not already present.

    Returns:
        float: The directivity value in dBi.
    """
    logger.debug("AntennaPattern: Calculating directivity of antenna pattern data.")
    ensure_domega(pattern_3d)
    Umax = float(pattern_3d["P_tp_lin"].max())
    Uavg = float(
        (pattern_3d["P_tp_lin"] * pattern_3d[DOMEGA]).sum(("Theta", "Phi"))
        / (pattern_3d[DOMEGA].sum())
    )
    return float(10 * np.log10(Umax / Uavg))


def losses(pattern_3d: xr.Dataset, gain_dbi: float | None) -> float:
    """Calculate the ohmic losses of the antenna pattern data.

    Antenna losses are the declared header gain minus the calculated directivity.

    Args:
        pattern_3d (xr.Dataset): Processed pattern dataset.
        gain_dbi (float | None): Declared gain in dBi from the pattern metadata.

    Raises:
        ValueError: If no gain is declared in the pattern metadata.

    Returns:
        float: The loss value in dB (gain - directivity).
    """
    logger.debug("AntennaPattern: Calculating losses of antenna pattern data.")
    if gain_dbi is None:
        raise ValueError(
            "AntennaPattern: Loss can only be calculated if 'Gain' is available in the header"
        )
    return float(gain_dbi - directivity(pattern_3d))
