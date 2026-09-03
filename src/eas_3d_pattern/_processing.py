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

.. todo::
    ``_process_pattern_data`` was moved here unchanged and still does five
    separable jobs: branching on the sampling format and assembling the grid,
    deriving field components (dB to linear, complex E-fields, total power from
    Co/Cr), building the dataset and its attributes, dispatching the coordinate
    transform, and reporting grid irregularity. Only the first of those is
    NGMN-format-specific and only the second is antenna mathematics, so this
    module currently straddles the ``ngmn`` / ``metrics`` boundary drawn
    elsewhere in the package. Decomposing it is deliberately deferred: it is the
    least-covered, highest-risk code in the class and warranted its own step.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xarray as xr

from eas_3d_pattern.ngmn.coordinates import (
    DEFAULT_INTERNAL_COORD_SYSTEM,
    to_internal_frame,
)
from eas_3d_pattern.ngmn.metadata import Metadata

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
    """Builds the processed ``Pattern_3D`` dataset from raw NGMN rows."""

    def _process_pattern_data(self) -> xr.Dataset:
        """Process the raw data during __init__.

        Processes the JSON antenna pattern data into the a standardized format to use methods like plotting or beam efficiency calculations.
        """
        if (
            self.is_uniform_sampling
            and self.theta_sampling is not None
            and self.phi_sampling is not None
        ):
            X, Y = np.meshgrid(self.theta_sampling, self.phi_sampling, indexing="ij")
            coords = np.column_stack([X.ravel(order="C"), Y.ravel(order="C")])
            pattern_data = self.raw_pattern_dataframe
            if len(pattern_data) != len(coords):
                logger.error(
                    f"Number of sampling points n={len(coords)} does not equal pattern data m={len(pattern_data)}. Could not construct dataframe."
                )
                raise ValueError(
                    f"Number of sampling points n={len(coords)} does not equal pattern data m={len(pattern_data)}. Could not construct dataframe."
                )
            pattern_data = pd.concat(
                [pd.DataFrame(coords, columns=["Theta", "Phi"]), pattern_data], axis=1
            )
        elif not self.is_uniform_sampling:
            pattern_data = self.raw_pattern_dataframe
        else:
            logger.error("AntennaPattern: No uniform or nonuniform sampling detected.")
            raise ValueError(
                "AntennaPattern: No uniform or nonuniform sampling detected."
            )

        # construct the dataset
        for field_name in COMPONENT_COLUMNS:
            if field_name not in pattern_data.columns:
                pattern_data[field_name] = np.nan
        pattern_data["P_co_dB"] = -pattern_data["MagAttenuationCo"]
        pattern_data["P_cr_dB"] = -pattern_data["MagAttenuationCr"]
        pattern_data["P_co_lin"] = 10 ** (pattern_data["P_co_dB"] / 10)
        pattern_data["P_cr_lin"] = 10 ** (pattern_data["P_cr_dB"] / 10)
        pattern_data["Phase_co_rad"] = np.deg2rad(pattern_data["PhaseCo"])
        pattern_data["Phase_cr_rad"] = np.deg2rad(pattern_data["PhaseCr"])
        if pattern_data["Phase_co_rad"].isna().any():
            pattern_data["Phase_co_rad"] = np.zeros(pattern_data["Phase_co_rad"].shape)
        if pattern_data["Phase_cr_rad"].isna().any():
            pattern_data["Phase_cr_rad"] = np.zeros(pattern_data["Phase_cr_rad"].shape)

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

        # assign index and coordinates
        pattern_data = pattern_data.set_index(["Theta", "Phi"])
        if pattern_data.index.duplicated().any():
            logger.error(
                "AntennaPattern: Duplicate (Theta, Phi) coordinate pairs found."
            )
            raise ValueError(
                "AntennaPattern: Duplicate (Theta, Phi) coordinate pairs found."
            )
        df = pattern_data.to_xarray()
        df = df.assign_attrs(
            gain_dbi=self.gain_dbi,
            phi_hpbw=self.phi_hpbw,
            theta_hpbw=self.theta_hpbw,
            front_to_back=self.front_to_back,
            coordinate_system=self.coordinate_system,
        )

        # coordinate system and grid
        if self.coordinate_system != DEFAULT_INTERNAL_COORD_SYSTEM:
            logger.warning(
                f"AntennaPattern: Coordinate system {self.coordinate_system} not used for calculations. Transforming 'Pattern_3D' attribute to {DEFAULT_INTERNAL_COORD_SYSTEM}."
            )
            df = to_internal_frame(
                df, self.coordinate_system, DEFAULT_INTERNAL_COORD_SYSTEM
            )
        dTheta = np.diff(df["Theta"])
        dPhi = np.diff(df["Phi"])
        if len(np.unique(dTheta)) != 1:
            logger.warning(
                "AntennaPattern: Non-uniform gridded data detected in Theta. Calculations might misbehave."
            )
        if len(np.unique(dPhi)) != 1:
            logger.warning(
                "AntennaPattern: Non-unfirom gridded data detected in Phi. Calculations might misbehave."
            )
        return df
