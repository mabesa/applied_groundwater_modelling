import folium
from folium.plugins import BeautifyIcon
import geopandas as gpd
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
    
    # Load the groundwater data
    gw_map_gdf = gpd.read_file(gw_map_path, layer='GS_GW_LEITER_F')
    
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
    
    # Create the map
    m = folium.Map(
        location=map_center,
        zoom_start=zoom_level,
        tiles='OpenStreetMap'
    )
    
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
        title_html = f"""
        <h3 style="text-align:center; font-family:Arial, sans-serif;
                   font-size:16px; font-weight:bold; margin:8px 0 6px 0;">
            {map_title}
        </h3>
        """
        # Insert before map container in notebook display
        m.get_root().html.add_child(folium.Element(title_html))

    return m

'''
def plot_model_area_map(
    gw_depth_path: str, 
    rivers_path: str, 
    gauges_path: str,
    model_boundary_path: str = None,
    figsize: Tuple[int, int] = (12, 12), 
    custom_title: str = None,
    show_river_labels: bool = True
) -> Tuple[Any, Any]:
    """
    Displays a map with groundwater depth, rivers, gauges, and an optional model boundary.

    This function loads and plots geospatial data for groundwater depth, 
    river networks, monitoring gauges, and an optional model boundary outline.

    Requires the 'geopandas' and 'matplotlib' libraries.

    Parameters
    ----------
    gw_depth_path : str
        File path to the groundwater depth GeoPackage (.gpkg).
    rivers_path : str
        File path to the rivers GeoPackage (.gpkg).
    gauges_path : str
        File path to the gauges GeoPackage (.gpkg).
    model_boundary_path : str, optional
        File path to the model boundary GeoPackage (.gpkg), by default None.
    figsize : tuple, optional
        Figure size (width, height) in inches, by default (12, 12).
    custom_title : str, optional
        Custom title for the plot, by default None.
    show_river_labels : bool, optional
        If True, label the rivers “Sihl” and “Limmat” on the map, by default True.

    Returns
    -------
    tuple
        A tuple containing the Matplotlib figure and axes objects.
    """
    try:
        import geopandas as gpd
        import matplotlib.pyplot as plt
    except ImportError:
        print("This function requires 'geopandas' and 'matplotlib'.")
        print("Please install them using: pip install geopandas matplotlib")
        return None, None

    # --- 1. Load Geospatial Data ---
    gw_depth = gpd.read_file(gw_depth_path, layer='GS_GW_LEITER_F')
    rivers = gpd.read_file(rivers_path, layer='AVZH_GEWAESSER_F')
    gauges = gpd.read_file(gauges_path, layer='GS_GRUNDWASSERPEGEL_P')

    # --- 2. Define Color Scheme and Labels ---
    custom_colors = {
        1: '#eda53f',  # light orange
        2: '#cfe2f3',  # pale blue
        3: '#cfe2f3',
        4: '#9fc5e8',  # slightly darker pale blue
        6: '#6fa8dc',  # darkest shade of pale blue
        8: '#ead1dc',  # lighter pink
        10: '#d5a6bd',  # light pink
    }
    
    # English labels for groundwater types
    type_labels = {
        1: 'Low thickness (<2m)',
        2: 'Medium thickness (2-10m)',
        3: 'Suspected occurrence',
        4: 'High thickness (10-20m)',
        6: 'Very high thickness (>20m)',
        8: 'Gravel aquifer, low thickness',
        10: 'Gravel aquifer, medium thickness',
    }

    # Add a new column with descriptive labels for the legend
    gw_depth['GWL_DESC'] = gw_depth['GWLTYP'].map(type_labels).fillna('Other')

    # Create a mapping from description back to GWLTYP to find the correct color
    desc_to_type = {v: k for k, v in type_labels.items()}
    
    # Get the unique descriptions and sort them alphabetically (this is how geopandas orders them)
    sorted_descriptions = sorted(gw_depth['GWL_DESC'].unique())
    
    # Create the color list in the same order as the sorted descriptions
    colors_list = [custom_colors.get(desc_to_type.get(desc), '#999999') for desc in sorted_descriptions]
    custom_cmap = ListedColormap(colors_list)

    # --- 3. Create the Plot ---
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # Plot base layers
    # This plot call creates its own legend for the groundwater types (Legend 1)
    gw_depth.plot(ax=ax, column='GWL_DESC', categorical=True, legend=True,
                  legend_kwds={'title': "Groundwater Type", 'loc': 'upper right', 'bbox_to_anchor': (1.0, 1.0)},
                  cmap=custom_cmap, alpha=0.7)
    
    # Plot other layers. We will create a manual legend for these.
    rivers.plot(ax=ax, color='blue', linewidth=1.5)
    gauges.plot(ax=ax, color='red', marker='^', markersize=50)

    # --- 4a. Optional river labels ---
    # Pick the name column robustly
    possible_name_cols = ['GEWAESSERNAME', 'NAME', 'name', 'GEW_NAME', 'GEWAESSER', 'WATERBODY', 'waterbody']
    name_col = next((c for c in possible_name_cols if c in rivers.columns), None)

    # Utility to offset in meters or degrees depending on CRS
    def _offset_vals(dx_m=0.0, dy_m=0.0):
        if getattr(rivers, "crs", None) is not None and getattr(rivers.crs, "is_geographic", False):
            # ~1e-3 deg ≈ 100 m near Zurich
            return dx_m / 100000.0, dy_m / 100000.0
        return dx_m, dy_m

    if show_river_labels and 'GEWAESSERNAME' in rivers.columns:

        # Clip the surface water layer to the following limits: 
        xlim = [2674000, 2684000]
        ylim = [1246000, 1252000]
        rivers = rivers.cx[xlim[0]:xlim[1], ylim[0]:ylim[1]]

        def label_feature(label_text: str, query_value: str, color='blue', fontsize=13, dx=0.0, dy=0.0):
            subset = rivers[rivers[name_col].astype(str).str.contains(rf'\b{query_value}\b', case=False, na=False)]
            if subset.empty:
                return
            geom = union_all(list(subset.geometry))
            rp = geom.representative_point()
            dxv, dyv = _offset_vals(dx, dy)
            txt = ax.annotate(
                label_text,
                xy=(rp.x + dxv, rp.y + dyv),
                ha='center',
                va='center',
                fontsize=fontsize,
                color=color,
                fontweight='bold',
                alpha=0.95,
                zorder=10
            )
            txt.set_path_effects([
                path_effects.Stroke(linewidth=3.0, foreground='white'),
                path_effects.Normal()
            ])

        # Move "Sihl" label more to the south-west
        label_feature("Sihl", "Sihl", dx=-700.0, dy=-600.0)

        # Ensure "Limmat" label is visible 
        label_feature("Limmat", "Limmat", dx=6000.0, dy=-1000.0)

        # Normalize names to match Zürichsee with or without umlaut/accents
        norm_names = rivers[name_col].astype(str).str.normalize('NFKD').str.encode('ascii', 'ignore').str.decode('ascii')
        lake_mask = norm_names.str.contains(r'\bZürichsee\b', case=False, na=False) | norm_names.str.contains(r'\blake zurich\b', case=False, na=False)
        lake_gdf = rivers[lake_mask]
        
        if not lake_gdf.empty:
            lake_geom = union_all(list(lake_gdf.geometry))
            minx, miny, maxx, maxy = lake_geom.bounds
            # Place near the lake outlet
            dx_in, dy_in = _offset_vals(0.0, 0.0)
            lx = maxx - dx_in
            ly = miny + dy_in
            lake_txt = ax.annotate(
                "Lake Zurich",
                xy=(lx, ly),
                ha='center',
                va='center',
                fontsize=12,
                color='black',
                fontweight='bold',
                zorder=10
            )
            lake_txt.set_path_effects([
                path_effects.Stroke(linewidth=2.5, foreground='black', alpha=0.4),
                path_effects.Normal()
            ])

        # Ensure "Lake Zurich" label is visible 
        label_feature("Lake Zurich", "Lake Zurich")


    # --- 4b. Create a second, manual legend (Legend 2) ---
    # Create proxy artists for the legend handles
    legend_handles = [
        Line2D([0], [0], color='blue', lw=1.5, label='Rivers'),
        Line2D([0], [0], marker='^', color='red', label='Gauges', linestyle='None', markersize=8)
    ]
    legend_labels = ['Rivers', 'Gauges']

    # Plot model boundary if provided and add its handle to the legend
    if model_boundary_path:
        try:
            model_boundary = gpd.read_file(model_boundary_path)
            model_boundary.plot(ax=ax, facecolor='none', edgecolor='black', 
                                linestyle='--', linewidth=2.5)
            legend_handles.append(Line2D([0], [0], color='black', lw=2.5, linestyle='--', label='Model Boundary'))
            legend_labels.append('Model Boundary')
        except Exception as e:
            print(f"Could not load or plot model boundary from {model_boundary_path}: {e}")

    # Create the second legend object from the handles and labels
    legend2 = Legend(ax, legend_handles, legend_labels, loc='upper left')
    
    # Add the second legend to the plot manually, which preserves the first legend
    ax.add_artist(legend2)

    # --- 5. Formatting ---
    if custom_title:
        ax.set_title(custom_title, fontsize=16, weight='bold')
    else:
        ax.set_title('Model Area Delineation', fontsize=16, weight='bold')
    ax.set_xlabel('Easting (m, CH1903+ / LV95)')
    ax.set_ylabel('Northing (m, CH1903+ / LV95)')
    ax.grid(True, linestyle=':', alpha=0.6)
    
    ax.set_xlim(2674000, 2684000)
    ax.set_ylim(1246000, 1252000)

    plt.tight_layout()
    
    return fig, ax
'''

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
    title_obj = ax.set_title(title_text, fontsize=16, weight='bold', loc='center')
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
        title_html = f"""
        <div style="position: relative; width:100%; text-align:center; padding:6px 0 4px 0;
                    font-size:16px; font-weight:600; font-family:Arial;">
            {map_title}
        </div>
        """
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







