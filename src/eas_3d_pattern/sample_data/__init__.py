import importlib.resources
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_JSON: list[Path] = []

try:
    resource_names = list(importlib.resources.contents(__package__))
    resource_names.sort()

    for item_name in resource_names:
        if item_name.endswith(".json") and importlib.resources.is_resource(
            __package__, item_name
        ):
            try:
                with importlib.resources.path(__package__, item_name) as path_context:
                    resolved_path = Path(path_context)

                if resolved_path.is_file():
                    SAMPLE_JSON.append(resolved_path)
                else:
                    logger.warning(
                        f"Path for sample '{item_name}' in '{__package__}' "
                        f" ('{resolved_path}') was not a file after context. Skipping."
                    )
            except FileNotFoundError:
                logger.warning(
                    f"Sample file '{item_name}' listed but not found by "
                    f"importlib.resources.path in '{__package__}'. Skipping."
                )
            except Exception as e_path:
                logger.error(
                    f"Error resolving path for sample '{item_name}' in '{__package__}': {e_path}"
                )

    if SAMPLE_JSON:
        logger.debug(
            f"Found and resolved paths for {len(SAMPLE_JSON)} sample(s) in '{__package__}'."
        )
    else:
        logger.debug(
            f"No .json sample files found or resolved in '{__package__}'. "
            "Ensure files exist, have .json extension, and 'include' "
            "in pyproject.toml is correct for 'sample_data/*.json'."
        )

except ModuleNotFoundError:
    logger.error(
        f"Could not resolve current package '{__package__}' for listing samples."
    )
except Exception as e:
    logger.error(
        f"Error populating sample file lists in '{__package__}': {e}", exc_info=True
    )


__all__ = [
    "SAMPLE_JSON",
]
