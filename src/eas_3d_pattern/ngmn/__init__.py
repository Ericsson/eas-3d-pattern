# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""NGMN BASTA domain package.

Groups code bound to the NGMN BASTA specification. Currently exposes the
read-only :class:`Metadata` accessors; future NGMN concerns (schema handling,
coordinate systems) can be added as sibling modules without further renames.
"""

from __future__ import annotations

from eas_3d_pattern.ngmn.metadata import Metadata

__all__ = ["Metadata"]
