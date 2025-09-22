from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import MultiLineString
import folium
import flopy
from flopy.utils import GridIntersect


from typing import Tuple
import warnings

import numpy as np
import geopandas as gpd

from scipy.interpolate import griddata

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

import rasterio
from rasterio.features import rasterize



def intersect_boundary_with_flopy_grid_buffer_opt(boundary_segments_gdf, modelgrid, desc_filter="west", 
                                      buffer_distance=None, check_crs=True, debug=True):
    """
    Use FloPy's GridIntersect to find cells that intersect with boundary segments
    
    Parameters:
    boundary_segments_gdf: GeoDataFrame with boundary segments
    modelgrid: FloPy modelgrid object (StructuredGrid, VertexGrid, or UnstructuredGrid)
    desc_filter: description to filter boundary segments
    buffer_distance: float, buffer distance to apply to lines (in CRS units). If None, auto-calculate
    check_crs: bool, whether to check and align coordinate reference systems
    debug: bool, whether to print debugging information
    
    Returns:
    dict with intersection results
    """
    
    # Filter boundary segments for specified description
    west_boundary = boundary_segments_gdf[boundary_segments_gdf['desc'] == desc_filter].copy()
    
    if west_boundary.empty:
        print(f"No boundary segments found with desc='{desc_filter}'")
        return None
    
    print(f"Found {len(west_boundary)} boundary segments with desc='{desc_filter}'")
    
    # Check and align coordinate reference systems
    if check_crs:
        print(f"\n=== CRS COMPATIBILITY CHECK ===")
        
        # Get boundary CRS
        boundary_crs = west_boundary.crs
        print(f"Boundary segments CRS: {boundary_crs}")
        
        # Get modelgrid CRS
        if hasattr(modelgrid, 'crs') and modelgrid.crs is not None:
            grid_crs = modelgrid.crs
            print(f"Model grid CRS: {grid_crs}")
        else:
            # Try to infer from coordinates - Swiss coordinates are typically in the hundreds of thousands
            if hasattr(modelgrid, 'xcellcenters') and hasattr(modelgrid, 'ycellcenters'):
                x_range = (modelgrid.xcellcenters.min(), modelgrid.xcellcenters.max())
                y_range = (modelgrid.ycellcenters.min(), modelgrid.ycellcenters.max())
                print(f"Model grid X range: {x_range}")
                print(f"Model grid Y range: {y_range}")
                
                if x_range[0] > 100000 and y_range[0] > 100000:
                    grid_crs = 'EPSG:2056'  # Swiss CH1903+ / LV95
                    print(f"Inferred model grid CRS as Swiss: {grid_crs}")
                else:
                    grid_crs = None
                    print("Warning: Could not determine model grid CRS")
            else:
                grid_crs = None
                print("Warning: Model grid CRS information not available")
        
        # Align CRS if needed
        if boundary_crs != grid_crs and grid_crs is not None:
            print(f"Converting boundary segments from {boundary_crs} to {grid_crs}")
            try:
                west_boundary = west_boundary.to_crs(grid_crs)
                print("CRS conversion successful")
            except Exception as e:
                print(f"Warning: CRS conversion failed: {e}")
    
    # Print boundary extent for debugging
    if debug:
        bounds = west_boundary.total_bounds
        print(f"\n=== BOUNDARY EXTENT ===")
        print(f"Boundary bounds (minx, miny, maxx, maxy): {bounds}")
        
        if hasattr(modelgrid, 'extent'):
            grid_extent = modelgrid.extent
            print(f"Model grid extent: {grid_extent}")
        elif hasattr(modelgrid, 'xcellcenters') and hasattr(modelgrid, 'ycellcenters'):
            grid_bounds = [
                modelgrid.xcellcenters.min(), modelgrid.ycellcenters.min(),
                modelgrid.xcellcenters.max(), modelgrid.ycellcenters.max()
            ]
            print(f"Model grid bounds: {grid_bounds}")
        
        # Check if boundary and grid overlap
        try:
            if hasattr(modelgrid, 'extent'):
                gx_min, gx_max, gy_min, gy_max = modelgrid.extent
            else:
                gx_min, gx_max = modelgrid.xcellcenters.min(), modelgrid.xcellcenters.max()
                gy_min, gy_max = modelgrid.ycellcenters.min(), modelgrid.ycellcenters.max()
            
            bx_min, by_min, bx_max, by_max = bounds
            
            overlap_x = not (bx_max < gx_min or bx_min > gx_max)
            overlap_y = not (by_max < gy_min or by_min > gy_max)
            overlap = overlap_x and overlap_y
            
            print(f"Spatial overlap detected: {overlap}")
            if not overlap:
                print("WARNING: No spatial overlap between boundary and grid!")
                print("This is likely why no intersections were found.")
        except Exception as e:
            print(f"Could not check spatial overlap: {e}")
    
    # Auto-calculate buffer distance if not provided
    if buffer_distance is None:
        # Use average cell size as buffer distance
        try:
            if hasattr(modelgrid, 'delr') and hasattr(modelgrid, 'delc'):
                if np.isscalar(modelgrid.delr):
                    avg_delr = modelgrid.delr
                else:
                    avg_delr = np.mean(modelgrid.delr)
                
                if np.isscalar(modelgrid.delc):
                    avg_delc = modelgrid.delc
                else:
                    avg_delc = np.mean(modelgrid.delc)
                
                buffer_distance = min(avg_delr, avg_delc) / 2.0
                print(f"Auto-calculated buffer distance: {buffer_distance:.2f} units")
            else:
                buffer_distance = 50.0  # Default 50 units
                print(f"Using default buffer distance: {buffer_distance} units")
        except:
            buffer_distance = 50.0
            print(f"Using default buffer distance: {buffer_distance} units")
    else:
        print(f"Using provided buffer distance: {buffer_distance} units")
    
    # Create GridIntersect object
    gix = GridIntersect(modelgrid, method="vertex", rtree=True)
    
    # Convert all boundary segments to geometries and apply buffer
    line_geometries = []
    buffered_geometries = []
    
    for idx, row in west_boundary.iterrows():
        if row.geometry.geom_type == 'LineString':
            line_geometries.append(row.geometry)
            buffered_geometries.append(row.geometry.buffer(buffer_distance))
        elif row.geometry.geom_type == 'MultiLineString':
            for geom in row.geometry.geoms:
                line_geometries.append(geom)
                buffered_geometries.append(geom.buffer(buffer_distance))
    
    # Create MultiLineString and MultiPolygon for intersections
    if len(line_geometries) == 1:
        boundary_multiline = line_geometries[0]
        boundary_buffered = buffered_geometries[0]
    else:
        boundary_multiline = MultiLineString(line_geometries)
        from shapely.geometry import MultiPolygon
        if len(buffered_geometries) == 1:
            boundary_buffered = buffered_geometries[0]
        else:
            boundary_buffered = MultiPolygon(buffered_geometries) if len(buffered_geometries) > 1 else buffered_geometries[0]
    
    # Try intersection with original lines first
    print(f"\n=== INTERSECTION ATTEMPTS ===")
    print("Attempting intersection with original line geometries...")
    try:
        intersected_cellids_lines = gix.intersects(boundary_multiline, shapetype="linestring")
        detailed_intersection_lines = gix.intersect(boundary_multiline, shapetype="linestring")
        print(f"Original lines: Found {len(intersected_cellids_lines)} intersected cells")
    except Exception as e:
        print(f"Original lines intersection failed: {e}")
        intersected_cellids_lines = np.array([], dtype=object)
        detailed_intersection_lines = None
    
    # Try intersection with buffered geometries (as polygons)
    print("Attempting intersection with buffered geometries...")
    try:
        intersected_cellids_buffered = gix.intersects(boundary_buffered, shapetype="polygon")
        detailed_intersection_buffered = gix.intersect(boundary_buffered, shapetype="polygon")
        print(f"Buffered polygons: Found {len(intersected_cellids_buffered)} intersected cells")
    except Exception as e:
        print(f"Buffered intersection failed: {e}")
        intersected_cellids_buffered = np.array([], dtype=object)
        detailed_intersection_buffered = None
    
    # Choose the best result
    if len(intersected_cellids_lines) > 0:
        print("Using original line intersection results")
        intersected_cellids = intersected_cellids_lines
        detailed_intersection = detailed_intersection_lines
        used_geometry = boundary_multiline
        intersection_type = "linestring"
    elif len(intersected_cellids_buffered) > 0:
        print("Using buffered polygon intersection results")
        intersected_cellids = intersected_cellids_buffered
        detailed_intersection = detailed_intersection_buffered
        used_geometry = boundary_buffered
        intersection_type = "polygon_buffered"
    else:
        print("No intersections found with either method!")
        intersected_cellids = np.array([], dtype=object)
        detailed_intersection = None
        used_geometry = boundary_multiline
        intersection_type = "none"
    
    print(f"Final result: Found {len(intersected_cellids)} grid cells intersecting with '{desc_filter}' boundary")
    
    return {
        'west_boundary': west_boundary,
        'boundary_multiline': boundary_multiline,
        'boundary_buffered': boundary_buffered,
        'used_geometry': used_geometry,
        'intersection_type': intersection_type,
        'buffer_distance': buffer_distance,
        'intersected_cellids': intersected_cellids,
        'detailed_intersection': detailed_intersection,
        'grid_intersect': gix
    }

def debug_grid_and_boundary(boundary_segments_gdf, modelgrid, desc_filter="west"):
    """
    Additional debugging function to visualize grid and boundary extents
    """
    import matplotlib.pyplot as plt
    
    # Filter boundary
    west_boundary = boundary_segments_gdf[boundary_segments_gdf['desc'] == desc_filter].copy()
    if west_boundary.empty:
        print("No boundary segments found for debugging")
        return
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # Plot 1: Overview
    ax1.set_title('Overview: Grid and Boundary Extents')
    
    # Plot model grid
    if hasattr(modelgrid, 'xcellcenters') and hasattr(modelgrid, 'ycellcenters'):
        # Plot grid outline
        x_edges = modelgrid.xvertices if hasattr(modelgrid, 'xvertices') else None
        y_edges = modelgrid.yvertices if hasattr(modelgrid, 'yvertices') else None
        
        if x_edges is not None and y_edges is not None:
            # Plot grid cells
            for i in range(min(10, x_edges.shape[0]-1)):  # Plot max 10 cells for clarity
                for j in range(min(10, x_edges.shape[1]-1)):
                    rect = plt.Rectangle(
                        (x_edges[i,j], y_edges[i,j]), 
                        x_edges[i,j+1] - x_edges[i,j],
                        y_edges[i+1,j] - y_edges[i,j],
                        fill=False, edgecolor='blue', alpha=0.5
                    )
                    ax1.add_patch(rect)
        
        # Plot grid extent
        x_min, x_max = modelgrid.xcellcenters.min(), modelgrid.xcellcenters.max()
        y_min, y_max = modelgrid.ycellcenters.min(), modelgrid.ycellcenters.max()
        ax1.plot([x_min, x_max, x_max, x_min, x_min], 
                [y_min, y_min, y_max, y_max, y_min], 'b-', linewidth=2, label='Grid Extent')
    
    # Plot boundary
    west_boundary.plot(ax=ax1, color='red', linewidth=3, label='West Boundary')
    ax1.set_aspect('equal')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Detailed view
    ax2.set_title('Detailed View: First Few Grid Cells')
    
    # Plot a subset of grid cells in detail
    if hasattr(modelgrid, 'xcellcenters') and hasattr(modelgrid, 'ycellcenters'):
        pmv = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax2)
        pmv.plot_grid(lw=0.5, color='blue', alpha=0.7)
        
        # Add cell numbers for first few cells
        for i in range(min(5, modelgrid.nrow)):
            for j in range(min(5, modelgrid.ncol)):
                x_center = modelgrid.xcellcenters[i, j]
                y_center = modelgrid.ycellcenters[i, j]
                ax2.text(x_center, y_center, f'{i},{j}', 
                        ha='center', va='center', fontsize=8)
    
    # Plot boundary on detailed view
    west_boundary.plot(ax=ax2, color='red', linewidth=3, alpha=0.8)
    
    # Focus on intersection area
    bounds = west_boundary.total_bounds
    margin = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) * 0.1
    ax2.set_xlim(bounds[0] - margin, bounds[2] + margin)
    ax2.set_ylim(bounds[1] - margin, bounds[3] + margin)
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print coordinate info
    print("\n=== COORDINATE DEBUGGING INFO ===")
    print(f"Boundary bounds: {bounds}")
    if hasattr(modelgrid, 'xcellcenters'):
        print(f"Grid X range: {modelgrid.xcellcenters.min():.2f} to {modelgrid.xcellcenters.max():.2f}")
        print(f"Grid Y range: {modelgrid.ycellcenters.min():.2f} to {modelgrid.ycellcenters.max():.2f}")
        print(f"Grid cell size (first cell): delr={modelgrid.delr[0] if hasattr(modelgrid.delr, '__len__') else modelgrid.delr}, delc={modelgrid.delc[0] if hasattr(modelgrid.delc, '__len__') else modelgrid.delc}")


def intersect_boundary_with_flopy_grid(boundary_segments_gdf, modelgrid, desc_filter="west"):
    """
    Use FloPy's GridIntersect to find cells that intersect with boundary segments
    
    Parameters:
    boundary_segments_gdf: GeoDataFrame with boundary segments
    modelgrid: FloPy modelgrid object (StructuredGrid, VertexGrid, or UnstructuredGrid)
    desc_filter: description to filter boundary segments
    
    Returns:
    dict with intersection results
    """
    
    # Filter boundary segments for specified description
    west_boundary = boundary_segments_gdf[boundary_segments_gdf['desc'] == desc_filter].copy()
    
    if west_boundary.empty:
        print(f"No boundary segments found with desc='{desc_filter}'")
        return None
    
    print(f"Found {len(west_boundary)} boundary segments with desc='{desc_filter}'")
    
    # Create GridIntersect object
    gix = GridIntersect(modelgrid, method="vertex", rtree=True)
    
    # Convert all boundary segments to a single MultiLineString for efficient intersection
    line_geometries = []
    for idx, row in west_boundary.iterrows():
        if row.geometry.geom_type == 'LineString':
            line_geometries.append(row.geometry)
        elif row.geometry.geom_type == 'MultiLineString':
            line_geometries.extend(list(row.geometry.geoms))
    
    if len(line_geometries) == 1:
        boundary_multiline = line_geometries[0]
    else:
        boundary_multiline = MultiLineString(line_geometries)
    
    # Perform intersection using FloPy's GridIntersect
    # Use intersects() method to get cellids only (faster than full intersect())
    intersected_cellids = gix.intersects(boundary_multiline, shapetype="linestring")
    
    # For more detailed intersection (with lengths, etc.), use intersect() method
    detailed_intersection = gix.intersect(boundary_multiline, shapetype="linestring")
    
    print(f"Found {len(intersected_cellids)} grid cells intersecting with '{desc_filter}' boundary")
    
    return {
        'west_boundary': west_boundary,
        'boundary_multiline': boundary_multiline,
        'intersected_cellids': intersected_cellids,
        'detailed_intersection': detailed_intersection,
        'grid_intersect': gix
    }

def create_ibound_mapping_diagnostic(ibound, modelgrid, intersection_results):
    """
    Create diagnostic information to understand the mapping between 
    modelgrid cellids and ibound array indices
    """
    print(f"\n=== IBOUND-MODELGRID MAPPING DIAGNOSTIC ===")
    
    print(f"ibound array shape: {ibound.shape}")
    print(f"ibound unique values: {np.unique(ibound)}")
    print(f"Active cells in ibound: {np.sum(ibound == 1)}")
    
    if hasattr(modelgrid, 'nrow') and hasattr(modelgrid, 'ncol'):
        print(f"Modelgrid shape: nlay={getattr(modelgrid, 'nlay', 1)}, nrow={modelgrid.nrow}, ncol={modelgrid.ncol}")
    
    # Check if shapes are compatible
    if len(ibound.shape) == 3:
        expected_shape = (getattr(modelgrid, 'nlay', 1), modelgrid.nrow, modelgrid.ncol)
        print(f"Expected 3D shape based on modelgrid: {expected_shape}")
        shapes_match = ibound.shape == expected_shape
    elif len(ibound.shape) == 2:
        expected_shape = (modelgrid.nrow, modelgrid.ncol)
        print(f"Expected 2D shape based on modelgrid: {expected_shape}")
        shapes_match = ibound.shape == expected_shape
    else:
        shapes_match = False
    
    print(f"Shapes compatible: {shapes_match}")
    
    if not shapes_match:
        print("WARNING: ibound array shape does not match modelgrid dimensions!")
        print("This could explain why cellids from GridIntersect don't map correctly to ibound.")
        
        # Suggest potential solutions
        print("\nPotential solutions:")
        if len(ibound.shape) == 3 and hasattr(modelgrid, 'nlay'):
            print(f"1. Check if modelgrid layers match: modelgrid.nlay={getattr(modelgrid, 'nlay', 'unknown')} vs ibound layers={ibound.shape[0]}")
        if len(ibound.shape) >= 2:
            print(f"2. Check if row/col dimensions match: modelgrid=({modelgrid.nrow},{modelgrid.ncol}) vs ibound=({ibound.shape[-2]},{ibound.shape[-1]})")
        print("3. Verify that ibound array corresponds to the same grid as modelgrid")
        print("4. Check if ibound needs to be transposed or reshaped")
    
    # Test with first few intersected cellids
    if intersection_results and len(intersection_results['intersected_cellids']) > 0:
        print(f"\nTesting first few intersected cellids:")
        for i, cellid in enumerate(intersection_results['intersected_cellids'][:3]):
            print(f"\nCellid {i}: {cellid}")
            
            if isinstance(cellid, (tuple, list, np.ndarray)) and len(cellid) >= 2:
                if len(cellid) == 3:
                    k, r, c = int(cellid[0]), int(cellid[1]), int(cellid[2])
                    print(f"  3D cellid: layer={k}, row={r}, col={c}")
                    
                    # Check bounds
                    if hasattr(modelgrid, 'nlay'):
                        k_valid = 0 <= k < getattr(modelgrid, 'nlay', 1)
                    else:
                        k_valid = k == 0  # Assume single layer
                    r_valid = 0 <= r < modelgrid.nrow
                    c_valid = 0 <= c < modelgrid.ncol
                    
                    print(f"    Valid for modelgrid: layer={k_valid}, row={r_valid}, col={c_valid}")
                    
                    # Check ibound access
                    if len(ibound.shape) == 3:
                        k_ibound_valid = 0 <= k < ibound.shape[0]
                        r_ibound_valid = 0 <= r < ibound.shape[1]
                        c_ibound_valid = 0 <= c < ibound.shape[2]
                        print(f"    Valid for ibound: layer={k_ibound_valid}, row={r_ibound_valid}, col={c_ibound_valid}")
                        
                        if k_ibound_valid and r_ibound_valid and c_ibound_valid:
                            value = ibound[k, r, c]
                            print(f"    ibound[{k}, {r}, {c}] = {value}")
                    elif len(ibound.shape) == 2:
                        r_ibound_valid = 0 <= r < ibound.shape[0]
                        c_ibound_valid = 0 <= c < ibound.shape[1]
                        print(f"    Valid for 2D ibound: row={r_ibound_valid}, col={c_ibound_valid}")
                        
                        if r_ibound_valid and c_ibound_valid:
                            value = ibound[r, c]
                            print(f"    ibound[{r}, {c}] = {value}")
                
                elif len(cellid) == 2:
                    r, c = int(cellid[0]), int(cellid[1])
                    print(f"  2D cellid: row={r}, col={c}")
                    
                    # Similar checks for 2D cellid
                    r_valid = 0 <= r < modelgrid.nrow
                    c_valid = 0 <= c < modelgrid.ncol
                    print(f"    Valid for modelgrid: row={r_valid}, col={c_valid}")
                    
                    if len(ibound.shape) == 2:
                        r_ibound_valid = 0 <= r < ibound.shape[0]
                        c_ibound_valid = 0 <= c < ibound.shape[1]
                        print(f"    Valid for ibound: row={r_ibound_valid}, col={c_ibound_valid}")
                        
                        if r_ibound_valid and c_ibound_valid:
                            value = ibound[r, c]
                            print(f"    ibound[{r}, {c}] = {value}")

def assign_ibound_from_intersection(ibound, intersection_results, modelgrid):
    """
    Assign ibound = -1 for cells that intersect with boundary
    
    Parameters:
    ibound: numpy array with boundary conditions
    intersection_results: results from intersect_boundary_with_flopy_grid
    modelgrid: FloPy modelgrid object (needed to convert cellids to array indices)
    
    Returns:
    updated ibound array
    """
    
    if intersection_results is None:
        print("No intersection results to process")
        return ibound
    
    # Make a copy to avoid modifying original
    new_ibound = ibound.copy()
    
    intersected_cellids = intersection_results['intersected_cellids']
    
    print(f"\n=== DEBUGGING IBOUND ASSIGNMENT WITH MODELGRID ===")
    print(f"ibound shape: {new_ibound.shape}")
    print(f"modelgrid type: {type(modelgrid)}")
    print(f"Number of intersected cellids: {len(intersected_cellids)}")
    
    if hasattr(modelgrid, 'nrow') and hasattr(modelgrid, 'ncol'):
        print(f"Modelgrid dimensions: nlay={getattr(modelgrid, 'nlay', 1)}, nrow={modelgrid.nrow}, ncol={modelgrid.ncol}")
    
    if len(intersected_cellids) > 0:
        print(f"First few cellids from GridIntersect:")
        for i, cellid in enumerate(intersected_cellids[:5]):
            print(f"  cellid[{i}]: {cellid} (type: {type(cellid)})")
    
    # Process cellids using modelgrid methods
    modifications_made = 0
    
    def extract_row_col_from_cellid(cellid):
        """Helper function to extract row, col from various cellid formats including numpy.record"""
        print(f"    Raw cellid: {cellid} (type: {type(cellid)})")
        
        # Handle numpy.record objects (common in FloPy GridIntersect results)
        if isinstance(cellid, np.record):
            print(f"    Detected numpy.record, dtype: {cellid.dtype}")
            print(f"    Record fields: {cellid.dtype.names if cellid.dtype.names else 'No named fields'}")
            
            # Try to access the record as an array or tuple
            try:
                # Convert record to tuple/array
                cellid_array = cellid.item() if hasattr(cellid, 'item') else cellid
                print(f"    Converted record to: {cellid_array} (type: {type(cellid_array)})")
                
                # Now process the converted data
                if isinstance(cellid_array, tuple):
                    if len(cellid_array) == 1 and isinstance(cellid_array[0], tuple):
                        # Nested tuple case: ((40, 11),)
                        inner_tuple = cellid_array[0]
                        print(f"    Found nested tuple: {inner_tuple}")
                        if len(inner_tuple) == 2:
                            row, col = int(inner_tuple[0]), int(inner_tuple[1])
                            print(f"    Extracted row={row}, col={col}")
                            return row, col, None
                        elif len(inner_tuple) == 3:
                            layer, row, col = int(inner_tuple[0]), int(inner_tuple[1]), int(inner_tuple[2])
                            print(f"    Extracted layer={layer}, row={row}, col={col}")
                            return row, col, layer
                    elif len(cellid_array) == 2:
                        # Direct tuple: (40, 11)
                        row, col = int(cellid_array[0]), int(cellid_array[1])
                        print(f"    Direct tuple: row={row}, col={col}")
                        return row, col, None
                    elif len(cellid_array) == 3:
                        # 3D tuple: (0, 40, 11)
                        layer, row, col = int(cellid_array[0]), int(cellid_array[1]), int(cellid_array[2])
                        print(f"    3D tuple: layer={layer}, row={row}, col={col}")
                        return row, col, layer
                
                # Try accessing as array indices
                elif hasattr(cellid_array, '__len__') and len(cellid_array) >= 2:
                    if len(cellid_array) == 2:
                        row, col = int(cellid_array[0]), int(cellid_array[1])
                        print(f"    Array-like (2D): row={row}, col={col}")
                        return row, col, None
                    elif len(cellid_array) >= 3:
                        layer, row, col = int(cellid_array[0]), int(cellid_array[1]), int(cellid_array[2])
                        print(f"    Array-like (3D): layer={layer}, row={row}, col={col}")
                        return row, col, layer
                
            except Exception as e:
                print(f"    Error processing numpy.record: {e}")
            
            # Alternative: try to access record fields directly
            try:
                # Check if record has standard field names
                if hasattr(cellid, 'dtype') and cellid.dtype.names:
                    fields = cellid.dtype.names
                    print(f"    Record has fields: {fields}")
                    
                    # Common field patterns in FloPy
                    if 'cellids' in fields:
                        cellids_value = cellid['cellids']
                        print(f"    Found 'cellids' field: {cellids_value}")
                        return extract_row_col_from_cellid(cellids_value)
                    elif 'row' in fields and 'col' in fields:
                        row, col = int(cellid['row']), int(cellid['col'])
                        layer = int(cellid['layer']) if 'layer' in fields else None
                        print(f"    Found row/col fields: row={row}, col={col}, layer={layer}")
                        return row, col, layer
                
                # Try treating the record as indexable
                if len(cellid) >= 2:
                    if len(cellid) == 2:
                        row, col = int(cellid[0]), int(cellid[1])
                        print(f"    Indexed record (2D): row={row}, col={col}")
                        return row, col, None
                    elif len(cellid) >= 3:
                        layer, row, col = int(cellid[0]), int(cellid[1]), int(cellid[2])
                        print(f"    Indexed record (3D): layer={layer}, row={row}, col={col}")
                        return row, col, layer
                        
            except Exception as e:
                print(f"    Error accessing record fields: {e}")
        
        # Handle nested tuples like ((40, 11),)
        elif isinstance(cellid, tuple) and len(cellid) == 1 and isinstance(cellid[0], tuple):
            inner_tuple = cellid[0]
            print(f"    Detected nested tuple, extracting: {inner_tuple}")
            if len(inner_tuple) == 2:
                row, col = int(inner_tuple[0]), int(inner_tuple[1])
                print(f"    Extracted row={row}, col={col}")
                return row, col, None  # No layer info
            elif len(inner_tuple) == 3:
                layer, row, col = int(inner_tuple[0]), int(inner_tuple[1]), int(inner_tuple[2])
                print(f"    Extracted layer={layer}, row={row}, col={col}")
                return row, col, layer
        
        # Handle regular tuples like (40, 11) or (0, 40, 11)
        elif isinstance(cellid, (tuple, list, np.ndarray)):
            if len(cellid) == 2:
                row, col = int(cellid[0]), int(cellid[1])
                print(f"    Direct 2D: row={row}, col={col}")
                return row, col, None
            elif len(cellid) == 3:
                layer, row, col = int(cellid[0]), int(cellid[1]), int(cellid[2])
                print(f"    Direct 3D: layer={layer}, row={row}, col={col}")
                return row, col, layer
        
        # Handle single numbers (node numbers)
        elif isinstance(cellid, (int, np.integer)):
            print(f"    Single node number: {cellid}")
            # Would need modelgrid.get_lrc() method to convert
            if hasattr(modelgrid, 'get_lrc'):
                lrc = modelgrid.get_lrc(cellid)
                if len(lrc) == 3:
                    layer, row, col = lrc[0], lrc[1], lrc[2]
                    print(f"    Converted to layer={layer}, row={row}, col={col}")
                    return row, col, layer
                else:
                    row, col = lrc[0], lrc[1]
                    print(f"    Converted to row={row}, col={col}")
                    return row, col, None
        
        print(f"    Could not parse cellid format: {cellid}")
        return None, None, None
    
    for idx, cellid in enumerate(intersected_cellids):
        try:
            print(f"\nProcessing cellid {idx}: {cellid}")
            
            # Extract row, col, layer from cellid
            row, col, layer = extract_row_col_from_cellid(cellid)
            
            if row is None or col is None:
                print(f"  Failed to extract row/col from cellid: {cellid}")
                continue
            
            # Validate indices against modelgrid
            if not (0 <= row < modelgrid.nrow):
                print(f"  Row {row} out of bounds (nrow={modelgrid.nrow})")
                continue
            if not (0 <= col < modelgrid.ncol):
                print(f"  Col {col} out of bounds (ncol={modelgrid.ncol})")
                continue
            
            # Handle layer validation
            if layer is not None:
                if hasattr(modelgrid, 'nlay') and not (0 <= layer < modelgrid.nlay):
                    print(f"  Layer {layer} out of bounds (nlay={modelgrid.nlay})")
                    continue
            
            print(f"  Valid indices: row={row}, col={col}, layer={layer}")
            
            # Map to ibound array indices and modify
            if len(new_ibound.shape) == 3:  # 3D ibound
                if layer is not None:
                    # Use specific layer
                    if 0 <= layer < new_ibound.shape[0]:
                        current_value = new_ibound[layer, row, col]
                        print(f"  Current ibound[{layer}, {row}, {col}] = {current_value}")
                        
                        if current_value == 1:  # Only modify active cells
                            new_ibound[layer, row, col] = -1
                            print(f"  ✓ Set ibound[{layer}, {row}, {col}] = -1")
                            modifications_made += 1
                        else:
                            print(f"  - Skipped (not active): ibound[{layer}, {row}, {col}] = {current_value}")
                    else:
                        print(f"  Layer {layer} out of bounds for ibound shape {new_ibound.shape}")
                else:
                    # Apply to all layers (since no layer specified)
                    for k in range(new_ibound.shape[0]):
                        current_value = new_ibound[k, row, col]
                        print(f"  Current ibound[{k}, {row}, {col}] = {current_value}")
                        
                        if current_value == 1:  # Only modify active cells
                            new_ibound[k, row, col] = -1
                            print(f"  ✓ Set ibound[{k}, {row}, {col}] = -1")
                            modifications_made += 1
                        else:
                            print(f"  - Skipped (not active): ibound[{k}, {row}, {col}] = {current_value}")
            
            elif len(new_ibound.shape) == 2:  # 2D ibound
                current_value = new_ibound[row, col]
                print(f"  Current ibound[{row}, {col}] = {current_value}")
                
                if current_value == 1:  # Only modify active cells
                    new_ibound[row, col] = -1
                    print(f"  ✓ Set ibound[{row}, {col}] = -1")
                    modifications_made += 1
                else:
                    print(f"  - Skipped (not active): ibound[{row}, {col}] = {current_value}")
            
        except Exception as e:
            print(f"  Error processing cellid {cellid}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    modified_cells = np.sum((ibound == 1) & (new_ibound == -1))
    print(f"\n=== SUMMARY ===")
    print(f"Modifications attempted: {modifications_made}")
    print(f"Actually modified cells: {modified_cells}")
    print(f"Original active cells: {np.sum(ibound == 1)}")
    print(f"New active cells: {np.sum(new_ibound == 1)}")
    print(f"New constant head cells: {np.sum(new_ibound == -1)}")
    
    if modified_cells != modifications_made:
        print(f"WARNING: Discrepancy between attempted ({modifications_made}) and actual ({modified_cells}) modifications!")
    
    return new_ibound

def visualize_flopy_intersection(intersection_results, ibound, map_style='OpenStreetMap'):
    """
    Visualize the FloPy intersection results on a map
    """
    
    if intersection_results is None:
        print("No intersection results to visualize")
        return None
    
    west_boundary = intersection_results['west_boundary']
    intersected_cellids = intersection_results['intersected_cellids']
    gix = intersection_results['grid_intersect']
    
    # Convert boundary to WGS84 for web mapping
    west_boundary_web = west_boundary.to_crs(epsg=4326)
    
    # Get grid cell polygons for intersected cells
    # We'll create polygons from the modelgrid
    modelgrid = gix.mfgrid
    
    # Convert modelgrid coordinates to WGS84 if needed
    if hasattr(modelgrid, 'xcellcenters') and hasattr(modelgrid, 'ycellcenters'):
        # For structured grids
        from shapely.geometry import Polygon
        import geopandas as gpd
        
        intersected_polygons = []
        intersected_coords = []
        
        for cellid in intersected_cellids:
            if len(cellid) >= 2:
                if len(cellid) == 3:  # 3D grid
                    k, i, j = cellid
                    if k == 0:  # Only plot top layer
                        intersected_coords.append((i, j))
                else:  # 2D grid
                    i, j = cellid
                    intersected_coords.append((i, j))
        
        # Get cell vertices for intersected cells
        for i, j in intersected_coords:
            try:
                # Get cell vertices using modelgrid methods
                cell_polygon = modelgrid.get_cell_polygon(i, j)
                intersected_polygons.append(cell_polygon)
            except:
                # Fallback: create simple polygon from cell bounds
                xmin = modelgrid.xvertices[i, j]
                xmax = modelgrid.xvertices[i, j+1] if j+1 < modelgrid.xvertices.shape[1] else modelgrid.xvertices[i, j]
                ymin = modelgrid.yvertices[i, j]
                ymax = modelgrid.yvertices[i+1, j] if i+1 < modelgrid.yvertices.shape[0] else modelgrid.yvertices[i, j]
                
                cell_polygon = Polygon([
                    (xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)
                ])
                intersected_polygons.append(cell_polygon)
        
        # Create GeoDataFrame for intersected cells
        if intersected_polygons:
            intersected_gdf = gpd.GeoDataFrame(
                {'cellid': [str(coord) for coord in intersected_coords]},
                geometry=intersected_polygons,
                crs=modelgrid.crs if hasattr(modelgrid, 'crs') and modelgrid.crs else 'EPSG:2056'
            )
            intersected_gdf_web = intersected_gdf.to_crs(epsg=4326)
        else:
            intersected_gdf_web = None
    
    # Calculate map center
    bounds = west_boundary_web.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles=map_style
    )
    
    # Add intersected cells (red polygons)
    if intersected_gdf_web is not None:
        for idx, row in intersected_gdf_web.iterrows():
            if row.geometry.geom_type == 'Polygon':
                coords = [[point[1], point[0]] for point in row.geometry.exterior.coords]
                folium.Polygon(
                    locations=coords,
                    color='red',
                    weight=2,
                    fillColor='red',
                    fillOpacity=0.6,
                    popup=f"Intersected cell: {row['cellid']}"
                ).add_to(m)
    
    # Add boundary segments (thick blue line)
    for idx, row in west_boundary_web.iterrows():
        if row.geometry.geom_type == 'LineString':
            coordinates = [[point[1], point[0]] for point in row.geometry.coords]
            folium.PolyLine(
                locations=coordinates,
                color='#004488',
                weight=8,
                opacity=1.0,
                popup=f"West boundary segment"
            ).add_to(m)
        elif row.geometry.geom_type == 'MultiLineString':
            for line in row.geometry.geoms:
                coordinates = [[point[1], point[0]] for point in line.coords]
                folium.PolyLine(
                    locations=coordinates,
                    color='#004488',
                    weight=8,
                    opacity=1.0,
                    popup=f"West boundary segment"
                ).add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 280px; height: auto; 
                background-color: white; border: 2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4>FloPy Grid-Boundary Intersection</h4>
    <div style="margin: 5px 0;">
        <span style="background-color: #004488; width: 20px; height: 4px; 
                     display: inline-block; margin-right: 10px;"></span>
        West Boundary Segments
    </div>
    <div style="margin: 5px 0;">
        <span style="background-color: red; width: 20px; height: 20px; 
                     display: inline-block; margin-right: 10px; opacity: 0.6;"></span>
        Intersected Grid Cells
    </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Fit bounds
    southwest = [bounds[1], bounds[0]]
    northeast = [bounds[3], bounds[2]]
    m.fit_bounds([southwest, northeast], padding=(50, 50))
    
    return m

def plot_flopy_intersection_result(intersection_results, ibound):
    """
    Use FloPy's built-in plotting to visualize intersection results
    """
    if intersection_results is None:
        return
    
    gix = intersection_results['grid_intersect']
    detailed_intersection = intersection_results['detailed_intersection']
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot model grid
    pmv = flopy.plot.PlotMapView(modelgrid=gix.mfgrid, ax=ax)
    pmv.plot_grid(lw=0.5, color='gray', alpha=0.5)
    
    # Plot ibound
    if len(ibound.shape) == 3:
        ibound_layer = ibound[0, :, :]  # Plot top layer
    else:
        ibound_layer = ibound
    
    pmv.plot_array(ibound_layer, masked_values=[0], alpha=0.3, cmap='viridis')
    
    # Plot intersection result using FloPy's method
    gix.plot_intersection_result(detailed_intersection, ax=ax)
    
    # Plot boundary segments
    west_boundary = intersection_results['west_boundary']
    west_boundary.plot(ax=ax, color='red', linewidth=3, label='West Boundary')
    
    ax.set_aspect('equal')
    ax.legend()
    ax.set_title('FloPy Grid-Boundary Intersection')
    plt.tight_layout()
    plt.show()

def grid_to_gdf(modelgrid, crs=None) -> gpd.GeoDataFrame:
    """Convert a FloPy StructuredGrid to a GeoDataFrame of cell polygons.

    Parameters
    ----------
    modelgrid : flopy.discretization.StructuredGrid
        The FloPy structured grid.
    crs : any, optional
        CRS to assign to the output GeoDataFrame (e.g., from boundary_gdf.crs).

    Returns
    -------
    geopandas.GeoDataFrame
        Columns: row, col, geometry (Polygon)
    """
    xv, yv = modelgrid.xvertices, modelgrid.yvertices  # shape (nrow+1, ncol+1)
    nrow, ncol = modelgrid.nrow, modelgrid.ncol
    polys, rows, cols = [], [], []
    for r in range(nrow):
        for c in range(ncol):
            # Corner order: (r,c) -> (r,c+1) -> (r+1,c+1) -> (r+1,c)
            polys.append(
                Polygon(
                    [
                        (float(xv[r, c]), float(yv[r, c])),
                        (float(xv[r, c + 1]), float(yv[r, c + 1])),
                        (float(xv[r + 1, c + 1]), float(yv[r + 1, c + 1])),
                        (float(xv[r + 1, c]), float(yv[r + 1, c])),
                    ]
                )
            )
            rows.append(r)
            cols.append(c)
    g = gpd.GeoDataFrame({"row": rows, "col": cols, "geometry": polys}, crs=crs)
    return g


def _unary_union(gdf: gpd.GeoDataFrame, repair: bool = False) -> BaseGeometry:
    """Return a single (multi)polygon geometry from a GeoDataFrame.

    Uses Shapely 2.0's union_all when available (faster, non-deprecated).
    Falls back to shapely.ops.unary_union for older Shapely versions.

    Parameters
    ----------
    gdf : GeoDataFrame
        Input geometries.
    repair : bool, optional
        If True, attempt to make invalid geometries valid before union
        (buffer(0) fallback if make_valid unavailable).

    Returns
    -------
    BaseGeometry
        Unified geometry.
    """
    if gdf is None or gdf.empty:
        raise ValueError("boundary_gdf is empty or None")

    geoms = gdf.geometry
    if repair:
        # Attempt validity repair (Shapely 2 has make_valid)
        try:
            from shapely import make_valid  # type: ignore
            geoms = geoms.apply(make_valid)
        except Exception:
            geoms = geoms.apply(lambda g: g if g.is_valid else g.buffer(0))

    # Prefer Shapely 2 union_all
    try:
        from shapely import union_all  # Shapely >= 2.0
        unified = union_all(list(geoms.values))
    except Exception:  # pragma: no cover - fallback path
        from shapely.ops import unary_union
        unified = unary_union(geoms)

    if callable(unified):  # Safety check
        raise TypeError("Unified geometry is callable; incorrect Shapely interaction.")

    return unified


def compute_active_mask(
    grid_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    frac_threshold: float = 0.5,
) -> gpd.GeoDataFrame:
    """Compute area fraction of each cell inside the boundary and tag active cells.

    Parameters
    ----------
    grid_gdf : GeoDataFrame
        GeoDataFrame with cell polygons and row/col columns.
    boundary_gdf : GeoDataFrame
        Boundary polygons (can be multi-part). Will be unioned.
    frac_threshold : float, default 0.5
        Minimum fraction of cell area within boundary to mark as active.

    Returns
    -------
    GeoDataFrame
        Copy of grid_gdf with added columns: 'frac_inside' (float) and 'active' (bool).
    """
    if grid_gdf.crs is None and boundary_gdf.crs is not None:
        grid_gdf = grid_gdf.set_crs(boundary_gdf.crs)
    elif grid_gdf.crs is not None and boundary_gdf.crs is not None and grid_gdf.crs != boundary_gdf.crs:
        warnings.warn(
            "CRS mismatch between grid and boundary; reprojecting grid to boundary CRS.",
            stacklevel=2,
        )
        grid_gdf = grid_gdf.to_crs(boundary_gdf.crs)

    boundary = _unary_union(boundary_gdf)
    areas = grid_gdf.geometry.area
    inter_areas = grid_gdf.geometry.intersection(boundary).area
    with np.errstate(divide="ignore", invalid="ignore"):
        frac_inside = np.where(areas > 0, inter_areas / areas, 0.0)

    out = grid_gdf.copy()
    out["frac_inside"] = frac_inside
    out["active"] = frac_inside >= float(frac_threshold)
    return out


def ibound_from_active(
    grid_gdf: gpd.GeoDataFrame,
    nlay: int = 1,
    active_field: str = "active",
    active_value: int = 1,
    inactive_value: int = 0,
) -> np.ndarray:
    """Build a 3D IBOUND array from a grid GeoDataFrame with an 'active' field.

    Parameters
    ----------
    grid_gdf : GeoDataFrame
        Must contain integer 'row' and 'col' columns and a boolean active field.
    nlay : int
        Number of model layers.
    active_field : str
        Name of the boolean column indicating active cells.
    active_value : int
        Value assigned to active cells in IBOUND.
    inactive_value : int
        Value assigned to inactive cells in IBOUND.

    Returns
    -------
    np.ndarray
        IBOUND array of shape (nlay, nrow, ncol).
    """
    if active_field not in grid_gdf.columns:
        raise KeyError(f"Column '{active_field}' not found in grid_gdf")

    nrow = int(grid_gdf["row"].max()) + 1
    ncol = int(grid_gdf["col"].max()) + 1
    ib2d = np.full((nrow, ncol), inactive_value, dtype=int)

    # Set active cells
    active_rows = grid_gdf.loc[grid_gdf[active_field], "row"].to_numpy()
    active_cols = grid_gdf.loc[grid_gdf[active_field], "col"].to_numpy()
    ib2d[active_rows, active_cols] = active_value

    # Stack across layers
    ibound = np.repeat(ib2d[np.newaxis, :, :], repeats=int(nlay), axis=0)
    return ibound


def build_grid_gdf_and_ibound(
    modelgrid,
    boundary_gdf: gpd.GeoDataFrame,
    frac_threshold: float = 0.5,
    nlay: int = 1,
) -> Tuple[gpd.GeoDataFrame, np.ndarray]:
    """Convenience wrapper: grid polygons + active tagging + IBOUND.

    Parameters
    ----------
    modelgrid : flopy.discretization.StructuredGrid
        The FloPy structured grid.
    boundary_gdf : GeoDataFrame
        Case-study boundary polygons (CRS should match model coordinates).
    frac_threshold : float
        Minimum fraction of cell area within boundary to mark as active.
    nlay : int
        Number of layers for IBOUND.

    Returns
    -------
    (grid_gdf, ibound)
        grid_gdf includes 'row', 'col', 'geometry', 'frac_inside', 'active'.
        ibound is a (nlay, nrow, ncol) integer array.
    """
    grid_gdf = grid_to_gdf(modelgrid, crs=boundary_gdf.crs)
    grid_gdf = compute_active_mask(grid_gdf, boundary_gdf, frac_threshold=frac_threshold)
    ibound = ibound_from_active(grid_gdf, nlay=nlay)
    return grid_gdf, ibound

def interpolate_isohypses_to_grid(gdf_isohypses, modelgrid, buffer_distance=500):
    """
    Interpolate groundwater isohypses to a MODFLOW structured grid.
    
    Parameters:
    -----------
    gdf_isohypses : geopandas.GeoDataFrame
        Geodataframe containing isohypse lines with elevation values
    modelgrid : flopy.discretization.StructuredGrid
        MODFLOW structured grid object
    buffer_distance : float
        Buffer distance (in model units) to extend clipping beyond model grid extent
    
    Returns:
    --------
    numpy.ndarray
        2D array of interpolated groundwater elevations matching the model grid
    """
    
    # Create model grid boundary polygon for clipping
    from shapely.geometry import Polygon
    
    # Get model grid extent
    xmin, xmax, ymin, ymax = modelgrid.extent
    
    # Create buffered boundary polygon
    boundary = Polygon([
        (xmin - buffer_distance, ymin - buffer_distance),
        (xmax + buffer_distance, ymin - buffer_distance),
        (xmax + buffer_distance, ymax + buffer_distance),
        (xmin - buffer_distance, ymax + buffer_distance)
    ])
    
    # Create boundary geodataframe with same CRS as isohypses
    boundary_gdf = gpd.GeoDataFrame([1], geometry=[boundary], crs=gdf_isohypses.crs)
    
    # Clip isohypses to the buffered model grid extent
    print(f"Original isohypses: {len(gdf_isohypses)} features")
    gdf_clipped = gpd.clip(gdf_isohypses, boundary_gdf)
    print(f"Clipped isohypses: {len(gdf_clipped)} features")
    
    if len(gdf_clipped) == 0:
        raise ValueError("No isohypses found within the model grid extent (including buffer). Check CRS alignment.")
    
    # Use clipped data for interpolation
    gdf_isohypses = gdf_clipped
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters
    y_centers = modelgrid.ycellcenters
    
    # Create arrays of point coordinates for interpolation
    x_flat = x_centers.flatten()
    y_flat = y_centers.flatten()
    
    # Extract points and values from isohypse lines
    points_x = []
    points_y = []
    values = []
    
    # Assuming the elevation values are in a column (adjust column name as needed)
    # Common column names: 'ELEVATION', 'VALUE', 'Z', 'GW_ELEV', etc.
    elevation_column = None
    
    # Try to identify the elevation column
    possible_columns = ['ELEVATION', 'ELEV', 'VALUE', 'Z', 'GW_ELEV', 'HEIGHT', 'H']
    for col in possible_columns:
        if col in gdf_isohypses.columns:
            elevation_column = col
            break
    
    if elevation_column is None:
        # If no standard column found, use the first numeric column
        numeric_columns = gdf_isohypses.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            elevation_column = numeric_columns[0]
            print(f"Using column '{elevation_column}' for elevation values")
        else:
            raise ValueError("No elevation column found in the geodataframe")
    
    # Extract points along each isohypse line
    for idx, row in gdf_isohypses.iterrows():
        geom = row.geometry
        elevation = row[elevation_column]
        
        if geom.geom_type == 'LineString':
            # Sample points along the line
            coords = list(geom.coords)
            for coord in coords:
                points_x.append(coord[0])
                points_y.append(coord[1])
                values.append(elevation)
        
        elif geom.geom_type == 'MultiLineString':
            # Handle multipart lines
            for line in geom.geoms:
                coords = list(line.coords)
                for coord in coords:
                    points_x.append(coord[0])
                    points_y.append(coord[1])
                    values.append(elevation)
    
    # Convert to numpy arrays
    points_x = np.array(points_x)
    points_y = np.array(points_y)
    values = np.array(values)
    
    # Create points array for scipy interpolation
    points = np.column_stack((points_x, points_y))
    grid_points = np.column_stack((x_flat, y_flat))
    
    # Interpolate using different methods (you can choose the best one)
    print("Interpolating groundwater elevations...")
    
    # Method 1: Linear interpolation (recommended for most cases)
    try:
        interpolated_values = griddata(points, values, grid_points, method='linear')
        
        # Fill any NaN values with nearest neighbor interpolation
        nan_mask = np.isnan(interpolated_values)
        if np.any(nan_mask):
            print("Filling NaN values with nearest neighbor interpolation...")
            interpolated_nearest = griddata(points, values, grid_points, method='nearest')
            interpolated_values[nan_mask] = interpolated_nearest[nan_mask]
    
    except Exception as e:
        print(f"Linear interpolation failed: {e}")
        print("Using nearest neighbor interpolation...")
        interpolated_values = griddata(points, values, grid_points, method='nearest')
    
    # Reshape back to grid dimensions
    gw_elevations = interpolated_values.reshape(x_centers.shape)
    
    return gw_elevations

def alternative_raster_interpolation(gdf_isohypses, modelgrid, cell_size=10):
    """
    Alternative method using rasterization and resampling.
    Useful if the line-based interpolation doesn't work well.
    
    Parameters:
    -----------
    gdf_isohypses : geopandas.GeoDataFrame
        Geodataframe containing isohypse lines
    modelgrid : flopy.discretization.StructuredGrid
        MODFLOW structured grid object
    cell_size : float
        Resolution for intermediate raster (meters)
    
    Returns:
    --------
    numpy.ndarray
        2D array of interpolated groundwater elevations
    """
    
    # Get model bounds
    xmin, xmax, ymin, ymax = modelgrid.extent
    
    # Create high-resolution grid for rasterization
    width = int((xmax - xmin) / cell_size)
    height = int((ymax - ymin) / cell_size)
    
    # Create transform for the raster
    from rasterio.transform import from_bounds
    transform = from_bounds(xmin, ymin, xmax, ymax, width, height)
    
    # Identify elevation column (same logic as above)
    elevation_column = None
    possible_columns = ['ELEVATION', 'ELEV', 'VALUE', 'Z', 'GW_ELEV', 'HEIGHT', 'H']
    for col in possible_columns:
        if col in gdf_isohypses.columns:
            elevation_column = col
            break
    
    if elevation_column is None:
        numeric_columns = gdf_isohypses.select_dtypes(include=[np.number]).columns
        elevation_column = numeric_columns[0] if len(numeric_columns) > 0 else 'value'
    
    # Create shapes for rasterization
    shapes = [(geom, value) for geom, value in zip(gdf_isohypses.geometry, gdf_isohypses[elevation_column])]
    
    # Rasterize the lines
    raster = rasterize(shapes, out_shape=(height, width), transform=transform, dtype=np.float32)
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters.flatten()
    y_centers = modelgrid.ycellcenters.flatten()
    
    # Sample the raster at model grid points
    from rasterio.transform import rowcol
    interpolated_values = []
    
    for x, y in zip(x_centers, y_centers):
        row, col = rowcol(transform, x, y)
        if 0 <= row < height and 0 <= col < width:
            interpolated_values.append(raster[row, col])
        else:
            interpolated_values.append(np.nan)
    
    # Convert to numpy array and reshape
    interpolated_values = np.array(interpolated_values)
    gw_elevations = interpolated_values.reshape(modelgrid.xcellcenters.shape)
    
    return gw_elevations


