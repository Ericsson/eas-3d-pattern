# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""NGMN spherical pattern coordinate systems and conversion to the internal frame.

All calculations in this library run in ``SPCS_Ericsson``, which matches
``SPCS_Polar`` except that phi is defined on [-180, 179]. This module owns the
per-system transforms into that frame and the post-condition checks that reject
out-of-spec input.

Split out of ``parser.py`` (Phase 4a of the god-class decomposition, plan
section 2.1.3).
"""

from __future__ import annotations

import logging

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

#: Coordinate systems named by the NGMN BASTA specification, plus the internal frame.
#: Currently informational only — the transform whitelist is ``_TO_ERICSSON``.
EXPECTED_COORDINATE_SYSTEMS = [
    "SPCS_Polar",
    "SPCS_CW",
    "SPCS_CCW",
    "SPCS_Geo",
    "SPCS_Ericsson",
]

#: The frame every calculation in this library is performed in.
DEFAULT_INTERNAL_COORD_SYSTEM = "SPCS_Ericsson"

#: Valid theta range of the internal frame, in degrees.
THETA_RANGE_DEG = (0, 180)
#: Valid phi range of the internal frame, in degrees.
PHI_RANGE_DEG = (-180, 179)

# Coordinate transforms into the internal SPCS_Ericsson frame.
# Each entry maps (theta, phi) arrays -> (theta, phi) arrays. The phi operator
# (>= vs >) and the leading negation differ per system and are load-bearing:
# CW/Geo negate the wrapped value, so phi=180 maps consistently to -180 across
# all four systems. The dict keys also serve as the whitelist of source systems.
_TO_ERICSSON = {
    "SPCS_Polar": lambda t, p: (t, np.where(p >= 180, p - 360, p)),
    "SPCS_CW": lambda t, p: (t + 90, -np.where(p > 180, p - 360, p)),
    "SPCS_CCW": lambda t, p: (t + 90, np.where(p >= 180, p - 360, p)),
    "SPCS_Geo": lambda t, p: (np.flip(t), -np.where(p > 180, p - 360, p)),
}


def to_internal_frame(
    pattern_3d: xr.Dataset,
    from_system: str,
    to_system: str,
) -> xr.Dataset:
    """Convert the Theta/Phi index of a pattern dataset into the internal frame.

    Args:
        pattern_3d (xr.Dataset): Pattern dataset indexed by Theta and Phi.
        from_system (str): Declared source coordinate system.
        to_system (str): Target system. Only ``SPCS_Ericsson`` is implemented.

    Raises:
        NotImplementedError: If ``to_system`` is not ``SPCS_Ericsson``.
        ValueError: If ``from_system`` is not a supported source system, or if the
            transformed theta/phi fall outside the internal ranges, which means the
            input was out of spec for the declared system.

    Returns:
        xr.Dataset: Dataset re-indexed into the internal frame and sorted by Theta, Phi.

    Note:
        ``SPCS_Ericsson`` uses the same coordinate system as ``SPCS_Polar``, however
        phi is defined between -180 and 179.
    """
    if to_system != DEFAULT_INTERNAL_COORD_SYSTEM:
        logger.error(
            f"Antenna Pattern: Change to coordinate system {to_system} not implemented yet. Use the default ({DEFAULT_INTERNAL_COORD_SYSTEM}) for now."
        )
        raise NotImplementedError(
            f"Antenna Pattern: Change to coordinate system {to_system} not implemented yet. Use the default ({DEFAULT_INTERNAL_COORD_SYSTEM}) for now."
        )
    transformable_systems = tuple(_TO_ERICSSON)
    if from_system not in _TO_ERICSSON:
        logger.error(
            f"AntennaPattern: Unsupported source coordinate system '{from_system}'. Expected one of {transformable_systems}."
        )
        raise ValueError(
            f"AntennaPattern: Unsupported source coordinate system '{from_system}'. Expected one of {transformable_systems}."
        )

    phi = pattern_3d.coords["Phi"].values
    theta = pattern_3d.coords["Theta"].values
    # to_system is guaranteed SPCS_Ericsson by the guard above.
    new_theta, new_phi = _TO_ERICSSON[from_system](theta, phi)
    pattern_3d = pattern_3d.assign_coords(
        Theta=("Theta", new_theta),
        Phi=("Phi", new_phi),
    )

    _reject_out_of_range(pattern_3d, from_system)

    pattern_3d = pattern_3d.assign_attrs(
        coordinate_system=to_system,
    )
    return pattern_3d.sortby(["Theta", "Phi"])


def _reject_out_of_range(pattern_3d: xr.Dataset, from_system: str) -> None:
    """Raise if transformed coordinates left the valid internal ranges.

    Args:
        pattern_3d (xr.Dataset): Dataset already re-indexed into the internal frame.
        from_system (str): Source system, named in the error for diagnosis.

    Raises:
        ValueError: If theta or phi fall outside the internal frame's ranges.
    """
    theta_min, theta_max = THETA_RANGE_DEG
    new_theta = pattern_3d.coords["Theta"].values
    if new_theta.min() < theta_min or new_theta.max() > theta_max:
        logger.error(
            f"AntennaPattern: Transformed theta out of range [{theta_min}, {theta_max}] ([{new_theta.min()}, {new_theta.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
        )
        raise ValueError(
            f"AntennaPattern: Transformed theta out of range [{theta_min}, {theta_max}] ([{new_theta.min()}, {new_theta.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
        )

    phi_min, phi_max = PHI_RANGE_DEG
    new_phi = pattern_3d.coords["Phi"].values
    if new_phi.min() < phi_min or new_phi.max() > phi_max:
        logger.error(
            f"AntennaPattern: Transformed phi out of range [{phi_min}, {phi_max}] ([{new_phi.min()}, {new_phi.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
        )
        raise ValueError(
            f"AntennaPattern: Transformed phi out of range [{phi_min}, {phi_max}] ([{new_phi.min()}, {new_phi.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
        )
