"""Figure construction for antenna radiation patterns.

Split out of ``parser.py`` (Phase 1 of the god-class decomposition, plan section 2.1.3).

These are pure functions: they take the pattern dataset and return a figure. They neither
read nor mutate ``AntennaPattern`` state, and they do not display anything — the caller
decides whether to render. ``AntennaPattern.plot()`` and ``AntennaPattern.plot_3D()`` remain
the public entry points and are unchanged in behaviour.
"""

import logging

import numpy as np
import plotly.graph_objects as go
import xarray as xr

logger = logging.getLogger(__name__)


def _validate_component(pattern_3d: xr.Dataset, component_name: str) -> None:
    """Raise if the requested component is not present in the dataset.

    Args:
        pattern_3d: The processed pattern dataset.
        component_name: Name of the data variable to plot.

    Raises:
        ValueError: If ``component_name`` is not a data variable of ``pattern_3d``.
    """
    if component_name not in pattern_3d.data_vars:
        message = (
            f"AntennaPattern: Component '{component_name}' not found. "
            f"Make sure to select a component with data."
        )
        logger.error(message)
        raise ValueError(message)


def build_heatmap(
    pattern_3d: xr.Dataset,
    title: str,
    component_name: str = "P_tp_dB",
    remove_layout_components: bool = False,
) -> go.Figure:
    """Build the 2D heatmap figure for a radiation pattern.

    Args:
        pattern_3d: The processed pattern dataset, indexed by Theta and Phi.
        title: Figure title, normally the source filename.
        component_name: Data variable to plot. Defaults to 'P_tp_dB', the power pattern.
        remove_layout_components: Strip title, colour bar and tick labels for a bare plot.

    Returns:
        go.Figure: The constructed heatmap. Not displayed.
    """
    _validate_component(pattern_3d, component_name)

    fig = go.Figure(
        data=go.Heatmap(
            z=pattern_3d[component_name].values,
            x=pattern_3d["Phi"].values,
            y=pattern_3d["Theta"].values,
            colorscale="turbo",
            zmin=-30,
            zmax=0,
            colorbar={"title": component_name, "thickness": 9},
            hovertemplate="φ = %{x:.0f}°<br>θ = %{y:.0f}°<br>val = %{z:.2f}<br><extra></extra>",
            showscale=not (remove_layout_components),
        )
    )
    fig.update_yaxes(autorange="reversed")
    if remove_layout_components:
        fig.update_layout(
            xaxis={
                "showticklabels": False,
                "showgrid": False,
                "zeroline": False,
                "showline": False,
            },
            yaxis={
                "showticklabels": False,
                "showgrid": False,
                "zeroline": False,
                "showline": False,
            },
            plot_bgcolor="rgba(0,0,0,0)",  # sin fondo gris en el área del heatmap
            paper_bgcolor="rgba(0,0,0,0)",  # sin fondo/gris alrededor
            margin={"t": 0, "l": 0, "r": 0, "b": 0},  # recorta al mínimo
            height=500,
        )
    else:
        fig.update_layout(
            title={
                "text": title,
                "x": 0.5,
                "y": 0.93,
                "yanchor": "bottom",
                "font": {"size": 16},
            },
            xaxis={
                "title": "φ [°]",
                "tickmode": "linear",
                "title_standoff": 10,
                "dtick": 30,
                "showgrid": True,
                "tickangle": -45,
                "gridcolor": "rgba(0,0,0,0.2)",
                "zeroline": False,
            },
            yaxis={
                "title": "θ [°]",
                "tickmode": "linear",
                "title_standoff": 10,
                "dtick": 30,
                "showgrid": True,
                "gridcolor": "rgba(0,0,0,0.2)",
                "zeroline": False,
            },
            margin={"t": 40, "l": 60, "r": 60, "b": 60},
            height=500,
        )
    return fig


def build_polar_3d(
    pattern_3d: xr.Dataset,
    title: str,
    component_name: str = "P_tp_dB",
    db_floor: float = -30.0,
    show_axes_arrows: bool = True,
) -> go.Figure:
    """Build the 3D polar surface figure for a radiation pattern.

    Args:
        pattern_3d: The processed pattern dataset, indexed by Theta and Phi.
        title: Figure title, normally the source filename.
        component_name: Data variable to plot. Defaults to 'P_tp_dB', the power pattern.
        db_floor: Lower dB clip, which smooths the surface. Defaults to -30.
        show_axes_arrows: Overlay the coordinate axis arrows. Defaults to True.

    Returns:
        go.Figure: The constructed 3D surface. Not displayed.
    """
    _validate_component(pattern_3d, component_name)

    theta_rad = np.radians(pattern_3d.coords["Theta"].values)
    phi_rad = np.radians(pattern_3d.coords["Phi"].values)
    theta_grid, phi_grid = np.meshgrid(theta_rad, phi_rad, indexing="ij")
    r = pattern_3d[component_name].values
    r_clipped = np.clip(r, db_floor, r.max())
    r_clipped -= r_clipped.min()
    X = r_clipped * np.sin(theta_grid) * np.cos(phi_grid)
    Y = r_clipped * np.sin(theta_grid) * np.sin(phi_grid)
    Z = r_clipped * np.cos(theta_grid)

    fig = go.Figure()
    fig.add_trace(
        go.Surface(
            x=X,
            y=Y,
            z=Z,
            surfacecolor=r,
            colorscale="turbo",
            cmin=db_floor,
            cmax=0,
            colorbar={"title": component_name, "thickness": 9},
        )
    )
    fig.update_layout(
        title={
            "text": title,
            "x": 0.5,
            "y": 0.93,
            "yanchor": "bottom",
            "font": {"size": 16},
        },
        height=650,
        margin={"t": 50, "l": 0, "r": 0, "b": 0},
        scene={
            "aspectmode": "data",
            "xaxis_title": "x",
            "yaxis_title": "y",
            "zaxis_title": "z",
        },
    )
    if show_axes_arrows:
        L = r_clipped.max() + 6
        fig.add_trace(
            go.Scatter3d(
                x=[0, L],
                y=[0, 0],
                z=[0, 0],
                mode="lines",
                line={"color": "black", "width": 6},
                showlegend=False,
                hoverinfo="skip",
                hovertemplate=None,
            )
        )
        fig.add_trace(
            go.Scatter3d(
                x=[0, 0],
                y=[0, L / 2],
                z=[0, 0],
                mode="lines",
                line={"color": "black", "width": 6},
                showlegend=False,
                hoverinfo="skip",
                hovertemplate=None,
            )
        )
        fig.add_trace(
            go.Scatter3d(
                x=[0, 0],
                y=[0, 0],
                z=[0, L / 2],
                mode="lines",
                line={"color": "black", "width": 6},
                showlegend=False,
                hoverinfo="skip",
                hovertemplate=None,
            )
        )
        fig.add_trace(
            go.Cone(
                x=[L, 0, 0],
                y=[0, L / 2, 0],
                z=[0, 0, L / 2],
                u=[4, 0, 0],
                v=[0, 4, 0],
                w=[0, 0, 4],
                anchor="tail",
                showscale=False,
                autocolorscale=False,
                sizemode="absolute",
                sizeref=0.3,
                colorscale=[[0, "black"], [1, "black"]],
                showlegend=False,
                hoverinfo="skip",
                hovertemplate=None,
            )
        )
    return fig
