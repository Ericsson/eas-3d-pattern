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
pass-throughs over ``raw_data`` (the normalized NGMN BASTA JSON) with no side
effects and no dependence on the processed ``Pattern_3D`` dataset.

Split out of ``parser.py`` (Phase 2 of the god-class decomposition, plan
section 2.1.3).

``Metadata`` is inherited by ``AntennaPattern`` and is not meant to be
instantiated on its own. The attribute annotation below declares the state the
accessors read so that static type checkers resolve the accesses — it is
supplied at runtime by ``AntennaPattern.__init__``.
"""

from __future__ import annotations

from typing import Any

import numpy as np


class Metadata:
    """Read-only NGMN BASTA metadata accessors over ``raw_data``.

    Provided by the host class at runtime:

    Attributes:
        raw_data (dict[str, Any]): Normalized NGMN BASTA JSON payload.
    """

    raw_data: dict[str, Any]

    @property
    def BASTA_AA_WP_version(self) -> str:
        """BASTA AA working-package version string, verbatim from the source."""
        return str(self.raw_data["BASTA_AA_WP_version"])

    @property
    def supplier(self) -> str:
        """Antenna supplier name."""
        return str(self.raw_data["Supplier"])

    @property
    def antenna_model(self) -> str:
        """Antenna model identifier."""
        return str(self.raw_data["Antenna_Model"])

    @property
    def antenna_type(self) -> str:
        """Antenna type designation."""
        return str(self.raw_data["Antenna_Type"])

    @property
    def revision_version(self) -> str:
        """Data-file revision version."""
        return str(self.raw_data["Revision_Version"])

    @property
    def released_date(self) -> str:
        """Release date of the pattern data."""
        return str(self.raw_data["Released_Date"])

    @property
    def coordinate_system(self) -> str:
        """Declared NGMN coordinate system of the source data."""
        return str(self.raw_data["Coordinate_System"])

    @property
    def pattern_name(self) -> str | None:
        """Optional pattern name, or ``None`` if absent."""
        return self.raw_data.get("Pattern_Name")

    @property
    def beam_id(self) -> str | None:
        """Optional beam identifier, or ``None`` if absent."""
        return self.raw_data.get("Beam_ID")

    @property
    def pattern_type(self) -> str:
        """Pattern type designation."""
        return str(self.raw_data["Pattern_Type"])

    @property
    def frequency_hz(self) -> float:
        """Operating frequency normalized to hertz from any declared unit."""
        freq_dict = self.raw_data["Frequency"]
        val = float(freq_dict.get("value"))
        unit = freq_dict.get("unit", "")
        match unit:
            case "Hz":
                return val
            case "kHz":
                return val * 1e3
            case "MHz":
                return val * 1e6
            case "GHz":
                return val * 1e9
            case "THz":
                return val * 1e12
            case _:
                return val

    @property
    def frequency_range(self) -> list[float] | None:
        """Frequency bounds ``[lower, upper]`` in hertz, or ``None`` if absent."""
        freq_range_dict = self.raw_data.get("Frequency_Range")
        if not freq_range_dict:
            return None
        freq_range_list = [
            float(freq_range_dict.get("lower")),
            float(freq_range_dict.get("upper")),
        ]
        unit = freq_range_dict.get("unit", "")
        match unit:
            case "Hz":
                return freq_range_list
            case "kHz":
                return [v * 1e3 for v in freq_range_list]
            case "MHz":
                return [v * 1e6 for v in freq_range_list]
            case "GHz":
                return [v * 1e9 for v in freq_range_list]
            case "THz":
                return [v * 1e12 for v in freq_range_list]
            case _:
                return freq_range_list

    @property
    def eirp_dbm(self) -> float | None:
        """EIRP normalized to dBm from any declared power unit, or ``None``."""
        EIRP_dict = self.raw_data.get("EIRP")
        if not EIRP_dict:
            return None
        val = float(EIRP_dict.get("value"))
        unit = EIRP_dict.get("unit", "")
        match unit:
            case "mW":
                return float(10 * np.log10(val))
            case "W":
                return float(10 * np.log10(val * 1000))
            case "dBW":
                return float(val + 30)
            case "dBm":
                return val
            case _:
                return val

    @property
    def output_power_watt(self) -> float | None:
        """Configured output power normalized to watts, or ``None`` if absent."""
        configured_output_power = self.raw_data.get("Configured_Output_Power")
        if not configured_output_power:
            return None
        val = float(configured_output_power.get("value"))
        unit = configured_output_power.get("unit", "")
        match unit:
            case "mW":
                return val / 1000.0
            case "W":
                return val
            case "dBW":
                return float(np.pow(10, val / 10.0))
            case "dBm":
                return float(np.pow(10, val / 10.0) / 1000.0)
            case _:
                return val

    @property
    def gain_dbi(self) -> float | None:
        """Antenna gain in dBi (dBd converted with +2.15), or ``None`` if absent."""
        gain_dict = self.raw_data.get("Gain")
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
        return self.raw_data.get("Configuration")

    @property
    def rf_port(self) -> str | None:
        """Optional RF port identifier, or ``None`` if absent."""
        return self.raw_data.get("RF_Port")

    @property
    def array_id(self) -> str | None:
        """Optional array identifier, or ``None`` if absent."""
        return self.raw_data.get("Array_ID")

    @property
    def array_position(self) -> str | None:
        """Optional array position label, or ``None`` if absent."""
        return self.raw_data.get("Array_Position")

    @property
    def phi_hpbw(self) -> float:
        """Azimuth (phi) half-power beamwidth in degrees."""
        return float(self.raw_data["Phi_HPBW"])

    @property
    def theta_hpbw(self) -> float:
        """Elevation (theta) half-power beamwidth in degrees."""
        return float(self.raw_data["Theta_HPBW"])

    @property
    def front_to_back(self) -> float:
        """Front-to-back ratio in dB."""
        return float(self.raw_data["Front_to_Back"])

    @property
    def phi_electrical_pan(self) -> float | None:
        """Electrical azimuth pan in degrees, or ``None`` if absent."""
        return self.raw_data.get("Phi_Electrical_Pan")

    @property
    def theta_electrical_tilt(self) -> float | None:
        """Electrical downtilt in degrees, or ``None`` if absent."""
        return self.raw_data.get("Theta_Electrical_Tilt")

    @property
    def nominal_polarization(self) -> str:
        """Nominal polarization designation."""
        return str(self.raw_data["Nominal_Polarization"])

    @property
    def optional_comments(self) -> str:
        """Free-text comments field from the source data."""
        return str(self.raw_data["Optional_Comments"])
