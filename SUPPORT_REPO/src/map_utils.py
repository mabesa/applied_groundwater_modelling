import folium
from folium.plugins import BeautifyIcon
import geopandas as gpd
import os, shutil, tempfile, time
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.legend import Legend
import matplotlib.patheffects as path_effects
import json
from typing import Tuple, Any, Optional, Literal
from branca.element import MacroElement
from jinja2 import Template
from shapely import union_all
import textwrap
import numpy as np
import warnings
try:  # Access shared caption style
    from style_utils import FIGURE_CAPTION_STYLE
except Exception:  # Fallback defaults if import fails
    FIGURE_CAPTION_STYLE = {"fontsize": 10, "fontweight": "bold", "fontfamily": "Arial, sans-serif"}

def _caption_css(extra: str = "") -> str:
    """Return inline CSS string based on FIGURE_CAPTION_STYLE (points -> px)."""
    fs_pt = FIGURE_CAPTION_STYLE.get("fontsize", 10)
    # Approximate px conversion (96 dpi assumption)
    fs_px = round(fs_pt * 96 / 72)
    weight = FIGURE_CAPTION_STYLE.get("fontweight", "bold")
    family = FIGURE_CAPTION_STYLE.get("fontfamily", "Arial, sans-serif")
    return f"font-size:{fs_px}px;font-weight:{weight};font-family:{family};{extra}".replace(";;", ";")


def display_groundwater_resources_map(gw_map_path, zoom_level=10, 
                                      map_center=None, map_title=None):
    """
    Display an interactive zoomable map of groundwater types.
    
    Parameters:
    -----------
    gw_map_path : str
        Path to the groundwater geopackage file
    zoom_level : int, default=10
        Initial zoom level for the map
    map_center : tuple, default=None
        Center coordinates (lat, lon) for the map. If None, uses data bounds
    map_title : str, optional
        Optional title displayed at the top of the map
    
    Returns:
    --------
    folium.Map
        Interactive map object
    """
    
    # --- Robust read to avoid intermittent "database is locked" on shared JupyterHub storage ---
    def _safe_read_gpkg(path: str, layer: str, attempts: int = 5, delay: float = 0.6):
        last_err = None
        # If WAL sidecar files linger, copy to a local temp file each attempt
        for i in range(attempts):
            try:
                # Always copy to a unique temp file (sidesteps file-level locks on NFS)
                with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp:
                    tmp_path = tmp.name
                shutil.copy2(path, tmp_path)
                try:
                    return gpd.read_file(tmp_path, layer=layer)
                finally:
                    # Best-effort cleanup
                    for ext in ('', '-wal', '-shm'):
                        try:
                            os.remove(tmp_path + ext)
                        except OSError:
                            pass
            except Exception as e:  # noqa: BLE001
                last_err = e
                # If not a lock related issue, break early
                if 'lock' not in str(e).lower():
                    break
                time.sleep(delay)
        raise last_err if last_err else RuntimeError('Unknown failure reading GeoPackage')

    gw_map_gdf = _safe_read_gpkg(gw_map_path, layer='GS_GW_LEITER_F')
    
    # Keep only essential columns to avoid JSON serialization issues
    # Only keep GWLTYP (groundwater type) and geometry
    essential_columns = ['GWLTYP', 'geometry']
    gw_map_gdf = gw_map_gdf[essential_columns]
    
    # Convert to WGS84 for folium
    if gw_map_gdf.crs != "EPSG:4326":
        gw_map_gdf = gw_map_gdf.to_crs("EPSG:4326")
    
    # Define custom colors for each category
    custom_colors = {
        1: '#eda53f',  # light orange
        2: '#cfe2f3',  # pale blue
        3: '#cfe2f3',
        4: '#9fc5e8',  # slightly darker pale blue
        6: '#6fa8dc',  # darkest shade of pale blue
        8: '#ead1dc',  # lighter pink
        10: '#d5a6bd',  # light pink
    }
    
    # Set default colors for any type not explicitly defined
    default_colors = [
        '#e41a1c',  # Red
        '#984ea3',  # Purple
        '#ff7f00',  # Orange
        '#ffff33',  # Yellow
        '#a65628',  # Brown
        '#f781bf',  # Pink
        '#999999'   # Gray
    ]
    
    # Get unique groundwater types
    gw_types = gw_map_gdf['GWLTYP'].unique()
    
    # Create color dictionary
    color_dict = {}
    default_color_index = 0
    
    for gw_type in gw_types:
        if gw_type in custom_colors:
            color_dict[gw_type] = custom_colors[gw_type]
        else:
            color_dict[gw_type] = default_colors[default_color_index % len(default_colors)]
            default_color_index += 1
    
    # English labels for groundwater types
    type_labels = {
        1: 'Low groundwater thickness area (mostly less than 2m)',
        2: 'Medium groundwater thickness area (2 to 10m)',
        3: 'Suspected groundwater occurrence',
        4: 'High groundwater thickness area (10 to 20m)',
        6: 'Very high groundwater thickness area (more than 20m)',
        8: 'Gravel groundwater aquifer above valleys, low thickness',
        10: 'Gravel groundwater aquifer above valleys, medium thickness',
    }
    
    # Calculate map center if not provided
    if map_center is None:
        bounds = gw_map_gdf.total_bounds
        map_center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    
    # Create the map with tiles=None then add multiple base layers explicitly.
    # Rationale: Some JupyterHub deployments or corporate proxies intermittently block
    # the default OpenStreetMap layer requested via the folium.Map(tiles=...) shortcut,
    # leading to a blank (grey) background. By adding explicit TileLayer objects we:
    #  (1) provide multiple fallback providers, and
    #  (2) ensure a visible base layer even if one provider fails.
    m = folium.Map(
        location=map_center,
        zoom_start=zoom_level,
        tiles=None,
        control_scale=True
    )
    try:
        # OpenStreetMap (provider name is safe)
        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            name='OpenStreetMap',
            overlay=False,
            control=True
        ).add_to(m)
        # Carto Positron (explicit URL + attribution to avoid provider name mismatch across folium versions)
        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            name='CartoDB Positron',
            overlay=False,
            control=True
        ).add_to(m)
        # Stamen Terrain (explicit URL + attribution)
        folium.TileLayer(
            tiles='https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png',
            attr='Map tiles by <a href="http://stamen.com">Stamen Design</a>, CC BY 3.0 — Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            name='Stamen Terrain',
            overlay=False,
            control=True
        ).add_to(m)
    except Exception as _tile_err:
        warnings.warn(f"Could not add one or more base tile layers: {_tile_err}")
    
    # Add each groundwater type as a separate layer
    for gw_type in gw_types:
        # Filter data for this type
        type_data = gw_map_gdf[gw_map_gdf['GWLTYP'] == gw_type]
        
        # Get label and color
        label = type_labels.get(gw_type, f"Type {gw_type}")
        color = color_dict[gw_type]
        
        # Convert to GeoJSON format to avoid serialization issues
        geojson_data = type_data.to_json()
        
        # Add to map
        folium.GeoJson(
            geojson_data,
            style_function=lambda x, color=color: {
                'fillColor': color,
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.7,
            },
            popup=folium.Popup(label, parse_html=True),
            tooltip=label
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 10px; right: 10px; width: 300px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:10px; padding: 10px">
    <h4>Groundwater Types</h4>
    '''
    
    for gw_type in sorted(gw_types):
        label = type_labels.get(gw_type, f"Type {gw_type}")
        color = color_dict[gw_type]
        legend_html += f'''
        <div style="margin-bottom: 2px;">
            <span style="display: inline-block; width: 20px; height: 20px; 
                         background-color: {color}; border: 1px solid black; 
                         margin-right: 10px; vertical-align: middle;"></span>
            <span style="vertical-align: middle;">{label}</span>
        </div>
        '''
    
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    
    if map_title:
        title_style = _caption_css("margin:8px 0 6px 0;text-align:center;")
        title_html = f"<h3 style=\"{title_style}\">{map_title}</h3>"
        m.get_root().html.add_child(folium.Element(title_html))

    return m



def plot_model_area_map(
    gw_depth_path: str, 
    rivers_path: str | None = None, 
    gauges_path: str | None = None,
    model_boundary_path: str | None = None,
    figsize: Tuple[int, int] = (12, 12), 
    custom_title: str | None = None,
    show_river_labels: bool = True,
    basemap: Optional[Literal[
        "osm",
        "carto-positron",
        "carto-voyager",
        "esri-imagery",
        "opentopomap",]] = None,
    basemap_alpha: float = 0.9,
) -> Tuple[Any, Any]:
    """
    Displays a map with groundwater depth, and optionally rivers, gauges, and a model boundary.

    Parameters
    ----------
    gw_depth_path : str
        File path to the groundwater depth GeoPackage (.gpkg), layer 'GS_GW_LEITER_F'.
    rivers_path : str | None, optional
        File path to the rivers GeoPackage (.gpkg), layer 'AVZH_GEWAESSER_F'. If None, rivers are omitted.
    gauges_path : str | None, optional
        File path to the gauges GeoPackage (.gpkg), layer 'GS_GRUNDWASSERPEGEL_P'. If None, gauges are omitted.
    model_boundary_path : str | None, optional
        File path to the model boundary GeoPackage (.gpkg). If None, boundary is omitted.
    figsize : tuple, optional
        Figure size (width, height) in inches, by default (12, 12).
    custom_title : str | None, optional
        Custom title for the plot.
    show_river_labels : bool, optional
        If True and rivers are provided, label “Sihl” and “Limmat” on the map.
    basemap : {'osm','carto-positron','carto-voyager','esri-imagery','opentopomap'} | None, optional
        If set, adds a web tile basemap under the layers (via contextily). Default None.
    basemap_alpha : float, optional
        Tile transparency for the basemap.

    Returns
    -------
    tuple
        (fig, ax) Matplotlib figure and axes.
    """
    try:
        import os
        import geopandas as gpd
        import matplotlib.pyplot as plt
    except ImportError:
        print("This function requires 'geopandas' and 'matplotlib'.")
        print("Please install them using: pip install geopandas matplotlib")
        return None, None

    # --- 1. Load Geospatial Data ---
    gw_depth = gpd.read_file(gw_depth_path, layer='GS_GW_LEITER_F')

    rivers = None
    if rivers_path:
        try:
            if os.path.exists(rivers_path):
                rivers = gpd.read_file(rivers_path, layer='AVZH_GEWAESSER_F')
            else:
                print(f"Rivers path not found: {rivers_path}")
        except Exception as e:
            print(f"Could not load rivers from {rivers_path}: {e}")
            rivers = None

    gauges = None
    if gauges_path:
        try:
            if os.path.exists(gauges_path):
                gauges = gpd.read_file(gauges_path, layer='GS_GRUNDWASSERPEGEL_P')
            else:
                print(f"Gauges path not found: {gauges_path}")
        except Exception as e:
            print(f"Could not load gauges from {gauges_path}: {e}")
            gauges = None

    # --- 2. Define Color Scheme and Labels ---
    custom_colors = {
        1: '#eda53f',
        2: '#cfe2f3',
        3: '#cfe2f3',
        4: '#9fc5e8',
        6: '#6fa8dc',
        8: '#ead1dc',
        10: '#d5a6bd',
    }
    type_labels = {
        1: 'Low thickness (<2m)',
        2: 'Medium thickness (2-10m)',
        3: 'Suspected occurrence',
        4: 'High thickness (10-20m)',
        6: 'Very high thickness (>20m)',
        8: 'Gravel aquifer, low thickness',
        10: 'Gravel aquifer, medium thickness',
    }

    gw_depth['GWL_DESC'] = gw_depth['GWLTYP'].map(type_labels).fillna('Other')
    desc_to_type = {v: k for k, v in type_labels.items()}
    sorted_descriptions = sorted(gw_depth['GWL_DESC'].unique())
    colors_list = [custom_colors.get(desc_to_type.get(desc), '#999999') for desc in sorted_descriptions]
    from matplotlib.colors import ListedColormap
    custom_cmap = ListedColormap(colors_list)

    # --- 3. Create the Plot ---
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # Base layer (creates its own legend)
    gw_depth.plot(
        ax=ax, column='GWL_DESC', categorical=True, legend=True,
        legend_kwds={'title': "Groundwater Type", 'loc': 'upper right', 'bbox_to_anchor': (1.0, 1.0)},
        cmap=custom_cmap, alpha=0.7
    )

    # Other layers (we make a manual legend for these)
    legend_handles = []
    legend_labels = []

    if rivers is not None and not rivers.empty:
        rivers.plot(ax=ax, color='blue', linewidth=1.5)
        from matplotlib.lines import Line2D
        legend_handles.append(Line2D([0], [0], color='blue', lw=1.5, label='Rivers'))
        legend_labels.append('Rivers')

    if gauges is not None and not gauges.empty:
        gauges.plot(ax=ax, color='red', marker='^', markersize=50)
        from matplotlib.lines import Line2D
        legend_handles.append(Line2D([0], [0], marker='^', color='red', label='Gauges', linestyle='None', markersize=8))
        legend_labels.append('Gauges')

    # --- Optional river labels ---
    if show_river_labels and (rivers is not None) and (not rivers.empty):
        # Pick the name column robustly
        possible_name_cols = ['GEWAESSERNAME', 'NAME', 'name', 'GEW_NAME', 'GEWAESSER', 'WATERBODY', 'waterbody']
        name_col = next((c for c in possible_name_cols if c in rivers.columns), None)

        # Utility to offset in meters or degrees depending on CRS
        def _offset_vals(dx_m=0.0, dy_m=0.0):
            if getattr(rivers, "crs", None) is not None and getattr(rivers.crs, "is_geographic", False):
                return dx_m / 100000.0, dy_m / 100000.0
            return dx_m, dy_m

        # Clip surface water to focus window
        xlim = [2674000, 2684000]
        ylim = [1246000, 1252000]
        try:
            rivers_clip = rivers.cx[xlim[0]:xlim[1], ylim[0]:ylim[1]]
        except Exception:
            rivers_clip = rivers

        def label_feature(label_text: str, query_value: str, color='blue', fontsize=13, dx=0.0, dy=0.0):
            if name_col is None:
                return
            subset = rivers_clip[rivers_clip[name_col].astype(str).str.contains(rf'\b{query_value}\b', case=False, na=False)]
            if subset.empty:
                return
            geom = union_all(list(subset.geometry))
            rp = geom.representative_point()
            dxv, dyv = _offset_vals(dx, dy)
            import matplotlib.patheffects as path_effects
            txt = ax.annotate(
                label_text,
                xy=(rp.x + dxv, rp.y + dyv),
                ha='center', va='center',
                fontsize=fontsize, color=color, fontweight='bold', alpha=0.95, zorder=10
            )
            txt.set_path_effects([
                path_effects.Stroke(linewidth=3.0, foreground='white'),
                path_effects.Normal()
            ])

        label_feature("Sihl", "Sihl", dx=-700.0, dy=-600.0)
        label_feature("Limmat", "Limmat", dx=6000.0, dy=-1000.0)

        # Lake Zurich label (robust to umlauts)
        if name_col is not None:
            norm_names = rivers_clip[name_col].astype(str).str.normalize('NFKD').str.encode('ascii', 'ignore').str.decode('ascii')
            lake_mask = norm_names.str.contains(r'\bZurichsee\b', case=False, na=False) | norm_names.str.contains(r'\blake zurich\b', case=False, na=False)
            lake_gdf = rivers_clip[lake_mask]
            if not lake_gdf.empty:
                lake_geom = union_all(list(lake_gdf.geometry))
                minx, miny, maxx, maxy = lake_geom.bounds
                lx, ly = maxx, miny
                ax.annotate(
                    "Lake Zurich", xy=(lx, ly), ha='center', va='center',
                    fontsize=12, color='black', fontweight='bold', zorder=10
                )

    # Plot model boundary and add legend handle
    if model_boundary_path:
        try:
            model_boundary = gpd.read_file(model_boundary_path)
            model_boundary.plot(ax=ax, facecolor='none', edgecolor='black', linestyle='--', linewidth=2.5)
            from matplotlib.lines import Line2D
            legend_handles.append(Line2D([0], [0], color='black', lw=2.5, linestyle='--', label='Model Boundary'))
            legend_labels.append('Model Boundary')
        except Exception as e:
            print(f"Could not load or plot model boundary from {model_boundary_path}: {e}")

    # Manual legend for non-categorical layers if any present
    if legend_handles:
        from matplotlib.legend import Legend
        legend2 = Legend(ax, legend_handles, legend_labels, loc='upper left')
        ax.add_artist(legend2)

    # --- 5. Formatting ---
    title_text = custom_title or 'Model Area Delineation'
    wrap_width = 90
    title_text = textwrap.fill(title_text, width=wrap_width)
    try:
        from style_utils import apply_caption_style, FIGURE_CAPTION_STYLE
        title_obj = apply_caption_style(ax, title_text, pad=10)
        title_obj.set_ha('center')
    except Exception:
        # Fallback uses same style dict if available (already imported earlier globally)
        fs = FIGURE_CAPTION_STYLE.get('fontsize', 12) if 'FIGURE_CAPTION_STYLE' in globals() else 10
        fw = FIGURE_CAPTION_STYLE.get('fontweight', 'bold') if 'FIGURE_CAPTION_STYLE' in globals() else 'bold'
        title_obj = ax.set_title(title_text, fontsize=fs, fontweight=fw, loc='center')
    # Ensure Matplotlib also wraps dynamically if space is tight
    try:
        title_obj.set_wrap(True)
    except Exception:
        pass

    ax.set_xlabel('Easting (m, CH1903+ / LV95)')
    ax.set_ylabel('Northing (m, CH1903+ / LV95)')
    ax.grid(True, linestyle=':', alpha=0.6)

    ax.set_xlim(2674000, 2684000)
    ax.set_ylim(1246000, 1252000)

    # Optional basemap (keeps axes in LV95 by passing crs)
    if basemap:
        try:
            import contextily as cx
            prov = cx.providers  # unified access to xyzservices via contextily
            # Map requested key to provider object names
            aliases = {
                "osm": ("OpenStreetMap", "Mapnik"),
                "carto-positron": ("CartoDB", "Positron"),
                "carto-voyager": ("CartoDB", "Voyager"),
                "esri-imagery": ("Esri", "WorldImagery"),
                "opentopomap": ("OpenTopoMap", None),
            }
            ns, layer = aliases.get(basemap, ("OpenStreetMap", "Mapnik"))
            try:
                src = getattr(prov, ns)
                if layer:
                    src = getattr(src, layer)
            except AttributeError:
                # Fallback to OSM Mapnik if requested provider not present
                src = prov.OpenStreetMap.Mapnik
            cx.add_basemap(ax, source=src, crs=gw_depth.crs, alpha=basemap_alpha, attribution_size=6)
        except Exception as e:
            print(f"Basemap '{basemap}' skipped: {e}")


    plt.tight_layout()
    return fig, ax




def display_concessions_map(
    concessions,
    boundary_gdf=None,
    id_col: str = "concession_id",
    use_col: str = "NUTZART",
    description_col: str = "BESCHREIBUNG",
    fassart_col: str = "FASSART",
    map_center=None,
    zoom_start: int = 14,
    map_title: str = None,
    max_description_chars: int = 180,
    marker_size: int = 14
):
    if isinstance(concessions, str):
        concessions_gdf = gpd.read_file(concessions)
    else:
        concessions_gdf = concessions.copy()

    if concessions_gdf.crs is None:
        raise ValueError("Concessions GeoDataFrame must have a CRS defined.")
    if not all(concessions_gdf.geometry.geom_type.isin(["Point"])):
        raise ValueError("Concessions layer must contain only Point geometries.")
    if concessions_gdf.crs.to_string() != "EPSG:4326":
        concessions_gdf = concessions_gdf.to_crs("EPSG:4326")

    if boundary_gdf is not None:
        b_gdf = boundary_gdf.copy()
        if b_gdf.crs is None:
            raise ValueError("Boundary GeoDataFrame must have a CRS defined.")
        if b_gdf.crs.to_string() != "EPSG:4326":
            b_gdf = b_gdf.to_crs("EPSG:4326")
    else:
        b_gdf = None

    if map_center is None:
        bounds = concessions_gdf.total_bounds
        map_center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    # --- Colors per concession (unique id) ---
    unique_ids = list(concessions_gdf[id_col].astype(str).unique())
    def generate_colors(n):
        return [f"hsl({int(360*i/n)},70%,45%)" for i in range(n or 1)]
    id_color_map = dict(zip(unique_ids, generate_colors(len(unique_ids))))

    # --- Shapes per use category (simple SVG set) ---
    use_categories = list(concessions_gdf[use_col].fillna("Unspecified").astype(str).unique())
    shape_cycle = ['circle', 'square', 'triangle', 'diamond', 'star']
    shape_map = {u: shape_cycle[i % len(shape_cycle)] for i, u in enumerate(use_categories)}

    m = folium.Map(location=map_center, zoom_start=zoom_start, tiles="OpenStreetMap")

    if map_title:
        title_style = _caption_css("position:relative;width:100%;display:block;padding:6px 0 4px 0;text-align:center;")
        # Maintain slightly lighter weight if original style requested 600 vs bold
        # (We already mapped weight from style dict; user can adjust there.)
        title_html = f"<div style=\"{title_style}\">{map_title}</div>"
        m.get_root().html.add_child(folium.Element(title_html))

    if b_gdf is not None and not b_gdf.empty:
        folium.GeoJson(
            b_gdf.to_json(),
            name="Model Boundary",
            style_function=lambda _:
                {"color": "black", "weight": 2, "fill": False, "dashArray": "5,5"}
        ).add_to(m)

    # --- Helper: build simple SVG for a given shape/color ---
    # Smaller marker size (reduced further per request)
    def _marker_svg(shape: str, fill: str, size: int = None, stroke: str = '#111') -> str:
        s = size or marker_size
        half = s / 2
        if shape == 'circle':
            body = f'<circle cx="{half}" cy="{half}" r="{half - 1.5}" fill="{fill}" stroke="{stroke}" stroke-width="1.2" />'
        elif shape == 'square':
            pad = 2
            body = f'<rect x="{pad}" y="{pad}" width="{s-2*pad}" height="{s-2*pad}" rx="3" ry="3" fill="{fill}" stroke="{stroke}" stroke-width="1.2" />'
        elif shape == 'triangle':
            body = f'<path d="M {half} 2 L {s-2} {s-2} L 2 {s-2} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.2" />'
        elif shape == 'diamond':
            body = f'<path d="M {half} 1.5 L {s-1.5} {half} L {half} {s-1.5} L 1.5 {half} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.2" />'
        elif shape == 'star':
            # Use original 24x24 coordinate system and scale down via width/height
            return (
                f'<svg width="{s}" height="{s}" viewBox="0 0 24 24">'
                '<path d="M12 2.5l2.6 5.5 6 .55-4.6 3.95 1.4 5.8L12 15.9 6.6 18.3l1.4-5.8L3.4 8.55l6-.55z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.0" stroke-linejoin="round" />'
                '</svg>'
            )
        else:
            body = f'<circle cx="{half}" cy="{half}" r="{half - 1.5}" fill="{fill}" stroke="{stroke}" stroke-width="1.2" />'
        return f'<svg width="{s}" height="{s}" viewBox="0 0 {s} {s}">{body}</svg>'

    # --- Add markers using DivIcon with inline SVG ---
    for _, row in concessions_gdf.iterrows():
        use_val = str(row.get(use_col, 'Unspecified'))
        cid_val = str(row.get(id_col, 'N/A'))
        desc_val = row.get(description_col, '')
        if isinstance(desc_val, str) and len(desc_val) > max_description_chars:
            desc_disp = desc_val[:max_description_chars] + '...'
        else:
            desc_disp = desc_val
        fass_val = row.get(fassart_col, 'N/A')

        color = id_color_map.get(cid_val, '#666666')
        shape = shape_map.get(use_val, 'circle')

        svg_html = _marker_svg(shape, color)
        # center offset half of size
        offset = marker_size / 2
        html = f'<div style="transform: translate(-{offset}px,-{offset}px);">{svg_html}</div>'

        tooltip_txt = f"{id_col}: {cid_val} | {fassart_col}: {fass_val}"
        popup_html = (
            f"<div style='font-size:12px;'><b>{id_col}:</b> {cid_val}<br>"
            f"<b>{use_col}:</b> {use_val}<br>"
            f"<b>{fassart_col}:</b> {fass_val}<br>"
            f"<b>Description:</b><br>{desc_disp}</div>"
        )

        folium.Marker(
            location=(row.geometry.y, row.geometry.x),
            icon=folium.DivIcon(html=html),
            tooltip=tooltip_txt,
            popup=folium.Popup(popup_html, max_width=320)
        ).add_to(m)

    # --- Legend for use (shape) categories with SVG icons mirroring BeautifyIcon shapes ---
    # Legend SVG uses neutral grey so color is reserved for ID differentiation on map
    def _legend_svg(shape: str, size: int = 12, fill: str = '#9a9a9a', stroke: str = '#222') -> str:
        half = size / 2
        if shape == 'circle':
            body = f'<circle cx="{half}" cy="{half}" r="{half - 1.2}" fill="{fill}" stroke="{stroke}" stroke-width="1.0" />'
        elif shape == 'square':
            pad = 1.5
            body = f'<rect x="{pad}" y="{pad}" width="{size-2*pad}" height="{size-2*pad}" rx="3" ry="3" fill="{fill}" stroke="{stroke}" stroke-width="1.0" />'
        elif shape == 'triangle':
            body = f'<path d="M {half} 1 L {size-1} {size-1} L 1 {size-1} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.0" />'
        elif shape == 'diamond':
            body = f'<path d="M {half} 1 L {size-1} {half} L {half} {size-1} L 1 {half} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.0" />'
        elif shape == 'star':
            return (
                f'<svg width="{size}" height="{size}" viewBox="0 0 24 24">'
                '<path d="M12 2.5l2.6 5.5 6 .55-4.6 3.95 1.4 5.8L12 15.9 6.6 18.3l1.4-5.8L3.4 8.55l6-.55z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="0.9" stroke-linejoin="round" />'
                '</svg>'
            )
        else:
            body = f'<circle cx="{half}" cy="{half}" r="{half - 1.2}" fill="{fill}" stroke="{stroke}" stroke-width="1.0" />'
        return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{body}</svg>'

    shape_legend_items = "".join(
        f"""
        <div style=\"display:flex;align-items:center;margin-bottom:4px;gap:6px;\">
            <div>{_legend_svg(shape_map[u])}</div>
            <div style=\"font-size:12px;line-height:1.1;\">
                <span style=\"font-weight:500;\">{u}</span>
            </div>
        </div>
        """
        for u in use_categories
    )
    shape_legend_html = f"""
    <div style=\"
        position: fixed;
        bottom: 12px; left: 12px; z-index:9999;
        background: white; padding:10px 12px;
        border:1px solid #888; border-radius:4px;
        box-shadow:0 0 4px rgba(0,0,0,0.3);\">
        <div style=\"font-weight:600; margin-bottom:6px; font-size:13px;\">
            Use (Marker Shape)
        </div>
        {shape_legend_items}
    </div>
    """
    m.get_root().html.add_child(folium.Element(shape_legend_html))

    # Optional ID legend if not too many
    if len(unique_ids) <= 20:
        # Build HTML for legend items
        id_items = "".join(
            f"<div style='display:flex;align-items:center;margin-bottom:3px;'>"
            f"<div style='width:14px;height:14px;background:{id_color_map[cid]};border:1px solid #222;margin-right:6px;'></div>"
            f"<div style='font-size:11px;'>{cid}</div>"
            f"</div>" for cid in unique_ids
        )

        # Inject a Leaflet control via a script tag (simpler than Jinja macro to avoid render issues)
        legend_container_html = (
            f"<div style=\"background:white;padding:10px 12px;border:1px solid #888;"+
            "border-radius:4px;max-height:300px;overflow-y:auto;"+
            "box-shadow:0 0 4px rgba(0,0,0,0.3);\">"+
            "<div style='font-weight:600;margin-bottom:6px;font-size:13px;'>Concession IDs (Color)</div>"+
            f"{id_items}"+
            "</div>"
        )
        legend_script = f"""
<script>
(function() {{
    var existing = document.querySelector('.concession-id-legend');
    if(existing) return; // avoid duplicates when re-rendered
    var idLegend = L.control({{position:'topright'}});
    idLegend.onAdd = function(map) {{
        var div = L.DomUtil.create('div','concession-id-legend');
        div.innerHTML = `{legend_container_html}`;
        L.DomEvent.disableClickPropagation(div);
        return div;
    }});
    idLegend.addTo({m.get_name()});
}})();
</script>
"""
        m.get_root().html.add_child(folium.Element(legend_script))

    folium.LayerControl(collapsed=True).add_to(m)
    return m



def plot_interactive_model_domain_3d(
    mf,
    bas=None,
    chd=None,
    riv=None,
    layer=0,
    exaggeration=1.0,
    engine="plotly",
    show_chd=True,
    show_riv=True,
    mask_inactive=True,
    top_alpha=0.65,
    bot_alpha=0.65,
    draw_grid=True,
    grid_line_color="#555555",
    grid_line_width=1.0,
    vertical_line_opacity=0.25,
    show_verticals=True,
    custom_title=None,
    fill_chd_surface=True,
    chd_surface_opacity=0.55,
    chd_surface_color="royalblue",
    chd_point_markers=False,
    show_chd_label=True,  # now only affects legend entry; no text annotation drawn
    chd_label_text="CHD boundary",
    show_exaggeration_label=True,
    exaggeration_label_format="Vertical exaggeration: {exag:g}x",
):
    """
    Interactive 3‑D view of single‑layer model geometry (top, bottom) and optional CHD / RIV cells.

    Now draws true grid surfaces (not just points) and (optionally) vertical
    lines connecting top/bottom corner nodes.

    Parameters
    ----------
    mf : flopy.modflow.Modflow
    bas : ModflowBas
    chd : ModflowChd
    riv : ModflowRiv
    layer : int
    exaggeration : float
        Vertical exaggeration factor.
    engine : {'plotly','mpl'}
    show_chd, show_riv : bool
    mask_inactive : bool
    top_alpha, bot_alpha : float
        Opacity of top / bottom surfaces.
    draw_grid : bool
        Draw horizontal grid lines on top & bottom surfaces.
    grid_line_color : str
    grid_line_width : float
    # --- New CHD surface options ---
    fill_chd_surface : bool
        Draw filled Mesh3d surface over CHD cells.
    chd_surface_opacity : float
        Opacity of CHD surface (0-1).
    chd_surface_color : str
        Color of CHD surface (solid fill).
    chd_point_markers : bool
        Still plot points for CHD (in addition to surface) when True.
    show_chd_label : bool
        Add a text label at centroid of CHD cells (Plotly engine only).
    chd_label_text : str
        Text for CHD boundary label.
    show_exaggeration_label : bool
        If True, adds a small annotation (lower-left) with the vertical exaggeration value.
    exaggeration_label_format : str
        Format string for exaggeration label; must contain '{exag}' placeholder.
    fill_chd_surface=True,
    chd_surface_opacity=0.55,
    chd_surface_color="royalblue",
    chd_point_markers=False,
    show_verticals : bool
        Draw vertical lines at each corner.
    vertical_line_opacity : float
    """
    if not hasattr(mf, "dis"):
        raise RuntimeError("Model missing DIS package.")
    dis = mf.dis
    top_centers = dis.top.array.copy()
    bot_centers = dis.botm.array[layer].copy()
    grid = mf.modelgrid
    nrow, ncol = top_centers.shape

    if bas is None:
        bas = mf.get_package("BAS6")
    if bas is None:
        # No BAS: proceed without masking (treat all as active)
        if mask_inactive:
            warnings.warn("BAS package not found; inactive cell masking skipped.", RuntimeWarning)
        ibound = np.ones((nrow, ncol), dtype=int)
        mask_inactive_effective = False
    else:
        ibound = bas.ibound.array[layer]
        mask_inactive_effective = mask_inactive

    # Mask inactive center cells only if we have BAS
    if mask_inactive_effective:
        inactive_mask = (ibound == 0)
        top_centers = np.where(inactive_mask, np.nan, top_centers)
        bot_centers = np.where(inactive_mask, np.nan, bot_centers)

    # Helper: derive corner elevations from surrounding active cell centers
    def centers_to_corners(arr2d):
        nr, nc = arr2d.shape
        corners = np.full((nr + 1, nc + 1), np.nan, dtype=float)
        for i in range(nr + 1):
            r_idx = [i - 1, i]
            r_idx = [r for r in r_idx if 0 <= r < nr]
            for j in range(nc + 1):
                c_idx = [j - 1, j]
                c_idx = [c for c in c_idx if 0 <= c < nc]
                vals = []
                for rr in r_idx:
                    for cc in c_idx:
                        v = arr2d[rr, cc]
                        if np.isfinite(v):
                            vals.append(v)
                if vals:
                    corners[i, j] = float(np.mean(vals))
        return corners

    top_corners = centers_to_corners(top_centers)
    bot_corners = centers_to_corners(bot_centers)

    # Collect CHD / RIV points (cell centers)
    # Collect CHD / RIV points & polys (for filled surface) AFTER ibound defined
    chd_cells = []  # (xc, yc, shead)
    chd_polys = []  # (row, col, shead)
    if show_chd and chd is not None:
        try:
            spd0 = chd.stress_period_data[0]
        except Exception:
            spd0 = []
        for rec in spd0:
            k_, i_, j_ = rec["k"], rec["i"], rec["j"]
            if k_ != layer:
                continue
            if mask_inactive and ibound[i_, j_] == 0:
                continue
            shead_val = float(rec["shead"])
            chd_cells.append((grid.xcellcenters[i_, j_],
                              grid.ycellcenters[i_, j_],
                              shead_val))
            chd_polys.append((i_, j_, shead_val))

    riv_stage_pts = []
    riv_rbot_pts = []
    if show_riv and riv is not None:
        r0 = riv.stress_period_data[0]
        for rec in r0:
            k, i, j = rec["k"], rec["i"], rec["j"]
            if k != layer:
                continue
            if mask_inactive and ibound[i, j] == 0:
                continue
            xc = grid.xcellcenters[i, j]
            yc = grid.ycellcenters[i, j]
            riv_stage_pts.append((xc, yc, float(rec["stage"])))
            riv_rbot_pts.append((xc, yc, float(rec["rbot"])))

    # Try plotly
    if engine == "plotly":
        try:
            import plotly.graph_objects as go
        except ImportError:
            warnings.warn("Plotly not installed. Falling back to Matplotlib.")
            engine = "mpl"

    if engine == "plotly":
        import plotly.graph_objects as go

        fig = go.Figure()

        # Corner coordinate arrays from FloPy (nrow+1, ncol+1)
        xv = grid.xvertices
        yv = grid.yvertices

        # Compute elevation range (true, un‑exaggerated)
        elev_min = float(np.nanmin([np.nanmin(bot_corners), np.nanmin(top_corners)]))
        elev_max = float(np.nanmax([np.nanmax(bot_corners), np.nanmax(top_corners)]))

        # Prepare shared color scaling (use true elevations, not exaggerated)
        cmin, cmax = elev_min, elev_max

        # Build tick labels so z-axis shows true elevations (not exaggerated values)
        if exaggeration != 1.0:
            nticks = 6
            real_ticks = np.linspace(elev_min, elev_max, nticks)
            scaled_tickvals = real_ticks * exaggeration
            ticktext = [f"{t:.1f}" for t in real_ticks]
        else:
            real_ticks = scaled_tickvals = ticktext = None

        # Surfaces (top & bottom) using corner grids
        fig.add_trace(go.Surface(
            x=xv,
            y=yv,
            z=top_corners * exaggeration,
            surfacecolor=top_corners,  # use true elevations for color
            cmin=cmin, cmax=cmax,
            colorscale="Viridis",
            opacity=top_alpha,
            showscale=True,          # single shared colorbar
            name="Top",
            colorbar=dict(title="Elevation (m)")
        ))
        fig.add_trace(go.Surface(
            x=xv,
            y=yv,
            z=bot_corners * exaggeration,
            surfacecolor=bot_corners,  # use true elevations for color
            cmin=cmin, cmax=cmax,
            colorscale="Viridis",
            opacity=bot_alpha,
            showscale=False,         # hide second (previously overlapping) colorbar
            name="Bottom"
        ))

        # Optional horizontal grid lines (top & bottom)
        if draw_grid:
            # Row lines
            for i in range(nrow + 1):
                # Top
                fig.add_trace(go.Scatter3d(
                    x=xv[i, :],
                    y=yv[i, :],
                    z=(top_corners[i, :] * exaggeration),
                    mode="lines",
                    line=dict(color=grid_line_color, width=grid_line_width),
                    hoverinfo="skip",
                    name="Top grid" if i == 0 else None,
                    showlegend=(i == 0)
                ))
                # Bottom
                fig.add_trace(go.Scatter3d(
                    x=xv[i, :],
                    y=yv[i, :],
                    z=(bot_corners[i, :] * exaggeration),
                    mode="lines",
                    line=dict(color=grid_line_color, width=grid_line_width),
                    hoverinfo="skip",
                    name="Bottom grid" if i == 0 else None,
                    showlegend=(i == 0)
                ))
            # Column lines
            for j in range(ncol + 1):
                fig.add_trace(go.Scatter3d(
                    x=xv[:, j],
                    y=yv[:, j],
                    z=(top_corners[:, j] * exaggeration),
                    mode="lines",
                    line=dict(color=grid_line_color, width=grid_line_width),
                    hoverinfo="skip",
                    name=None,
                    showlegend=False
                ))
                fig.add_trace(go.Scatter3d(
                    x=xv[:, j],
                    y=yv[:, j],
                    z=(bot_corners[:, j] * exaggeration),
                    mode="lines",
                    line=dict(color=grid_line_color, width=grid_line_width),
                    hoverinfo="skip",
                    name=None,
                    showlegend=False
                ))

        # Vertical corner lines
        if show_verticals:
            vx = xv.ravel()
            vy = yv.ravel()
            zt = (top_corners * exaggeration).ravel()
            zb = (bot_corners * exaggeration).ravel()
            seg_x = []
            seg_y = []
            seg_z = []
            for x0, y0, z0t, z0b in zip(vx, vy, zt, zb):
                if np.isnan(z0t) or np.isnan(z0b):
                    continue
                seg_x.extend([x0, x0, None])
                seg_y.extend([y0, y0, None])
                seg_z.extend([z0b, z0t, None])
            if seg_x:
                fig.add_trace(go.Scatter3d(
                    x=seg_x,
                    y=seg_y,
                    z=seg_z,
                    mode="lines",
                    line=dict(color="rgba(120,120,120,0.6)", width=1),
                    opacity=vertical_line_opacity,
                    hoverinfo="skip",
                    name="Vertical grid"
                ))

        # Add a legend-only square marker for CHD boundary (no spatial text label)
        if show_chd and show_chd_label and (chd_cells or fill_chd_surface):
            fig.add_trace(go.Scatter3d(
                x=[None], y=[None], z=[None],  # dummy for legend only
                mode="markers",
                marker=dict(size=8, color=chd_surface_color, symbol="square"),
                name=chd_label_text,
                hoverinfo="skip",
                showlegend=True
            ))

        # CHD points
        # CHD filled surface (Mesh3d of quads triangulated)
        if show_chd and fill_chd_surface and chd_polys:
            verts_x = []
            verts_y = []
            verts_z = []
            tri_i = []
            tri_j = []
            tri_k = []
            vcount = 0
            for (ri, cj, shead_val) in chd_polys:
                try:
                    cell_verts = grid.get_cell_vertices(ri, cj)
                except Exception:
                    continue
                if not cell_verts:
                    continue
                if len(cell_verts) >= 4 and cell_verts[0] == cell_verts[-1]:
                    quad = cell_verts[:-1][:4]
                else:
                    quad = cell_verts[:4]
                if len(quad) < 4:
                    continue
                for (vx0, vy0) in quad:
                    verts_x.append(vx0)
                    verts_y.append(vy0)
                    verts_z.append(shead_val * exaggeration)
                tri_i.append(vcount + 0)
                tri_j.append(vcount + 1)
                tri_k.append(vcount + 2)
                tri_i.append(vcount + 0)
                tri_j.append(vcount + 2)
                tri_k.append(vcount + 3)
                vcount += 4
            if verts_x:
                fig.add_trace(go.Mesh3d(
                    x=verts_x,
                    y=verts_y,
                    z=verts_z,
                    i=tri_i,
                    j=tri_j,
                    k=tri_k,
                    color=chd_surface_color,
                    opacity=chd_surface_opacity,
                    name="CHD surface",
                    hoverinfo="skip",
                    flatshading=True,
                ))

        # CHD points (optional or fallback)
        if chd_cells and (chd_point_markers or not fill_chd_surface):
            cx, cy, cz = zip(*[(a, b, c * exaggeration) for a, b, c in chd_cells])
            fig.add_trace(go.Scatter3d(
                x=cx, y=cy, z=cz,
                mode="markers",
                marker=dict(size=5, color="blue", symbol="diamond"),
                name="CHD shead (pts)"
            ))


        # RIV stage & rbot
        if riv_stage_pts:
            rx, ry, rz = zip(*[(a, b, c * exaggeration) for a, b, c in riv_stage_pts])
            fig.add_trace(go.Scatter3d(
                x=rx, y=ry, z=rz,
                mode="markers",
                marker=dict(size=4, color="deepskyblue"),
                name="RIV stage"
            ))
        if riv_rbot_pts:
            rbx, rby, rbz = zip(*[(a, b, c * exaggeration) for a, b, c in riv_rbot_pts])
            fig.add_trace(go.Scatter3d(
                x=rbx, y=rby, z=rbz,
                mode="markers",
                marker=dict(size=3, color="navy"),
                name="RIV rbot"
            ))

        if custom_title:
            fig.update_layout(title=custom_title)
        else: 
            fig.update_layout(title="Interactive 3D Model Domain (Plotly)")

        scene_kwargs = dict(
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Elevation (m)",
            aspectmode="data"
        )
        if exaggeration != 1.0 and scaled_tickvals is not None:
            scene_kwargs["zaxis"] = dict(
                title="Elevation (m)",
                tickmode="array",
                tickvals=scaled_tickvals,
                ticktext=ticktext
            )

        fig.update_layout(
            scene=scene_kwargs,
            legend=dict(
                itemsizing="constant",
                x=0.01,          # left side
                y=0.98,           # upper vertically
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(255,255,255,0.6)",
                bordercolor="rgba(150,150,150,0.4)",
                borderwidth=1
            ),
            margin=dict(l=0, r=0, b=0, t=40)
        )
        # Add vertical exaggeration annotation (lower-left corner)
        if show_exaggeration_label:
            try:
                label_txt = exaggeration_label_format.format(exag=exaggeration)
            except Exception:
                label_txt = f"Vertical exaggeration: {exaggeration:g}x"
            fig.add_annotation(dict(
                x=0.01, y=0.02, xref='paper', yref='paper',
                text=label_txt,
                showarrow=False,
                font=dict(size=11, color='black'),
                bgcolor='rgba(255,255,255,0.65)',
                bordercolor='rgba(120,120,120,0.5)',
                borderwidth=1,
                align='left'
            ))
        return fig

    # Matplotlib fallback unchanged (still scatter at centers)
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    xcc = grid.xcellcenters
    ycc = grid.ycellcenters
    ax.scatter(xcc[~np.isnan(bot_centers)],
               ycc[~np.isnan(bot_centers)],
               bot_centers[~np.isnan(bot_centers)] * exaggeration,
               s=3, c=bot_centers[~np.isnan(bot_centers)], cmap="terrain", alpha=bot_alpha, label="Bottom")
    ax.scatter(xcc[~np.isnan(top_centers)],
               ycc[~np.isnan(top_centers)],
               top_centers[~np.isnan(top_centers)] * exaggeration,
               s=3, c=top_centers[~np.isnan(top_centers)], cmap="viridis", alpha=top_alpha, label="Top")

    if chd_cells:
        cx, cy, cz = zip(*[(a, b, c * exaggeration) for a, b, c in chd_cells])
        ax.scatter(cx, cy, cz, c="blue", s=15, marker="D", label="CHD shead")

    if riv_stage_pts:
        rx, ry, rz = zip(*[(a, b, c * exaggeration) for a, b, c in riv_stage_pts])
        ax.scatter(rx, ry, rz, c="deepskyblue", s=12, marker="o", label="RIV stage")
    if riv_rbot_pts:
        rbx, rby, rbz = zip(*[(a, b, c * exaggeration) for a, b, c in riv_rbot_pts])
        ax.scatter(rbx, rby, rbz, c="navy", s=10, marker="x", label="RIV rbot")

    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Elevation (m)")
    if custom_title:
        ax.set_title(custom_title)
    else:
        ax.set_title("3D Model Domain (Matplotlib fallback)")
    ax.legend(loc="upper left")
    plt.tight_layout()
    return fig


def create_dem_overlay_map(
    dem_path: str,
    colormap: str = "viridis",
    opacity: float = 0.55,
    clip_percentiles: tuple[float, float] = (1, 99),
    tiles: str = "OpenStreetMap",
    zoom_start: int | None = None,
    add_layer_control: bool = True,
):
    """Return a folium.Map with a semi‑transparent DEM overlay on a tile background.

    Parameters
    ----------
    dem_path : str
        Path to a raster readable by rasterio.
    colormap : str, default 'viridis'
        Matplotlib colormap name.
    opacity : float, default 0.55
        Overall DEM layer opacity (alpha embedded per pixel). 0..1.
    clip_percentiles : (float, float), default (1, 99)
        Lower/upper percentiles for robust elevation stretch.
    tiles : str, default 'OpenStreetMap'
        Base tiles name accepted by folium (e.g., 'OpenStreetMap','CartoDB.Positron').
    zoom_start : int | None
        If provided, overrides automatic zoom. If None a heuristic is used.
    add_layer_control : bool, default True
        If True adds a layer control widget.

    Returns
    -------
    folium.Map
        Interactive map with DEM overlay.
    """
    try:
        import rasterio
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors
        from pyproj import Transformer
    except ImportError as e:
        raise ImportError("create_dem_overlay_map requires rasterio, matplotlib, pyproj") from e

    with rasterio.open(dem_path) as src:
        data = src.read(1).astype(float)
        bounds = src.bounds
        src_crs = src.crs

    # Handle invalids
    data[~np.isfinite(data)] = np.nan
    if np.isnan(data).all():
        vmin, vmax = 0, 1
    else:
        valid = data[np.isfinite(data)]
        if valid.size:
            p_lo, p_hi = clip_percentiles
            vmin, vmax = np.percentile(valid, [p_lo, p_hi])
        else:
            vmin, vmax = float(np.nanmin(data)), float(np.nanmax(data))

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = cm.get_cmap(colormap)
    rgba = cmap(norm(data))  # 0..1 floats
    rgba[..., 3] = opacity
    rgba[~np.isfinite(data), 3] = 0.0
    img = (rgba * 255).astype(np.uint8)

    # Project bounds to WGS84
    transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    lon_min, lat_min = transformer.transform(bounds.left, bounds.bottom)
    lon_max, lat_max = transformer.transform(bounds.right, bounds.top)
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    # Heuristic zoom: rough guess by latitude span
    if zoom_start is None:
        lat_span = abs(lat_max - lat_min)
        if lat_span > 2:
            zoom_start = 7
        elif lat_span > 0.5:
            zoom_start = 9
        elif lat_span > 0.1:
            zoom_start = 11
        else:
            zoom_start = 13

    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles=tiles, control_scale=True)

    folium.raster_layers.ImageOverlay(
        image=img,
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        opacity=1.0,  # internal alpha used
        name="DEM overlay",
        interactive=False,
        cross_origin=False,
        zindex=2,
    ).add_to(fmap)

    if add_layer_control:
        folium.LayerControl().add_to(fmap)

    return fmap


def create_interactive_dem_map(
    dem_path: str,
    colormaps: tuple[str, ...] = ("viridis", "plasma", "cividis", "terrain"),
    default_colormap: str = "viridis",
    opacity: float = 0.55,
    clip_percentiles: tuple[float, float] = (1, 99),
    tiles: str = "OpenStreetMap",
    zoom_start: int | None = None,
    container_title: str = "DEM Controls",
    custom_title: str | None = None
):
    """Create an interactive folium map with a DEM overlay and UI controls.

    Features (client-side JS):
      * Opacity slider (updates overlay opacity)
      * Colormap dropdown (switches pre-rendered colorized PNGs)
      * Reverse checkbox (toggles between normal & reversed LUT)

    Implementation notes:
      * All (colormap, reversed) variants are pre-rendered once and embedded
        as base64 data URIs. Switching is instant without round trips.
      * PNGs generated via matplotlib (plt.imsave) to avoid adding Pillow.

    Parameters
    ----------
    dem_path : str
        Raster path readable by rasterio.
    colormaps : tuple[str,...]
        List of matplotlib colormap names to provide.
    default_colormap : str
        Initially selected colormap (must be in colormaps).
    opacity : float
        Initial opacity (0..1).
    clip_percentiles : (float,float)
        Robust stretch percentiles.
    tiles : str
        Base tiles provider name.
    zoom_start : int | None
        Optional manual zoom; else derived from raster extent.
    container_title : str
        Title shown atop control box.
    custom_title : str | None
        Title shown atop the map.

    Returns
    -------
    folium.Map
        Interactive map object.
    """
    try:
        import rasterio
        import matplotlib.cm as cm
        import matplotlib.colors as mcolors
        from pyproj import Transformer
        import matplotlib.pyplot as plt
        from io import BytesIO
        import base64
    except ImportError as e:
        raise ImportError("create_interactive_dem_map requires rasterio, matplotlib, pyproj") from e

    if default_colormap not in colormaps:
        raise ValueError(f"default_colormap '{default_colormap}' not in provided colormaps {colormaps}")

    # -- Load raster --
    with rasterio.open(dem_path) as src:
        data = src.read(1).astype(float)
        bounds = src.bounds
        src_crs = src.crs

    data[~np.isfinite(data)] = np.nan
    if np.isnan(data).all():
        vmin, vmax = 0, 1
    else:
        valid = data[np.isfinite(data)]
        if valid.size:
            vmin, vmax = np.percentile(valid, list(clip_percentiles))
        else:
            vmin, vmax = float(np.nanmin(data)), float(np.nanmax(data))

    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    def render_png(cmap_name: str, reverse: bool) -> str:
        cmap_obj = cm.get_cmap(cmap_name)
        if reverse:
            cmap_obj = cmap_obj.reversed()
        rgba = cmap_obj(norm(data))  # float 0..1
        # Uniform alpha handled client side so keep full alpha then adjust by opacity in JS
        rgba[..., 3] = 1.0
        rgba[~np.isfinite(data), 3] = 0.0
        buf = BytesIO()
        plt.imsave(buf, rgba, format="png")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    # Precompute images
    image_registry: dict[str, dict[str, str]] = {}
    for cmap_name in colormaps:
        image_registry[cmap_name] = {
            "normal": render_png(cmap_name, False),
            "reversed": render_png(cmap_name, True),
        }

    # Project bounds to WGS84
    transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    lon_min, lat_min = transformer.transform(bounds.left, bounds.bottom)
    lon_max, lat_max = transformer.transform(bounds.right, bounds.top)
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    # Zoom heuristic
    if zoom_start is None:
        lat_span = abs(lat_max - lat_min)
        if lat_span > 2:
            zoom_start = 7
        elif lat_span > 0.5:
            zoom_start = 9
        elif lat_span > 0.1:
            zoom_start = 11
        else:
            zoom_start = 13

    # Base map with explicit multi-provider support. We set tiles=None first and add providers.
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles=None, control_scale=True)

    # Add a suite of base layers; ensure requested 'tiles' provider is added last so it is active.
    # Mapping from generic parameter values to folium provider specs or (custom URL, attr, name)
    provider_order = [
        ('openstreetmap', ('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                           '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                           'OpenStreetMap')),
        ('carto-positron', ('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                            'CartoDB Positron')),
        ('carto-voyager', ('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
                           '&copy; OpenStreetMap contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                           'CartoDB Voyager')),
        ('esri-imagery', ('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                          'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
                          'Esri WorldImagery')),
        ('opentopomap', ('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
                         'Map data: &copy; OpenStreetMap contributors, SRTM | Style: &copy; OpenTopoMap (CC-BY-SA)',
                         'OpenTopoMap')),
    ]

    # Normalize tiles param for matching
    norm_tiles = (tiles or 'OpenStreetMap').lower()
    added = set()
    for key, (prov, attr, name) in provider_order:
        try:
            if attr is not None:
                folium.TileLayer(tiles=prov, attr=attr, name=name, overlay=False, control=True).add_to(fmap)
            else:
                folium.TileLayer(prov, name=name, control=True).add_to(fmap)
            added.add(key)
        except Exception as _tile_err:
            warnings.warn(f"Failed to add base layer {key}: {_tile_err}")
    # If requested provider exists, add it again last (activates it) unless already last via ordering
    try:
        if norm_tiles not in added:
            pass  # already handled via default OSM fallback
        elif norm_tiles not in ('opentopomap', 'esri-imagery') and norm_tiles != 'openstreetmap':
            # Add its folium name again to ensure activation (only for some carto variants)
            mapping = {
                'carto-positron': 'CartoDB Positron',
                'carto-voyager': 'CartoDB Voyager',
            }
            if norm_tiles in mapping:
                folium.TileLayer(mapping[norm_tiles], name=mapping[norm_tiles], control=True).add_to(fmap)
    except Exception as _reactivate_err:
        warnings.warn(f"Could not set requested base layer active: {_reactivate_err}")

    if custom_title:
        map_title = custom_title
    else:
        map_title = "Digital Elevation Model"
    if map_title:
        # Reuse unified caption CSS (function defined near top)
        title_style = _caption_css("position:relative;width:100%;text-align:center;padding:6px 0 4px 0;")
        title_html = f"<div style=\"{title_style}\">{map_title}</div>"
        fmap.get_root().html.add_child(folium.Element(title_html))

    # Add initial overlay as standard Folium layer (data URI works as image source)
    initial_src = image_registry[default_colormap]["normal"]
    overlay = folium.raster_layers.ImageOverlay(
        image=initial_src,
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        opacity=opacity,
        name="DEM overlay",
        interactive=False,
        cross_origin=False,
        zindex=2,
    )
    overlay.add_to(fmap)

    # Build control panel HTML & JS logic
    # JSON registry for images
    import json as _json
    registry_json = _json.dumps(image_registry)
    # Escape braces used by JS object/blocks with double braces in f-string
    options_html = ''.join(
        f"<option value='{c}' {'selected' if c==default_colormap else ''}>{c}</option>" for c in colormaps
    )
    controls_html = f"""
        <div id='dem-control-box' style='position: fixed; bottom: 12px; right: 12px; z-index:9999; background: rgba(255,255,255,0.9); padding:10px 12px; border:1px solid #777; border-radius:6px; width: 220px; font-family: Arial, sans-serif; font-size:12px;'>
            <div style='font-weight:bold; font-size:13px; margin-bottom:4px;'>{container_title}</div>
            <label style='display:block; margin-top:4px;'>Colormap
                <select id='dem-colormap-select' style='width:100%; margin-top:2px;'>
                    {options_html}
                </select>
            </label>
            <label style='display:block; margin-top:6px;'>Opacity: <span id='dem-opacity-val'>{int(opacity*100)}</span>%
                <input id='dem-opacity-slider' type='range' min='0' max='100' value='{int(opacity*100)}' step='1' style='width:100%;'>
            </label>
            <label style='display:block; margin-top:6px;'>
                <input id='dem-reverse-checkbox' type='checkbox' style='vertical-align:middle;'> Reverse
            </label>
        </div>
        <script>
            (function() {{
                var registry = {registry_json};
                var selectEl = document.getElementById('dem-colormap-select');
                var sliderEl = document.getElementById('dem-opacity-slider');
                var reverseEl = document.getElementById('dem-reverse-checkbox');
                var opacityVal = document.getElementById('dem-opacity-val');
                function getOverlayImg() {{
                    var imgs = document.querySelectorAll('img.leaflet-image-layer');
                    for (var i=0; i<imgs.length; i++) {{
                        if (imgs[i].src && imgs[i].src.indexOf('data:image/png;base64') === 0) return imgs[i];
                    }}
                    return null;
                }}
                function updateImage() {{
                    var img = getOverlayImg();
                    if (!img) return;
                    var cmap = selectEl.value;
                    var mode = reverseEl.checked ? 'reversed' : 'normal';
                    img.src = registry[cmap][mode];
                }}
                function updateOpacity() {{
                    var img = getOverlayImg();
                    var op = parseInt(sliderEl.value, 10)/100.0;
                    opacityVal.textContent = parseInt(sliderEl.value,10);
                    if (img) img.style.opacity = op;
                }}
                selectEl.addEventListener('change', updateImage);
                reverseEl.addEventListener('change', updateImage);
                sliderEl.addEventListener('input', updateOpacity);
            }})();
        </script>
        """
    fmap.get_root().html.add_child(folium.Element(controls_html))

    return fmap










