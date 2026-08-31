# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- This changelog.
- Test coverage for the metadata properties, the two plotting methods, and the directivity
  calculations (78 tests), taking the suite from 44 to 122 and `src` coverage to 81%.
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
