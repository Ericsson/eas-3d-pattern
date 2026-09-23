# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for the schema-source provenance model.

``SchemaSource`` records *where* a loaded schema came from (URL, cache or the
bundled copy). Failure to obtain any schema is an exception, not a member, so it
is not represented here. The human-readable rendering lives on the enum itself;
``SchemaManager`` only holds the state and the source-specific detail.
"""

from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator, SchemaError

from eas_3d_pattern import SchemaSource
from eas_3d_pattern.schema_manager import NGMNSchema, SchemaManager


class TestSchemaSourceEnum:
    """The enum owns the wording; the caller supplies the source-specific detail."""

    def test_three_provenance_members_exist(self):
        assert {s.name for s in SchemaSource} == {"URL", "CACHE", "BUNDLED"}

    def test_url_message_embeds_detail(self):
        msg = SchemaSource.URL.message("https://example.org/schema.json")
        assert "URL" in msg
        assert "https://example.org/schema.json" in msg

    def test_cache_message_embeds_detail(self):
        msg = SchemaSource.CACHE.message("/tmp/cache/schema_abc.json")
        assert "cache" in msg.lower()
        assert "/tmp/cache/schema_abc.json" in msg

    def test_bundled_message_embeds_detail(self):
        msg = SchemaSource.BUNDLED.message("eas_3d_pattern.schemas/schema.json")
        assert "Bundled" in msg
        assert "eas_3d_pattern.schemas/schema.json" in msg

    @pytest.mark.parametrize("source", list(SchemaSource))
    def test_every_member_renders_a_message(self, source: SchemaSource):
        """No member may be left without a template."""
        rendered = source.message("DETAIL")
        assert "DETAIL" in rendered
        assert rendered  # non-empty


class TestManagerRecordsProvenance:
    """The live singleton must end initialization in a known provenance state."""

    def test_singleton_has_a_source_after_load(self):
        assert NGMNSchema.schema_source in set(SchemaSource)

    def test_source_message_is_derived_from_source(self):
        expected = NGMNSchema.schema_source.message(NGMNSchema._source_detail)
        assert NGMNSchema.source_message == expected

    def test_source_message_marker_before_any_source(self):
        """With no source recorded, the message is the not-yet-loaded marker."""
        manager = SchemaManager.__new__(SchemaManager)
        manager.schema_source = None
        manager._source_detail = ""
        assert manager.source_message == "Schema loading not yet attempted."


class TestSchemaVersionConfiguration:
    """The configured version is the source of truth; the loaded schema must match."""

    def test_singleton_configured_version(self):
        assert NGMNSchema.schema_version == "2020-12"

    def test_loaded_schema_matches_configured_version(self):
        """The verifier accepts a schema whose $schema dialect matches the config."""
        manager = SchemaManager.__new__(SchemaManager)
        manager.schema_version = "2020-12"
        manager._verify_schema_version(
            {"$schema": "https://json-schema.org/draft/2020-12/schema"}
        )  # must not raise

    def test_mismatched_dialect_raises(self):
        manager = SchemaManager.__new__(SchemaManager)
        manager.schema_version = "2020-12"
        with pytest.raises(SchemaError, match="(?i)not configured"):
            manager._verify_schema_version(
                {"$schema": "http://json-schema.org/draft-07/schema#"}
            )

    def test_missing_dialect_raises(self):
        manager = SchemaManager.__new__(SchemaManager)
        manager.schema_version = "2020-12"
        with pytest.raises(SchemaError, match="(?i)not configured"):
            manager._verify_schema_version({"type": "object"})

    def test_supported_version_selects_validator(self):
        manager = SchemaManager.__new__(SchemaManager)
        manager.schema_version = "2020-12"
        assert manager._validator_for_configured_version() is Draft202012Validator

    def test_unsupported_version_raises(self):
        manager = SchemaManager.__new__(SchemaManager)
        manager.schema_version = "2019-09"
        with pytest.raises(ValueError, match="(?i)unsupported schema version"):
            manager._validator_for_configured_version()
