"""
utils/chart_helpers.py — Reusable Matplotlib figure builders for Tuneback.

Every function returns a plt.Figure that is not yet attached to any widget.
Pages call embed_figure() or popup_figure() to display it.

Keeping all chart-building code in one place means:
  - No Matplotlib boilerplate scattered across page files.
  - The viva demonstrator can show Matplotlib knowledge in one focused file.
  - Dark theme is applied consistently to every chart.

Python concepts demonstrated: function encapsulation, list slicing,
zip(), enumerate(), Matplotlib figure/axes API.

Public figure-builder functions
--------------------------------
make_bar_chart(labels, values, title, ...)
make_horizontal_bar_chart(labels, values, title, ...)
make_line_chart(x, y, title, ...)
make_multi_line_chart(x, series, title, ...)
make_grouped_bar_chart(labels, groups, title, ...)
make_radar_chart(labels, values, title, ...)
make_heatmap(data, row_labels, col_labels, title, ...)

Embedding helpers
-----------------
embed_figure(fig, parent_frame, **pack_kwargs) → FigureCanvasTkAgg
popup_figure(fig, title)                        → opens a Toplevel window
clear_frame_charts(frame)                       → destroys existing canvas
"""

from __future__ import annotations

import tkinter as tk
from typing import Sequence

import customtkinter
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ui import theme

# ---------------------------------------------------------------------------
# Use the non-interactive Agg backend for all figure creation so figures can
# be built on any thread and only rendered to a widget when embed_figure()
# is called.  This must be set before any Figure is created.
# ---------------------------------------------------------------------------
matplotlib.use("Agg")

# ---------------------------------------------------------------------------
# Dark style constants — mirrors ui/theme.py values so charts blend in.
# ---------------------------------------------------------------------------
_BG        = theme.BG          # figure / axes background
_SURFACE   = theme.SURFACE     # slightly lighter panel bg (tick area)
_TEXT      = theme.TEXT        # axis labels, titles
_MUTED     = theme.TEXT_MUTED  # grid lines, minor text
_ACCENT    = theme.ACCENT      # primary bar / line colour
_COLORS    = theme.CHART_COLORS  # multi-series palette
_BORDER    = theme.BORDER


def _apply_dark_style(ax: plt.Axes, fig: plt.Figure) -> None:
    """Apply the Tuneback dark style to a Matplotlib axes and figure.

    Called at the end of every figure-builder before returning.
    """
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    # Spine (border) colour
    for spine in ax.spines.values():
        spine.set_color(_BORDER)

    # Tick and label colours
    ax.tick_params(colors=_MUTED, labelsize=9)
    ax.xaxis.label.set_color(_MUTED)
    ax.yaxis.label.set_color(_MUTED)

    # Title colour
    if ax.get_title():
        ax.title.set_color(_TEXT)

    # Grid — subtle horizontal lines only
    ax.yaxis.grid(True, color=_BORDER, linewidth=0.5, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.grid(False)


def _apply_dark_style_polar(ax: plt.Axes, fig: plt.Figure) -> None:
    """Dark style variant for polar (radar) axes."""
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.spines["polar"].set_color(_BORDER)
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.grid(color=_BORDER, linewidth=0.5, alpha=0.6)


# ---------------------------------------------------------------------------
# Figure builders — each returns a plt.Figure
# ---------------------------------------------------------------------------

def make_bar_chart(
    labels: Sequence[str],
    values: Sequence[float],
    title:  str = "",
    color:  str | None = None,
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple[float, float] = (7, 3.5),
    max_label_len: int = 20,
) -> plt.Figure:
    """Vertical bar chart.

    Parameters
    ----------
    labels        : X-axis category labels.
    values        : Bar heights (same length as labels).
    title         : Chart title (empty = no title).
    color         : Bar colour; defaults to ACCENT.
    xlabel/ylabel : Axis labels.
    figsize       : (width, height) in inches.
    max_label_len : Truncate long labels to this many characters.

    Returns
    -------
    plt.Figure — call embed_figure() or popup_figure() to display.
    """
    color = color or _ACCENT
    # Truncate very long labels so they don't overlap
    short_labels = [
        lbl[:max_label_len] + "…" if len(str(lbl)) > max_label_len else str(lbl)
        for lbl in labels
    ]

    fig, ax = plt.subplots(figsize=figsize)
    x_pos = range(len(short_labels))
    bars = ax.bar(x_pos, values, color=color, width=0.6, zorder=2)

    # Value labels on top of bars
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(values) * 0.01,
            str(int(val)) if val == int(val) else f"{val:.1f}",
            ha="center", va="bottom", fontsize=8, color=_MUTED,
        )

    ax.set_xticks(list(x_pos))
    ax.set_xticklabels(short_labels, rotation=30, ha="right", fontsize=9)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, fontsize=11, pad=10)

    # Remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    _apply_dark_style(ax, fig)
    fig.tight_layout()
    return fig


def make_horizontal_bar_chart(
    labels: Sequence[str],
    values: Sequence[float],
    title:  str = "",
    color:  str | None = None,
    xlabel: str = "",
    figsize: tuple[float, float] = (6, 4),
    max_label_len: int = 30,
) -> plt.Figure:
    """Horizontal bar chart — good for ranked artist/track lists.

    The first bar (highest ranked) appears at the top.
    """
    color = color or _ACCENT
    short_labels = [
        lbl[:max_label_len] + "…" if len(str(lbl)) > max_label_len else str(lbl)
        for lbl in labels
    ]
    # Reverse so highest value is at the top
    rev_labels = list(reversed(short_labels))
    rev_values = list(reversed(values))

    fig, ax = plt.subplots(figsize=figsize)
    y_pos = range(len(rev_labels))
    bars = ax.barh(list(y_pos), rev_values, color=color, height=0.6, zorder=2)

    # Value labels at end of bars
    max_val = max(values) if values else 1
    for bar, val in zip(bars, rev_values):
        ax.text(
            bar.get_width() + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(int(val)) if val == int(val) else f"{val:.1f}",
            va="center", fontsize=8, color=_MUTED,
        )

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(rev_labels, fontsize=9)
    if xlabel:
        ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, fontsize=11, pad=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    _apply_dark_style(ax, fig)
    # Remove y-axis grid; add x-axis grid instead
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=_BORDER, linewidth=0.5, linestyle="--", alpha=0.6)

    fig.tight_layout()
    return fig


def make_line_chart(
    x:      Sequence,
    y:      Sequence[float],
    title:  str = "",
    color:  str | None = None,
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple[float, float] = (8, 3),
    fill:   bool = True,
    xtick_step: int = 1,
) -> plt.Figure:
    """Single-series line chart with optional area fill.

    Parameters
    ----------
    x           : X-axis labels (strings or numbers).
    y           : Y-axis values.
    fill        : Fill area under the line (default True).
    xtick_step  : Show every Nth x-axis label (reduces crowding).
    """
    color = color or _ACCENT
    fig, ax = plt.subplots(figsize=figsize)

    x_pos = list(range(len(x)))
    ax.plot(x_pos, y, color=color, linewidth=2, zorder=3)
    if fill:
        ax.fill_between(x_pos, y, alpha=0.15, color=color, zorder=2)

    # Sparse x-axis labels
    tick_positions = list(range(0, len(x), max(xtick_step, 1)))
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [str(x[i]) for i in tick_positions],
        rotation=30, ha="right", fontsize=8,
    )

    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, fontsize=11, pad=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _apply_dark_style(ax, fig)
    fig.tight_layout()
    return fig


def make_multi_line_chart(
    x:      Sequence,
    series: dict[str, Sequence[float]],
    title:  str = "",
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple[float, float] = (9, 4),
    xtick_step: int = 1,
) -> plt.Figure:
    """Multi-series line chart with a legend.

    Parameters
    ----------
    series : dict mapping series name → list of y-values.
             Series are drawn in dict insertion order using CHART_COLORS.
    """
    fig, ax = plt.subplots(figsize=figsize)
    x_pos = list(range(len(x)))

    for i, (name, values) in enumerate(series.items()):
        color = _COLORS[i % len(_COLORS)]
        ax.plot(x_pos, values, color=color, linewidth=2, label=name, zorder=3)

    # Legend
    legend = ax.legend(
        fontsize=8, framealpha=0.3,
        facecolor=_SURFACE, edgecolor=_BORDER,
        labelcolor=_TEXT,
    )

    tick_positions = list(range(0, len(x), max(xtick_step, 1)))
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [str(x[i]) for i in tick_positions],
        rotation=30, ha="right", fontsize=8,
    )

    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, fontsize=11, pad=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _apply_dark_style(ax, fig)
    fig.tight_layout()
    return fig


def make_grouped_bar_chart(
    labels: Sequence[str],
    groups: dict[str, Sequence[float]],
    title:  str = "",
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple[float, float] = (8, 4),
    color_map: dict[str, str] | None = None,
) -> plt.Figure:
    """Grouped (clustered) bar chart for side-by-side comparison.

    Parameters
    ----------
    labels : Category labels on the x-axis.
    groups : dict mapping group name → list of values (same length as labels).
    """
    n_groups = len(groups)
    n_cats   = len(labels)
    width    = 0.8 / n_groups   # Each bar's width inside the cluster

    fig, ax = plt.subplots(figsize=figsize)
    x_pos = list(range(n_cats))

    for i, (group_name, values) in enumerate(groups.items()):
        color  = (color_map or {}).get(group_name, _COLORS[i % len(_COLORS)])
        offset = (i - (n_groups - 1) / 2) * width
        positions = [x + offset for x in x_pos]
        ax.bar(positions, values, width=width * 0.9,
               color=color, label=group_name, zorder=2)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)

    legend = ax.legend(
        fontsize=8, framealpha=0.3,
        facecolor=_SURFACE, edgecolor=_BORDER,
        labelcolor=_TEXT,
    )

    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, fontsize=11, pad=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _apply_dark_style(ax, fig)
    fig.tight_layout()
    return fig


def make_radar_chart(
    labels:     Sequence[str],
    values:     Sequence[float],
    title:      str = "",
    color:      str | None = None,
    figsize:    tuple[float, float] = (5, 5),
    value_range: tuple[float, float] = (0, 100),
) -> plt.Figure:
    """Spider / radar chart for multi-dimensional personality scores.

    Parameters
    ----------
    labels      : Axis labels (one per dimension).
    values      : Score per dimension (same length as labels).
    value_range : (min, max) for the radial axis.
    """
    color = color or _ACCENT
    n = len(labels)
    if n < 3:
        raise ValueError("Radar chart requires at least 3 dimensions.")

    # Compute angle for each axis — evenly spaced around the circle
    import math
    angles = [2 * math.pi * i / n for i in range(n)]
    angles_closed = angles + [angles[0]]   # close the polygon

    # Close the value list too
    values_list   = list(values)
    values_closed = values_list + [values_list[0]]

    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"polar": True})

    # Draw the filled polygon
    ax.plot(angles_closed, values_closed, color=color, linewidth=2)
    ax.fill(angles_closed, values_closed, color=color, alpha=0.20)

    # Set axis labels at each spoke
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9, color=_TEXT)

    # Radial axis range
    ax.set_ylim(value_range)
    ax.set_yticks([value_range[0], (value_range[1] - value_range[0]) // 2, value_range[1]])
    ax.set_yticklabels(
        [str(int(value_range[0])), str(int((value_range[1] - value_range[0]) // 2)),
         str(int(value_range[1]))],
        fontsize=7, color=_MUTED,
    )

    if title:
        ax.set_title(title, fontsize=11, pad=20, color=_TEXT)

    _apply_dark_style_polar(ax, fig)
    fig.tight_layout()
    return fig


def make_heatmap(
    data:       Sequence[Sequence[float]],
    row_labels: Sequence[str],
    col_labels: Sequence[str],
    title:      str = "",
    figsize:    tuple[float, float] = (10, 4),
    cmap:       str = "Greens",
) -> plt.Figure:
    """Colour-coded grid heatmap (e.g. listening hours by weekday × hour).

    Parameters
    ----------
    data       : 2-D list [rows][cols] of numeric values.
    row_labels : Labels for the y-axis (rows).
    col_labels : Labels for the x-axis (columns).
    cmap       : Matplotlib colormap name.
    """
    import numpy as np
    arr = np.array(data, dtype=float)

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(arr, cmap=cmap, aspect="auto")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=8, rotation=45, ha="right")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=9)

    if title:
        ax.set_title(title, fontsize=11, pad=10)

    # Colour bar
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.ax.tick_params(colors=_MUTED, labelsize=8)
    cbar.outline.set_edgecolor(_BORDER)

    _apply_dark_style(ax, fig)
    # imshow sets spines differently — remove grid that looks wrong here
    ax.yaxis.grid(False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Embedding / display helpers
# ---------------------------------------------------------------------------

def embed_figure(
    fig: plt.Figure,
    parent_frame,
    **pack_kwargs,
) -> FigureCanvasTkAgg:
    """Embed a Matplotlib figure inside a CustomTkinter / Tkinter frame.

    Creates a FigureCanvasTkAgg, calls draw(), and packs the canvas widget
    into parent_frame.

    Parameters
    ----------
    fig          : The plt.Figure to embed.
    parent_frame : The CTkFrame or Frame that will contain the chart.
    **pack_kwargs: Extra kwargs forwarded to canvas.get_tk_widget().pack().
                  Defaults: fill="both", expand=True.

    Returns
    -------
    FigureCanvasTkAgg — keep a reference so the canvas is not garbage-collected.

    Example
    -------
        fig = make_bar_chart(labels, values, title="Top Artists")
        canvas = embed_figure(fig, my_frame, fill="both", expand=True)
    """
    pack_kwargs.setdefault("fill", "both")
    pack_kwargs.setdefault("expand", True)

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(**pack_kwargs)
    return canvas


def popup_figure(fig: plt.Figure, title: str = "Chart Detail") -> None:
    """Open a resizable pop-out window containing an enlarged version of fig.

    The Toplevel is styled to match the Tuneback dark theme.

    Parameters
    ----------
    fig   : The plt.Figure to display.
    title : Window title bar text.
    """
    popup = customtkinter.CTkToplevel()
    popup.title(title)
    popup.geometry("900x600")
    popup.configure(fg_color=theme.BG)
    popup.resizable(True, True)
    popup.lift()          # bring to front
    popup.focus_force()   # capture keyboard focus

    # Close button
    close_btn = customtkinter.CTkButton(
        popup,
        text="✕  Close",
        width=100,
        height=30,
        fg_color=theme.SURFACE_RAISED,
        hover_color=theme.SURFACE,
        text_color=theme.TEXT_MUTED,
        font=theme.label_style(theme.FONT_S),
        command=popup.destroy,
    )
    close_btn.pack(anchor="ne", padx=theme.PAD_M, pady=(theme.PAD_M, 0))

    # Chart frame
    chart_frame = customtkinter.CTkFrame(popup, fg_color=theme.BG)
    chart_frame.pack(fill="both", expand=True, padx=theme.PAD_M, pady=theme.PAD_M)

    embed_figure(fig, chart_frame)


def clear_frame_charts(frame) -> None:
    """Destroy all FigureCanvasTkAgg widgets inside a frame.

    Call this before re-embedding a chart (e.g. when refresh() rebuilds
    a page) to avoid leaking canvas objects.

    Parameters
    ----------
    frame : The CTkFrame whose charts should be cleared.
    """
    for widget in frame.winfo_children():
        widget.destroy()
    plt.close("all")   # release Matplotlib figure memory
