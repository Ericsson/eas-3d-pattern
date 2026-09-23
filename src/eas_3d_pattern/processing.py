# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Assembly of raw NGMN pattern rows into the processed xarray dataset.

Split out of ``parser.py`` (Phase 4c of the god-class decomposition, plan
section 2.1.3). ``PatternProcessing`` is inherited by ``AntennaPattern`` and is
not meant to be instantiated on its own; it extends
:class:`~eas_3d_pattern.ngmn.metadata.Metadata` because every input it needs is
a metadata accessor.

``_process_pattern_data`` orchestrates the assembly in five steps, each a
focused helper: assembling the sampling grid (``_get_pattern_from_uniform_sampling``
for the uniform branch), deriving field components (``_derive_field_components`` —
dB to linear, complex E-fields, total power from Co/Cr), building the dataset and
its attributes (``_build_dataset``), dispatching the coordinate transform
(``_apply_coordinate_transform``) and reporting grid irregularity
(``_warn_on_irregular_grid``).

.. note::
    Only grid assembly is NGMN-format-specific and only component derivation is
    antenna mathematics, so this module still straddles the ``ngmn`` / ``metrics``
    boundary drawn elsewhere in the package. A cleaner home for those two concerns
    is a possible future move.
"""

from __future__ import annotations

import logging
import warnings
from typing import cast

import numpy as np
import pandas as pd
import xarray as xr

from eas_3d_pattern.ngmn.coordinates import (
    DEFAULT_INTERNAL_COORD_SYSTEM,
    to_internal_frame,
)
from eas_3d_pattern.ngmn.metadata import Metadata
from eas_3d_pattern.util_func.guards import verify

logger = logging.getLogger(__name__)

#: Component columns expected on a 3drp row; absent ones are filled with NaN.
COMPONENT_COLUMNS = [
    "MagAttenuationTP",
    "MagAttenuationCo",
    "MagAttenuationCr",
    "PhaseCo",
    "PhaseCr",
]


class PatternProcessing(Metadata):
    """Builds the processed ``pattern`` dataset from raw NGMN rows."""

    pattern: xr.Dataset

    @property
    def Pattern_3D(self) -> xr.Dataset:
        """Deprecated alias for :attr:`pattern`.

        Renamed to the PEP 8-compliant :attr:`pattern`. Use that instead.

        Returns:
            xr.Dataset: The processed pattern dataset (the same object as
            :attr:`pattern`).

        Warns:
            DeprecationWarning: Always; ``Pattern_3D`` is scheduled for removal.
        """
        deprecation_warning = "AntennaPattern.Pattern_3D is deprecated and will be removed in a future release; use AntennaPattern.pattern instead."
        logger.warning(deprecation_warning)
        warnings.warn(
            deprecation_warning,
            FutureWarning,
            stacklevel=2,
        )
        return self.pattern

    @staticmethod
    def _get_pattern_from_uniform_sampling(
        theta_sampling: np.ndarray | None,
        phi_sampling: np.ndarray | None,
        raw_pattern: pd.DataFrame,
    ) -> pd.DataFrame:
        """Lay uniformly-sampled pattern rows onto their (Theta, Phi) grid.

        Args:
            theta_sampling (np.ndarray | None): Theta grid vector; required for
                uniform sampling.
            phi_sampling (np.ndarray | None): Phi grid vector; required for uniform
                sampling.
            raw_pattern (pd.DataFrame): Raw pattern rows to place onto the grid.

        Returns:
            pd.DataFrame: ``raw_pattern`` with prepended ``Theta`` and ``Phi``
            coordinate columns.

        Raises:
            AssertionError: If a sampling grid is missing (an internal invariant
                that uniform sampling should already guarantee).
            ValueError: If the number of rows does not match the number of grid
                points.
        """
        verify(theta_sampling is not None,
               "Uniform sampling requires theta sampling to be provided",
               AssertionError)
        verify(phi_sampling is not None,
               "Uniform sampling requires phi sampling to be provided",
               AssertionError)
        # verify() has guaranteed both grids are non-None at runtime; cast lets
        # mypy drop the None arm that it cannot narrow through the guard.
        X, Y = np.meshgrid(
            cast("np.ndarray", theta_sampling),
            cast("np.ndarray", phi_sampling),
            indexing="ij",
        )
        coords = np.column_stack([X.ravel(order="C"), Y.ravel(order="C")])
        verify(len(raw_pattern) == len(coords),
               f"Number of sampling points n={len(coords)} does not equal pattern data m={len(raw_pattern)}. Could not construct dataframe.")
        return pd.concat(
            [pd.DataFrame(coords, columns=["Theta", "Phi"]), raw_pattern], axis=1
        )

    @staticmethod
    def _derive_field_components(pattern_data: pd.DataFrame) -> pd.DataFrame:
        """Derive linear/dB powers, complex E-fields and total power on the frame.

        Fills any absent NGMN component column with NaN, converts the Co/Cr
        magnitudes to linear power and complex E-fields, and sets total power
        either from a declared ``MagAttenuationTP`` column or, when that column is
        absent, by reconstructing it from the Co/Cr components.

        Args:
            pattern_data (pd.DataFrame): Frame carrying the raw NGMN component
                columns (a subset of ``COMPONENT_COLUMNS``).

        Returns:
            pd.DataFrame: The same frame with the derived power, phase, E-field and
            total-power columns added.
        """
        # Ensure dataset columns
        missing_components = pd.Index(COMPONENT_COLUMNS).difference(pattern_data.columns)
        pattern_data[missing_components] = np.nan

        pattern_data["P_co_dB"] = -pattern_data["MagAttenuationCo"]
        pattern_data["P_cr_dB"] = -pattern_data["MagAttenuationCr"]
        pattern_data["P_co_lin"] = 10 ** (pattern_data["P_co_dB"] / 10)
        pattern_data["P_cr_lin"] = 10 ** (pattern_data["P_cr_dB"] / 10)
        # Phase is an optional column in the NGMN schema (Data_Set cells are non-null
        # numbers), so an absent phase column is uniformly NaN; fillna(0) sets it to zero
        # phase, collapsing exp(1j*phase) to 1 so the E-field is its real magnitude.
        pattern_data["Phase_co_rad"] = np.deg2rad(pattern_data["PhaseCo"]).fillna(0)
        pattern_data["Phase_cr_rad"] = np.deg2rad(pattern_data["PhaseCr"]).fillna(0)

        pattern_data["E_co_complex"] = np.sqrt(pattern_data["P_co_lin"]) * np.exp(
            1j * pattern_data["Phase_co_rad"]
        )  # complex number
        pattern_data["E_cr_complex"] = np.sqrt(pattern_data["P_cr_lin"]) * np.exp(
            1j * pattern_data["Phase_cr_rad"]
        )  # complex number

        if pattern_data["MagAttenuationTP"].isna().any():
            logger.debug(
                "AntennaPattern: TP component is NaN. Using Co and Cr components instead to construct TP."
            )
            pattern_data["P_tp_lin"] = np.square(
                np.abs(pattern_data["E_co_complex"])
            ) + np.square(np.abs(pattern_data["E_cr_complex"]))
            pattern_data["P_tp_dB"] = 10 * np.log10(pattern_data["P_tp_lin"])
        else:
            pattern_data["P_tp_dB"] = -pattern_data["MagAttenuationTP"]
            pattern_data["P_tp_lin"] = 10 ** (pattern_data["P_tp_dB"] / 10)

        return pattern_data

    def _build_dataset(self, pattern_data: pd.DataFrame) -> xr.Dataset:
        """Convert the indexed frame to an xarray dataset with metadata attributes.

        Args:
            pattern_data (pd.DataFrame): Frame indexed by ``(Theta, Phi)`` carrying
                the derived component columns.

        Returns:
            xr.Dataset: The pattern as a dataset, with scalar antenna metadata
            attached as dataset attributes.
        """
        ds = pattern_data.to_xarray()
        ds = ds.assign_attrs(
            gain_dbi=self.gain_dbi,
            phi_hpbw=self.phi_hpbw,
            theta_hpbw=self.theta_hpbw,
            front_to_back=self.front_to_back,
            coordinate_system=self.coordinate_system,
        )
        return ds

    def _apply_coordinate_transform(self, ds: xr.Dataset) -> xr.Dataset:
        """Transform the dataset into the internal coordinate frame if needed.

        Args:
            ds (xr.Dataset): Pattern dataset in its declared coordinate system.

        Returns:
            xr.Dataset: The dataset in ``DEFAULT_INTERNAL_COORD_SYSTEM``, transformed
            only when the declared system differs.
        """
        if self.coordinate_system != DEFAULT_INTERNAL_COORD_SYSTEM:
            logger.warning(
                f"AntennaPattern: Coordinate system {self.coordinate_system} detected. Transforming to {DEFAULT_INTERNAL_COORD_SYSTEM}."
            )
            ds = to_internal_frame(ds, self.coordinate_system, DEFAULT_INTERNAL_COORD_SYSTEM)
        return ds

    @staticmethod
    def _warn_on_irregular_grid(ds: xr.Dataset) -> None:
        """Warn when the Theta or Phi grid spacing is not uniform.

        Args:
            ds (xr.Dataset): Pattern dataset indexed by ``Theta`` and ``Phi``.
        """
        for axis in ("Theta", "Phi"):
            if len(np.unique(np.diff(ds[axis]))) != 1:
                logger.warning(
                    "AntennaPattern: Non-uniform gridded data detected in %s. Calculations might misbehave.",
                    axis,
                )

    def _process_pattern_data(self) -> xr.Dataset:
        """Process the raw data during __init__.

        Processes the JSON antenna pattern data into a standardized format to use methods like plotting or beam efficiency calculations.
        """
        pattern_data = self.raw_pattern_dataframe if not self.is_uniform_sampling else \
                        self._get_pattern_from_uniform_sampling(self.theta_sampling,
                                                                self.phi_sampling,
                                                                self.raw_pattern_dataframe)

        pattern_data = self._derive_field_components(pattern_data)

        # assign index and coordinates
        pattern_data = pattern_data.set_index(["Theta", "Phi"])
        verify(not pattern_data.index.duplicated().any(),
               "AntennaPattern: Duplicate (Theta, Phi) coordinate pairs found.")

        ds = self._build_dataset(pattern_data)
        ds = self._apply_coordinate_transform(ds)
        self._warn_on_irregular_grid(ds)
        return ds
