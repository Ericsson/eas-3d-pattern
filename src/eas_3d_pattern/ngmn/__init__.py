# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""NGMN BASTA domain package.

Groups code bound to the NGMN BASTA specification: reading and validating 3drp
JSON files (:mod:`~eas_3d_pattern.ngmn.loader`), the read-only :class:`Metadata`
accessors, and the coordinate-system conversions
(:mod:`~eas_3d_pattern.ngmn.coordinates`).
"""

from __future__ import annotations

from eas_3d_pattern.ngmn.coordinates import (
    DEFAULT_INTERNAL_COORD_SYSTEM,
    EXPECTED_COORDINATE_SYSTEMS,
    to_internal_frame,
)
from eas_3d_pattern.ngmn.loader import (
    load_json_file,
    normalize_keys,
    validate_against_schema,
)
from eas_3d_pattern.ngmn.metadata import Metadata

__all__ = [
    "DEFAULT_INTERNAL_COORD_SYSTEM",
    "EXPECTED_COORDINATE_SYSTEMS",
    "Metadata",
    "load_json_file",
    "normalize_keys",
    "to_internal_frame",
    "validate_against_schema",
]
