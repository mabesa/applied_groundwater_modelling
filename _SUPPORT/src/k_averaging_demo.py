"""
Interactive demo for K-averaging methods between MODFLOW 6 cells.

Visualizes how different averaging methods (harmonic, geometric, logarithmic,
arithmetic) produce different effective K values when adjacent cells have
different hydraulic conductivities.

Usage:
    from k_averaging_demo import show_k_averaging
    show_k_averaging()
"""

import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import display, Image
import io


def _compute_means(K_i, K_j):
    """Compute effective K using four averaging methods.

    Parameters
    ----------
    K_i : float
        Hydraulic conductivity of cell i (m/d)
    K_j : float
        Hydraulic conductivity of cell j (m/d)

    Returns
    -------
    dict
        Effective K for each method
    """
    harmonic = 2 * K_i * K_j / (K_i + K_j)
    arithmetic = (K_i + K_j) / 2
    geometric = np.sqrt(K_i * K_j)

    # Logarithmic mean: (K_i - K_j) / ln(K_i / K_j), equals K_i when K_i = K_j
    if abs(K_i - K_j) / max(K_i, K_j) < 1e-10:
        logarithmic = K_i
    else:
        logarithmic = (K_i - K_j) / np.log(K_i / K_j)

    return {
        "Harmonic": harmonic,
        "Geometric": geometric,
        "Logarithmic": logarithmic,
        "Arithmetic": arithmetic,
    }


# Consistent colors and markers for the four methods
_METHOD_STYLES = {
    "Harmonic": {"color": "#2166ac", "marker": "D"},
    "Geometric": {"color": "#4dac26", "marker": "s"},
    "Logarithmic": {"color": "#b8860b", "marker": "^"},
    "Arithmetic": {"color": "#b2182b", "marker": "o"},
}


def _create_k_averaging_figure(K_i, K_j):
    """Create the K-averaging comparison figure.

    Returns a matplotlib figure showing all four effective K values
    on a horizontal log-scale axis, with K_i and K_j as reference lines.
    """
    means = _compute_means(K_i, K_j)
    K_min, K_max = min(K_i, K_j), max(K_i, K_j)
    contrast = K_max / K_min

    fig, ax = plt.subplots(figsize=(7, 2.8))

    # Plot reference lines for K_i and K_j
    ax.axvline(K_i, color="0.4", linestyle="--", linewidth=1.2, zorder=1)
    ax.axvline(K_j, color="0.4", linestyle="--", linewidth=1.2, zorder=1)

    # Label K_i and K_j at the top
    y_label = 1.35
    ax.text(K_i, y_label, f"$K_i$ = {K_i:.3g}", ha="center", va="bottom",
            fontsize=9, color="0.3", fontweight="bold")
    ax.text(K_j, y_label, f"$K_j$ = {K_j:.3g}", ha="center", va="bottom",
            fontsize=9, color="0.3", fontweight="bold")

    # Plot each averaging method
    y_positions = {"Harmonic": 0.4, "Geometric": 0.7, "Logarithmic": 1.0, "Arithmetic": 1.3}
    for name, K_eff in means.items():
        style = _METHOD_STYLES[name]
        y = y_positions[name]
        ax.plot(K_eff, y, marker=style["marker"], color=style["color"],
                markersize=10, zorder=3, markeredgecolor="white", markeredgewidth=0.8)
        ax.annotate(f"{name}\n{K_eff:.3g} m/d",
                    xy=(K_eff, y), xytext=(12, 0), textcoords="offset points",
                    fontsize=8, color=style["color"], va="center", fontweight="bold")

    # Axis formatting
    pad = 3.0
    ax.set_xlim(K_min / pad, K_max * pad)
    ax.set_xscale("log")
    ax.set_xlabel("Effective hydraulic conductivity, $K_{eff}$ (m/d)", fontsize=9)
    ax.set_ylim(0.0, 1.8)
    ax.set_yticks([])

    # Insight text
    if contrast < 1.01:
        insight = "K values are equal — all methods give the same result."
    elif contrast < 5:
        ratio = means["Arithmetic"] / means["Harmonic"]
        insight = (f"Contrast = {contrast:.1f}x — "
                   f"arithmetic is {ratio:.1f}x larger than harmonic.")
    else:
        ratio = means["Arithmetic"] / means["Harmonic"]
        insight = (f"Contrast = {contrast:.0f}x — "
                   f"arithmetic is {ratio:.0f}x larger than harmonic. "
                   f"The low-K cell dominates the harmonic mean!")

    ax.set_title(insight, fontsize=9, style="italic", pad=18)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    plt.tight_layout()
    return fig


def show_k_averaging():
    """Display an interactive K-averaging comparison widget.

    Creates two log-scale sliders for K_i and K_j, with a real-time plot
    showing where harmonic, geometric, logarithmic, and arithmetic means
    fall on a log axis. Helps students build intuition for when the choice
    of averaging method matters.

    Returns
    -------
    ipywidgets.VBox
        Widget to display in a Jupyter notebook cell.

    Example
    -------
    >>> from k_averaging_demo import show_k_averaging
    >>> show_k_averaging()
    """
    K_i_slider = widgets.FloatLogSlider(
        value=100, base=10, min=-2, max=3, step=0.1,
        description="K_i (m/d):",
        style={"description_width": "initial"},
        readout_format=".2g",
    )
    K_j_slider = widgets.FloatLogSlider(
        value=1, base=10, min=-2, max=3, step=0.1,
        description="K_j (m/d):",
        style={"description_width": "initial"},
        readout_format=".2g",
    )

    output = widgets.Output()

    def update_plot(_=None):
        plt.close("all")
        with output:
            output.clear_output(wait=True)
            fig = _create_k_averaging_figure(K_i_slider.value, K_j_slider.value)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            buf.seek(0)
            display(Image(data=buf.getvalue()))
            buf.close()
            plt.close("all")

    K_i_slider.observe(update_plot, names="value")
    K_j_slider.observe(update_plot, names="value")

    ui = widgets.VBox([
        widgets.HTML(
            "<b>Explore:</b> Drag the sliders to change K values and observe how "
            "the averaging methods diverge as contrast increases. "
            "The ordering harmonic &le; geometric &le; logarithmic &le; arithmetic "
            "always holds."
        ),
        K_i_slider,
        K_j_slider,
        output,
    ])

    # Generate initial plot
    update_plot()

    return ui
