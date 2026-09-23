# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Reading, normalizing and validating NGMN BASTA 3drp JSON files.

Pure functions: no dependency on ``AntennaPattern`` and none on the schema
singleton — the caller supplies both the schema and a description of where it
came from, so this module stays usable when the schema manager is reworked to
load lazily (plan section 1.2).

Split out of ``parser.py`` (Phase 4b of the god-class decomposition, plan
section 2.1.3).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

logger = logging.getLogger(__name__)

# Maps vendor-specific variant -> canonical key
ALTERNATIVES: dict[str, str] = {
    # "Theta_Tilt" comes from the NGMN whitepaper:
    # https://www.ngmn.org/wp-content/uploads/NGMN_BASTA_Recommendations-for-Base-Station-Antennas_V13.0.pdf
    # "Theta_Electrical_Tilt" comes from the latest JSON Schema:
    # https://www.ngmn.org/schema/basta/NGMN_BASTA_AA_3drp_JSON_Schema_WP3_0_latest.json
    "Theta_Tilt": "Theta_Electrical_Tilt",
}

def json_load(filepath: str | Path,
              normalize: bool = True) -> dict[str, Any]:
    """json_load.

    This is a full json load operation which also normalizes
    the data by default. The normalization can be disabled by the flag.
    Normalization modifies the json loaded inplace.

    Args:
        filepath (str | Path): Path to the JSON data file.
        normalize (bool, optional): Normalization flag enabled/disabled.
            Defaults to True.

    Returns:
        dict[str, Any]: Parsed JSON payload, normalized or not.
    """
    return normalize_keys(load_json_file(filepath)) if normalize else \
        load_json_file(filepath)

def load_json_file(filepath: str | Path) -> dict[str, Any]:
    """Read a JSON pattern file from disk.

    Args:
        filepath (str | Path): Path to the JSON data file.

    Raises:
        ValueError: If the file does not contain valid JSON.
        OSError: If the file cannot be read.

    Returns:
        dict[str, Any]: Parsed JSON payload.
    """
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


def normalize_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize vendor-specific keys to canonical names.

    Some vendors use non-standard key names in their 3drp JSON files. This replaces
    known variants with the canonical key defined in the latest NGMN BASTA JSON
    schema, using the module-level ``ALTERNATIVES`` mapping.

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
        data (dict[str, Any]): Raw dictionary loaded from a JSON antenna pattern file.

    Returns:
        dict[str, Any]: The same dictionary with variant keys replaced by their
        canonical equivalents.
    """
    for variant, canonical in ALTERNATIVES.items():
        if variant in data and canonical not in data:
            data[canonical] = data.pop(variant)
    return data


def validate_against_schema(
    data_instance: dict[str, Any],
    schema_instance: dict[str, Any],
    data_filepath: str | Path,
    schema_source: str,
) -> None:
    """Validate pattern data against the NGMN BASTA JSON schema.

    Args:
        data_instance (dict[str, Any]): Normalized pattern payload.
        schema_instance (dict[str, Any]): Schema to validate against.
        data_filepath (str | Path): Source file, named in the error for diagnosis.
        schema_source (str): Human-readable origin of the schema, named in the error.

    Raises:
        ValidationError: If the data does not conform, carrying an enriched message
            that names the file, the schema source and the failing data path.
    """
    logger.debug(
        f"AntennaPattern: Validating user data against schema: '{schema_source}'..."
    )
    try:
        validate(instance=data_instance, schema=schema_instance)
        logger.debug("AntennaPattern: User data validation successful.")
    except ValidationError as e:
        error_path_str = " -> ".join(map(str, e.path)) if e.path else "document root"
        full_error_message = f"Antenna data validation FAILED for '{data_filepath}'.\nSchema source: '{schema_source}'.\nError at data path: '{error_path_str}'.\nValidation Message: {e.message} (Validator: '{e.validator}')"
        logger.error(full_error_message)
        raise ValidationError(full_error_message) from e
