# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""NGMN BASTA metadata accessors for antenna pattern data.

This module holds the read-only NGMN BASTA metadata properties. They are pure
pass-throughs over ``data`` (the normalized NGMN BASTA JSON) with no side
effects and no dependence on the processed ``pattern`` dataset.

Split out of ``parser.py`` (Phase 2 of the god-class decomposition, plan
section 2.1.3).

``Metadata`` is inherited by ``AntennaPattern`` and is not meant to be
instantiated on its own. The attribute annotation below declares the state the
accessors read so that static type checkers resolve the accesses — it is
supplied at runtime by ``AntennaPattern.__init__``.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Small offset added to the inclusive stop of an NGMN [start, step, stop] sampling
# triple so ``np.arange`` includes the final grid point despite float rounding.
_SAMPLING_STOP_EPSILON = 1e-6

#: Multiplier from each NGMN frequency unit to hertz. An unknown unit maps to 1.0
#: (value returned unscaled), matching the original fall-through behaviour.
_HZ_MULTIPLIER: dict[str, float] = {
    "Hz": 1.0,
    "kHz": 1e3,
    "MHz": 1e6,
    "GHz": 1e9,
    "THz": 1e12,
}


def _to_hz(value: float, unit: str) -> float:
    """Scale a frequency value to hertz by its declared unit.

    Args:
        value (float): Frequency magnitude in ``unit``.
        unit (str): NGMN frequency unit; an unknown unit leaves ``value`` unscaled.

    Returns:
        float: The frequency in hertz.
    """
    return value * _HZ_MULTIPLIER.get(unit, 1.0)


def _to_dbm(value: float, unit: str) -> float:
    """Convert a power value to dBm by its declared unit.

    Args:
        value (float): Power magnitude in ``unit``.
        unit (str): NGMN power unit; an unknown unit leaves ``value`` unscaled.

    Returns:
        float: The power in dBm.
    """
    match unit:
        case "mW":
            return float(10 * np.log10(value))
        case "W":
            return float(10 * np.log10(value * 1000))
        case "dBW":
            return value + 30
        case "dBm":
            return value
        case _:
            return value


def _to_watt(value: float, unit: str) -> float:
    """Convert a power value to watts by its declared unit.

    Args:
        value (float): Power magnitude in ``unit``.
        unit (str): NGMN power unit; an unknown unit leaves ``value`` unscaled.

    Returns:
        float: The power in watts.
    """
    match unit:
        case "mW":
            return value / 1000.0
        case "W":
            return value
        case "dBW":
            return float(np.pow(10, value / 10.0))
        case "dBm":
            return float(np.pow(10, value / 10.0) / 1000.0)
        case _:
            return value


class Metadata:
    """Read-only NGMN BASTA metadata accessors over ``data``.

    Provided by the host class at runtime:

    Attributes:
        data (dict[str, Any]): Normalized NGMN BASTA JSON payload.
    """

    data: dict[str, Any]

    @property
    def raw_data(self) -> dict[str, Any]:
        """Deprecated alias for :attr:`data`.

        The payload is normalized on load, so ``raw_data`` was a misnomer. Use
        :attr:`data` instead.

        Returns:
            dict[str, Any]: The normalized NGMN BASTA JSON payload (the same
            object as :attr:`data`).

        Warns:
            DeprecationWarning: Always; ``raw_data`` is scheduled for removal.
        """
        deprecation_warning = "AntennaPattern.raw_data is deprecated and will be removed in a future release; use AntennaPattern.data instead."
        logger.warning(deprecation_warning)
        warnings.warn(
            deprecation_warning,
            FutureWarning, # FutureWarning instead of DeprecationWarning has been chosen because of the general expected audence of this library, which is not expected to run test suites. Tehrefore is better to provide a clear and visual deprecation warning masked through a FutureWarning.
            stacklevel=2,
        )
        return self.data

    @property
    def BASTA_AA_WP_version(self) -> str:
        """BASTA AA working-package version string, verbatim from the source.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["BASTA_AA_WP_version"])

    @property
    def supplier(self) -> str:
        """Antenna supplier name.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Supplier"])

    @property
    def antenna_model(self) -> str:
        """Antenna model identifier.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Antenna_Model"])

    @property
    def antenna_type(self) -> str:
        """Antenna type designation.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Antenna_Type"])

    @property
    def revision_version(self) -> str:
        """Data-file revision version.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Revision_Version"])

    @property
    def released_date(self) -> str:
        """Release date of the pattern data.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Released_Date"])

    @property
    def coordinate_system(self) -> str:
        """Declared NGMN coordinate system of the source data.

        Required. Raises ``KeyError`` if absent, since it drives the coordinate
        transform and has no safe default.
        """
        return str(self.data["Coordinate_System"])

    @property
    def pattern_name(self) -> str | None:
        """Optional pattern name, or ``None`` if absent."""
        return self.data.get("Pattern_Name")

    @property
    def beam_id(self) -> str | None:
        """Optional beam identifier, or ``None`` if absent."""
        return self.data.get("Beam_ID")

    @property
    def pattern_type(self) -> str:
        """Pattern type designation.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Pattern_Type"])

    @property
    def frequency_hz(self) -> float:
        """Operating frequency normalized to hertz from any declared unit."""
        freq_dict = self.data["Frequency"]
        return _to_hz(float(freq_dict.get("value")), freq_dict.get("unit", ""))

    @property
    def frequency_range(self) -> list[float] | None:
        """Frequency bounds ``[lower, upper]`` in hertz, or ``None`` if absent."""
        freq_range_dict = self.data.get("Frequency_Range")
        if not freq_range_dict:
            return None
        unit = freq_range_dict.get("unit", "")
        return [
            _to_hz(float(freq_range_dict.get("lower")), unit),
            _to_hz(float(freq_range_dict.get("upper")), unit),
        ]

    @property
    def eirp_dbm(self) -> float | None:
        """EIRP normalized to dBm from any declared power unit, or ``None``."""
        EIRP_dict = self.data.get("EIRP")
        if not EIRP_dict:
            return None
        return _to_dbm(float(EIRP_dict.get("value")), EIRP_dict.get("unit", ""))

    @property
    def output_power_watt(self) -> float | None:
        """Configured output power normalized to watts, or ``None`` if absent."""
        configured_output_power = self.data.get("Configured_Output_Power")
        if not configured_output_power:
            return None
        return _to_watt(
            float(configured_output_power.get("value")),
            configured_output_power.get("unit", ""),
        )

    @property
    def gain_dbi(self) -> float | None:
        """Antenna gain in dBi (dBd converted with +2.15), or ``None`` if absent."""
        gain_dict = self.data.get("Gain")
        if not gain_dict:
            return None
        val = float(gain_dict.get("value"))
        unit = gain_dict.get("unit", "")
        match unit:
            case "dBi":
                return val
            case "dBd":
                return val + 2.15
            case _:
                return val

    @property
    def configuration(self) -> str | None:
        """Optional configuration label, or ``None`` if absent."""
        return self.data.get("Configuration")

    @property
    def rf_port(self) -> str | None:
        """Optional RF port identifier, or ``None`` if absent."""
        return self.data.get("RF_Port")

    @property
    def array_id(self) -> str | None:
        """Optional array identifier, or ``None`` if absent."""
        return self.data.get("Array_ID")

    @property
    def array_position(self) -> str | None:
        """Optional array position label, or ``None`` if absent."""
        return self.data.get("Array_Position")

    @property
    def phi_hpbw(self) -> float:
        """Azimuth (phi) half-power beamwidth in degrees."""
        return float(self.data["Phi_HPBW"])

    @property
    def theta_hpbw(self) -> float:
        """Elevation (theta) half-power beamwidth in degrees."""
        return float(self.data["Theta_HPBW"])

    @property
    def front_to_back(self) -> float:
        """Front-to-back ratio in dB."""
        return float(self.data["Front_to_Back"])

    @property
    def phi_electrical_pan(self) -> float | None:
        """Electrical azimuth pan in degrees, or ``None`` if absent."""
        return self.data.get("Phi_Electrical_Pan")

    @property
    def theta_electrical_tilt(self) -> float | None:
        """Electrical downtilt in degrees, or ``None`` if absent."""
        return self.data.get("Theta_Electrical_Tilt")

    @property
    def nominal_polarization(self) -> str:
        """Nominal polarization designation.

        Required NGMN field. Raises ``KeyError`` if absent.
        """
        return str(self.data["Nominal_Polarization"])

    @property
    def optional_comments(self) -> str | None:
        """Free-text comments field, or ``None`` if absent.

        Not part of the NGMN BASTA schema (an extension field), so it is treated
        as optional rather than required.
        """
        value = self.data.get("Optional_Comments")
        return None if value is None else str(value)

    @property
    def theta_sampling(self) -> np.ndarray | None:
        """Theta grid as a column vector, or ``None`` for non-uniform sampling."""
        theta_sampling_list = self.data.get("Theta_Sampling")
        if not theta_sampling_list:
            return None
        return np.arange(
            theta_sampling_list[0],
            theta_sampling_list[2] + _SAMPLING_STOP_EPSILON,
            theta_sampling_list[1],
        ).reshape(-1, 1)

    @property
    def phi_sampling(self) -> np.ndarray | None:
        """Phi grid as a row vector, or ``None`` for non-uniform sampling."""
        phi_sampling_list = self.data.get("Phi_Sampling")
        if not phi_sampling_list:
            return None
        return np.arange(
            phi_sampling_list[0],
            phi_sampling_list[2] + _SAMPLING_STOP_EPSILON,
            phi_sampling_list[1],
        ).reshape(1, -1)

    @property
    def raw_pattern_dataframe(self) -> pd.DataFrame:
        """Raw ``Data_Set`` as a DataFrame with the declared row-structure columns."""
        return pd.DataFrame(
            self.data["Data_Set"], columns=self.data["Data_Set_Row_Structure"]
        )

    @property
    def is_uniform_sampling(self) -> bool:
        """True when both Theta and Phi sampling triples are present."""
        return bool(
            self.data.get("Theta_Sampling") and self.data.get("Phi_Sampling")
        )

    @property
    def is_nonuniform_sampling(self) -> bool:
        """Negation of :attr:`is_uniform_sampling`.

        .. deprecated::
            Redundant with ``not is_uniform_sampling``; scheduled for removal in a
            future release. Use ``not pattern.is_uniform_sampling`` instead.
        """
        deprecation_warning = "is_nonuniform_sampling is deprecated and will be removed in a future release; use 'not is_uniform_sampling' instead."
        logger.warning(deprecation_warning)
        warnings.warn(
            deprecation_warning,
            FutureWarning,
            stacklevel=2,
        )
        return not self.is_uniform_sampling
