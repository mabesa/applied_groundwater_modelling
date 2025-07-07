import folium
import geopandas as gpd
from matplotlib.colors import ListedColormap
import json
from typing import Tuple, Any
from matplotlib.lines import Line2D
from matplotlib.legend import Legend

def display_groundwater_resources_map(gw_map_path, zoom_level=10, map_center=None):
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
                top: 10px; right: 10px; width: 300px; height: auto; 
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
    
    return m

def plot_model_area_map(
    gw_depth_path: str, 
    rivers_path: str, 
    gauges_path: str,
    model_boundary_path: str = None,
    figsize: Tuple[int, int] = (12, 12)
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
    ax.set_title('Model Area Delineation', fontsize=16, weight='bold')
    ax.set_xlabel('Easting (m, CH1903+ / LV95)')
    ax.set_ylabel('Northing (m, CH1903+ / LV95)')
    ax.grid(True, linestyle=':', alpha=0.6)
    
    ax.set_xlim(2674000, 2684000)
    ax.set_ylim(1246000, 1252000)

    plt.tight_layout()
    
    return fig, ax


