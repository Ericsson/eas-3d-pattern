# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Antenna pattern metrics.

Figures of merit derived from the processed pattern dataset — directivity,
ohmic losses, and the shared solid-angle quadrature weights they integrate
against. Implemented as pure functions taking the dataset, so they can be used
and tested without constructing an ``AntennaPattern``.

Not re-exported from the top-level package: ``AntennaPattern`` remains the
supported entry point while the API-naming work (plan section 2.9 / M2-14) is
still open.
"""

from __future__ import annotations

from eas_3d_pattern.metrics.directivity import directivity, losses
from eas_3d_pattern.metrics.efficiency import beam_efficiency
from eas_3d_pattern.metrics.peak import find_peak, top_3db_border
from eas_3d_pattern.metrics.quadrature import DOMEGA, ensure_domega

__all__ = [
    "DOMEGA",
    "beam_efficiency",
    "directivity",
    "ensure_domega",
    "find_peak",
    "losses",
    "top_3db_border",
]
