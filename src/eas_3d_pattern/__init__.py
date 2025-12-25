import logging
from importlib.metadata import PackageNotFoundError, version

from .parser import AntennaPattern
from .sample_data import SAMPLE_JSON
from .schema_manager import NGMNSchema
from .sector_definitions import SectorDefinition
from .util_func.report import generate_report_eas

LIBRARY_PACKAGE_NAME = __name__
library_root_logger = logging.getLogger(LIBRARY_PACKAGE_NAME)
if not library_root_logger.hasHandlers():
    library_root_logger.addHandler(logging.NullHandler())
try:
    __version__ = version(LIBRARY_PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "SAMPLE_JSON",
    "AntennaPattern",
    "NGMNSchema",
    "SectorDefinition",
    "generate_report_eas",
]
