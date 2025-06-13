import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundaryBoxSquare:
    """Draws a rectangle in the Theta/Phi plane.

    This class sets boundaries in Theta/Phi for beam efficiency calcuation.
    Theta/Phi are in degrees.
    "<" and "<=" strings are used to indicate lt or le operations.

    Attributes:
        theta_min (tuple[float, str]): The minimum theta value and its comparison operator.
        theta_max (tuple[float, str]): The maximum theta value and its comparison operator.
        phi_min (tuple[float, str]): The minimum phi value and its comparison operator.
        phi_max (tuple[float, str]): The maximum phi value and its comparison operator.
        name (str, optional): The name of the sector. Defaults to "Generic Sector".

    Raises:
        ValueError: If the sector name is empty or limits are invalid.
    """

    theta_min: tuple[float, str]
    theta_max: tuple[float, str]
    phi_min: tuple[float, str]
    phi_max: tuple[float, str]
    name: str = "Generic Sector"

    def __post_init__(self):
        if self.theta_min[0] > self.theta_max[0]:
            logger.error(
                f"SectorDefinition: Cannot add sector '{self.name}': theta_min ({self.theta_min[0]}) cannot be greater than theta_max ({self.theta_max[0]})."
            )
            raise ValueError(
                f"SectorDefinition: Cannot add sector '{self.name}': theta_min ({self.theta_min[0]}) cannot be greater than theta_max ({self.theta_max[0]})."
            )
        if self.phi_min[0] > self.phi_max[0]:
            logger.error(
                f"SectorDefinition: Cannot add sector '{self.name}': phi_min ({self.phi_min[0]}) cannot be greater than phi_max ({self.phi_max[1]})."
            )
            raise ValueError(
                f"SectorDefinition: Cannot add sector '{self.name}': phi_min ({self.phi_min[0]}) cannot be greater than phi_max ({self.phi_max[1]})."
            )

        if (
            (self.theta_min[1] not in ["<", "<="])
            or (self.theta_max[1] not in ["<", "<="])
            or (self.phi_min[1] not in ["<", "<="])
            or (self.phi_max[1] not in ["<", "<="])
        ):
            logger.error(
                f"SectorDefinition: Cannot add sector '{self.name}': Invalid bounds specification, only symbols '<' and '<=' are allowed."
            )
            raise ValueError(
                f"SectorDefinition: Cannot add sector '{self.name}': Invalid bounds specification, only symbols '<' and '<=' are allowed."
            )

    def __str__(self):
        return (
            f"'{self.name}': \t"
            f"[{self.theta_min[0]:.1f}{self.theta_min[1]}Theta{self.theta_max[1]}{self.theta_max[0]:.1f}], "
            f"[{self.phi_min[0]:.1f}{self.phi_min[1]}Phi{self.phi_max[1]}{self.phi_max[0]:.1f}]"
        )


class SectorDefinition:
    """Class that holds all the boundary objects (e.g. 'BoundaryBoxSquare').

    This class uses multiple BoundaryBoxSquare objects as definitions for beam efficiency calculations within 'AntennaPattern'.
    If no arguments are given to __init__, the default rectangular sectors are loaded.
    Currently only support rectangular shapes with 'BoundaryBoxSquare' class.

    Args:
        load_default (bool, optional): Whether to load the default sectors. Defaults to True.
        top_border (float | None, optional): The top border in degrees. Required if load_default is True. Defaults to None.
    """

    def __init__(
        self, load_default: bool = True, top_border: float | None = None
    ) -> None:
        self.sectors: dict[str, BoundaryBoxSquare] = {}
        if load_default:
            if top_border is None:
                logger.error(
                    "SectorDefinition: Must specify 'top_border' in degrees if load_default is True due to dynamic nature."
                )
                raise ValueError(
                    "SectorDefinition: Must specify 'top_border' in degrees if load_default is True due to dynamic nature."
                )
            self._load_default_sectors(top_border=top_border)

    def _load_default_sectors(self, top_border: float) -> None:
        logger.debug(
            "SectorDefinition: Loading default analysis sectors into SectorDefinition."
        )
        self.add_sector(
            name="Cell",
            theta_min=(top_border, "<="),
            theta_max=(165, "<="),
            phi_min=(-60.0, "<="),
            phi_max=(60.0, "<="),
        )
        self.add_sector(
            name="Int1",
            theta_min=(top_border, "<="),
            theta_max=(165, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(-60.0, "<"),
        )
        self.add_sector(
            name="Int2",
            theta_min=(top_border, "<="),
            theta_max=(165, "<="),
            phi_min=(60.0, "<"),
            phi_max=(180.0, "<"),
        )
        self.add_sector(
            name="Int3",
            theta_min=(70.0, "<="),
            theta_max=(top_border, "<"),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        self.add_sector(
            name="EMF",
            theta_min=(165.0, "<"),
            theta_max=(180.0, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        self.add_sector(
            name="Wasted",
            theta_min=(0.0, "<="),
            theta_max=(70.0, "<"),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )

    def add_sector(
        self,
        name: str,
        theta_min: tuple[float, str],
        theta_max: tuple[float, str],
        phi_min: tuple[float, str],
        phi_max: tuple[float, str],
    ) -> None:
        """Adds a sector to the SectorDefinition.

        Args:
            name (str): The name of the sector.
            theta_min (tuple[float, str]): A tuple containing the minimum theta value and its comparison operator.
            theta_max (tuple[float, str]): A tuple containing the maximum theta value and its comparison operator.
            phi_min (tuple[float, str]): A tuple containing the minimum phi value and its comparison operator.
            phi_max (tuple[float, str]): A tuple containing the maximum phi value and its comparison operator.

        Returns:
            None

        Raises:
            ValueError: If the sector name is empty.
        """
        if not name:  # Basic check for name
            logger.error("SectorDefinition: Sector name cannot be empty.")
            raise ValueError("SectorDefinition: Sector name cannot be empty.")
        if name in self.sectors:
            logger.warning(
                f"SectorDefinition: Sector '{name}' already exists. Overwriting with new definition."
            )
        self.sectors[name] = BoundaryBoxSquare(
            theta_min, theta_max, phi_min, phi_max, name
        )
        logger.debug(
            f"SectorDefinition: Added/Updated sector: '{name}' - {self.sectors[name]}"
        )
        return

    def clear_sectors(self) -> None:
        """Clears all the sectors from the SectorDefinition.

        Returns:
            None
        """
        self.sectors = {}
        logger.info("SectorDefinition: All sectors cleared from SectorDefinition.")

    def __str__(self):
        if not self.sectors:
            return "SectorDefinition (No sectors defined)"
        output = [f"SectorDefinition ({len(self.sectors)} defined Sectors)"]
        for sector_box in self.sectors.values():
            output.append(f"{sector_box}")
        return "\n".join(output)
