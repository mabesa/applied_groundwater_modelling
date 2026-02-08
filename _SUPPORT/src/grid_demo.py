"""
Grid demonstration utilities for MODFLOW 6 discretization concepts.

This module provides interactive visualizations comparing different MODFLOW 6
grid types (DIS, DISV) for educational purposes.

Usage:
    from grid_demo import show_grid_comparison
    show_grid_comparison()
"""

import numpy as np
import tempfile
import shutil
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import ipywidgets as widgets
from IPython.display import display, Image
import io

from flopy.utils.triangle import Triangle
from flopy.utils.voronoi import VoronoiGrid


def create_structured_grid(nrows=10, ncols=10, extent=(0, 10, 0, 10)):
    """Create a structured grid as list of cell vertices.

    Parameters
    ----------
    nrows : int
        Number of rows
    ncols : int
        Number of columns
    extent : tuple
        (xmin, xmax, ymin, ymax) domain extent

    Returns
    -------
    list
        List of cell vertex coordinate lists
    """
    xmin, xmax, ymin, ymax = extent
    dx = (xmax - xmin) / ncols
    dy = (ymax - ymin) / nrows
    cells = []
    for i in range(nrows):
        for j in range(ncols):
            x0, y0 = xmin + j * dx, ymin + i * dy
            cells.append([(x0, y0), (x0 + dx, y0), (x0 + dx, y0 + dy), (x0, y0 + dy)])
    return cells


def create_quadtree_grid(base_size=8, extent=(0, 10, 0, 10), center=(5, 5)):
    """Create a quadtree-refined grid with finer cells near center.

    Parameters
    ----------
    base_size : int
        Base grid size (cells per side)
    extent : tuple
        (xmin, xmax, ymin, ymax) domain extent
    center : tuple
        (x, y) center point for refinement (e.g., well location)

    Returns
    -------
    list
        List of cell vertex coordinate lists
    """
    xmin, xmax, ymin, ymax = extent
    cx, cy = center
    cells = []
    cell_size = (xmax - xmin) / base_size

    for i in range(base_size):
        for j in range(base_size):
            x0 = xmin + j * cell_size
            y0 = ymin + i * cell_size
            cell_cx = x0 + cell_size / 2
            cell_cy = y0 + cell_size / 2
            dist = np.sqrt((cell_cx - cx)**2 + (cell_cy - cy)**2)

            if dist < 2.0:  # Inner zone - subdivide twice
                quarter = cell_size / 4
                for di in range(4):
                    for dj in range(4):
                        sx, sy = x0 + dj * quarter, y0 + di * quarter
                        cells.append([(sx, sy), (sx + quarter, sy),
                                     (sx + quarter, sy + quarter), (sx, sy + quarter)])
            elif dist < 3.5:  # Middle zone - subdivide once
                half = cell_size / 2
                for di in range(2):
                    for dj in range(2):
                        sx, sy = x0 + dj * half, y0 + di * half
                        cells.append([(sx, sy), (sx + half, sy),
                                     (sx + half, sy + half), (sx, sy + half)])
            else:  # Outer zone - no subdivision
                cells.append([(x0, y0), (x0 + cell_size, y0),
                             (x0 + cell_size, y0 + cell_size), (x0, y0 + cell_size)])
    return cells


def create_triangular_grid(extent=(0, 10, 0, 10), center=(5, 5)):
    """Create a triangular grid using FloPy's Triangle utility.

    Parameters
    ----------
    extent : tuple
        (xmin, xmax, ymin, ymax) domain extent
    center : tuple
        (x, y) center point for refinement (e.g., well location)

    Returns
    -------
    list
        List of cell vertex coordinate lists
    """
    xmin, xmax, ymin, ymax = extent
    cx, cy = center

    ws = tempfile.mkdtemp()

    try:
        # Outer boundary
        boundary = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]

        # Create Triangle with refinement
        tri = Triangle(model_ws=ws, angle=30, maximum_area=1.5)
        tri.add_polygon(boundary)

        # Add refinement regions (concentric)
        r1 = 1.5  # Inner radius
        r2 = 3.0  # Middle radius
        n_pts = 12

        # Inner refinement zone
        inner_poly = [(cx + r1 * np.cos(2*np.pi*i/n_pts),
                       cy + r1 * np.sin(2*np.pi*i/n_pts)) for i in range(n_pts)]
        tri.add_polygon(inner_poly)
        tri.add_region((cx, cy), attribute=1, maximum_area=0.1)

        # Middle refinement zone
        middle_poly = [(cx + r2 * np.cos(2*np.pi*i/n_pts),
                        cy + r2 * np.sin(2*np.pi*i/n_pts)) for i in range(n_pts)]
        tri.add_polygon(middle_poly)
        tri.add_region((cx + r1 + 0.1, cy), attribute=2, maximum_area=0.4)

        # Build triangulation
        tri.build(verbose=False)

        # Extract cells as vertex lists
        verts = tri.get_vertices()
        cell2d = tri.get_cell2d()

        cells = []
        for cell in cell2d:
            # cell format: (cellid, xc, yc, ncvert, v1, v2, v3, ...)
            ncvert = cell[3]
            vert_indices = cell[4:4+ncvert]
            cell_verts = [(verts[vi][1], verts[vi][2]) for vi in vert_indices]
            cells.append(cell_verts)

        return cells
    finally:
        shutil.rmtree(ws)


def create_voronoi_grid(extent=(0, 10, 0, 10), center=(5, 5)):
    """Create a Voronoi grid using FloPy's VoronoiGrid utility.

    Parameters
    ----------
    extent : tuple
        (xmin, xmax, ymin, ymax) domain extent
    center : tuple
        (x, y) center point for refinement (e.g., well location)

    Returns
    -------
    list
        List of cell vertex coordinate lists
    """
    xmin, xmax, ymin, ymax = extent
    cx, cy = center

    ws = tempfile.mkdtemp()

    try:
        # Outer boundary
        boundary = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]

        # Create Triangle (Voronoi is built from Delaunay triangulation)
        tri = Triangle(model_ws=ws, angle=30, maximum_area=1.5)
        tri.add_polygon(boundary)

        # Add refinement regions
        r1 = 1.5
        r2 = 3.0
        n_pts = 12

        inner_poly = [(cx + r1 * np.cos(2*np.pi*i/n_pts),
                       cy + r1 * np.sin(2*np.pi*i/n_pts)) for i in range(n_pts)]
        tri.add_polygon(inner_poly)
        tri.add_region((cx, cy), attribute=1, maximum_area=0.1)

        middle_poly = [(cx + r2 * np.cos(2*np.pi*i/n_pts),
                        cy + r2 * np.sin(2*np.pi*i/n_pts)) for i in range(n_pts)]
        tri.add_polygon(middle_poly)
        tri.add_region((cx + r1 + 0.1, cy), attribute=2, maximum_area=0.4)

        # Build triangulation
        tri.build(verbose=False)

        # Create Voronoi from Triangle
        vor = VoronoiGrid(tri)

        # Extract cell vertices using get_disv_gridprops
        gridprops = vor.get_disv_gridprops()
        vertices = gridprops['vertices']

        cells = []
        for cell in gridprops['cell2d']:
            # cell format: (cellid, xc, yc, ncvert, v0, v1, v2, ...)
            ncvert = cell[3]
            vert_indices = list(cell[4:4+ncvert])
            cell_verts = [(vertices[vi][1], vertices[vi][2]) for vi in vert_indices]
            cells.append(cell_verts)

        return cells
    finally:
        shutil.rmtree(ws)


def _create_grid_figure(grid_type, show_well):
    """Create and return a matplotlib figure for the specified grid type.

    Internal function that creates the plot without displaying it.
    """
    fig, ax = plt.subplots(1, 1, figsize=(4, 4), dpi=100)
    extent = (0, 10, 0, 10)
    center = (5, 5)

    if grid_type == 'Structured (rectangles)':
        cells = create_structured_grid(10, 10, extent)
        title = "Structured Grid (DIS)"
    elif grid_type == 'Quadtree (quadrilaterals)':
        cells = create_quadtree_grid(8, extent=extent, center=center)
        title = "Quadtree Grid (DISV)"
    elif grid_type == 'Triangular':
        cells = create_triangular_grid(extent, center)
        title = "Triangular Grid (DISV)"
    else:  # Voronoi
        cells = create_voronoi_grid(extent, center)
        title = "Voronoi Grid (DISV)"

    patches = [MplPolygon(cell, closed=True) for cell in cells]
    collection = PatchCollection(patches, facecolor='lightblue', edgecolor='darkblue',
                                 linewidth=0.5, alpha=0.7)
    ax.add_collection(collection)

    if show_well:
        ax.plot(5, 5, 'ro', markersize=8, label='Well', zorder=5)
        ax.legend(loc='upper right', fontsize=8)

    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.5, 10.5)
    ax.set_aspect('equal')
    ax.set_xlabel('X', fontsize=8)
    ax.set_ylabel('Y', fontsize=8)
    ax.set_title(f"{title} ({len(cells)} cells)", fontsize=9)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    return fig


def show_grid_comparison():
    """Display an interactive comparison of MODFLOW 6 grid types.

    Creates a dropdown widget to select between:
    - Structured (rectangles) - DIS package
    - Quadtree (quadrilaterals) - DISV package
    - Triangular - DISV package
    - Voronoi - DISV package

    All unstructured types show local refinement around a central well location.

    Example
    -------
    >>> from grid_demo import show_grid_comparison
    >>> show_grid_comparison()
    """
    from IPython.display import clear_output

    grid_selector = widgets.Dropdown(
        options=['Structured (rectangles)', 'Quadtree (quadrilaterals)', 'Triangular', 'Voronoi'],
        value='Structured (rectangles)',
        description='Grid Type:',
        style={'description_width': 'initial'}
    )

    well_toggle = widgets.Checkbox(value=True, description='Show well location')

    output = widgets.Output()

    def update_plot(_=None):
        plt.close('all')
        with output:
            clear_output(wait=True)
            fig = _create_grid_figure(grid_selector.value, well_toggle.value)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            display(Image(data=buf.getvalue()))
            buf.close()
            plt.close('all')

    grid_selector.observe(update_plot, names='value')
    well_toggle.observe(update_plot, names='value')

    ui = widgets.VBox([
        widgets.HTML("<b>Figure 1:</b> Interactive comparison of MODFLOW 6 grid types.<br>"
                     "Triangular and Voronoi grids use FloPy's Triangle and VoronoiGrid utilities.<br>"
                     "All unstructured types (DISV) show refinement near the well."),
        grid_selector,
        well_toggle,
        output
    ])

    # Generate initial plot BEFORE displaying UI
    update_plot()

    # Return widget instead of displaying - let notebook cell handle display
    return ui
