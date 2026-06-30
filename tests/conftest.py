"""Shared pytest fixtures for eas-3d-pattern tests.

Provides a synthetic NGMN-BASTA-like antenna pattern factory so tests can run
fast and offline without depending on the multi-megabyte bundled sample data.
The factory writes a minimal valid 3drp JSON file to a temp path and returns
that path, which is what ``AntennaPattern`` consumes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

# Default uniform grid: theta 0..180, phi -180..179 (SPCS_Ericsson native range).
DEFAULT_THETA_SAMPLING = [0.0, 5.0, 180.0]
DEFAULT_PHI_SAMPLING = [-180.0, 5.0, 175.0]


def _grid(sampling: list[float]) -> np.ndarray:
    """Build a 1D grid from a [start, step, stop] NGMN sampling triple."""
    start, step, stop = sampling
    return np.arange(start, stop + 1e-6, step)


def build_pattern_dict(
    coordinate_system: str = "SPCS_Ericsson",
    theta_sampling: list[float] | None = None,
    phi_sampling: list[float] | None = None,
    peak_theta: float = 90.0,
    peak_phi: float = 0.0,
    theta_rolloff: float = 0.05,
    phi_rolloff: float = 0.01,
    max_attenuation: float = 40.0,
    data_set: list[list[float]] | None = None,
    row_structure: list[str] | None = None,
    extra: dict | None = None,
) -> dict:
    """Build a minimal valid NGMN 3drp pattern dictionary.

    The synthetic main beam is a separable quadratic roll-off in theta and phi
    centered on ``(peak_theta, peak_phi)``, clipped at ``max_attenuation`` dB.
    """
    theta_sampling = theta_sampling or list(DEFAULT_THETA_SAMPLING)
    phi_sampling = phi_sampling or list(DEFAULT_PHI_SAMPLING)
    thetas = _grid(theta_sampling)
    phis = _grid(phi_sampling)

    if data_set is None:
        rows: list[list[float]] = []
        for th in thetas:
            for ph in phis:
                atten = (
                    theta_rolloff * (th - peak_theta) ** 2
                    + phi_rolloff * (ph - peak_phi) ** 2
                )
                atten = float(min(atten, max_attenuation))
                # MagAttenuationTP, MagAttenuationCo, MagAttenuationCr
                rows.append([atten, atten, atten + 20.0])
        data_set = rows
        row_structure = [
            "MagAttenuationTP",
            "MagAttenuationCo",
            "MagAttenuationCr",
        ]

    pattern: dict = {
        "Coordinate_System": coordinate_system,
        "Gain": {"value": 15.0, "unit": "dBi"},
        "Phi_HPBW": 65.0,
        "Theta_HPBW": 7.0,
        "Front_to_Back": 30.0,
        "Theta_Sampling": theta_sampling,
        "Phi_Sampling": phi_sampling,
        "Data_Set_Row_Structure": row_structure,
        "Data_Set": data_set,
    }
    if extra:
        pattern.update(extra)
    return pattern


@pytest.fixture
def pattern_path(tmp_path: Path) -> Callable[..., str]:
    """Return a factory that writes a synthetic pattern JSON and returns its path."""
    counter = {"n": 0}

    def _make(**kwargs) -> str:
        pattern = build_pattern_dict(**kwargs)
        counter["n"] += 1
        file_path = tmp_path / f"pattern_{counter['n']}.json"
        file_path.write_text(json.dumps(pattern), encoding="utf-8")
        return str(file_path)

    return _make
