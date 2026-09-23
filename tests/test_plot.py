"""Tests for ``AntennaPattern.plot()`` and ``AntennaPattern.plot_3D()``.

Three layers, deliberately:

1. ``TestPlotContract`` / ``TestPlot3DContract`` — the call contract: return type, the
   ``show_fig`` behaviour, component validation.
2. ``TestPlotContent`` / ``TestPlot3DContent`` — what the figure actually *contains*:
   which data array was plotted, on which axis, with which colour range. Type-and-shape
   assertions alone cannot catch a figure that is well-formed but wrong.
3. ``TestFigureSpecSnapshot`` — a golden snapshot of the full serialized figure spec,
   stored under ``tests/fixtures/``. This is the regression net for the planned
   god-class decomposition, which must move code without altering any figure.

All tests pass ``show_fig=False``; with ``show_fig=True`` the methods call ``fig.show()``,
which tries to open a browser renderer.

Regenerating the baselines after an *intentional* plot change::

    EAS_UPDATE_BASELINES=1 poetry run pytest tests/test_plot.py

Then open the resulting PNGs in ``tests/fixtures/`` and confirm they look right before
committing them.

Baselines are PNGs rather than serialized figure specs: they are human-readable, render
inline in pull-request diffs, and catch purely visual regressions (title placement, tick
spacing, colour-bar geometry, figure height) that attribute assertions do not. Comparison
uses ``matplotlib.testing.compare.compare_images``, which works on any PNG pair regardless
of which library drew it — so it applies to today's plotly output and will carry over
unchanged after the planned matplotlib migration. ``pytest-mpl`` is installed alongside it
for that migration, when ``@pytest.mark.mpl_image_compare`` becomes usable directly.

Image tests carry the ``image`` marker. Rendering can vary with the kaleido/Chromium
build, so if they prove unstable on a runner they can be excluded with::

    poetry run pytest -m "not image"
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest
from matplotlib.testing.compare import compare_images
from matplotlib.testing.exceptions import ImageComparisonFailure

from eas_3d_pattern import SAMPLE_JSON, AntennaPattern

# Components derived by the parser from the NGMN attenuation columns.
PLOTTABLE_COMPONENTS = ["P_tp_dB", "P_co_dB", "P_cr_dB"]

# Bundled sample indices, named so the image baselines are not opaque magic numbers.
SAMPLE_NON_UNIFORM = 0  # VENDOR_ANTMODEL1_2100 ... NonUniformSampling
SAMPLE_UNIFORM = 1  # VENDOR_ANTMODEL2_2100 ... UniformSampling

FIXTURE_DIR = Path(__file__).parent / "fixtures"
UPDATE_BASELINES = os.environ.get("EAS_UPDATE_BASELINES") == "1"

# RMS tolerance for baseline image comparison. Small enough to catch a moved title or a
# changed tick interval, loose enough to absorb anti-aliasing noise between renders.
IMAGE_RMS_TOLERANCE = 1.0

# plot() pins the heatmap colour range to the normalized dB window.
EXPECTED_HEATMAP_ZMIN = -30
EXPECTED_HEATMAP_ZMAX = 0
EXPECTED_COLORSCALE_NAME = "turbo"


@pytest.fixture
def pattern(pattern_path) -> AntennaPattern:
    """A loaded synthetic pattern shared by the plotting tests."""
    return AntennaPattern(pattern_path(), validate=False)


def assert_matches_baseline_image(fig: go.Figure, name: str) -> None:
    """Compare a figure's rendered PNG against the stored baseline.

    On mismatch ``compare_images`` writes ``<name>-failed-diff.png`` next to the
    baseline, so the visual difference can be inspected directly.
    """
    baseline = FIXTURE_DIR / f"{name}.png"

    if UPDATE_BASELINES or not baseline.exists():
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(baseline), format="png")
        if not UPDATE_BASELINES:
            pytest.fail(
                f"Baseline {baseline.name} was missing and has now been written. "
                f"View it, confirm it is correct, commit it, and re-run."
            )
        return

    actual = FIXTURE_DIR / f"{name}-actual.png"
    fig.write_image(str(actual), format="png")
    try:
        result = compare_images(str(baseline), str(actual), tol=IMAGE_RMS_TOLERANCE)
    except ImageComparisonFailure as exc:
        pytest.fail(
            f"{name}: image dimensions changed versus baseline ({exc}). "
            f"If intentional, regenerate with EAS_UPDATE_BASELINES=1."
        )
    else:
        if result is None:
            actual.unlink(missing_ok=True)
        else:
            pytest.fail(
                f"{name}: rendered figure differs from baseline.\n{result}\n"
                f"Inspect {name}-failed-diff.png. If the change is intentional, "
                f"regenerate with EAS_UPDATE_BASELINES=1."
            )


class TestPlotContract:
    """``plot()`` — call contract."""

    def test_returns_figure_when_show_fig_false(self, pattern):
        assert isinstance(pattern.plot(show_fig=False), go.Figure)

    def test_figure_contains_a_trace(self, pattern):
        assert len(pattern.plot(show_fig=False).data) > 0

    @pytest.mark.parametrize("component", PLOTTABLE_COMPONENTS)
    def test_accepts_each_component(self, pattern, component):
        assert isinstance(
            pattern.plot(component_name=component, show_fig=False), go.Figure
        )

    def test_returns_none_and_shows_when_show_fig_true(self, pattern, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(go.Figure, "show", lambda self: calls.append("shown"))

        assert pattern.plot(show_fig=True) is None
        assert calls == ["shown"]

    def test_unknown_component_raises(self, pattern):
        with pytest.raises(ValueError, match="not found"):
            pattern.plot(component_name="not_a_component", show_fig=False)


class TestPlotContent:
    """``plot()`` — what is actually in the figure."""

    @pytest.mark.parametrize("component", PLOTTABLE_COMPONENTS)
    def test_z_is_the_requested_component(self, pattern, component):
        """The heatmap must carry the requested component, not a hardcoded one."""
        fig = pattern.plot(component_name=component, show_fig=False)
        expected = pattern.pattern[component].values
        np.testing.assert_allclose(np.asarray(fig.data[0].z), expected)

    def test_phi_on_x_and_theta_on_y(self, pattern):
        """Axis assignment must not be transposed."""
        fig = pattern.plot(show_fig=False)
        np.testing.assert_allclose(
            np.asarray(fig.data[0].x), pattern.pattern["Phi"].values
        )
        np.testing.assert_allclose(
            np.asarray(fig.data[0].y), pattern.pattern["Theta"].values
        )

    def test_theta_axis_is_reversed(self, pattern):
        """Theta increases downward; losing this silently flips the plot."""
        fig = pattern.plot(show_fig=False)
        assert fig.layout.yaxis.autorange == "reversed"

    def test_colour_range_is_pinned(self, pattern):
        fig = pattern.plot(show_fig=False)
        assert fig.data[0].zmin == EXPECTED_HEATMAP_ZMIN
        assert fig.data[0].zmax == EXPECTED_HEATMAP_ZMAX

    def test_colorscale_is_turbo(self, pattern):
        """Plotly expands named scales to stop lists, so compare against the named scale."""
        fig = pattern.plot(show_fig=False)
        expected = (
            go.Figure(go.Heatmap(z=[[0]], colorscale=EXPECTED_COLORSCALE_NAME))
            .data[0]
            .colorscale
        )
        assert fig.data[0].colorscale == expected

    def test_remove_layout_components_hides_scale_and_ticks(self, pattern):
        """The bare-plot flag must actually strip the chrome."""
        bare = pattern.plot(show_fig=False, remove_layout_components=True)
        full = pattern.plot(show_fig=False, remove_layout_components=False)

        assert bare.data[0].showscale is False
        assert full.data[0].showscale is True
        assert bare.layout.xaxis.showticklabels is False
        assert bare.layout.title.text is None
        assert full.layout.title.text is not None


class TestPlot3DContract:
    """``plot_3D()`` — call contract."""

    def test_returns_figure_when_show_fig_false(self, pattern):
        assert isinstance(pattern.plot_3D(show_fig=False), go.Figure)

    @pytest.mark.parametrize("component", PLOTTABLE_COMPONENTS)
    def test_accepts_each_component(self, pattern, component):
        assert isinstance(
            pattern.plot_3D(component_name=component, show_fig=False), go.Figure
        )

    def test_returns_none_and_shows_when_show_fig_true(self, pattern, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(go.Figure, "show", lambda self: calls.append("shown"))

        assert pattern.plot_3D(show_fig=True) is None
        assert calls == ["shown"]

    def test_unknown_component_raises(self, pattern):
        with pytest.raises(ValueError, match="not found"):
            pattern.plot_3D(component_name="not_a_component", show_fig=False)


class TestPlot3DContent:
    """``plot_3D()`` — what is actually in the figure."""

    def test_surface_is_first_trace(self, pattern):
        fig = pattern.plot_3D(show_fig=False)
        assert isinstance(fig.data[0], go.Surface)

    @pytest.mark.parametrize("component", PLOTTABLE_COMPONENTS)
    def test_surfacecolor_is_the_requested_component(self, pattern, component):
        """Colour must come from the requested component's raw dB values."""
        fig = pattern.plot_3D(component_name=component, show_fig=False)
        expected = pattern.pattern[component].values
        np.testing.assert_allclose(np.asarray(fig.data[0].surfacecolor), expected)

    def test_geometry_is_the_clipped_spherical_projection(self, pattern):
        """x/y/z must be the db_floor-clipped, min-shifted radius in Cartesian form."""
        db_floor = -30.0
        fig = pattern.plot_3D(db_floor=db_floor, show_fig=False)

        theta = np.radians(pattern.pattern.coords["Theta"].values)
        phi = np.radians(pattern.pattern.coords["Phi"].values)
        theta_grid, phi_grid = np.meshgrid(theta, phi, indexing="ij")
        r = np.clip(pattern.pattern["P_tp_dB"].values, db_floor, None)
        r = r - r.min()

        np.testing.assert_allclose(
            np.asarray(fig.data[0].x), r * np.sin(theta_grid) * np.cos(phi_grid)
        )
        np.testing.assert_allclose(np.asarray(fig.data[0].z), r * np.cos(theta_grid))

    def test_cmin_tracks_db_floor(self, pattern):
        """The colour floor must follow the requested db_floor, not a constant."""
        assert pattern.plot_3D(db_floor=-45.0, show_fig=False).data[0].cmin == -45.0
        assert pattern.plot_3D(db_floor=-10.0, show_fig=False).data[0].cmin == -10.0

    def test_db_floor_changes_the_geometry(self, pattern):
        """A different floor must produce a different surface, not an identical one."""
        shallow = np.asarray(pattern.plot_3D(db_floor=-10.0, show_fig=False).data[0].z)
        deep = np.asarray(pattern.plot_3D(db_floor=-60.0, show_fig=False).data[0].z)
        assert not np.allclose(shallow, deep)

    def test_axes_arrows_add_line_and_cone_traces(self, pattern):
        """The overlay adds 3 axis lines plus 1 cone trace on top of the surface."""
        without = pattern.plot_3D(show_axes_arrows=False, show_fig=False)
        with_arrows = pattern.plot_3D(show_axes_arrows=True, show_fig=False)

        assert len(without.data) == 1
        assert len(with_arrows.data) == 5
        assert sum(isinstance(t, go.Scatter3d) for t in with_arrows.data) == 3
        assert sum(isinstance(t, go.Cone) for t in with_arrows.data) == 1


@pytest.mark.image
class TestBaselineImages:
    """Human-reviewable PNG baselines, stored in ``tests/fixtures/``.

    These protect the upcoming decomposition, which must move code without altering any
    rendered figure. They cover what the attribute assertions above cannot: title
    placement, tick intervals, colour-bar geometry, figure dimensions — anything visual.

    Unlike the tests above, these use the **real bundled NGMN samples** rather than the
    synthetic fixture. The synthetic pattern is a clipped quadratic roll-off — a smooth
    blob with no nulls or sidelobes — so a reviewer cannot tell from it whether the plot
    is a plausible antenna pattern. The bundled samples render a real main beam, nulls and
    sidelobe structure, which is what makes a visual baseline worth reviewing. Both
    sampling formats are covered because the parser treats them differently.

    Cost is about 0.15 s per load, paid only by these four tests.
    """

    @pytest.fixture
    def non_uniform(self) -> AntennaPattern:
        """Real ANTMODEL1 sample, non-uniform sampling."""
        return AntennaPattern(SAMPLE_JSON[SAMPLE_NON_UNIFORM], validate=False)

    @pytest.fixture
    def uniform(self) -> AntennaPattern:
        """Real ANTMODEL2 sample, uniform sampling."""
        return AntennaPattern(SAMPLE_JSON[SAMPLE_UNIFORM], validate=False)

    def test_plot_matches_baseline(self, non_uniform):
        assert_matches_baseline_image(
            non_uniform.plot(show_fig=False), "plot_heatmap_non_uniform"
        )

    def test_plot_uniform_matches_baseline(self, uniform):
        assert_matches_baseline_image(
            uniform.plot(show_fig=False), "plot_heatmap_uniform"
        )

    def test_plot_bare_matches_baseline(self, non_uniform):
        fig = non_uniform.plot(show_fig=False, remove_layout_components=True)
        assert_matches_baseline_image(fig, "plot_heatmap_bare")

    def test_plot_3d_matches_baseline(self, non_uniform):
        assert_matches_baseline_image(
            non_uniform.plot_3D(show_fig=False), "plot_3d_default"
        )

    def test_plot_3d_no_arrows_matches_baseline(self, non_uniform):
        fig = non_uniform.plot_3D(show_axes_arrows=False, show_fig=False)
        assert_matches_baseline_image(fig, "plot_3d_no_arrows")
