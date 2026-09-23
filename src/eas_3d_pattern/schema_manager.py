import hashlib
import importlib.resources
import json
import logging
import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Any

import requests
from jsonschema import Draft202012Validator, SchemaError

from .ngmn.loader import validate_against_schema

# --- Logger Configuration ---
logger = logging.getLogger(__name__)


class SchemaSource(Enum):
    """Where a loaded schema was obtained from.

    This is the *provenance* of a schema, not the outcome of loading it: failure
    to obtain any schema is signalled by an exception, not by a member here.

    Members:
        URL: Freshly downloaded from the remote NGMN schema URL.
        CACHE: Read from the on-disk file cache of a previous download.
        BUNDLED: Loaded from the copy shipped inside the package.
    """

    URL = "url"
    CACHE = "cache"
    BUNDLED = "bundled"

    def message(self, detail: str) -> str:
        """Render a human-readable description of this source.

        The enum owns the wording; the caller supplies the source-specific
        ``detail`` (the URL, or the ``package/filename`` of the bundled copy).

        Args:
            detail (str): The source-specific locator to embed in the message.

        Returns:
            str: A description such as ``"Downloaded from URL (https://...)"``.
        """
        templates = {
            SchemaSource.URL: "Downloaded from URL ({detail})",
            SchemaSource.CACHE: "Loaded from file cache ({detail})",
            SchemaSource.BUNDLED: "Bundled Schema ({detail})",
        }
        return templates[self].format(detail=detail)

# --- Schema Configuration ---
# Schema URL to always get the latest version
SCHEMA_URL = (
    "https://www.ngmn.org/schema/basta/NGMN_BASTA_AA_3drp_JSON_Schema_WP3_0_latest.json"
)

# Local schema path as fallback
BUNDLED_SCHEMA_FILENAME = "NGMN_BASTA_AA_3drp_JSON_Schema_WP3_0_latest.json"
BUNDLED_SCHEMA_PACKAGE_REF = "eas_3d_pattern.schemas"

# Cache configuration for local copy
CACHE_DIR_NAME = ".ngmn_json_schema_cache"  # Cache directory
# CACHE_EXPIRY_SECONDS = 24 * 60 * 60  # Cache schemas for 1 day
REQUESTS_TIMEOUT_SECONDS = 10  # Timeout for fetching schema from URL

# JSON Schema draft this manager is configured to validate against. The loaded
# schema's "$schema" dialect must match this, or loading is rejected.
SCHEMA_VERSION = "2020-12"

# Maps a JSON Schema "$schema" dialect URI to the short version this manager uses.
_SCHEMA_DIALECT_VERSIONS = {
    "https://json-schema.org/draft/2020-12/schema": "2020-12",
    "http://json-schema.org/draft/2020-12/schema#": "2020-12",
}


class SchemaManager:
    """Singleton Schema Manager to validate and cache the NGMN JSON schema.

    Used to validate antenna pattern JSON data against the schema.
    SchemaManger downloads and cache the NGMN JSON schema. Usage as a singleton within the package.
    Fallbacks to local package copy if not internet access.
    If the schema content is still None, it logs a critical error message and raises a RuntimeError.
    """

    def __init__(self):
        self.schema_url = SCHEMA_URL
        self.bundled_filename = BUNDLED_SCHEMA_FILENAME
        self.bundled_package_ref = BUNDLED_SCHEMA_PACKAGE_REF
        self.cache_dir_name = CACHE_DIR_NAME
        # self.cache_expiry_seconds = CACHE_EXPIRY_SECONDS
        self.requests_timeout = REQUESTS_TIMEOUT_SECONDS
        self.schema_version = SCHEMA_VERSION
        self.cache_root_dir = os.path.abspath(self.cache_dir_name)

        self.schema_content: dict[str, Any] | None = None
        self.schema_source: SchemaSource | None = None
        self._source_detail: str = ""

        # Clear cache -> ensure cache dir exists -> load and validate schema from URL or fallback to bundled schema -> save to cache
        self._clear_cache_directory()
        self._ensure_cache_directory_exists()
        self._load_and_validate_schema()

        if self.schema_content is None:
            msg = " SchemaManager failed to load any schema."
            logger.critical(msg)
            raise RuntimeError(msg)
        logger.info(
            f"SchemaManager: JSON NGMN Schema initialized succesfully. Schema source: {self.source_message}"
        )

    @property
    def source_message(self) -> str:
        """Human-readable description of where the schema was loaded from.

        Derived from :attr:`schema_source`; returns a not-yet-loaded marker while
        no source has been recorded.
        """
        if self.schema_source is None:
            return "Schema loading not yet attempted."
        return self.schema_source.message(self._source_detail)

    def _set_source(self, source: SchemaSource, detail: str) -> None:
        self.schema_source = source
        self._source_detail = detail

    def validate(self, data: dict[str, Any], data_filepath: str | Path) -> None:
        """Validate pattern data against this manager's loaded schema.

        Convenience wrapper that supplies this manager's own schema content and
        source description to the pure ``validate_against_schema`` mechanism, so
        callers do not need to reach into the manager's internals.

        Args:
            data (dict[str, Any]): Normalized pattern payload to validate.
            data_filepath (str | Path): Source file, named in any error for diagnosis.

        Raises:
            ValueError: If no schema is available to validate against.
            ValidationError: If the data does not conform to the schema.
        """
        if self.schema_content is None:
            msg = "Validation requested but no schema is available."
            logger.error(f"SchemaManager: {msg}")
            raise ValueError(msg)
        validate_against_schema(
            data, self.schema_content, data_filepath, self.source_message
        )

    ##### Cache management #####
    def _clear_cache_directory(self) -> None:
        if os.path.exists(self.cache_root_dir):
            try:
                shutil.rmtree(self.cache_root_dir)
                logger.info(
                    f"SchemaManager: Cleared cache directory: {self.cache_root_dir}"
                )
            except OSError as e:
                logger.error(
                    f"SchemaManager: Error clearing cache directory {self.cache_root_dir}. Error: {e}"
                )
        else:
            logger.debug(
                f"SchemaManager: Cache directory {self.cache_root_dir} not found, nothing to clear."
            )

    def _ensure_cache_directory_exists(self):
        try:
            os.makedirs(self.cache_root_dir, exist_ok=True)
            logger.debug(
                f"SchemaManager: Cache directory ensured: {self.cache_root_dir}"
            )
        except OSError as e:
            logger.error(
                f"SchemaManager: Could not create cache directory {self.cache_root_dir}. File caching will be disabled. Error: {e}"
            )

    def _get_cached_schema_filepath_for_url(self) -> str | None:
        if not self.schema_url or not os.path.isdir(self.cache_root_dir):
            return None
        url_hash = hashlib.md5(self.schema_url.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_root_dir, f"schema_{url_hash}.json")

    def _load_json_from_file(
        self, file_path: str, file_description: str
    ) -> dict[str, Any]:
        logger.debug(f"SchemaManager: Loading {file_description} from: {file_path}")
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except FileNotFoundError:
            logger.error(f"SchemaManager: {file_description} not found: {file_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(
                f"SchemaManager: Invalid JSON in {file_description} {file_path}: {e}"
            )
            raise
        except OSError as e:
            logger.error(
                f"SchemaManager: Could not read {file_description} {file_path}: {e}"
            )
            raise

    def _fetch_from_url_and_write_to_cache(self) -> dict[str, Any] | None:
        logger.info(
            f"SchemaManager: Attempting to download schema from URL: {self.schema_url}"
        )
        content = None
        try:
            response = requests.get(self.schema_url, timeout=self.requests_timeout)
            response.raise_for_status()
            content = response.json()
            self._set_source(SchemaSource.URL, self.schema_url)
            logger.info(
                f"SchemaManager: Successfully downloaded schema: {self.source_message}"
            )

            # Save to file cache when download was successfull
            cache_filepath = self._get_cached_schema_filepath_for_url()
            if cache_filepath:
                try:
                    with open(cache_filepath, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=2)
                    logger.info(
                        f"SchemaManager: Schema content saved to file cache: {cache_filepath}"
                    )
                except OSError as e:
                    logger.warning(
                        f"SchemaManager: Could not write to file cache {cache_filepath}. Error: {e}"
                    )
            return content  # type: ignore[no-any-return]
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"SchemaManager: Failed to download schema from {self.schema_url}. Error: {e}"
            )
        except json.JSONDecodeError as e:
            logger.warning(
                f"SchemaManager: Content from {self.schema_url} is not valid JSON. Error: {e}"
            )
        return None

    def _load_bundled(self) -> dict[str, Any]:
        logger.info(
            f"SchemaManager: Attempting to load bundled schema: {self.bundled_package_ref}/{self.bundled_filename}"
        )
        try:
            schema_resource = (
                importlib.resources.files(self.bundled_package_ref)
                / self.bundled_filename
            )
            with schema_resource.open(encoding="utf-8") as sf:
                content = json.load(sf)
            self._set_source(
                SchemaSource.BUNDLED,
                f"{self.bundled_package_ref}/{self.bundled_filename}",
            )
            logger.info(
                f"SchemaManager: Successfully loaded schema: {self.source_message}"
            )
            return content  # type: ignore[no-any-return]
        except Exception as e:
            msg = f"CRITICAL - Failed to load bundled schema ({self.bundled_package_ref}/{self.bundled_filename}). Error: {e}"
            logger.critical(msg)
            raise RuntimeError(msg) from e

    def _load_and_validate_schema(self):
        """Core Logic: Loading, validating and saving schema.

        Order: URL (fresh download) -> Bundled Fallback -> Save to file cache.
        Populates self.schema_content and self.source_message.
        """
        loaded_content = None
        loaded_content = self._fetch_from_url_and_write_to_cache()
        if loaded_content is None:
            logger.warning(
                f"SchemaManager: URL fetch for {self.schema_url} failed. Using bundled schema."
            )
            loaded_content = self._load_bundled()

        self._verify_schema_version(loaded_content)
        validator = self._validator_for_configured_version()

        try:
            validator.check_schema(loaded_content)
            logger.info(
                f"SchemaManager: Schema ({self.source_message}) meta-validation successful."
            )
            self.schema_content = loaded_content
        except SchemaError as e:
            logger.error(
                f"SchemaManager: META-VALIDATION FAILED for schema from '{self.source_message}': {e.message}"
            )
            raise SchemaError(
                f"Schema obtained from '{self.source_message}' is invalid."
            ) from e

    def _verify_schema_version(self, loaded_content: dict[str, Any]) -> None:
        """Reject a loaded schema whose dialect differs from the configured version.

        Args:
            loaded_content (dict[str, Any]): The schema just loaded, before use.

        Raises:
            SchemaError: If the schema declares no ``$schema`` dialect, or one that
                does not match :attr:`schema_version` — the manager is not
                configured to validate against that version.
        """
        dialect = loaded_content.get("$schema")
        declared_version = _SCHEMA_DIALECT_VERSIONS.get(dialect) if dialect else None
        if declared_version != self.schema_version:
            msg = (
                f"SchemaManager is not configured for the loaded schema version: "
                f"declared '$schema'={dialect!r} (version {declared_version!r}), "
                f"configured version {self.schema_version!r}."
            )
            logger.error(msg)
            raise SchemaError(msg)

    def _validator_for_configured_version(self) -> type[Draft202012Validator]:
        """Select the validator class for the configured schema version.

        Raises:
            ValueError: If :attr:`schema_version` is not one this manager supports.

        Returns:
            type[Draft202012Validator]: The matching jsonschema validator class.
        """
        match self.schema_version:
            case "2020-12":
                return Draft202012Validator
            case _:
                msg = f"Unsupported schema version configured: {self.schema_version!r}."
                logger.error(msg)
                raise ValueError(msg)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id=0x{id(self):x}, schema_loaded={'True' if self.schema_content else 'False'}, source={self.source_message})>"

    def __str__(self) -> str:
        return str(self.schema_content)


# --- Singleton-like instance (module-level) ---
NGMNSchema = SchemaManager()
