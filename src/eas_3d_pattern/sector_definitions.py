import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# --- Preset constants ---
NGMN_TYPE_A_THETA_HPBW_MIN: float = 0.5
NGMN_TYPE_A_THETA_HPBW_MAX: float = 25.0
NGMN_TYPE_A_SECTOR_PHI_MIN: float = 50.0
NGMN_TYPE_A_SECTOR_PHI_MAX: float = 130.0
NGMN_TYPE_A_THETA3: float = 165.0
NGMN_TYPE_A_THETA4: float = 180.0

EAS_THETA_WASTED_BORDER: float = 70.0
EAS_THETA_EMF_BORDER: float = 165.0
EAS_THETA_LOWER: float = 180.0
EAS_SECTOR_PHI_HALF: float = 60.0


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
        return f"'{self.name}': \t[{self.theta_min[0]:.1f}{self.theta_min[1]}Theta{self.theta_max[1]}{self.theta_max[0]:.1f}], [{self.phi_min[0]:.1f}{self.phi_min[1]}Phi{self.phi_max[1]}{self.phi_max[0]:.1f}]"


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
            theta_max=(EAS_THETA_EMF_BORDER, "<="),
            phi_min=(-EAS_SECTOR_PHI_HALF, "<="),
            phi_max=(EAS_SECTOR_PHI_HALF, "<="),
        )
        self.add_sector(
            name="Int1",
            theta_min=(top_border, "<="),
            theta_max=(EAS_THETA_EMF_BORDER, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(-EAS_SECTOR_PHI_HALF, "<"),
        )
        self.add_sector(
            name="Int2",
            theta_min=(top_border, "<="),
            theta_max=(EAS_THETA_EMF_BORDER, "<="),
            phi_min=(EAS_SECTOR_PHI_HALF, "<"),
            phi_max=(180.0, "<"),
        )
        self.add_sector(
            name="Int3",
            theta_min=(EAS_THETA_WASTED_BORDER, "<="),
            theta_max=(top_border, "<"),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        self.add_sector(
            name="EMF",
            theta_min=(EAS_THETA_EMF_BORDER, "<"),
            theta_max=(EAS_THETA_LOWER, "<="),
            phi_min=(-180.0, "<="),
            phi_max=(180.0, "<"),
        )
        self.add_sector(
            name="Wasted",
            theta_min=(0.0, "<="),
            theta_max=(EAS_THETA_WASTED_BORDER, "<"),
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

    @classmethod
    def presets(cls) -> list[str]:
        """Return the list of available sector preset names.

        Returns:
            list[str]: Names that can be passed to ``from_preset()``.
        """
        return list(_PRESET_REGISTRY.keys())

    @classmethod
    def from_preset(cls, name: str, **kwargs: Any) -> "SectorDefinition":
        """Create a SectorDefinition from a named preset.

        Args:
            name: Preset identifier (see ``presets()`` for valid names).
            **kwargs: Parameters required by the specific preset builder.

        Returns:
            SectorDefinition: Configured instance with sectors loaded.

        Raises:
            ValueError: If the preset name is not recognized.

        Example:
            >>> sectors = SectorDefinition.from_preset("eas", top_border=85.0)
            >>> sectors = SectorDefinition.from_preset(
            ...     "ngmn-v13-type-a",
            ...     theta_beam_peak=96.0,
            ...     theta_hpbw=7.0,
            ...     nominal_sector_phi=120.0,
            ... )
        """
        if name not in _PRESET_REGISTRY:
            available = ", ".join(_PRESET_REGISTRY.keys())
            raise ValueError(
                f"SectorDefinition: Unknown preset '{name}'. Available presets: {available}"
            )
        builder = _PRESET_REGISTRY[name]
        return builder(**kwargs)

    def __str__(self):
        if not self.sectors:
            return "SectorDefinition (No sectors defined)"
        output = [f"SectorDefinition ({len(self.sectors)} defined Sectors)"]
        for sector_box in self.sectors.values():
            output.append(f"{sector_box}")
        return "\n".join(output)


# --- Preset builder functions ---


def _build_eas_preset(top_border: float, **_kwargs: Any) -> SectorDefinition:
    """Build the traditional EAS sector definition.

    Args:
        top_border: Upper theta boundary in degrees (typically from -3 dB point).
        **_kwargs: Unused, absorbed for registry interface compatibility.

    Returns:
        SectorDefinition with the 6 EAS sectors.
    """
    return SectorDefinition(load_default=True, top_border=top_border)


def _build_ngmn_type_a_preset(
    theta_beam_peak: float,
    theta_hpbw: float,
    phi_nominal_direction: float = 0.0,
    nominal_sector_phi: float = 120.0,
    **_kwargs: Any,
) -> SectorDefinition:
    """Build NGMN BASTA V13 Type A sector definition.

    Computes AR boundaries per NGMN BASTA V13.0, Section 7.2.4, Table 7-1,
    Type A: Macro BS Beam.

    The Interference AR (non-rectangular) is decomposed into 3 rectangular
    sub-regions: left, right, and upper strips around the Service AR.

    Args:
        theta_beam_peak: Beam peak theta in degrees (internal coord system).
        theta_hpbw: Elevation half-power beamwidth in degrees.
        phi_nominal_direction: Nominal azimuth direction in degrees. Defaults to 0.
        nominal_sector_phi: Nominal sector width in degrees. Defaults to 120.
        **_kwargs: Unused, absorbed for registry interface compatibility.

    Returns:
        SectorDefinition with 6 sectors: Service, Interference_Left,
        Interference_Right, Interference_Upper, Upper, Lower.

    Raises:
        ValueError: If parameters fall outside NGMN Type A applicability constraints.
    """
    if not (NGMN_TYPE_A_THETA_HPBW_MIN <= theta_hpbw <= NGMN_TYPE_A_THETA_HPBW_MAX):
        raise ValueError(
            f"SectorDefinition: NGMN Type A requires HPBW_θ in "
            f"[{NGMN_TYPE_A_THETA_HPBW_MIN}°, {NGMN_TYPE_A_THETA_HPBW_MAX}°], "
            f"got {theta_hpbw}°."
        )
    if not (
        NGMN_TYPE_A_SECTOR_PHI_MIN <= nominal_sector_phi <= NGMN_TYPE_A_SECTOR_PHI_MAX
    ):
        raise ValueError(
            f"SectorDefinition: NGMN Type A requires NominalSector_φ in "
            f"[{NGMN_TYPE_A_SECTOR_PHI_MIN}°, {NGMN_TYPE_A_SECTOR_PHI_MAX}°], "
            f"got {nominal_sector_phi}°."
        )

    # Table 7-1 boundary formulas
    theta_1 = min(90.0, theta_beam_peak - theta_hpbw)
    theta_2 = theta_beam_peak - theta_hpbw / 2.0
    theta_3 = NGMN_TYPE_A_THETA3
    theta_4 = NGMN_TYPE_A_THETA4
    phi_1 = phi_nominal_direction - nominal_sector_phi / 2.0
    phi_2 = phi_nominal_direction + nominal_sector_phi / 2.0

    instance = SectorDefinition(load_default=False)

    # Service AR: [theta_2, theta_3] x [phi_1, phi_2]
    instance.add_sector(
        name="Service",
        theta_min=(theta_2, "<="),
        theta_max=(theta_3, "<="),
        phi_min=(phi_1, "<="),
        phi_max=(phi_2, "<="),
    )

    # Interference AR decomposed into 3 rectangles:
    # Left strip: [theta_1, theta_3] x [-180, phi_1)
    instance.add_sector(
        name="Interference_Left",
        theta_min=(theta_1, "<="),
        theta_max=(theta_3, "<="),
        phi_min=(-180.0, "<="),
        phi_max=(phi_1, "<"),
    )

    # Right strip: [theta_1, theta_3] x (phi_2, 180)
    instance.add_sector(
        name="Interference_Right",
        theta_min=(theta_1, "<="),
        theta_max=(theta_3, "<="),
        phi_min=(phi_2, "<"),
        phi_max=(180.0, "<"),
    )

    # Upper strip: [theta_1, theta_2) x [phi_1, phi_2]
    instance.add_sector(
        name="Interference_Upper",
        theta_min=(theta_1, "<="),
        theta_max=(theta_2, "<"),
        phi_min=(phi_1, "<="),
        phi_max=(phi_2, "<="),
    )

    # Upper AR: [0, theta_1) x [-180, 180)
    instance.add_sector(
        name="Upper",
        theta_min=(0.0, "<="),
        theta_max=(theta_1, "<"),
        phi_min=(-180.0, "<="),
        phi_max=(180.0, "<"),
    )

    # Lower AR: (theta_3, 180] x [-180, 180)
    instance.add_sector(
        name="Lower",
        theta_min=(theta_3, "<"),
        theta_max=(theta_4, "<="),
        phi_min=(-180.0, "<="),
        phi_max=(180.0, "<"),
    )

    logger.debug(
        f"SectorDefinition: Loaded NGMN Type A preset with ϑ₁={theta_1:.1f}°, "
        f"ϑ₂={theta_2:.1f}°, ϑ₃={theta_3:.1f}°, φ₁={phi_1:.1f}°, φ₂={phi_2:.1f}°."
    )
    return instance


# --- Preset registry ---
_PRESET_REGISTRY: dict[str, Callable[..., SectorDefinition]] = {
    "eas": _build_eas_preset,
    "ngmn-v13-type-a": _build_ngmn_type_a_preset,
}
