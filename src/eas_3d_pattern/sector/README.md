# Sector presets: EAS vs. NGMN BASTA V13 Type A

This package defines the angular regions used for **beam-efficiency** calculations —
the fraction of an antenna's radiated power that falls into named regions of the
θ/φ sphere. Two presets are provided, selectable via
`from_preset("eas", ...)` / `from_preset("ngmn-v13-type-a", ...)`.

Both split the sphere into rectangular `BoundaryBox` regions in (θ, φ) and integrate
power over each. The difference is **how the region boundaries are chosen** and
**what the regions represent**.

## Quick comparison

| | **EAS** (`eas`) | **NGMN Type A** (`ngmn-v13-type-a`) |
|---|---|---|
| Origin | Ericsson EAS convention | NGMN BASTA V13.0, §7.2.4, Table 7-1 (Macro BS Beam) |
| Regions | `Cell`, `Int1`, `Int2`, `Int3`, `EMF`, `Wasted` (6) | `Service`, `Interference_Left/Right/Upper`, `Upper`, `Lower` (6) |
| Elevation (θ) borders | **Mostly fixed** constants (70°, 165°, 180°); only the top border is beam-derived | **Beam-derived**: ϑ₁, ϑ₂ computed from beam peak and elevation HPBW (ϑ₃ = 165° is a fixed constant) |
| Azimuth (φ) borders | **Fixed** ±60° around boresight | **Configurable** sector `[φ₁, φ₂]` from the nominal sector direction and width |
| Inputs | `top_border` (typically the −3 dB point) | `theta_beam_peak`, `theta_hpbw`, `phi_nominal_direction`, `nominal_sector_phi` |
| Adapts to the beam? | Only the top border | Yes — elevation regions track the beam's peak and width |

## EAS

The EAS layout uses **fixed angular thresholds** for most borders, with only the
`top_border` (usually the pattern's −3 dB elevation point) supplied per antenna:

- `Cell` — the intended service region: `[top_border, 165°]` in θ, `±60°` in φ.
- `Int1` / `Int2` — interference to either azimuth side of the cell (same θ band,
  φ outside ±60°).
- `Int3` — the elevation band just above the cell (`[70°, top_border]`, full azimuth).
- `EMF` — the near-nadir band (`[165°, 180°]`, full azimuth).
- `Wasted` — the near-zenith cap (`[0°, 70°]`, full azimuth).

Because the thresholds are constants, EAS is simple and stable across antennas but
does **not** reshape its regions to the beam beyond the single top border.

## NGMN BASTA V13 Type A

The Type A layout derives its **elevation** boundaries from the beam itself, so the
regions adapt to each antenna's beam peak and elevation half-power beamwidth (HPBW).
Its four conceptual Angular Regions (ARs), per the spec:

- `Service` — the beam-centred coverage window, bounded in elevation by
  `[ϑ₂, ϑ₃]` and in azimuth by the nominal sector `[φ₁, φ₂]`.
- `Interference` — out-of-sector leakage flanking the service window; here decomposed
  into three rectangles (`Interference_Left`, `Interference_Right`, `Interference_Upper`)
  because the region is L-/U-shaped and `BoundaryBox` is rectangular.
- `Upper` — the near-zenith cap over the full azimuth (sky-side waste).
- `Lower` — the near-nadir cap over the full azimuth (ground radiation).

Key boundary facts (see `ngmn_type_a_preset.py` for the exact formulas):

- `ϑ₁ = min(90°, ϑ_peak − HPBW_θ)` and `ϑ₂ = ϑ_peak − HPBW_θ/2` — **beam-derived**.
- `ϑ₃ = 165°`, `ϑ₄ = 180°` — **fixed constants**.
- `[φ₁, φ₂]` — the nominal sector, centred on `phi_nominal_direction` with width
  `nominal_sector_phi`.

**Applicability constraints** (Type A is defined only within these ranges):

- Elevation HPBW: `0.5° ≤ HPBW_θ ≤ 25°`.
- Azimuth HPBW: `50° ≤ HPBW_φ ≤ 130°`.

Values outside these raise a `ValueError`.

## In short

EAS answers "how much power lands in a fixed set of angular buckets," while NGMN
Type A answers "how much power lands in regions defined relative to *this* beam"
(Angular Region Efficiency) — a beam-specific figure of merit for spatial focusing,
comparable across antennas because the regions are defined by each beam's own geometry.

## Extending

A new preset is a `SectorPreset` subclass with a `name` and a `load(...) -> Sector`
method, registered in `presets.py`. See `eas_preset.py` and `ngmn_type_a_preset.py`
for worked examples.
