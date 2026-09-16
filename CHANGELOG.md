# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- This changelog.
- Test coverage for the metadata properties, the two plotting methods, and the directivity
  calculations, plus dedicated tests added alongside the parser decomposition (coordinates,
  loader, normalization, non-uniform loading, processing, efficiency, peak). The suite grew
  from 44 to **228 tests** and `src` statement coverage to **88%**.
  Covers metadata unit conversion, the required/optional key split, the `plot()` /
  `plot_3D()` returned items , and which data array is drawn on which axis, with which 
  colour range and scale.
- Correctness tests for `calculate_directivity()` and `calculate_losses()`, which were
  previously at 8% and 20% statement coverage and are now fully covered. Directivity is
  verified against closed-form analytical values for isotropic, `sin^2`, `sin^4` and
  `cos^2` patterns, plus a check that total solid angle integrates to 4*pi and that the
  `sin(theta)` weighting is present (without it, pole-peaked and equator-peaked patterns
  would wrongly compare equal).
- Baseline-image regression tests for `plot()` and `plot_3D()`. Rendered PNGs are stored
  in `tests/fixtures/` and compared with `matplotlib.testing.compare.compare_images`, so
  purely visual regressions (title placement, tick intervals, colour-bar geometry, figure
  height) are caught. Baselines are generated from the bundled NGMN samples, covering both
  uniform and non-uniform sampling, and are regenerated with
  `EAS_UPDATE_BASELINES=1 pytest tests/test_plot.py`.
- An `image` pytest marker for the baseline-image tests. Renderer output can vary between
  environments, so they can be excluded with `pytest -m "not image"`.
- Development dependencies: `jupyterlab`, `matplotlib` and `pytest-mpl` (test-only, for
  image comparison), and `pytest-cov`. None of these affect the published wheel.
- A `verify()` guard helper in `eas_3d_pattern.util_func.guards`: a single check-and-raise
  utility (log an error and raise a chosen exception when a condition is falsy) that
  replaces the repeated inline `if ...: logger.error(...); raise ...` blocks across the
  parser, processing, metrics, coordinates and sector modules. Covered by `test_guards.py`.
- `json_load()` in `eas_3d_pattern.ngmn.loader` (also re-exported from `eas_3d_pattern.ngmn`):
  reads a pattern file and normalizes vendor-specific keys in one call, composed from the
  pure `load_json_file()` and `normalize_keys()` helpers.

### Changed

- The sector code moved from the single `sector_definitions.py` module into a
  `sector/` package: `sector.definitions` (the `BoundaryBox` region and the `Sector`
  collection), `sector.presets` (the `SectorPreset` base and the `from_preset` /
  `preset_names` / `validate_preset` registry helpers), and one module per preset
  (`sector.eas_preset.EasPreset`, `sector.ngmn_type_a_preset.NgmnTypeAPreset`). Presets
  are now `SectorPreset` subclasses with a `load()` method rather than free builder
  functions. The public names (`SectorDefinition`, `BoundaryBoxSquare`) remain importable
  from `eas_3d_pattern` unchanged; `BoundaryBox`, `Sector`, and the preset helpers are new
  public names exported from `eas_3d_pattern.sector`.

- Internal refactor (no public API change): the `AntennaPattern` god class was decomposed.
  Logic moved out of `parser.py` (1140 → 422 lines) into `ngmn/` (`loader`, `coordinates`,
  `metadata`) and `metrics/` (`directivity`, `efficiency`, `peak`, `quadrature`) sub-packages,
  plus `processing.py` and `plotting.py`. The public import surface (`AntennaPattern`,
  `SectorDefinition`, `NGMNSchema`, `SAMPLE_JSON`, `generate_report_eas`) is unchanged.

- **BREAKING** — `AntennaPattern(data_filepath=...)` now accepts `str | pathlib.Path`
  (previously `str` only), and the stored `AntennaPattern.data_filepath` attribute is now a
  `pathlib.Path` regardless of the input type (previously the raw `str` was passed). Code that
  passed a `str` continues to work; code that read `pattern.data_filepath` and relied on it
  being a `str` (e.g. calling `str`-only methods on it) must wrap it in `str(...)` or use the
  `Path` API. Internally, `os.path` was replaced by `pathlib` in `__init__` and `__str__`.

- **BREAKING** — Corrected the spelling of two public properties on `AntennaPattern`. 
  No deprecation aliases are provided; the old names are removed.

  | Old name | New name |
  |----------|----------|
  | `AntennaPattern.phi_eletrical_pan` | `AntennaPattern.phi_electrical_pan` |
  | `AntennaPattern.theta_eletrical_tilt` | `AntennaPattern.theta_electrical_tilt` |

  Migration: rename any attribute access. The underlying NGMN JSON
  keys (`Phi_Electrical_Pan`, `Theta_Electrical_Tilt`) were always spelled correctly
  and are unaffected, as is the output of `print(pattern)`.

- `AntennaPattern.plot()` and `AntennaPattern.plot_3D()` return annotations are now
  `go.Figure | None` (was `None | go.Figure`). No behavioural change.
- Reworded a `calculate_directivity()` docstring note for clarity.
- Renamed the loaded-payload attribute `AntennaPattern.raw_data` to
  `AntennaPattern.data`. The payload is normalized on load (vendor key variants are
  mapped to their canonical NGMN names). The old name is preserved as a deprecated 
  alias (see *Deprecated*), so existing code keeps working; migrate attribute access 
  from `pattern.raw_data` to `pattern.data`.
- Renamed the processed-dataset attribute `AntennaPattern.Pattern_3D` to
  `AntennaPattern.pattern` (PEP 8 lowercase, dropped the redundant `_3D` suffix). The
  old name is preserved as a deprecated alias (see *Deprecated*); migrate attribute
  access from `antenna.Pattern_3D` to `antenna.pattern`.

### Removed

- The internal Ericsson document link from the `calculate_beam_efficiency()` docstring.
  It pointed at an eridoc URL not reachable from the outside and exposed an internal
  document identifier in a public repository. 
  The EAS beam-efficiency methodology will be documented publicly instead.

### Deprecated

- `BoundaryBoxSquare` is renamed to `BoundaryBox` (the "Square" suffix was
  redundant). `BoundaryBoxSquare` remains as an alias for backward compatibility and
  is scheduled for removal in a future release; use `BoundaryBox` instead. The class
  also no longer carries a `name` field: a box is a pure geometry value object, and
  the owning `Sector`/`SectorDefinition` names it via its dict key.

- The `SectorDefinition(load_default=..., top_border=...)` constructor path is
  deprecated in favour of the preset builder
  `SectorDefinition.from_preset("eas", top_border=...)` (for the EAS sectors) or
  `SectorDefinition(load_default=False)` (for an empty instance). **This is not a
  breaking change: the constructor still works exactly as before.** `load_default`
  still defaults to `True` and still requires `top_border`, so existing calls keep
  their current behaviour; they now additionally emit a `DeprecationWarning`
  pointing at the replacement. The EAS sector geometry has moved out of
  `SectorDefinition` into the `eas` preset builder, and the deprecated path simply
  delegates to it, so the loaded sectors are identical. The `load_default` /
  `top_border` parameters are scheduled for removal in a future release, at which
  point `SectorDefinition()` will construct an empty instance.

  ```python
  # Deprecated — emits a DeprecationWarning (still works):
  sectors = SectorDefinition(load_default=True, top_border=85.0)  # EAS sectors
  sectors = SectorDefinition(load_default=False)  # empty instance

  # New way:
  from eas_3d_pattern.sector import from_preset, Sector

  sectors = from_preset("eas", top_border=85.0)  # EAS sectors
  sectors = Sector()  # empty instance

  # Still supported (SectorDefinition classmethod delegates to the preset registry):
  sectors = SectorDefinition.from_preset("eas", top_border=85.0)
  ```
- `AntennaPattern.Pattern_3D` is now a deprecated read-only alias for
  `AntennaPattern.pattern` and emits a `DeprecationWarning`. It returns the same
  `xarray.Dataset` object as `pattern` (not a copy). Scheduled for removal in a
  future release; use `antenna.pattern` instead.
- `AntennaPattern.raw_data` is now a deprecated read-only alias for
  `AntennaPattern.data` and emits a `DeprecationWarning`. It returns the same
  dictionary object as `data` (not a copy), so in-place mutation through the alias
  still reaches the underlying payload. Scheduled for removal in a future release;
  use `pattern.data` instead.
- `AntennaPattern.is_nonuniform_sampling` now emits a `DeprecationWarning` and is
  scheduled for removal in a future release. It is exactly the negation of
  `is_uniform_sampling`; use `not pattern.is_uniform_sampling` instead.

### Fixed

- Corrected the `Returns:` docstring on `plot()` and `plot_3D()`, which described the
  `show_fig` contract backwards. Both return the figure when `show_fig=False`, and `None`
  when `show_fig=True` (the figure is displayed instead) — the documentation stated the
  inverse. Behaviour was always correct; only the docs were wrong.
- Typo in the `Showcase_EAS_3D_Pattern` notebook ("adiation" → "radiation"), and removed a
  stale reference to batch reporting from its feature table.
- Grammar and typo corrections across the example notebooks (11 items).

## [v0.1.4] - 2026-07-27

Released prior to the introduction of this changelog. See the
[GitHub releases](https://github.com/Ericsson/eas-3d-pattern/releases) page for
notes on this and earlier versions.

[Unreleased]: https://github.com/Ericsson/eas-3d-pattern/compare/v0.1.4...HEAD
[v0.1.4]: https://github.com/Ericsson/eas-3d-pattern/releases/tag/v0.1.4
