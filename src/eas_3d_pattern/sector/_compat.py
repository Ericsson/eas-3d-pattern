# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Backward-compatible ``SectorDefinition`` wrapper.

``SectorDefinition`` predates the :class:`~eas_3d_pattern.sector.definitions.Sector`
/ preset split. It is retained so existing code keeps working; new code should use
:class:`Sector` and :func:`eas_3d_pattern.sector.presets.from_preset`.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, cast

from eas_3d_pattern.sector import presets
from eas_3d_pattern.sector.definitions import Sector
from eas_3d_pattern.util_func.guards import verify

logger = logging.getLogger(__name__)


class SectorDefinition(Sector):
    """Deprecated collection of boundary boxes; use :class:`Sector` and presets.

    .. deprecated::
        Use :class:`Sector` for an empty collection and the module-level preset
        helpers in :mod:`eas_3d_pattern.sector.presets`
        (:func:`~eas_3d_pattern.sector.from_preset`,
        :func:`~eas_3d_pattern.sector.preset_names`,
        :func:`~eas_3d_pattern.sector.validate_preset`) instead. This class and its
        preset-access classmethods are retained only for backward compatibility and
        are scheduled for removal.

    Retained for backward compatibility. The preset-access classmethods
    (:meth:`from_preset`, :meth:`validate_preset`, :meth:`presets`) delegate to
    :mod:`eas_3d_pattern.sector.presets`.

    Args:
        load_default (bool, optional): Deprecated. When ``True`` (the current
            default, preserved for backward compatibility), the instance is
            pre-loaded with the EAS preset sectors and ``top_border`` is required.
            Use ``SectorDefinition.from_preset("eas", top_border=...)`` for the
            preset, or ``SectorDefinition(load_default=False)`` for an empty
            instance. Defaults to ``True``.
        top_border (float | None, optional): Deprecated. Upper theta boundary in
            degrees, required when ``load_default`` is ``True``.
    """

    def __init__(
        self, load_default: bool = True, top_border: float | None = None
    ) -> None:
        super().__init__()
        deprecation_warning = "SectorDefinition(load_default=..., top_border=...) is deprecated; use eas_3d_pattern.sector.from_preset('eas', top_border=...) for the EAS preset, or Sector() for an empty collection."
        logger.warning(deprecation_warning)
        warnings.warn(deprecation_warning, FutureWarning, stacklevel=2)
        if load_default:
            verify(top_border is not None,
                   "SectorDefinition: Must specify 'top_border' in degrees when load_default is True.")
            # verify() guarantees top_border is non-None; cast narrows for mypy.
            self.sectors = presets.from_preset("eas", top_border=cast("float", top_border)).sectors

    @classmethod
    def presets(cls) -> list[str]:
        """Return the list of available sector preset names.

        .. deprecated::
            Use :func:`eas_3d_pattern.sector.preset_names` instead.

        Returns:
            list[str]: Names that can be passed to :meth:`from_preset`.
        """
        deprecation_warning = "SectorDefinition.presets is deprecated; use eas_3d_pattern.sector.preset_names for accessing the list of pre-defined sectors."
        logger.warning(deprecation_warning)
        warnings.warn(deprecation_warning, FutureWarning, stacklevel=2)
        return presets.preset_names()

    @classmethod
    def validate_preset(cls, name: str) -> None:
        """Verify that ``name`` is a known preset, raising otherwise.

        .. deprecated::
            Use :func:`eas_3d_pattern.sector.validate_preset` instead.

        Args:
            name (str): Preset identifier to check.

        Raises:
            ValueError: If ``name`` is not a registered preset.
        """
        deprecation_warning = "SectorDefinition.validate_preset is deprecated; use eas_3d_pattern.sector.validate_preset for validating a sector preset."
        logger.warning(deprecation_warning)
        warnings.warn(deprecation_warning, FutureWarning, stacklevel=2)
        presets.validate_preset(name)

    @classmethod
    def from_preset(cls, name: str, **kwargs: Any) -> Sector:
        """Create a :class:`Sector` from a named preset.

        .. deprecated::
            Use :func:`eas_3d_pattern.sector.from_preset` instead.

        Args:
            name (str): Preset identifier (see :meth:`presets`).
            **kwargs: Parameters required by the specific preset.

        Returns:
            Sector: The populated sector collection.

        Raises:
            ValueError: If the preset name is not recognized.
        """
        deprecation_warning = "SectorDefinition.from_preset is deprecated; use eas_3d_pattern.sector.from_preset for loading a sector preset."
        logger.warning(deprecation_warning)
        warnings.warn(deprecation_warning, FutureWarning, stacklevel=2)
        return presets.from_preset(name, **kwargs)
