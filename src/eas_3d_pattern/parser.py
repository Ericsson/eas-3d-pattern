import io
import json
import logging
import operator
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import xarray as xr
from jsonschema import ValidationError, validate

from eas_3d_pattern._plotting import build_heatmap, build_polar_3d
from eas_3d_pattern.ngmn import Metadata
from eas_3d_pattern.schema_manager import NGMNSchema
from eas_3d_pattern.sector_definitions import (
    BoundaryBoxSquare,
    SectorDefinition,
)

logger = logging.getLogger(__name__)

# Define a coordinate system to run calculations easier
EXPECTED_COORDINATE_SYSTEMS = [
    "SPCS_Polar",
    "SPCS_CW",
    "SPCS_CCW",
    "SPCS_Geo",
    "SPCS_Ericsson",
]
DEFAULT_INTERNAL_COORD_SYSTEM = "SPCS_Ericsson"

epsilon = 1e-6

# Maps vendor-specific variant -> canonical key
ALTERNATIVES: dict[str, str] = {
    # "Theta_Tilt" comes from the NGMN whitepaper:
    # https://www.ngmn.org/wp-content/uploads/NGMN_BASTA_Recommendations-for-Base-Station-Antennas_V13.0.pdf
    # "Theta_Electrical_Tilt" comes from the latest JSON Schema:
    # https://www.ngmn.org/schema/basta/NGMN_BASTA_AA_3drp_JSON_Schema_WP3_0_latest.json
    "Theta_Tilt": "Theta_Electrical_Tilt",
}

# Coordinate transforms into the internal SPCS_Ericsson frame.
# Each entry maps (theta, phi) arrays -> (theta, phi) arrays. The phi operator
# (>= vs >) and the leading negation differ per system and are load-bearing:
# CW/Geo negate the wrapped value, so phi=180 maps consistently to -180 across
# all four systems. The dict keys also serve as the whitelist of source systems.
_TO_ERICSSON = {
    "SPCS_Polar": lambda t, p: (t, np.where(p >= 180, p - 360, p)),
    "SPCS_CW": lambda t, p: (t + 90, -np.where(p > 180, p - 360, p)),
    "SPCS_CCW": lambda t, p: (t + 90, np.where(p >= 180, p - 360, p)),
    "SPCS_Geo": lambda t, p: (np.flip(t), -np.where(p > 180, p - 360, p)),
}


class AntennaPattern(Metadata):
    """Antenna pattern class to read, calculate and visualize JSON antenna pattern data.

    Initializes the AntennaPattern object by loading and validating (default False) the antenna pattern data against the NGMN JSON schema.
    The schema is loaded within the schema_manager.py module as a singleton.
    Antenna pattern data is eagerly processed into an xarray dataset for calculation and plotting. The xarray dataset is stored in self.Pattern_3D.
    All calculations and visualizations are then performed on the xarray dataset within self.Pattern_3D.

    Parameters:
        data_filepath (str): Path to the JSON data file containing antenna pattern info.
        validate (bool, optional): Whether to validate the data against the schema. Defaults to False.

    Note:
        Schema validation is resource intensive. Use with caution.
        'print(AntennaPattern)' gives overview information of the JSON loaded.

    Examples:
        >>> from eas_pattern_visualizer.parser import AntennaPattern
        >>> antenna_pattern = AntennaPattern("data/sample_data.json")
        >>> print(antenna_pattern)
        >>> antenna_pattern.calculate_beam_efficiency()
        >>> antenna_pattern.plot()

    Raises:
        FileNotFoundError: If data_filepath does not exist.
    """

    def __init__(self, data_filepath: str, validate: bool = False):
        if not os.path.exists(data_filepath):
            logger.error(f"Data file not found: {data_filepath}")
            raise FileNotFoundError(f"Data file not found: {data_filepath}")
        self.data_filepath: str = data_filepath
        self._schema: dict[str, Any] | None = NGMNSchema.schema_content
        self.raw_data: dict[str, Any] = self._normalize_json(
            self._load_data_from_file(data_filepath)
        )
        if not self.raw_data.get("Data_Set"):
            logger.error(
                f"AntennaPattern: 'Data_Set' is empty or missing in {data_filepath}."
            )
            raise ValueError(
                f"AntennaPattern: 'Data_Set' is empty or missing in {data_filepath}."
            )
        if validate:
            if self._schema is None:
                logger.error(
                    "AntennaPattern: Validation requested but no schema is available."
                )
                raise ValueError(
                    "AntennaPattern: Validation requested but no schema is available."
                )
            self._validate_data_against_schema(self.raw_data, self._schema)

        # ---- Process the pattern data into one normalized format ----
        self._sector_preset: str = "eas"
        self.Pattern_3D: xr.Dataset = self._process_pattern_data()

    def _load_data_from_file(self, filepath: str) -> dict[str, Any]:
        logger.debug(f"AntennaPattern: Loading user data from: {filepath}")
        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in user data file {filepath}: {e}")
            raise ValueError(f"Invalid JSON in user data file {filepath}: {e}") from e
        except OSError as e:
            logger.error(f"Could not read user data file {filepath}: {e}")
            raise OSError(f"Could not read user data file {filepath}: {e}") from e

    def _normalize_json(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize vendor-specific keys to canonical names.

        Some vendors use non-standard key names in their 3drp JSON files.
        This method replaces known variants with the canonical key defined
        in the latest NGMN BASTA JSON schema, using the module-level
        ALTERNATIVES mapping.

        The canonical key is only set if it is not already present in the data,
        preventing accidental overwrites when both keys coexist.

        Example:
            A file using the `NGMN whitepaper
            <https://www.ngmn.org/wp-content/uploads/NGMN_BASTA_Recommendations-for-Base-Station-Antennas_V13.0.pdf>`_ naming::

                {"Theta_Tilt": 6.0, ...}

            Is normalized to the current `JSON schema
            <https://www.ngmn.org/schema/basta/NGMN_BASTA_AA_3drp_JSON_Schema_WP3_0_latest.json>`_ naming::

                {"Theta_Electrical_Tilt": 6.0, ...}

        Args:
            data: Raw dictionary loaded from a JSON antenna pattern file.

        Returns:
            The same dictionary with variant keys replaced by their canonical equivalents.
        """
        for variant, canonical in ALTERNATIVES.items():
            if variant in data and canonical not in data:
                data[canonical] = data.pop(variant)
        return data

    def _validate_data_against_schema(
        self, data_instance: dict[str, Any], schema_instance: dict[str, Any]
    ) -> None:
        logger.debug(
            f"AntennaPattern: Validating user data against schema: '{NGMNSchema.source_message}'..."
        )
        try:
            validate(instance=data_instance, schema=schema_instance)
            logger.debug("AntennaPattern: User data validation successful.")
        except ValidationError as e:
            error_path_str = (
                " -> ".join(map(str, e.path)) if e.path else "document root"
            )
            full_error_message = f"Antenna data validation FAILED for '{self.data_filepath}'.\nSchema source: '{NGMNSchema.source_message}'.\nError at data path: '{error_path_str}'.\nValidation Message: {e.message} (Validator: '{e.validator}')"
            logger.error(full_error_message)
            raise ValidationError(full_error_message) from e

    @property
    def sector_preset(self) -> str:
        """The active sector preset name used by ``calculate_beam_efficiency()``.

        Defaults to ``"eas"``. Set to a different preset name to change the
        sector geometry used when ``sector_definitions`` is not explicitly passed.

        Raises:
            ValueError: If assigned a name not in ``available_sector_presets()``.
        """
        return self._sector_preset

    @sector_preset.setter
    def sector_preset(self, value: str) -> None:
        available = SectorDefinition.presets()
        if value not in available:
            raise ValueError(
                f"AntennaPattern: Unknown preset '{value}'. "
                f"Available presets: {available}"
            )
        self._sector_preset = value

    @classmethod
    def available_sector_presets(cls) -> list[str]:
        """Return the list of available sector preset names.

        Convenience accessor so users can discover presets directly from
        AntennaPattern without importing SectorDefinition separately.

        Returns:
            list[str]: Names that can be passed to ``sector_preset``.

        Example:
            >>> AntennaPattern.available_sector_presets()
            ['eas', 'ngmn-v13-type-a']
        """
        return SectorDefinition.presets()

    @property
    def theta_sampling(self) -> np.ndarray | None:
        theta_sampling_list = self.raw_data.get("Theta_Sampling")
        if not theta_sampling_list:
            return None
        return np.arange(
            theta_sampling_list[0],
            theta_sampling_list[2] + epsilon,
            theta_sampling_list[1],
        ).reshape(-1, 1)

    @property
    def phi_sampling(self) -> np.ndarray | None:
        phi_sampling_list = self.raw_data.get("Phi_Sampling")
        if not phi_sampling_list:
            return None
        return np.arange(
            phi_sampling_list[0], phi_sampling_list[2] + epsilon, phi_sampling_list[1]
        ).reshape(1, -1)

    @property
    def raw_pattern_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            self.raw_data["Data_Set"], columns=self.raw_data["Data_Set_Row_Structure"]
        )

    # ---- properties derived from JSON
    @property
    def is_uniform_sampling(self) -> bool:
        return bool(
            self.raw_data.get("Theta_Sampling") and self.raw_data.get("Phi_Sampling")
        )

    @property
    def is_nonuniform_sampling(self) -> bool:
        return not bool(
            self.raw_data.get("Theta_Sampling") and self.raw_data.get("Phi_Sampling")
        )

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
                logging.error(
                    f"Number of sampling points n={len(coords)} does not equal pattern data m={len(pattern_data)}. Could not construct dataframe."
                )
                raise ValueError(
                    f"Number of sampling points n={len(coords)} does not equal pattern data m={len(pattern_data)}. Could not construct dataframe."
                )
            pattern_data = pd.concat(
                [pd.DataFrame(coords, columns=["Theta", "Phi"]), pattern_data], axis=1
            )
        elif self.is_nonuniform_sampling:
            pattern_data = self.raw_pattern_dataframe
        else:
            logging.error("AntennaPattern: No uniform or nonuniform sampling detected.")
            raise ValueError(
                "AntennaPattern: No uniform or nonuniform sampling detected."
            )

        # construct the dataset
        component_columns = [
            "MagAttenuationTP",
            "MagAttenuationCo",
            "MagAttenuationCr",
            "PhaseCo",
            "PhaseCr",
        ]

        for field_name in component_columns:
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
            df = self._change_coordinate_system(
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

    def _change_coordinate_system(
        self,
        Pattern_3D: xr.Dataset,
        from_system: str,
        to_system: str,
    ) -> xr.Dataset:
        """Change the coordinate system (theta, phi index) of the antenna pattern data.

        Note: SPCS_Ericsson uses the same coordinate system as SPCS_Polar, however phi is defined between -180 and 179.
        """
        if to_system != "SPCS_Ericsson":
            logger.error(
                f"Antenna Pattern: Change to coordinate system {to_system} not implemented yet. Use the default (SPCS_Ericsson) for now."
            )
            raise NotImplementedError(
                f"Antenna Pattern: Change to coordinate system {to_system} not implemented yet. Use the default (SPCS_Ericsson) for now."
            )
        transformable_systems = tuple(_TO_ERICSSON)
        if from_system not in _TO_ERICSSON:
            logger.error(
                f"AntennaPattern: Unsupported source coordinate system '{from_system}'. Expected one of {transformable_systems}."
            )
            raise ValueError(
                f"AntennaPattern: Unsupported source coordinate system '{from_system}'. Expected one of {transformable_systems}."
            )
        phi = Pattern_3D.coords["Phi"].values
        theta = Pattern_3D.coords["Theta"].values
        # to_system is guaranteed SPCS_Ericsson by the guard above.
        new_theta, new_phi = _TO_ERICSSON[from_system](theta, phi)
        Pattern_3D = Pattern_3D.assign_coords(
            Theta=("Theta", new_theta),
            Phi=("Phi", new_phi),
        )
        new_theta = Pattern_3D.coords["Theta"].values
        if new_theta.min() < 0 or new_theta.max() > 180:
            logger.error(
                f"AntennaPattern: Transformed theta out of range [0, 180] ([{new_theta.min()}, {new_theta.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
            )
            raise ValueError(
                f"AntennaPattern: Transformed theta out of range [0, 180] ([{new_theta.min()}, {new_theta.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
            )
        new_phi = Pattern_3D.coords["Phi"].values
        if new_phi.min() < -180 or new_phi.max() > 179:
            logger.error(
                f"AntennaPattern: Transformed phi out of range [-180, 179] ([{new_phi.min()}, {new_phi.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
            )
            raise ValueError(
                f"AntennaPattern: Transformed phi out of range [-180, 179] ([{new_phi.min()}, {new_phi.max()}]) converting from '{from_system}'. Input data is likely out of spec for that system."
            )
        Pattern_3D = Pattern_3D.assign_attrs(
            coordinate_system=to_system,
        )
        return Pattern_3D.sortby(["Theta", "Phi"])

    def get_metadata_dict(self) -> dict[str, Any]:
        """Get meta data dictionary of the antenna pattern data.

        Metadata is everything beside 'Data_Set' and 'Data_Set_Row_Structure' from the JSON file.
        The metadata can be used to enrich pandas dataframes.

        Args:
            None

        Returns:
            dict: A dictionary with key and value pairs from the JSON file.

        Example:
            >>> meta_dict = antenna_pattern.get_metadata_dict()
        """
        metadata = self.raw_data.copy()
        metadata.pop("Data_Set", None)
        metadata.pop("Data_Set_Row_Structure", None)
        return metadata

    def _ensure_domega(self) -> None:
        """Ensure the solid-angle weight ``dOmega`` exists on ``Pattern_3D``.

        Computes ``dOmega = sin(theta) * dTheta * dPhi`` and injects it as a data variable,
        which is what turns a plain sum over grid points into a solid-angle-weighted
        integral over the sphere. No-op if it is already present, so the cost is paid once
        per pattern.

        ``np.gradient`` is applied to the coordinate arrays themselves, so it yields the
        local spacing at each point and therefore handles unevenly spaced grids as well as
        regular ones.

        Note:
            This mutates ``self.Pattern_3D`` in place. The side effect is deliberate and
            relied upon as a cache by ``calculate_directivity()`` and
            ``calculate_beam_efficiency()``.
        """
        if "dOmega" in self.Pattern_3D.data_vars:
            return

        weight = np.repeat(
            np.sin(np.deg2rad(self.Pattern_3D.Theta.values)).T[:, None],
            len(self.Pattern_3D.Phi),
            axis=1,
        )
        dTheta = np.abs(np.gradient(np.deg2rad(self.Pattern_3D["Theta"]))).reshape(
            -1, 1
        )
        dPhi = np.abs(np.gradient(np.deg2rad(self.Pattern_3D["Phi"]))).reshape(1, -1)
        self.Pattern_3D["dOmega"] = xr.DataArray(
            weight * (dTheta * dPhi),
            dims=("Theta", "Phi"),
            coords={"Theta": self.Pattern_3D.Theta, "Phi": self.Pattern_3D.Phi},
            name="dOmega",
        )

    def calculate_directivity(self) -> float:
        """Calculate the directivity of the antenna pattern data.

        Directivity is calculated with the average radiation intensity over the whole sphere and the maximum radiation intensity.
        Can only be calculated if data is complete (full sphere). Regular grids are advised.
        More advanced geometry calculation with something like Delaunay+Voronoi is not supported for now.

        Args:
            None

        Raises:
            None

        Returns:
            float: The directivity value in dBi.

        Example:
            >>> directivity_dbi = antenna_pattern.calculate_directivity()
            >>> losses = gain_dbi - directivity_dbi
        """
        logger.debug("AntennaPattern: Calculating directivity of antenna pattern data.")
        self._ensure_domega()
        Umax = float(self.Pattern_3D["P_tp_lin"].max())
        Uavg = float(
            (self.Pattern_3D["P_tp_lin"] * self.Pattern_3D["dOmega"]).sum(
                ("Theta", "Phi")
            )
            / (self.Pattern_3D["dOmega"].sum())
        )
        directivity_dbi = float(10 * np.log10(Umax / Uavg))
        return directivity_dbi

    def calculate_losses(self) -> float:
        """Calculate the losses of the antenna pattern data.

        Antenna losses are calculated by the gain value within the header and the calculated directivity.

        Args:
            None

        Raises:
            None

        Returns:
            float: The loss value in dB (gain - directivity).

        Example:
            >>> losses = antenna_pattern.calculate_losses()
        """
        logger.debug("AntennaPattern: Calculating losses of antenna pattern data.")
        if self.gain_dbi is None:
            raise ValueError(
                "AntennaPattern: Loss can only be calculated if 'Gain' is available in the header"
            )
        return float(self.gain_dbi - self.calculate_directivity())

    def _build_sectors_from_preset(self) -> SectorDefinition:
        """Build a SectorDefinition from the active preset and pattern metadata.

        Dispatches to the correct preset builder based on ``self._sector_preset``.

        Returns:
            SectorDefinition: Configured sector definition for this pattern.

        Raises:
            ValueError: If required metadata is missing for the selected preset.
        """
        if self._sector_preset == "eas":
            top_border = self.calculate_top_3db_point(power=False)
            return SectorDefinition.from_preset("eas", top_border=top_border)

        if self._sector_preset == "ngmn-v13-type-a":
            theta_peak, _ = self.find_peak_coordinates(power=False)
            theta_hpbw = self.raw_data.get("Theta_HPBW")
            phi_hpbw = self.raw_data.get("Phi_HPBW")
            if theta_hpbw is None or phi_hpbw is None:
                raise ValueError(
                    "AntennaPattern: NGMN Type A preset requires 'Theta_HPBW' and 'Phi_HPBW' in the pattern metadata."
                )
            phi_nominal = self.phi_electrical_pan or 0.0
            return SectorDefinition.from_preset(
                "ngmn-v13-type-a",
                theta_beam_peak=theta_peak,
                theta_hpbw=float(theta_hpbw),
                phi_nominal_direction=phi_nominal,
                nominal_sector_phi=float(phi_hpbw),
            )

        # Fallback for future presets registered externally
        return SectorDefinition.from_preset(self._sector_preset)

    def calculate_beam_efficiency(
        self, sector_definitions: SectorDefinition | None = None, powersum: bool = True
    ) -> dict[str, float]:
        """Calculate the beam efficiency of the antenna pattern data.

        Beam efficiency is calculated as the ratio of the overall powersum to the sectors defined.
        Calculations are based only on the summation method for now.

        Args:
            sector_definitions (SectorDefinition, optional): Defaults to None. If None, the default sector definitions will be used.
            powersum (bool, optional): Defaults to True. If True, beam efficiency is calculated on total power. If False, beam efficiency is calculated on co-polar pattern.

        Raises:
            TypeError: If sectors definitions are no BoundaryBoxSquare objects

        Returns:
            dict: A dictionary key value pair with the sector name as keys and the beam efficiency as values

        Note:
            Definitions and example of reporting can be found here: https://erilink.internal.ericsson.com/eridoc/erl/objectId/09004cffd60af4fb?docno=2%2F0363-KRE2014818%2F21&option=download&format=pdf

        Example:
            >>> antenna_pattern.calculate_beam_efficiency()  # default behavior

            >>> sector_defs = SectorDefinition(load_default=False)
            >>> sector_defs.add_sector(
            ...     name="left_beam_until_horizon",
            ...     theta_min=(90, "<="),
            ...     theta_max=(165, "<="),
            ...     phi_min=(-60, "<="),
            ...     phi_max=(0, "<="),
            ... )
            >>> antenna_pattern.calculate_beam_efficiency(
            ...     sector_definitions=sector_defs, powersum=False
            ... )
        """
        logger.debug(
            "AntennaPattern: Calculating beam efficiency of antenna pattern data."
        )
        if sector_definitions is None:
            sector_definitions = self._build_sectors_from_preset()

        if powersum:
            field_values = self.Pattern_3D["P_tp_lin"]
        else:
            field_values = self.Pattern_3D["P_co_lin"]

        self._ensure_domega()

        weighted_field_values = self.Pattern_3D["dOmega"] * field_values
        Sp_overall = float(weighted_field_values.sum())
        if Sp_overall == 0:
            logger.error(
                "AntennaPattern: Overall power is zero; cannot compute beam efficiency."
            )
            raise ValueError(
                "AntennaPattern: Overall power is zero; cannot compute beam efficiency."
            )

        operators_dict = {
            "<": operator.lt,
            "<=": operator.le,
            ">": operator.gt,
            ">=": operator.ge,
        }
        beam_efficiency = {}
        for sector_name, sector_boundary_box in sector_definitions.sectors.items():
            if isinstance(sector_boundary_box, BoundaryBoxSquare):
                Sp_region = (
                    weighted_field_values.where(
                        operators_dict[sector_boundary_box.theta_min[1]](
                            sector_boundary_box.theta_min[0],
                            weighted_field_values.Theta,
                        ),
                        drop=True,
                    )
                    .where(
                        operators_dict[sector_boundary_box.theta_max[1]](
                            weighted_field_values.Theta,
                            sector_boundary_box.theta_max[0],
                        ),
                        drop=True,
                    )
                    .where(
                        operators_dict[sector_boundary_box.phi_min[1]](
                            sector_boundary_box.phi_min[0], weighted_field_values.Phi
                        ),
                        drop=True,
                    )
                    .where(
                        operators_dict[sector_boundary_box.phi_max[1]](
                            weighted_field_values.Phi, sector_boundary_box.phi_max[0]
                        ),
                        drop=True,
                    )
                    .sum()
                )
                beam_efficiency[sector_name] = float(Sp_region / Sp_overall)
            else:
                logger.error(
                    f"Sector Definitions need to be class 'BoundaryBoxSquare' but is class {type(sector_boundary_box)}."
                )
                raise TypeError(
                    f"Sector Definitions need to be class 'BoundaryBoxSquare' but is class {type(sector_boundary_box)}."
                )

        return beam_efficiency

    def find_peak_coordinates(self, power: bool = False) -> tuple[float, float]:
        """Finds the peak coordinates of Theta/Phi of the antenna pattern data.

        Searches for the maximum value within the pattern data array.
        If two points represent a maximum value, the first one is returned.

        Args:
            power (bool, optional): Whether to search for peak of power or co-polarized component. Defaults to False.

        Returns:
            tuple[float, float]: (theta, phi) coordinates of the peak in degress.
        """
        if power:
            logger.debug(
                "AntennaPattern: Searching for peak of antenna pattern power component"
            )
            peak_tuple = (
                self.Pattern_3D.stack(pt=("Theta", "Phi"))
                .idxmax("pt")["P_tp_dB"]
                .values.item()
            )
        else:
            logger.debug(
                "AntennaPattern: Searching for peak of antenna pattern co-poloarized component"
            )
            peak_tuple = (
                self.Pattern_3D.stack(pt=("Theta", "Phi"))
                .idxmax("pt")["P_co_dB"]
                .values.item()
            )
        if not isinstance(peak_tuple, tuple):
            logger.error(
                "AntennaPattern: Failed to find peak coordinates for the component. Make sure to select a component with data."
            )
            raise ValueError(
                "AntennaPattern: Failed to find peak coordinates for the component. Make sure to select a component with data."
            )
        theta_val_peak, phi_val_peak = peak_tuple

        # enrich attributes with peak
        self.Pattern_3D = self.Pattern_3D.assign_attrs(
            peak_coordinates=peak_tuple,
        )
        logger.debug(f"AntennaPattern: Peak coordinates found: {peak_tuple}")
        return theta_val_peak, phi_val_peak

    def calculate_top_3db_point(self, power: bool = False) -> float:
        """Finds the Theta border for the top 3db point of the antenna pattern data.

        Note:
            No interpolation done, simplistic search which finds the last point reported above -3dB.

        Args:
            power (bool, optional): Whether to search for peak of power or co-polarized component. Defaults to False, which complies with the NGMN standard.

        Returns:
            float: Theta border for the top 3db point in degrees.
        """
        theta_val_peak, phi_val_peak = self.find_peak_coordinates(power)
        vertical_cut = self.Pattern_3D.sel(Phi=phi_val_peak)
        if power:
            vertical_cut_normed = vertical_cut["P_tp_dB"]
        else:
            vertical_cut_normed = vertical_cut["P_co_dB"]
        # Fallback: if no point at/below -3 dB exists above the peak (e.g. a very
        # narrow beam peaking at the top of the cut), the 3 dB border collapses to
        # the peak theta itself instead of leaving ``top_border`` unbound.
        top_border = float(theta_val_peak)
        # Advance the border by the actual theta grid step rather than a hardcoded
        # 1 deg, so the result is correct for any sampling resolution.
        theta_axis = np.sort(vertical_cut_normed["Theta"].values)
        if theta_axis.size > 1:
            grid_step = float(np.median(np.diff(theta_axis)))
        else:
            grid_step = 1.0
        for theta_val in np.flip(
            vertical_cut_normed.sel(Theta=slice(0, theta_val_peak))["Theta"]
        ):
            if vertical_cut_normed.sel(Theta=theta_val) <= -3:
                top_border = float(theta_val.values) + grid_step
                break
        else:
            logger.warning(
                "AntennaPattern: No -3 dB crossing found above the peak; using peak theta as top 3 dB border."
            )

        # enrich with top_3db_point
        self.Pattern_3D.attrs["top_3db_point"] = top_border
        return top_border

    def plot(
        self,
        component_name: str = "P_tp_dB",
        show_fig: bool = True,
        remove_layout_components: bool = False,
    ) -> go.Figure | None:
        """Plots the radiation pattern as heatmap.

        Delegates figure construction to :func:`eas_3d_pattern._plotting.build_heatmap`.

        Args:
            component_name (str, optional): Name of the component to be plotted. Defaults to 'P_tp_dB', thus power pattern.
            show_fig (bool, optional): Whether to show the figure. Defaults to True.
            remove_layout_components (bool, optional): Whether to remove text, color bar and tick labels from plots of the antenna patterns. Default is False.

        Raises:
            ValueError: If ``component_name`` is not present in the pattern data.

        Returns:
            go.Figure | None: The figure if show_fig is False, otherwise None (the figure is displayed instead).

        """
        fig = build_heatmap(
            self.Pattern_3D,
            title=Path(self.data_filepath).name,
            component_name=component_name,
            remove_layout_components=remove_layout_components,
        )
        if show_fig:
            fig.show()
            return None
        return fig

    def plot_3D(
        self,
        component_name: str = "P_tp_dB",
        db_floor: float = -30.0,
        show_axes_arrows: bool = True,
        show_fig: bool = True,
    ) -> go.Figure | None:
        """Plots the radiation pattern as 3D polar plot.

        Delegates figure construction to :func:`eas_3d_pattern._plotting.build_polar_3d`.

        Args:
            component_name (str, optional): Name of the component to be plotted. Defaults to 'P_tp_dB', thus power pattern.
            db_floor (float, optional): Sets a minimum floor to have smoother plots. Defaults to -30.
            show_axes_arrows (bool, optional): Shows coordinate axes arrows in the plot. Defaults to True.
            show_fig (bool, optional): Whether to show the figure. Defaults to True.

        Raises:
            ValueError: If ``component_name`` is not present in the pattern data.

        Returns:
            go.Figure | None: The figure if show_fig is False, otherwise None (the figure is displayed instead).

        """
        fig = build_polar_3d(
            self.Pattern_3D,
            title=Path(self.data_filepath).name,
            component_name=component_name,
            db_floor=db_floor,
            show_axes_arrows=show_axes_arrows,
        )
        if show_fig:
            fig.show()
            return None
        return fig

    def __str__(self) -> str:
        buf = io.StringIO()
        self.raw_pattern_dataframe.info(buf=buf)
        lines = [
            "===== Info =====",
            f"  File: '{os.path.basename(self.data_filepath)}'",
            f"  Supplier: {self.supplier or 'N/A'}",
            f"  Antenna Model: {self.antenna_model or 'N/A'}",
            f"  Antenna Type: {self.antenna_type or 'N/A'}",
            f"  Revision Version: {self.revision_version or 'N/A'}",
            f"  Released Date: {self.released_date or 'N/A'}",
            f"  Coordinate System: {self.coordinate_system or 'N/A'}",
            f"  Beam ID: {self.beam_id or 'N/A'}",
            f"  Pattern Type: {self.pattern_type or 'N/A'}",
            f"  Nominal Polarization: {self.nominal_polarization or 'N/A'}",
            f"  Optional Comments: {self.optional_comments or 'N/A'}",
            "==== Parameters ====",
            f"  Gain [dbi]: {self.gain_dbi if self.gain_dbi is not None else 'N/A'}",
            f"  EIRP [dBm]: {self.eirp_dbm if self.eirp_dbm is not None else 'N/A'}",
            f"  Phi HPBW [deg]: {self.phi_hpbw if self.phi_hpbw is not None else 'N/A'}",
            f"  Theta HPBW [deg]: {self.theta_hpbw if self.theta_hpbw is not None else 'N/A'}",
            f"  Front to Back [db]: {self.front_to_back if self.front_to_back is not None else 'N/A'}",
            "==== Frequency & Tilt ====",
            f"  Frequency [Hz]: {self.frequency_hz if self.frequency_hz is not None else 'N/A'}",
            f"  Frequency Range [Hz]: {self.frequency_range if self.frequency_range is not None else 'N/A'}",
            f"  Theta Electrical Tilt [deg]: {self.theta_electrical_tilt if self.theta_electrical_tilt is not None else 'N/A'}",
            f"  Phi Electrical Pan [deg]: {self.phi_electrical_pan if self.phi_electrical_pan is not None else 'N/A'}",
            "==== Dataset Info ====",
            f"  Theta Sampling Range: {[float(np.min(self.theta_sampling)), float(np.max(self.theta_sampling))] if self.theta_sampling is not None else 'N/A'}",
            f"  Phi Sampling Range: {[float(np.min(self.phi_sampling)), float(np.max(self.phi_sampling))] if self.phi_sampling is not None else 'N/A'}",
            f"  Pattern Data Info: {re.sub(r'<[^>]*>', '', buf.getvalue()) or 'N/A'}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<AntennaPattern(data_filepath='{self.data_filepath}', model='{self.antenna_model}', supplier='{self.supplier}')>"
