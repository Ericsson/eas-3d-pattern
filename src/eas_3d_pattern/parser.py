import io
import logging
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import xarray as xr

from eas_3d_pattern._plotting import build_heatmap, build_polar_3d
from eas_3d_pattern._processing import PatternProcessing
from eas_3d_pattern.metrics import (
    beam_efficiency,
    directivity,
    find_peak,
    losses,
    top_3db_border,
)
from eas_3d_pattern.ngmn.loader import (
    load_json_file,
    normalize_keys,
    validate_against_schema,
)
from eas_3d_pattern.schema_manager import NGMNSchema
from eas_3d_pattern.sector_definitions import SectorDefinition

logger = logging.getLogger(__name__)


class AntennaPattern(PatternProcessing):
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
        self.raw_data: dict[str, Any] = normalize_keys(load_json_file(data_filepath))
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
            validate_against_schema(
                self.raw_data,
                self._schema,
                self.data_filepath,
                NGMNSchema.source_message,
            )

        # ---- Process the pattern data into one normalized format ----
        self._sector_preset: str = "eas"
        self.Pattern_3D: xr.Dataset = self._process_pattern_data()

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

    def calculate_directivity(self) -> float:
        """Calculate the directivity of the antenna pattern data.

        Directivity is calculated with the average radiation intensity over the whole sphere and the maximum radiation intensity.
        Can only be calculated if data is complete (full sphere). Regular grids are advised.

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
        return directivity(self.Pattern_3D)

    def calculate_losses(self) -> float:
        """Calculate the losses of the antenna pattern data.

        Antenna losses are calculated by the gain value within the header and the calculated directivity.

        Args:
            None

        Raises:
            ValueError: If no 'Gain' is declared in the pattern metadata.

        Returns:
            float: The loss value in dB (gain - directivity).

        Example:
            >>> losses = antenna_pattern.calculate_losses()
        """
        return losses(self.Pattern_3D, self.gain_dbi)

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

        Delegates the integration to
        :func:`eas_3d_pattern.metrics.efficiency.beam_efficiency`.

        Args:
            sector_definitions (SectorDefinition, optional): Defaults to None. If None, the default sector definitions will be used.
            powersum (bool, optional): Defaults to True. If True, beam efficiency is calculated on total power. If False, beam efficiency is calculated on co-polar pattern.

        Raises:
            ValueError: If the overall power sums to zero.
            TypeError: If sectors definitions are no BoundaryBoxSquare objects

        Returns:
            dict: A dictionary key value pair with the sector name as keys and the beam efficiency as values

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
        if sector_definitions is None:
            sector_definitions = self._build_sectors_from_preset()
        return beam_efficiency(self.Pattern_3D, sector_definitions, powersum)

    def find_peak_coordinates(self, power: bool = False) -> tuple[float, float]:
        """Finds the peak coordinates of Theta/Phi of the antenna pattern data.

        Delegates the search to :func:`eas_3d_pattern.metrics.peak.find_peak` and
        publishes the result on the dataset attrs.

        Args:
            power (bool, optional): Whether to search for peak of power or co-polarized component. Defaults to False.

        Raises:
            ValueError: If no peak coordinate pair could be determined.

        Returns:
            tuple[float, float]: (theta, phi) coordinates of the peak in degress.

        Note:
            Publishes ``peak_coordinates`` on ``self.Pattern_3D.attrs``. The side
            effect is deliberate and relied upon by ``util_func/report.py``.
        """
        peak = find_peak(self.Pattern_3D, power)
        # enrich attributes with peak
        self.Pattern_3D = self.Pattern_3D.assign_attrs(
            peak_coordinates=peak,
        )
        return peak

    def calculate_top_3db_point(self, power: bool = False) -> float:
        """Finds the Theta border for the top 3db point of the antenna pattern data.

        Delegates to :func:`eas_3d_pattern.metrics.peak.top_3db_border`.

        Note:
            No interpolation done, simplistic search which finds the last point reported above -3dB.

            Locating the peak goes through ``find_peak_coordinates()`` so that
            ``peak_coordinates`` is published too — ``util_func/report.py`` calls only
            this method and then reads that attribute.

        Args:
            power (bool, optional): Whether to search for peak of power or co-polarized component. Defaults to False, which complies with the NGMN standard.

        Returns:
            float: Theta border for the top 3db point in degrees.
        """
        theta_val_peak, phi_val_peak = self.find_peak_coordinates(power)
        top_border = top_3db_border(
            self.Pattern_3D, theta_val_peak, phi_val_peak, power
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
