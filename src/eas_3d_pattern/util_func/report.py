import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from eas_3d_pattern import AntennaPattern, SectorDefinition

SUBBANDS_DEFAULT = {
    "698-806": (698, 806),
    "791-862": (791, 862),
    "824-894": (824, 894),
    "880-960": (880, 960),
    "1427-1518": (1427, 1518),
    "1695-1880": (1695, 1880),
    "1850-1990": (1850, 1990),
    "1920-2200": (1920, 2200),
    "2200-2490": (2200, 2490),
    "2490-2690": (2490, 2690),
}


@contextmanager
def temporarily_set_loglevel(logger_name: str, level: int) -> Iterator[None]:
    """A context manager to temporarily set the log level for to supress most messages during file reading."""
    logger = logging.getLogger(logger_name)
    old_level = logger.level
    try:
        logger.setLevel(level)
        yield
    finally:
        logger.setLevel(old_level)


def generate_report_eas(
    directory_path: Path | str,
    output_directory: Path | str,
    plot: bool = False,
    subbands: dict[str, tuple[int, int]] = SUBBANDS_DEFAULT,
) -> pd.DataFrame:
    """Generates a excel report for EAS JSON files.

    The report contains all antenna data, beam efficiency and sector information in the JSON files within a directory.
    Additionally, aggregated data per array and per tilt and per subband is also generated.

    Args:
        directory_path (Path | str): The path to the directory containing the JSON files.
        output_directory (Path | str): The path to the directory where the report will be saved.
        plot (bool, optional): Whether to generate plots of the antenna patterns. Default is False.
        subbands (dict[str, tuple[int, int]], optional): A dictionary of subbands and their corresponding frequency ranges. Default is SUBBANDS_DEFAULT.

    Returns:
        pd.DataFrame: A pandas DataFrame containing the raw data for the report.

    Example:
        >>> from eas_3d_pattern import generate_report_eas
        >>> df = generate_report_eas("path/to/directory", "path/to/output_directory")

        >>> df = generate_report_eas(
        ...     "path/to/directory", "path/to/output_directory", plot=True
        ... )  # with png plotting

        >>> my_own_subbands = {
            "Carrier1": (730, 750),
            "Carrier2": (1970, 1990),
            }
        >>> df = generate_report_eas(
        ...     "path/to/directory", "path/to/output_directory", subband=my_own_subbands
        ... )  # with own subband
    """
    directory_path = Path(directory_path)
    files = list(directory_path.glob("*.json"))
    if len(files) == 0:
        raise ValueError("Report: No .json files found in the directory.")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    df_list: list[pd.DataFrame] = []
    with temporarily_set_loglevel(logger_name="eas_3d_pattern", level=logging.ERROR):
        for file in tqdm(files):
            data = _process_a_file(file)
            if data is not None:
                data_row, pattern, sectors = data
                df_list.append(data_row)
                if plot:
                    _save_figure(pattern, sectors, output_directory)
        df_raw = pd.concat(df_list, ignore_index=True)

    report_name = output_directory / "BEreport.xlsx"
    _generate_excel_report(df_raw, report_name, subbands)
    return df_raw


def _process_a_file(
    file_path: Path,
) -> tuple[pd.DataFrame, AntennaPattern, SectorDefinition] | None:
    """Process a file and return the processed data.

    Args:
        file_path (Path): The path to the file to be processed.

    Returns:
        tuple[pd.DataFrame, AntennaPattern, SectorDefinition] | None:
            A tuple containing the processed data, the AntennaPattern instance,
            and the SectorDefinition instance. If an exception is raised, None is
            returned.

    Raises:
        Exception: If an error occurs during the processing of the file.
    """
    try:
        pattern = AntennaPattern(str(file_path), validate=False)
        data = pattern.get_metadata_dict()
        top_border = pattern.calculate_top_3db_point(power=False)
        eas_sectors = SectorDefinition(load_default=True, top_border=top_border)
        eff = pattern.calculate_beam_efficiency(sector_definitions=eas_sectors)
        data.update({f"{k}": v * 100 for k, v in eff.items()})
        data.update(
            {
                f"{k}_limits": [
                    v.phi_min[0],
                    v.theta_min[0],
                    v.phi_max[0],
                    v.theta_max[0],
                ]
                for k, v in eas_sectors.sectors.items()
            }
        )
        data["filepath"] = str(pattern.data_filepath)
        return (pd.json_normalize(data, sep="_"), pattern, eas_sectors)
    except Exception as e:
        logging.error(
            f"Reporting: Skipping corrupted or invalid file '{file_path.name}': {e}"
        )
        return None


def _save_figure(
    pattern: AntennaPattern,
    sector_definitions: SectorDefinition,
    output_directory: Path,
) -> None:
    """Saves the plot of the given AntennaPattern and SectorDefinition to a PNG file.

    Args:
        pattern (AntennaPattern): The AntennaPattern to plot.
        sector_definitions (SectorDefinition): The SectorDefinition to use for plotting.
        output_directory (Path): The directory to save the plot to.

    Returns:
        None
    """
    fig = pattern.plot(show_fig=False)
    if fig is None:
        return
    for k in sector_definitions.sectors:
        fig.add_shape(
            type="rect",
            x0=sector_definitions.sectors[k].phi_min[0],
            y0=sector_definitions.sectors[k].theta_min[0],
            x1=sector_definitions.sectors[k].phi_max[0],
            y1=sector_definitions.sectors[k].theta_max[0],
            line={"color": "White"},
        )
    fig.write_image(
        output_directory / f"{Path(pattern.data_filepath).stem}.png", format="png"
    )


def _generate_excel_report(
    df: pd.DataFrame, report_name: Path, subbands: dict[str, tuple[int, int]]
) -> None:
    """Generate an Excel report based on the provided DataFrame.

    Parameters:
        df (pd.DataFrame): The DataFrame to generate the report from.
        report_name (Path): The name of the report file.
        subbands (dict[str, tuple[int, int]]): A dictionary of subbands and their frequency ranges.

    Returns:
        None
    """
    df_per_array = (
        df.groupby(["Supplier", "Antenna_Model", "Revision_Version", "Array_ID"])[
            "Cell"
        ]
        .agg(["mean", "max"])
        .reset_index()
        .rename(columns={"mean": "Average", "max": "Max"})
    )

    df_per_array_per_tilt = df.pivot_table(
        index=["Supplier", "Antenna_Model", "Revision_Version", "Array_ID"],
        columns="Theta_Electrical_Tilt",
        values="Cell",
        aggfunc="mean",
    )
    df_per_array_per_tilt["Average"] = df_per_array_per_tilt.mean(axis=1)
    df_per_array_per_tilt = df_per_array_per_tilt.reset_index()

    avg_df_list = []
    for subband_str, subband_freqs in subbands.items():
        df_tmp = df[
            df["Frequency_value"].between(subband_freqs[0], subband_freqs[1])
        ].copy()
        if df_tmp.empty:
            continue
        df_tmp.loc[:, "Subband"] = subband_str
        pivot_df = df_tmp.pivot_table(
            index=[
                "Supplier",
                "Antenna_Model",
                "Revision_Version",
                "Array_ID",
                "Subband",
            ],
            columns="Theta_Electrical_Tilt",
            values="Cell",
            aggfunc="mean",
        )
        pivot_df["Average"] = pivot_df.mean(axis=1)
        avg_df_list.append(pivot_df.reset_index())
    df_per_arrayandsubband_per_tilt = pd.concat(avg_df_list, ignore_index=True)

    with pd.ExcelWriter(report_name) as writer:
        df.to_excel(writer, index=False, sheet_name="Raw_Data")
        df_per_array.to_excel(writer, index=False, sheet_name="Mean_Max_Per_ArrayID")
        df_per_array_per_tilt.to_excel(
            writer, index=False, sheet_name="Mean_ArrayID_Tilt"
        )
        df_per_arrayandsubband_per_tilt.to_excel(
            writer, index=False, sheet_name="Mean_ArrayID_Subband_Tilt"
        )
    logging.info("Report: ✨Generated EAS BE report in %s✨", report_name)
    return None
