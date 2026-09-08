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
  from 44 to **189 tests** and `src` statement coverage to **88%**.
  Covers metadata unit conversion, the required/optional key split, the `plot()` /
  `plot_3D()` return contract, and — for the plots — which data array is drawn on which
  axis, with which colour range and scale.
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

### Changed

- Internal refactor (no public API change): the `AntennaPattern` god class was decomposed.
  Logic moved out of `parser.py` (1140 → 422 lines) into `ngmn/` (`loader`, `coordinates`,
  `metadata`) and `metrics/` (`directivity`, `efficiency`, `peak`, `quadrature`) sub-packages,
  plus `_processing.py` and `_plotting.py`. The public import surface (`AntennaPattern`,
  `SectorDefinition`, `NGMNSchema`, `SAMPLE_JSON`, `generate_report_eas`) is unchanged.

- **BREAKING** — `AntennaPattern(data_filepath=...)` now accepts `str | pathlib.Path`
  (previously `str` only), and the stored `AntennaPattern.data_filepath` attribute is now a
  `pathlib.Path` regardless of the input type (previously the raw `str` as passed). Code that
  passed a `str` continues to work; code that read `pattern.data_filepath` and relied on it
  being a `str` (e.g. calling `str`-only methods on it) must wrap it in `str(...)` or use the
  `Path` API. Internally, `os.path` was replaced by `pathlib` in `__init__` and `__str__`.

- **BREAKING** — Corrected the spelling of two misspelled public properties on
  `AntennaPattern`. No deprecation aliases are provided; the old names are removed
  outright.

  | Old name | New name |
  |----------|----------|
  | `AntennaPattern.phi_eletrical_pan` | `AntennaPattern.phi_electrical_pan` |
  | `AntennaPattern.theta_eletrical_tilt` | `AntennaPattern.theta_electrical_tilt` |

  Migration: rename any attribute access in your own code. The underlying NGMN JSON
  keys (`Phi_Electrical_Pan`, `Theta_Electrical_Tilt`) were always spelled correctly
  and are unaffected, as is the output of `print(pattern)`.

- `AntennaPattern.plot()` and `AntennaPattern.plot_3D()` return annotations are now
  `go.Figure | None` (was `None | go.Figure`). No behavioural change.
- Reworded a `calculate_directivity()` docstring note for clarity.
- Renamed the loaded-payload attribute `AntennaPattern.raw_data` to
  `AntennaPattern.data`. The payload is normalized on load (vendor key variants are
  mapped to their canonical NGMN names), so `raw_data` was a misnomer. The old name
  is preserved as a deprecated alias (see *Deprecated*), so existing code keeps
  working; migrate attribute access from `pattern.raw_data` to `pattern.data`.
- Renamed the processed-dataset attribute `AntennaPattern.Pattern_3D` to
  `AntennaPattern.pattern` (PEP 8 lowercase, dropped the redundant `_3D` suffix). The
  old name is preserved as a deprecated alias (see *Deprecated*); migrate attribute
  access from `antenna.Pattern_3D` to `antenna.pattern`.

### Removed

- The internal Ericsson document link from the `calculate_beam_efficiency()` docstring.
  It pointed at an eridoc URL that external users cannot reach and exposed an internal
  document identifier in a public repository. The EAS beam-efficiency methodology will be
  documented publicly instead (plan section 12.1 / M5-5).

### Deprecated

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
