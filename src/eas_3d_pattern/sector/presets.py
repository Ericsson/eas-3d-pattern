# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Preset registry: the :class:`SectorPreset` base and the lookup helpers.

Each concrete preset lives in its own module (``eas_preset``, ``ngmn_type_a_preset``)
and subclasses :class:`SectorPreset`, implementing :meth:`SectorPreset.load` to
return a populated :class:`~eas_3d_pattern.sector.definitions.Sector`. This module
aggregates them into a name registry and exposes :func:`preset_names` and
:func:`from_preset`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from eas_3d_pattern.sector.definitions import Sector
from eas_3d_pattern.util_func.guards import verify


class SectorPreset(ABC):
    """Base class for a named sector preset.

    A preset knows how to build a specific :class:`Sector` layout from
    pattern-derived parameters. Concrete subclasses declare a ``name`` and
    implement :meth:`load`.
    """

    #: Registry key under which the preset is looked up by :func:`from_preset`.
    name: str

    @abstractmethod
    def load(self, *args: Any, **kwargs: Any) -> Sector:
        """Build and return the sector layout for this preset.

        Args:
            *args: Positional parameters required by the specific preset.
            **kwargs: Keyword parameters required by the specific preset.

        Returns:
            Sector: A populated sector collection.
        """
        raise NotImplementedError


# --- Registry ---
# Populated at import time by the concrete preset modules below. The imports are
# at the bottom to avoid a cycle: the preset modules import this module for the
# base class, so they must be imported after SectorPreset is defined.
_REGISTRY: dict[str, SectorPreset] = {}


def _register(preset: SectorPreset) -> None:
    """Register a preset instance under its ``name``."""
    _REGISTRY[preset.name] = preset


def preset_names() -> list[str]:
    """Return the list of available preset names.

    Returns:
        list[str]: Names that can be passed to :func:`from_preset`.
    """
    return list(_REGISTRY.keys())


def validate_preset(name: str) -> None:
    """Verify that ``name`` is a known preset, raising otherwise.

    Args:
        name (str): Preset identifier to check.

    Raises:
        ValueError: If ``name`` is not registered.
    """
    available = ", ".join(_REGISTRY.keys())
    verify(name in _REGISTRY,
           f"SectorPreset: Unknown preset '{name}'. Available presets: {available}")


def from_preset(name: str, **kwargs: Any) -> Sector:
    """Build a :class:`Sector` from a named preset.

    Args:
        name (str): Preset identifier (see :func:`preset_names`).
        **kwargs: Parameters required by the specific preset.

    Returns:
        Sector: The populated sector collection.

    Raises:
        ValueError: If the preset name is not recognized.
    """
    validate_preset(name)
    return _REGISTRY[name].load(**kwargs)


# Concrete presets self-register on import. Imported here (bottom of module) so
# that ``SectorPreset`` and ``_register`` already exist when they run.
from eas_3d_pattern.sector.eas_preset import EasPreset  # noqa: E402
from eas_3d_pattern.sector.ngmn_type_a_preset import NgmnTypeAPreset  # noqa: E402

_register(EasPreset())
_register(NgmnTypeAPreset())
