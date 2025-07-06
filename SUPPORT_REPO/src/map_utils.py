import folium
import geopandas as gpd
from matplotlib.colors import ListedColormap
import json
from typing import Tuple, Any

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


def plot_model_delineation_map(
    gw_depth_path: str, 
    rivers_path: str, 
    gauges_path: str,
    figsize: Tuple[int, int] = (12, 12)
) -> Tuple[Any, Any]:
    """
    Displays a map with groundwater depth, rivers, and gauges.

    This function loads and plots geospatial data for groundwater depth, 
    river networks, and monitoring gauges.

    Requires the 'geopandas' and 'matplotlib' libraries.

    Parameters
    ----------
    gw_depth_path : str
        File path to the groundwater depth GeoPackage (.gpkg).
    rivers_path : str
        File path to the rivers GeoPackage (.gpkg).
    gauges_path : str
        File path to the gauges GeoPackage (.gpkg).
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
    # Specify layer names to avoid ambiguity and errors with multi-layer gpkg files
    gw_depth = gpd.read_file(gw_depth_path, layer='GS_GW_LEITER_F')
    rivers = gpd.read_file(rivers_path, layer='AVZH_GEWAESSER_F')
    gauges = gpd.read_file(gauges_path, layer='GS_GRUNDWASSERPEGEL_P')

    # --- 2. Define Color Scheme ---
    # Reuse the same color scheme as the interactive map
    custom_colors = {
        1: '#eda53f',  # light orange
        2: '#cfe2f3',  # pale blue
        3: '#cfe2f3',
        4: '#9fc5e8',  # slightly darker pale blue
        6: '#6fa8dc',  # darkest shade of pale blue
        8: '#ead1dc',  # lighter pink
        10: '#d5a6bd',  # light pink
    }
    
    # Get unique types present in the data and sort them
    gw_types = sorted(gw_depth['GWLTYP'].unique())
    # Create a list of colors corresponding to the sorted types
    colors_list = [custom_colors.get(t, '#999999') for t in gw_types] # Use grey for undefined
    custom_cmap = ListedColormap(colors_list)

    # --- 3. Create the Plot ---
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # Plot base layers
    gw_depth.plot(
        ax=ax, 
        column='GWLTYP', 
        categorical=True, 
        legend=True,
        legend_kwds={'title': "Groundwater Thickness Type"},
        cmap=custom_cmap,
        alpha=0.7
    )
    rivers.plot(ax=ax, color='blue', linewidth=1.5, label='Rivers')
    gauges.plot(ax=ax, color='red', marker='^', markersize=50, label='Gauges')

    # --- 3. Formatting ---
    ax.set_title('Groundwater Resources, Rivers, and Gauges', fontsize=16, weight='bold')
    ax.set_xlabel('Easting (m)')
    ax.set_ylabel('Northing (m)')
    ax.grid(True, linestyle=':', alpha=0.6)
    
    # Create a single legend for layers plotted with 'label'
    handles, labels = ax.get_legend_handles_labels()
    # The legend for gw_depth is created by its own plot call, so we only need the others.
    ax.legend(handles, labels, loc='upper left')
    
    # Set plot limits to focus on the Limmat Valley
    ax.set_xlim(2674000, 2684000)
    ax.set_ylim(1246000, 1252000)

    plt.tight_layout()
    
    return fig, ax


