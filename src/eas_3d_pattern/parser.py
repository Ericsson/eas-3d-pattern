import io
import json
import logging
import operator
import os
import re
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import xarray as xr
from jsonschema import ValidationError, validate

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


class AntennaPattern:
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
        self.raw_data: dict[str, Any] = self._load_data_from_file(data_filepath)
        if validate and self._schema is not None:
            self._validate_data_against_schema(self.raw_data, self._schema)

        # ---- Process the pattern data into one normalized format ----
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
            full_error_message = (
                f"Antenna data validation FAILED for '{self.data_filepath}'.\n"
                f"Schema source: '{NGMNSchema.source_message}'.\n"
                f"Error at data path: '{error_path_str}'.\n"
                f"Validation Message: {e.message} (Validator: '{e.validator}')"
            )
            logger.error(full_error_message)
            raise ValidationError(full_error_message) from e

    @property
    def BASTA_AA_WP_version(self) -> str:
        return str(self.raw_data["BASTA_AA_WP_version"])

    @property
    def supplier(self) -> str:
        return str(self.raw_data["Supplier"])

    @property
    def antenna_model(self) -> str:
        return str(self.raw_data["Antenna_Model"])

    @property
    def antenna_type(self) -> str:
        return str(self.raw_data["Antenna_Type"])

    @property
    def revision_version(self) -> str:
        return str(self.raw_data["Revision_Version"])

    @property
    def released_date(self) -> str:
        return str(self.raw_data["Released_Date"])

    @property
    def coordinate_system(self) -> str:
        return str(self.raw_data["Coordinate_System"])

    @property
    def pattern_name(self) -> str | None:
        return self.raw_data.get("Pattern_Name")

    @property
    def beam_id(self) -> str | None:
        return self.raw_data.get("Beam_ID")

    @property
    def pattern_type(self) -> str:
        return str(self.raw_data["Pattern_Type"])

    @property
    def frequency_hz(self) -> float:
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
        return self.raw_data.get("Configuration")

    @property
    def rf_port(self) -> str | None:
        return self.raw_data.get("RF_Port")

    @property
    def array_id(self) -> str | None:
        return self.raw_data.get("Array_ID")

    @property
    def array_position(self) -> str | None:
        return self.raw_data.get("Array_Position")

    @property
    def phi_hpbw(self) -> float:
        return float(self.raw_data["Phi_HPBW"])

    @property
    def theta_hpbw(self) -> float:
        return float(self.raw_data["Theta_HPBW"])

    @property
    def front_to_back(self) -> float:
        return float(self.raw_data["Front_to_Back"])

    @property
    def phi_eletrical_pan(self) -> float | None:
        return self.raw_data.get("Phi_Electrical_Pan")

    @property
    def theta_eletrical_tilt(self) -> float | None:
        return self.raw_data.get("Theta_Electrical_Tilt")

    @property
    def nominal_polarization(self) -> str:
        return str(self.raw_data["Nominal_Polarization"])

    @property
    def optional_comments(self) -> str:
        return str(self.raw_data["Optional_Comments"])

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
        if self.coordinate_system not in DEFAULT_INTERNAL_COORD_SYSTEM:
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
        phi = Pattern_3D.coords["Phi"].values
        theta = Pattern_3D.coords["Theta"].values
        if from_system == "SPCS_Polar":
            if to_system == "SPCS_Ericsson":
                Pattern_3D = Pattern_3D.assign_coords(
                    Theta=("Theta", theta),
                    Phi=("Phi", np.where(phi >= 180, phi - 360, phi)),
                )
        if from_system == "SPCS_CW":
            if to_system == "SPCS_Ericsson":
                Pattern_3D = Pattern_3D.assign_coords(
                    Theta=("Theta", theta + 90),
                    Phi=("Phi", -np.where(phi > 180, phi - 360, phi)),
                )
        if from_system == "SPCS_CCW":
            if to_system == "SPCS_Ericsson":
                Pattern_3D = Pattern_3D.assign_coords(
                    Theta=("Theta", theta + 90),
                    Phi=("Phi", np.where(phi >= 180, phi - 360, phi)),
                )
        if from_system == "SPCS_Geo":
            if to_system == "SPCS_Ericsson":
                Pattern_3D = Pattern_3D.assign_coords(
                    Theta=("Theta", np.flip(theta)),
                    Phi=("Phi", -np.where(phi > 180, phi - 360, phi)),
                )
        Pattern_3D = Pattern_3D.assign_attrs(
            coordinate_system=to_system,
        )
        return Pattern_3D.sortby(["Theta", "Phi"])

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
            logger.warning(
                "AntennaPattern: SectorDefinition is not defined. Taking default settings for beam efficiency calculation."
            )
            top_border = self.calculate_top_3db_point(power=False)
            sector_definitions = SectorDefinition(
                load_default=True, top_border=top_border
            )

        if powersum:
            field_values = self.Pattern_3D["P_tp_lin"]
        else:
            field_values = self.Pattern_3D["P_co_lin"]

        if "dOmega" not in list(self.Pattern_3D.data_vars.keys()):
            weight = np.repeat(
                np.sin(np.deg2rad(self.Pattern_3D.Theta.values)).T[:, None],
                len(self.Pattern_3D.Phi),
                axis=1,
            )
            dTheta = np.abs(np.gradient(np.deg2rad(self.Pattern_3D["Theta"]))).reshape(
                -1, 1
            )
            dPhi = np.abs(np.gradient(np.deg2rad(self.Pattern_3D["Phi"]))).reshape(
                1, -1
            )
            factor = dTheta * dPhi
            dOmega = weight * factor
            self.Pattern_3D["dOmega"] = xr.DataArray(
                dOmega,
                dims=("Theta", "Phi"),
                coords={"Theta": self.Pattern_3D.Theta, "Phi": self.Pattern_3D.Phi},
                name="dOmega",
            )

        weighted_field_values = self.Pattern_3D["dOmega"] * field_values
        Sp_overall = float(weighted_field_values.sum())

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
        for theta_val in np.flip(
            vertical_cut_normed.sel(Theta=slice(0, theta_val_peak))["Theta"]
        ):
            if vertical_cut_normed.sel(Theta=theta_val) <= -3:
                top_border = float((theta_val + 1).values)
                break

        # enrich with top_3db_point
        self.Pattern_3D.attrs["top_3db_point"] = top_border
        return top_border

    def plot(
        self, component_name: str = "P_tp_dB", show_fig: bool = True
    ) -> None | go.Figure:
        """Plots the radation pattern as heatmap.

        Plots with ploty the radation pattern as heatmap.
        Normalized radation pattern are shown in dB.

        Args:
            component_name (str, optional): Name of the component to be plotted. Defaults to 'P_tp_dB', thus power pattern.
            show_fig (bool, optional): Whether to show the figure. Defaults to True.

        Returns:
            None | go.Figure: None if show_fig is False else go.Figure

        """
        if component_name not in self.Pattern_3D.data_vars:
            logger.error(
                f"AntennaPattern: Component '{component_name}' not found. Make sure to select a component with data."
            )
            raise ValueError(
                f"AntennaPattern: Component '{component_name}' not found. Make sure to select a component with data."
            )

        fig = go.Figure(
            data=go.Heatmap(
                z=self.Pattern_3D[component_name].values,
                x=self.Pattern_3D["Phi"].values,
                y=self.Pattern_3D["Theta"].values,
                colorscale="turbo",
                zmin=-30,
                zmax=0,
                colorbar={"title": component_name, "thickness": 9},
                hovertemplate=(
                    "φ = %{x:.0f}°<br>"
                    "θ = %{y:.0f}°<br>"
                    "val = %{z:.2f}<br>"
                    "<extra></extra>"
                ),
            )
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            title={
                "text": os.path.basename(self.data_filepath),
                "x": 0.5,
                "y": 0.93,
                "yanchor": "bottom",
                "font": {"size": 16},
            },
            xaxis={
                "title": "φ [°]",
                "tickmode": "linear",
                "title_standoff": 10,
                "dtick": 30,
                "showgrid": True,
                "tickangle": -45,
                "gridcolor": "rgba(0,0,0,0.2)",
                "zeroline": False,
            },
            yaxis={
                "title": "θ [°]",
                "tickmode": "linear",
                "title_standoff": 10,
                "dtick": 30,
                "showgrid": True,
                "gridcolor": "rgba(0,0,0,0.2)",
                "zeroline": False,
            },
            margin={"t": 40, "l": 60, "r": 60, "b": 60},
            height=500,
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
            f"  Phi HPBW [deg]: {self.phi_hpbw if self.phi_hpbw else 'N/A'}",
            f"  Theta HPBW [deg]: {self.theta_hpbw if self.theta_hpbw else 'N/A'}",
            f"  Front to Back [db]: {self.front_to_back if self.front_to_back else 'N/A'}",
            "==== Frequency & Tilt ====",
            f"  Frequency [Hz]: {self.frequency_hz if self.frequency_hz else 'N/A'}",
            f"  Frequency Range [Hz]: {self.frequency_range if self.frequency_range is not None else 'N/A'}",
            f"  Theta Electrical Tilt [deg]: {self.theta_eletrical_tilt if self.theta_eletrical_tilt is not None else 'N/A'}",
            f"  Phi Electrical Pan [deg]: {self.phi_eletrical_pan if self.phi_eletrical_pan is not None else 'N/A'}",
            "==== Dataset Info ====",
            f"  Theta Sampling Range: {[float(np.min(self.theta_sampling)), float(np.max(self.theta_sampling))] if self.theta_sampling is not None else 'N/A'}",
            f"  Phi Sampling Range: {[float(np.min(self.phi_sampling)), float(np.max(self.phi_sampling))] if self.phi_sampling is not None else 'N/A'}",
            f"  Pattern Data Info: {re.sub(r'<[^>]*>', '', buf.getvalue()) or 'N/A'}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"<AntennaPattern(data_filepath='{self.data_filepath}', "
            f"model='{self.antenna_model}', supplier='{self.supplier}')>"
        )
