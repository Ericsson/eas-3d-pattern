# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Solid-angle quadrature weights for integration over the sphere.

Provides the ``dOmega`` weights that turn a plain sum over grid points into a
solid-angle-weighted integral. Shared by the directivity and beam-efficiency
metrics, which is why this lives in its own module rather than beside either.

Split out of ``parser.py`` (Phase 3a of the god-class decomposition, plan
section 2.1.3).
"""

from __future__ import annotations

import numpy as np
import xarray as xr

#: Name of the data variable holding the solid-angle weights on the dataset.
DOMEGA = "dOmega"


def ensure_domega(pattern_3d: xr.Dataset) -> None:
    """Ensure the solid-angle weight ``dOmega`` exists on ``pattern_3d``.

    Computes ``dOmega = sin(theta) * dTheta * dPhi`` and injects it as a data variable,
    which is what turns a plain sum over grid points into a solid-angle-weighted
    integral over the sphere. No-op if it is already present, so the cost is paid once
    per pattern.

    ``np.gradient`` is applied to the coordinate arrays themselves, so it yields the
    local spacing at each point and therefore handles unevenly spaced grids as well as
    regular ones.

    Args:
        pattern_3d (xr.Dataset): Processed pattern dataset, modified in place.

    Note:
        This mutates ``pattern_3d`` in place. The side effect is deliberate and relied
        upon as a cache by the directivity and beam-efficiency metrics.
    """
    if DOMEGA in pattern_3d.data_vars:
        return

    # The transpose operation for 1D vectors has no effect
    weight = np.repeat(
        np.sin(np.deg2rad(pattern_3d.Theta.values)).T[:, None],
        len(pattern_3d.Phi),
        axis=1,
    )
    dTheta = np.abs(np.gradient(np.deg2rad(pattern_3d["Theta"]))).reshape(-1, 1)
    dPhi = np.abs(np.gradient(np.deg2rad(pattern_3d["Phi"]))).reshape(1, -1)
    pattern_3d[DOMEGA] = xr.DataArray(
        weight * (dTheta * dPhi),
        dims=("Theta", "Phi"),
        coords={"Theta": pattern_3d.Theta, "Phi": pattern_3d.Phi},
        name=DOMEGA,
    )
