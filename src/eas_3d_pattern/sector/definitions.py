# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Core sector geometry: the boundary region and the collection that groups them.

Defines :class:`BoundaryBox` (a single rectangular region) and :class:`Sector`
(a named collection of boxes). This module is preset-agnostic: it knows nothing
about the EAS or NGMN presets, so the preset modules can depend on it without
creating an import cycle.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Any

from eas_3d_pattern.util_func.guards import verify

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundaryBox:
    """A rectangle in the Theta/Phi plane, in degrees.

    Sets inclusive/exclusive boundaries in Theta/Phi for beam-efficiency
    calculation; ``"<"`` and ``"<="`` strings indicate lt or le operations.

    The box carries no name of its own: it is a pure geometry value object. The
    owning :class:`Sector` names it via its ``sectors`` dict key.

    Attributes:
        theta_min (tuple[float, str]): The minimum theta value and its comparison operator.
        theta_max (tuple[float, str]): The maximum theta value and its comparison operator.
        phi_min (tuple[float, str]): The minimum phi value and its comparison operator.
        phi_max (tuple[float, str]): The maximum phi value and its comparison operator.

    Raises:
        ValueError: If the limits are invalid.
    """

    theta_min: tuple[float, str]
    theta_max: tuple[float, str]
    phi_min: tuple[float, str]
    phi_max: tuple[float, str]

    def __post_init__(self):
        verify(self.theta_min[0] <= self.theta_max[0],
               f"BoundaryBox: theta_min ({self.theta_min[0]}) cannot be greater than theta_max ({self.theta_max[0]}).")
        verify(self.phi_min[0] <= self.phi_max[0],
               f"BoundaryBox: phi_min ({self.phi_min[0]}) cannot be greater than phi_max ({self.phi_max[0]}).")
        verify(
            all(op in ("<", "<=") for op in
                (self.theta_min[1], self.theta_max[1], self.phi_min[1], self.phi_max[1])),
            "BoundaryBox: Invalid bounds specification, only symbols '<' and '<=' are allowed.",
        )

    def __str__(self):
        return f"[{self.theta_min[0]:.1f}{self.theta_min[1]}Theta{self.theta_max[1]}{self.theta_max[0]:.1f}], [{self.phi_min[0]:.1f}{self.phi_min[1]}Phi{self.phi_max[1]}{self.phi_max[0]:.1f}]"


class BoundaryBoxSquare(BoundaryBox):
    """Deprecated alias for :class:`BoundaryBox`.

    .. deprecated::
        The ``"Square"`` suffix was redundant. Use :class:`BoundaryBox` instead.
        Retained for backward compatibility and scheduled for removal.

    Note:
        Instances are ``BoundaryBox`` subclass instances, so
        ``isinstance(x, BoundaryBox)`` holds. Equality is class-sensitive: a
        ``BoundaryBoxSquare`` never compares equal to a plain ``BoundaryBox`` even
        with identical fields.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        deprecation_warning = "BoundaryBoxSquare is deprecated; use eas_3d_pattern.sector.BoundaryBox instead."
        logger.warning(deprecation_warning)
        warnings.warn(deprecation_warning, FutureWarning, stacklevel=2)
        super().__init__(*args, **kwargs)


class Sector:
    """A named collection of :class:`BoundaryBox` regions.

    A freshly constructed instance is empty; regions are added via
    :meth:`add_sector`. Preset builders (see :mod:`eas_3d_pattern.sector.presets`)
    return a populated ``Sector``.

    Currently only rectangular shapes (:class:`BoundaryBox`) are supported.
    """

    def __init__(self) -> None:
        self.sectors: dict[str, BoundaryBox] = {}

    def add_sector(
        self,
        name: str,
        theta_min: tuple[float, str],
        theta_max: tuple[float, str],
        phi_min: tuple[float, str],
        phi_max: tuple[float, str],
    ) -> None:
        """Add a named region to this sector collection.

        Args:
            name (str): The name of the region (used as the dict key).
            theta_min (tuple[float, str]): Minimum theta value and its comparison operator.
            theta_max (tuple[float, str]): Maximum theta value and its comparison operator.
            phi_min (tuple[float, str]): Minimum phi value and its comparison operator.
            phi_max (tuple[float, str]): Maximum phi value and its comparison operator.

        Raises:
            ValueError: If the region name is empty.
        """
        verify(name, "Sector: Sector name cannot be empty.")
        if name in self.sectors:
            logger.warning(
                f"Sector: Sector '{name}' already exists. Overwriting with new definition.")

        logger.info(f"Sector: Creating sector '{name}'.")
        self.sectors[name] = BoundaryBox(theta_min, theta_max, phi_min, phi_max)
        logger.debug(
            f"Sector: Added/Updated sector: '{name}' - {self.sectors[name]}"
        )

    def clear_sectors(self) -> None:
        """Clear all regions from this sector collection."""
        self.sectors = {}
        logger.info("Sector: All sectors cleared.")

    def __str__(self):
        if not self.sectors:
            return "Sector (No sectors defined)"
        output = [f"Sector ({len(self.sectors)} defined Sectors)"]
        for name, sector_box in self.sectors.items():
            output.append(f"'{name}': \t{sector_box}")
        return "\n".join(output)
