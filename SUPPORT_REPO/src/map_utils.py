import folium
from folium.plugins import BeautifyIcon
import geopandas as gpd
from matplotlib.colors import ListedColormap
import json
from typing import Tuple, Any
from matplotlib.lines import Line2D
from matplotlib.legend import Legend
from branca.element import MacroElement
from jinja2 import Template


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

def plot_model_area_map(
    gw_depth_path: str, 
    rivers_path: str, 
    gauges_path: str,
    model_boundary_path: str = None,
    figsize: Tuple[int, int] = (12, 12), 
    custom_title: str = None
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

    # --- 4. Create a second, manual legend (Legend 2) ---
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
    simple_shapes: bool = True
):
    """
    Create an interactive folium map of groundwater concessions.

    Parameters
    ----------
    concessions : (str | geopandas.GeoDataFrame)
        Path to a vector file (gpkg/shp) OR a GeoDataFrame containing point geometries.
    boundary_gdf : geopandas.GeoDataFrame, optional
        GeoDataFrame with a (multi)polygon model boundary to overlay.
    id_col : str
        Column with (unique) concession/group id.
    use_col : str
        Column with usage / category (controls point coloring).
    description_col : str
        Column with textual description (shown in popup).
    fassart_col : str
        Column with type of well (shown in popup).
    map_center : (lat, lon) tuple, optional
        Center of map. If None it is derived from data bounds.
    zoom_start : int
        Initial zoom level.
    map_title : str, optional
        Title shown above the map.
    max_description_chars : int
        Truncate very long descriptions for the popup.

    Returns
    -------
    folium.Map
    """
    
    # --- Load / validate concessions GeoDataFrame ---
    if isinstance(concessions, str):
        concessions_gdf = gpd.read_file(concessions)
    else:
        concessions_gdf = concessions.copy()

    if concessions_gdf.crs is None:
        raise ValueError("Concessions GeoDataFrame must have a CRS defined.")

    # Ensure geometry is point-type
    if not all(concessions_gdf.geometry.geom_type.isin(["Point"])):
        raise ValueError("Concessions layer must contain only Point geometries.")

    # Reproject to WGS84 for folium
    if concessions_gdf.crs.to_string() != "EPSG:4326":
        concessions_gdf = concessions_gdf.to_crs("EPSG:4326")

    # Boundary (optional)
    if boundary_gdf is not None:
        b_gdf = boundary_gdf.copy()
        if b_gdf.crs is None:
            raise ValueError("Boundary GeoDataFrame must have a CRS defined.")
        if b_gdf.crs.to_string() != "EPSG:4326":
            b_gdf = b_gdf.to_crs("EPSG:4326")
    else:
        b_gdf = None

    # --- Determine map center ---
    if map_center is None:
        bounds = concessions_gdf.total_bounds  # [minx, miny, maxx, maxy]
        map_center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    # --- Build color mapping for use_col categories ---
    categories = concessions_gdf[use_col].fillna("Unspecified").astype(str)
    unique_cats = list(categories.unique())

    palette = [
        "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
        "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf",
        "#393b79","#637939","#8c6d31","#843c39","#7b4173"
    ]
    # Extend palette if needed
    if len(unique_cats) > len(palette):
        extra = len(unique_cats) - len(palette)
        palette.extend([f"#555{hex(i%16)[2:]}{hex((i*5)%16)[2:]}"] * extra)
    color_map = {cat: palette[i] for i, cat in enumerate(unique_cats)}

    # --- Create folium map ---
    m = folium.Map(location=map_center, zoom_start=zoom_start, tiles="OpenStreetMap")

    # Optional title
    if map_title:
        title_html = f"""
        <div style="position: relative; width: 100%; text-align:center; padding:6px 0 4px 0;
                    font-size:16px; font-weight:600; font-family:Arial;">
            {map_title}
        </div>
        """
        m.get_root().html.add_child(folium.Element(title_html))

    # --- Add boundary polygon(s) ---
    if b_gdf is not None and not b_gdf.empty:
        folium.GeoJson(
            b_gdf.to_json(),
            name="Model Boundary",
            style_function=lambda _:
                {"color": "black", "weight": 2, "fill": False, "dashArray": "5,5"}
        ).add_to(m)

    # --- Add concession points ---
    for _, row in concessions_gdf.iterrows():
        use_val = str(row.get(use_col, "Unspecified"))
        cid_val = row.get(id_col, "N/A")
        desc_val = row.get(description_col, "")
        if isinstance(desc_val, str) and len(desc_val) > max_description_chars:
            desc_disp = desc_val[:max_description_chars] + "..."
        else:
            desc_disp = desc_val
        fass_val = row.get(fassart_col, "N/A")
        tooltip_txt = f"{id_col}: {cid_val} | {use_col}: {use_val}"
        popup_html = f"""
        <b>{id_col}:</b> {cid_val}<br>
        <b>{use_col}:</b> {use_val}<br>
        <b>Description:</b><br>{desc_disp}
        <b>Type of Well:</b><br>{fass_val}
        """
        folium.CircleMarker(
            location=(row.geometry.y, row.geometry.x),
            radius=6,
            color=color_map[use_val],
            fill=True,
            fill_color=color_map[use_val],
            fill_opacity=0.85,
            weight=1,
            tooltip=tooltip_txt,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    # --- Legend ---
    legend_items = "".join(
        f"""
        <div style="display:flex; align-items:center; margin-bottom:3px;">
            <div style="width:14px; height:14px; background:{color_map[c]};
                        border:1px solid #222; margin-right:6px;"></div>
            <div style="font-size:12px;">{c}</div>
        </div>
        """
        for c in unique_cats
    )
    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 12px; left: 12px; z-index:9999;
        background: white; padding:10px 12px;
        border:1px solid #888; border-radius:4px;
        box-shadow: 0 0 4px rgba(0,0,0,0.3);">
        <div style="font-weight:600; margin-bottom:6px; font-size:13px;">
            Concession Use
        </div>
        {legend_items}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=True).add_to(m)
    return m
'''


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







