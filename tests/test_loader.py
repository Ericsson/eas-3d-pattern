# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for loading and validating a pattern file.

Written ahead of the Phase 4b move of the loading helpers into
``eas_3d_pattern.ngmn.loader`` (plan section 2.1.3). These pin the failure paths,
which were the least covered code in the parser: a missing file, malformed JSON,
an unreadable path, and schema validation.

Key normalization is covered separately in ``test_normalize.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from eas_3d_pattern import SAMPLE_JSON, AntennaPattern
from eas_3d_pattern.schema_manager import NGMNSchema


class TestMissingOrUnreadableFile:
    """The path must exist and be readable before anything else happens."""

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError, match="(?i)data file not found"):
            AntennaPattern(str(missing), validate=False)

    def test_directory_instead_of_file_raises_os_error(self, tmp_path: Path):
        """A directory passes the existence check but cannot be read as JSON."""
        directory = tmp_path / "a_directory"
        directory.mkdir()
        with pytest.raises(OSError, match="(?i)could not read user data file"):
            AntennaPattern(str(directory), validate=False)


class TestMalformedJson:
    """Malformed JSON must surface as a clear ValueError, not a raw decode error."""

    def test_invalid_json_raises_value_error(self, tmp_path: Path):
        path = tmp_path / "broken.json"
        path.write_text('{"Coordinate_System": "SPCS_Ericsson",', encoding="utf-8")
        with pytest.raises(ValueError, match="(?i)invalid json"):
            AntennaPattern(str(path), validate=False)

    def test_empty_file_raises_value_error(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="(?i)invalid json"):
            AntennaPattern(str(path), validate=False)


class TestSchemaValidation:
    """``validate=True`` runs the data against the NGMN BASTA schema."""

    def test_schema_is_available_for_these_tests(self):
        """Guard: the assertions below are meaningless without a loaded schema."""
        assert NGMNSchema.schema_content is not None

    def test_synthetic_pattern_fails_real_schema(self, pattern_path):
        """The synthetic fixture is deliberately minimal and is not schema-valid.

        This exercises the validation failure path and the enriched error message,
        which names the offending file, the schema source and the data path.
        """
        path = pattern_path()
        with pytest.raises(ValidationError) as excinfo:
            AntennaPattern(path, validate=True)

        message = str(excinfo.value)
        assert "validation FAILED" in message
        assert Path(path).name in message
        assert "Error at data path" in message

    def test_validation_skipped_by_default(self, pattern_path):
        """Without validate=True the same minimal file loads fine."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        assert pattern.data["Coordinate_System"] == "SPCS_Ericsson"

    @pytest.mark.slow
    def test_bundled_sample_passes_real_schema(self):
        """A shipped NGMN sample must validate against the shipped schema.

        Guards against the bundled data and the schema drifting apart, and is the
        only route to the validation success path — the synthetic fixture is too
        minimal to be schema-valid. Slow: validation walks every data row.
        """
        pattern = AntennaPattern(SAMPLE_JSON[0], validate=True)
        assert pattern.data["Data_Set"]


class TestDataSetPresence:
    """``Data_Set`` is checked before any processing is attempted."""

    def test_missing_data_set_key_raises(self, tmp_path: Path):
        path = tmp_path / "no_dataset.json"
        path.write_text(
            json.dumps({"Coordinate_System": "SPCS_Ericsson"}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="(?i)data_set"):
            AntennaPattern(str(path), validate=False)


class TestRawDataDeprecatedAlias:
    """``raw_data`` is a deprecated alias for ``data`` (renamed in v0.2.0)."""

    def test_raw_data_returns_same_object_as_data(self, pattern_path):
        """The alias returns the very same dict object, not a copy."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        with pytest.warns(DeprecationWarning):
            assert pattern.raw_data is pattern.data

    def test_raw_data_access_warns(self, pattern_path):
        """Reading ``raw_data`` emits a DeprecationWarning naming ``data``."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        with pytest.warns(DeprecationWarning, match="(?i)use antennapattern.data"):
            _ = pattern.raw_data


class TestPattern3DDeprecatedAlias:
    """``Pattern_3D`` is a deprecated alias for ``pattern`` (renamed in v0.2.0)."""

    def test_pattern_3d_returns_same_object_as_pattern(self, pattern_path):
        """The alias returns the very same dataset object, not a copy."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        with pytest.warns(DeprecationWarning):
            assert pattern.Pattern_3D is pattern.pattern

    def test_pattern_3d_access_warns(self, pattern_path):
        """Reading ``Pattern_3D`` emits a DeprecationWarning naming ``pattern``."""
        pattern = AntennaPattern(pattern_path(), validate=False)
        with pytest.warns(DeprecationWarning, match="(?i)use antennapattern.pattern"):
            _ = pattern.Pattern_3D


class TestRepr:
    """``__repr__`` identifies the instance by file, model and supplier."""

    def test_repr_names_file_model_and_supplier(self, pattern_path):
        path = pattern_path(extra={"Antenna_Model": "ANTMODEL9", "Supplier": "VENDOR"})
        pattern = AntennaPattern(path, validate=False)

        text = repr(pattern)
        assert "AntennaPattern" in text
        assert "ANTMODEL9" in text
        assert "VENDOR" in text
