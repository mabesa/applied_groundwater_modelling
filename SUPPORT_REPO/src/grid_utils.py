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

def interpolate_aquifer_thickness_to_grid(contour_gdf, modelgrid, thickness_column='aquifer_thickness', 
                                        plot_points=False, figsize=(12, 12)):
    """
    Interpolate aquifer thickness from contour lines to model grid using scipy griddata.
    
    Parameters
    ----------
    contour_gdf : gpd.GeoDataFrame
        GeoDataFrame containing contour lines with aquifer thickness values
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    thickness_column : str, optional
        Column name containing aquifer thickness values (default: 'aquifer_thickness')
    plot_points : bool, optional
        Whether to plot the interpolation points (default: False)
    figsize : tuple, optional
        Figure size for plotting (default: (12, 12))
    
    Returns
    -------
    np.ndarray
        2D array of interpolated aquifer thickness values on model grid
    
    Raises
    ------
    ValueError
        If thickness_column not found in contour_gdf or no valid geometries found
    """
    import numpy as np
    from scipy.interpolate import griddata
    import matplotlib.pyplot as plt
    
    # Validate inputs
    if thickness_column not in contour_gdf.columns:
        raise ValueError(f"Column '{thickness_column}' not found in contour_gdf")
    
    # Extract points from contour geometries
    points_for_interp = _extract_points_from_contours(contour_gdf, thickness_column)
    
    if len(points_for_interp) == 0:
        raise ValueError("No valid points extracted from contour geometries")
    
    points_array = np.array(points_for_interp)
    
    # Optional visualization of interpolation points
    if plot_points:
        _plot_interpolation_points(points_array, figsize)
    
    # Perform interpolation
    aquifer_thickness = _interpolate_to_grid(points_array, modelgrid)
    
    return aquifer_thickness


def _extract_points_from_contours(contour_gdf, thickness_column):
    """
    Extract coordinate points and thickness values from contour line geometries.
    
    Parameters
    ----------
    contour_gdf : gpd.GeoDataFrame
        GeoDataFrame with contour line geometries
    thickness_column : str
        Column name containing thickness values
    
    Returns
    -------
    list
        List of tuples (x, y, thickness_value)
    """
    points_for_interp = []
    
    for idx, row in contour_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
            
        thickness_value = row[thickness_column]
        
        if row.geometry.geom_type == 'MultiLineString':
            for line in row.geometry.geoms:
                for x, y in line.coords:
                    points_for_interp.append((x, y, thickness_value))
                    
        elif row.geometry.geom_type == 'LineString':
            for x, y in row.geometry.coords:
                points_for_interp.append((x, y, thickness_value))
    
    return points_for_interp


def _plot_interpolation_points(points_array, figsize):
    """
    Plot the points used for interpolation.
    
    Parameters
    ----------
    points_array : np.ndarray
        Array of shape (n_points, 3) with columns [x, y, thickness]
    figsize : tuple
        Figure size
    """
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=figsize)
    sc = ax.scatter(points_array[:, 0], points_array[:, 1], 
                   c=points_array[:, 2], cmap='viridis', s=5)
    plt.colorbar(sc, label='Aquifer Thickness (m)')
    ax.set_title("Points from Contours for Interpolation")
    ax.set_xlabel("X-coordinate")
    ax.set_ylabel("Y-coordinate")
    ax.set_aspect('equal', adjustable='box')
    plt.show()


def _interpolate_to_grid(points_array, modelgrid):
    """
    Interpolate points to model grid using linear + nearest neighbor fallback.
    
    Parameters
    ----------
    points_array : np.ndarray
        Array of shape (n_points, 3) with columns [x, y, thickness]
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    
    Returns
    -------
    np.ndarray
        2D array of interpolated values on model grid
    """
    from scipy.interpolate import griddata
    
    # Get model grid cell centers
    grid_x, grid_y = modelgrid.xcellcenters, modelgrid.ycellcenters
    
    # First pass: linear interpolation for smooth surface between contours
    interpolated_values = griddata(
        points_array[:, :2],  # x, y coordinates
        points_array[:, 2],   # thickness values
        (grid_x, grid_y),
        method='linear'
    )
    
    # Second pass: fill NaN values using nearest neighbor interpolation
    nan_indices = np.isnan(interpolated_values)
    if np.any(nan_indices):
        nearest_values = griddata(
            points_array[:, :2],
            points_array[:, 2],
            (grid_x[nan_indices], grid_y[nan_indices]),
            method='nearest'
        )
        interpolated_values[nan_indices] = nearest_values
    
    return interpolated_values

def interpolate_aquifer_thickness_to_grid_robust(contour_gdf, modelgrid, thickness_column='aquifer_thickness', 
                                               point_spacing=10, plot_points=False, figsize=(12, 12),
                                               buffer_distance=None):
    """
    Robustly interpolate aquifer thickness from contour lines to model grid.
    Uses denser point sampling along contours and extends search area for small grids.
    
    Parameters
    ----------
    contour_gdf : gpd.GeoDataFrame
        GeoDataFrame containing contour lines with aquifer thickness values
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    thickness_column : str, optional
        Column name containing aquifer thickness values (default: 'aquifer_thickness')
    point_spacing : float, optional
        Distance between interpolation points along contour lines in model units (default: 10)
    plot_points : bool, optional
        Whether to plot the interpolation points (default: False)
    figsize : tuple, optional
        Figure size for plotting (default: (12, 12))
    buffer_distance : float, optional
        Buffer around grid extent to search for contours. Auto-calculated if None.
    
    Returns
    -------
    np.ndarray
        2D array of interpolated aquifer thickness values on model grid
    """
    import numpy as np
    from scipy.interpolate import griddata
    from shapely.geometry import Point, Polygon
    import geopandas as gpd
    
    # Validate inputs
    if thickness_column not in contour_gdf.columns:
        raise ValueError(f"Column '{thickness_column}' not found in contour_gdf")
    
    # Get model grid extent and calculate buffer if not provided
    grid_extent = modelgrid.extent  # [xmin, xmax, ymin, ymax]
    grid_width = grid_extent[1] - grid_extent[0]
    grid_height = grid_extent[3] - grid_extent[2]
    
    if buffer_distance is None:
        # Use 20% of the smaller grid dimension as buffer, minimum 100m
        buffer_distance = max(100, 0.2 * min(grid_width, grid_height))
    
    print(f"Using buffer distance: {buffer_distance:.1f} m around grid extent")
    
    # Create buffered search area
    search_polygon = Polygon([
        (grid_extent[0] - buffer_distance, grid_extent[2] - buffer_distance),
        (grid_extent[1] + buffer_distance, grid_extent[2] - buffer_distance),
        (grid_extent[1] + buffer_distance, grid_extent[3] + buffer_distance),
        (grid_extent[0] - buffer_distance, grid_extent[3] + buffer_distance)
    ])
    
    # Filter contours to search area
    search_gdf = gpd.GeoDataFrame([1], geometry=[search_polygon], crs=contour_gdf.crs)
    contours_in_area = gpd.clip(contour_gdf, search_gdf)
    
    if len(contours_in_area) == 0:
        print("Warning: No contours found in buffered search area. Using all contours.")
        contours_in_area = contour_gdf
    
    print(f"Using {len(contours_in_area)} contours (from {len(contour_gdf)} total)")
    
    # Extract dense points from contour geometries
    points_for_interp = _extract_dense_points_from_contours(
        contours_in_area, thickness_column, point_spacing
    )
    
    if len(points_for_interp) == 0:
        raise ValueError("No valid points extracted from contour geometries")
    
    points_array = np.array(points_for_interp)
    print(f"Extracted {len(points_array)} interpolation points")
    
    # Optional visualization of interpolation points
    if plot_points:
        _plot_interpolation_points_with_grid(points_array, modelgrid, figsize)
    
    # Perform robust interpolation
    aquifer_thickness = _interpolate_to_grid_robust(points_array, modelgrid)
    
    return aquifer_thickness


def _extract_dense_points_from_contours(contour_gdf, thickness_column, point_spacing):
    """
    Extract dense coordinate points along contour lines using interpolation.
    
    Parameters
    ----------
    contour_gdf : gpd.GeoDataFrame
        GeoDataFrame with contour line geometries
    thickness_column : str
        Column name containing thickness values
    point_spacing : float
        Distance between points along lines
    
    Returns
    -------
    list
        List of tuples (x, y, thickness_value)
    """
    from shapely.geometry import LineString
    
    points_for_interp = []
    
    for idx, row in contour_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
            
        thickness_value = row[thickness_column]
        
        if row.geometry.geom_type == 'MultiLineString':
            for line in row.geometry.geoms:
                dense_points = _densify_linestring(line, point_spacing)
                for x, y in dense_points:
                    points_for_interp.append((x, y, thickness_value))
                    
        elif row.geometry.geom_type == 'LineString':
            dense_points = _densify_linestring(row.geometry, point_spacing)
            for x, y in dense_points:
                points_for_interp.append((x, y, thickness_value))
    
    return points_for_interp


def _densify_linestring(linestring, point_spacing):
    """
    Create dense points along a LineString at regular intervals.
    
    Parameters
    ----------
    linestring : shapely.geometry.LineString
        Input line geometry
    point_spacing : float
        Distance between output points
    
    Returns
    -------
    list
        List of (x, y) coordinate tuples
    """
    if linestring.length == 0:
        return list(linestring.coords)
    
    # Calculate number of segments needed
    num_points = max(2, int(np.ceil(linestring.length / point_spacing)) + 1)
    
    # Create points at regular intervals along the line
    distances = np.linspace(0, linestring.length, num_points)
    dense_points = []
    
    for dist in distances:
        try:
            point = linestring.interpolate(dist)
            dense_points.append((point.x, point.y))
        except Exception:
            # Fallback: use original coordinates if interpolation fails
            continue
    
    # Ensure we always include the original vertices
    original_coords = list(linestring.coords)
    dense_points.extend(original_coords)
    
    # Remove duplicates (keep unique points within tolerance)
    unique_points = []
    tolerance = point_spacing * 0.1
    
    for point in dense_points:
        is_duplicate = False
        for existing_point in unique_points:
            if (abs(point[0] - existing_point[0]) < tolerance and 
                abs(point[1] - existing_point[1]) < tolerance):
                is_duplicate = True
                break
        if not is_duplicate:
            unique_points.append(point)
    
    return unique_points


def _plot_interpolation_points_with_grid(points_array, modelgrid, figsize):
    """
    Plot interpolation points with model grid overlay.
    
    Parameters
    ----------
    points_array : np.ndarray
        Array of shape (n_points, 3) with columns [x, y, thickness]
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    figsize : tuple
        Figure size
    """
    import matplotlib.pyplot as plt
    import flopy
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot interpolation points
    sc = ax.scatter(points_array[:, 0], points_array[:, 1], 
                   c=points_array[:, 2], cmap='viridis', s=15, alpha=0.7)
    plt.colorbar(sc, label='Aquifer Thickness (m)')
    
    # Plot model grid
    pmv = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax)
    pmv.plot_grid(linewidth=0.5, color='red', alpha=0.8)
    
    ax.set_title("Dense Interpolation Points with Model Grid")
    ax.set_xlabel("X-coordinate")
    ax.set_ylabel("Y-coordinate")

def _interpolate_to_grid_robust(points_array, modelgrid):
    """
    Robustly interpolate point data to model grid using multiple interpolation methods.
    
    Parameters
    ----------
    points_array : np.ndarray
        Array of shape (n_points, 3) with columns [x, y, thickness]
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    
    Returns
    -------
    np.ndarray
        2D array of interpolated values on model grid
    """
    from scipy.interpolate import griddata
    import numpy as np
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters
    y_centers = modelgrid.ycellcenters
    
    # Create arrays of point coordinates for interpolation
    x_flat = x_centers.flatten()
    y_flat = y_centers.flatten()
    grid_points = np.column_stack((x_flat, y_flat))
    
    # Extract points and values from input array
    point_coords = points_array[:, :2]  # x, y coordinates
    values = points_array[:, 2]         # thickness values
    
    print(f"Interpolating from {len(values)} points to {len(grid_points)} grid cells...")
    
    # Try multiple interpolation methods and choose the best one
    methods = ['linear', 'nearest', 'cubic']
    results = {}
    
    for method in methods:
        try:
            interpolated = griddata(
                point_coords, values, grid_points, 
                method=method, fill_value=np.nan
            )
            interpolated_2d = interpolated.reshape(x_centers.shape)
            
            # Check quality of interpolation
            valid_cells = np.isfinite(interpolated_2d)
            valid_fraction = valid_cells.sum() / interpolated_2d.size
            
            results[method] = {
                'data': interpolated_2d,
                'valid_fraction': valid_fraction,
                'min_val': np.nanmin(interpolated_2d),
                'max_val': np.nanmax(interpolated_2d)
            }
            
            print(f"  {method}: {valid_fraction:.1%} valid cells, "
                  f"range [{np.nanmin(interpolated_2d):.1f}, {np.nanmax(interpolated_2d):.1f}]")
            
        except Exception as e:
            print(f"  {method}: failed ({str(e)})")
            results[method] = None
    
    # Choose the best method (prioritize completeness, then linear over nearest)
    best_method = None
    best_result = None
    
    # First, try linear if it has good coverage
    if 'linear' in results and results['linear'] is not None:
        if results['linear']['valid_fraction'] > 0.8:  # 80% coverage threshold
            best_method = 'linear'
            best_result = results['linear']['data']
    
    # Fall back to cubic if linear didn't work well
    if best_method is None and 'cubic' in results and results['cubic'] is not None:
        if results['cubic']['valid_fraction'] > 0.7:  # 70% coverage threshold
            best_method = 'cubic'
            best_result = results['cubic']['data']
    
    # Finally fall back to nearest
    if best_method is None and 'nearest' in results and results['nearest'] is not None:
        best_method = 'nearest'
        best_result = results['nearest']['data']
    
    if best_result is None:
        raise RuntimeError("All interpolation methods failed")
    
    print(f"Using {best_method} interpolation method")
    
    # Fill any remaining NaN values with nearest neighbor
    if np.any(np.isnan(best_result)):
        print("Filling remaining NaN values with nearest neighbor...")
        nan_mask = np.isnan(best_result)
        
        try:
            nearest_result = griddata(
                point_coords, values, grid_points,
                method='nearest'
            ).reshape(x_centers.shape)
            
            best_result[nan_mask] = nearest_result[nan_mask]
        except:
            # If nearest neighbor fails, use mean value
            mean_val = np.nanmean(values)
            best_result[nan_mask] = mean_val
            print(f"  Filled {nan_mask.sum()} cells with mean value {mean_val:.1f}")
    
    # Apply reasonable bounds check
    min_input = values.min()
    max_input = values.max()
    
    # Clip to reasonable range (allow 20% extension beyond input range)
    range_extension = 0.2 * (max_input - min_input)
    lower_bound = max(0, min_input - range_extension)  # Thickness can't be negative
    upper_bound = max_input + range_extension
    
    best_result = np.clip(best_result, lower_bound, upper_bound)
    
    print(f"Final result: range [{best_result.min():.1f}, {best_result.max():.1f}], "
          f"mean {best_result.mean():.1f}")
    
    return best_result

def interpolate_aquifer_thickness_to_grid_improved(contour_gdf, modelgrid, thickness_column='aquifer_thickness', 
                                                 point_spacing=5, plot_points=False, figsize=(12, 12),
                                                 buffer_distance=None, smoothing_factor=0.1):
    """
    Improved interpolation of aquifer thickness with better handling of sparse data.
    
    Parameters
    ----------
    contour_gdf : gpd.GeoDataFrame
        GeoDataFrame containing contour lines with aquifer thickness values
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    thickness_column : str, optional
        Column name containing aquifer thickness values (default: 'aquifer_thickness')
    point_spacing : float, optional
        Distance between interpolation points along contour lines in model units (default: 5)
    plot_points : bool, optional
        Whether to plot the interpolation points (default: False)
    figsize : tuple, optional
        Figure size for plotting (default: (12, 12))
    buffer_distance : float, optional
        Buffer around grid extent to search for contours. Auto-calculated if None.
    smoothing_factor : float, optional
        Smoothing parameter for RBF interpolation (default: 0.1)
    
    Returns
    -------
    np.ndarray
        2D array of interpolated aquifer thickness values on model grid
    """
    import numpy as np
    from scipy.interpolate import griddata, Rbf
    from shapely.geometry import Point, Polygon
    import geopandas as gpd
    
    # Validate inputs
    if thickness_column not in contour_gdf.columns:
        raise ValueError(f"Column '{thickness_column}' not found in contour_gdf")
    
    # Get model grid extent and calculate buffer if not provided
    grid_extent = modelgrid.extent  # [xmin, xmax, ymin, ymax]
    grid_width = grid_extent[1] - grid_extent[0]
    grid_height = grid_extent[3] - grid_extent[2]
    
    if buffer_distance is None:
        # Use larger buffer for better interpolation coverage
        buffer_distance = max(200, 0.5 * min(grid_width, grid_height))
    
    print(f"Using buffer distance: {buffer_distance:.1f} m around grid extent")
    
    # Create buffered search area
    search_polygon = Polygon([
        (grid_extent[0] - buffer_distance, grid_extent[2] - buffer_distance),
        (grid_extent[1] + buffer_distance, grid_extent[2] - buffer_distance),
        (grid_extent[1] + buffer_distance, grid_extent[3] + buffer_distance),
        (grid_extent[0] - buffer_distance, grid_extent[3] + buffer_distance)
    ])
    
    # Filter contours to search area
    search_gdf = gpd.GeoDataFrame([1], geometry=[search_polygon], crs=contour_gdf.crs)
    contours_in_area = gpd.clip(contour_gdf, search_gdf)
    
    if len(contours_in_area) == 0:
        print("Warning: No contours found in buffered search area. Using all contours.")
        contours_in_area = contour_gdf
    
    print(f"Using {len(contours_in_area)} contours (from {len(contour_gdf)} total)")
    print(f"Thickness value range in contours: {contours_in_area[thickness_column].min():.1f} - {contours_in_area[thickness_column].max():.1f} m")
    
    # Extract dense points from contour geometries
    points_for_interp = _extract_dense_points_from_contours_improved(
        contours_in_area, thickness_column, point_spacing
    )
    
    if len(points_for_interp) == 0:
        raise ValueError("No valid points extracted from contour geometries")
    
    points_array = np.array(points_for_interp)
    print(f"Extracted {len(points_array)} interpolation points")
    
    # Add synthetic boundary points to prevent edge effects
    points_array = _add_boundary_constraint_points(points_array, modelgrid, buffer_distance)
    print(f"Total points after adding boundary constraints: {len(points_array)}")
    
    # Optional visualization of interpolation points
    if plot_points:
        _plot_interpolation_points_with_grid_improved(points_array, modelgrid, figsize)
    
    # Perform improved interpolation
    aquifer_thickness = _interpolate_to_grid_improved(points_array, modelgrid, smoothing_factor)
    
    # Apply geological constraints
    aquifer_thickness = _apply_geological_constraints(aquifer_thickness, contours_in_area[thickness_column])
    
    return aquifer_thickness


def _extract_dense_points_from_contours_improved(contour_gdf, thickness_column, point_spacing):
    """
    Improved extraction of dense coordinate points with better spacing control.
    """
    from shapely.geometry import LineString
    import numpy as np
    
    points_for_interp = []
    
    for idx, row in contour_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
            
        thickness_value = row[thickness_column]
        
        # Skip invalid thickness values
        if not np.isfinite(thickness_value) or thickness_value < 0:
            print(f"Warning: Skipping invalid thickness value: {thickness_value}")
            continue
        
        if row.geometry.geom_type == 'MultiLineString':
            for line in row.geometry.geoms:
                dense_points = _densify_linestring_improved(line, point_spacing)
                for x, y in dense_points:
                    points_for_interp.append((x, y, thickness_value))
                    
        elif row.geometry.geom_type == 'LineString':
            dense_points = _densify_linestring_improved(row.geometry, point_spacing)
            for x, y in dense_points:
                points_for_interp.append((x, y, thickness_value))
    
    return points_for_interp


def _densify_linestring_improved(linestring, point_spacing):
    """
    Improved densification with better point distribution.
    """
    import numpy as np
    
    if linestring.length == 0:
        return list(linestring.coords)
    
    # Use smaller spacing for better resolution
    effective_spacing = min(point_spacing, linestring.length / 20)  # At least 20 points per line
    num_points = max(5, int(np.ceil(linestring.length / effective_spacing)) + 1)
    
    # Create points at regular intervals
    distances = np.linspace(0, linestring.length, num_points)
    dense_points = []
    
    for dist in distances:
        try:
            point = linestring.interpolate(dist)
            dense_points.append((point.x, point.y))
        except Exception:
            continue
    
    # Always include original vertices for accuracy
    original_coords = list(linestring.coords)
    dense_points.extend(original_coords)
    
    # Remove duplicates with tighter tolerance
    unique_points = []
    tolerance = effective_spacing * 0.05  # 5% of spacing
    
    for point in dense_points:
        is_duplicate = False
        for existing_point in unique_points:
            if (abs(point[0] - existing_point[0]) < tolerance and 
                abs(point[1] - existing_point[1]) < tolerance):
                is_duplicate = True
                break
        if not is_duplicate:
            unique_points.append(point)
    
    return unique_points


def _add_boundary_constraint_points(points_array, modelgrid, buffer_distance):
    """
    Add synthetic points around the model boundary to prevent extrapolation artifacts.
    """
    import numpy as np
    
    # Get grid extent
    grid_extent = modelgrid.extent
    
    # Find reasonable thickness values for boundary points
    # Use median and interquartile range for stability
    thickness_values = points_array[:, 2]
    median_thickness = np.median(thickness_values)
    q25 = np.percentile(thickness_values, 25)
    q75 = np.percentile(thickness_values, 75)
    
    print(f"Adding boundary constraint points with thickness range: {q25:.1f} - {q75:.1f} m")
    
    # Create boundary points at corners and edges
    boundary_points = []
    
    # Corners (use median thickness)
    corners = [
        (grid_extent[0] - buffer_distance*0.5, grid_extent[2] - buffer_distance*0.5, median_thickness),
        (grid_extent[1] + buffer_distance*0.5, grid_extent[2] - buffer_distance*0.5, median_thickness),
        (grid_extent[1] + buffer_distance*0.5, grid_extent[3] + buffer_distance*0.5, median_thickness),
        (grid_extent[0] - buffer_distance*0.5, grid_extent[3] + buffer_distance*0.5, median_thickness),
    ]
    boundary_points.extend(corners)
    
    # Edge points (use varied thicknesses within reasonable range)
    n_edge_points = 5
    for i in range(n_edge_points):
        t = i / (n_edge_points - 1)
        # Vary thickness slightly around median
        thickness = median_thickness + (q75 - q25) * (np.random.random() - 0.5) * 0.5
        
        # Bottom edge
        x = grid_extent[0] + t * (grid_extent[1] - grid_extent[0])
        boundary_points.append((x, grid_extent[2] - buffer_distance*0.3, thickness))
        
        # Top edge
        boundary_points.append((x, grid_extent[3] + buffer_distance*0.3, thickness))
        
        # Left edge
        y = grid_extent[2] + t * (grid_extent[3] - grid_extent[2])
        boundary_points.append((grid_extent[0] - buffer_distance*0.3, y, thickness))
        
        # Right edge
        boundary_points.append((grid_extent[1] + buffer_distance*0.3, y, thickness))
    
    # Combine with original points
    boundary_array = np.array(boundary_points)
    combined_points = np.vstack([points_array, boundary_array])
    
    return combined_points


def _plot_interpolation_points_with_grid_improved(points_array, modelgrid, figsize):
    """
    Improved plotting with better visualization.
    """
    import matplotlib.pyplot as plt
    import flopy
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(figsize[0]*1.5, figsize[1]*0.8))
    
    # Left plot: All points
    sc1 = ax1.scatter(points_array[:, 0], points_array[:, 1], 
                     c=points_array[:, 2], cmap='viridis', s=10, alpha=0.7)
    plt.colorbar(sc1, ax=ax1, label='Aquifer Thickness (m)')
    
    # Plot model grid
    pmv1 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax1)
    pmv1.plot_grid(linewidth=0.5, color='red', alpha=0.8)
    
    ax1.set_title("All Interpolation Points")
    ax1.set_xlabel("X-coordinate")
    ax1.set_ylabel("Y-coordinate")
    ax1.set_aspect('equal')
    
    # Right plot: Points colored by source
    grid_extent = modelgrid.extent
    
    # Identify boundary constraint points (outside grid extent)
    is_boundary = ((points_array[:, 0] < grid_extent[0]) | 
                   (points_array[:, 0] > grid_extent[1]) |
                   (points_array[:, 1] < grid_extent[2]) | 
                   (points_array[:, 1] > grid_extent[3]))
    
    # Plot contour points
    contour_points = points_array[~is_boundary]
    if len(contour_points) > 0:
        ax2.scatter(contour_points[:, 0], contour_points[:, 1], 
                   c='blue', s=8, alpha=0.7, label='Contour Points')
    
    # Plot boundary points
    boundary_points = points_array[is_boundary]
    if len(boundary_points) > 0:
        ax2.scatter(boundary_points[:, 0], boundary_points[:, 1], 
                   c='red', s=15, alpha=0.8, label='Boundary Constraints')
    
    # Plot model grid
    pmv2 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax2)
    pmv2.plot_grid(linewidth=0.5, color='gray', alpha=0.8)
    
    ax2.set_title("Point Sources")
    ax2.set_xlabel("X-coordinate")
    ax2.set_ylabel("Y-coordinate")
    ax2.legend()
    ax2.set_aspect('equal')
    
    plt.tight_layout()
    plt.show()


def _interpolate_to_grid_improved(points_array, modelgrid, smoothing_factor):
    """
    Improved interpolation using multiple methods with better validation.
    """
    from scipy.interpolate import griddata, Rbf
    import numpy as np
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters
    y_centers = modelgrid.ycellcenters
    
    # Create arrays of point coordinates for interpolation
    x_flat = x_centers.flatten()
    y_flat = y_centers.flatten()
    grid_points = np.column_stack((x_flat, y_flat))
    
    # Extract points and values from input array
    point_coords = points_array[:, :2]  # x, y coordinates
    values = points_array[:, 2]         # thickness values
    
    print(f"Interpolating from {len(values)} points to {len(grid_points)} grid cells...")
    print(f"Input thickness range: {values.min():.1f} - {values.max():.1f} m")
    
    # Try different interpolation methods
    methods = ['linear', 'cubic', 'rbf']
    results = {}
    
    for method in methods:
        try:
            if method == 'rbf':
                # Use Radial Basis Function for smoother results
                rbf_interp = Rbf(point_coords[:, 0], point_coords[:, 1], values, 
                               function='multiquadric', smooth=smoothing_factor)
                interpolated = rbf_interp(x_flat, y_flat)
                interpolated_2d = interpolated.reshape(x_centers.shape)
            else:
                interpolated = griddata(
                    point_coords, values, grid_points, 
                    method=method, fill_value=np.nan
                )
                interpolated_2d = interpolated.reshape(x_centers.shape)
            
            # Check quality of interpolation
            valid_cells = np.isfinite(interpolated_2d)
            valid_fraction = valid_cells.sum() / interpolated_2d.size
            
            # Check for reasonable values
            reasonable_mask = (interpolated_2d >= 0) & (interpolated_2d <= values.max() * 1.5)
            reasonable_fraction = reasonable_mask.sum() / interpolated_2d.size
            
            results[method] = {
                'data': interpolated_2d,
                'valid_fraction': valid_fraction,
                'reasonable_fraction': reasonable_fraction,
                'min_val': np.nanmin(interpolated_2d),
                'max_val': np.nanmax(interpolated_2d),
                'mean_val': np.nanmean(interpolated_2d)
            }
            
            print(f"  {method}: {valid_fraction:.1%} valid, {reasonable_fraction:.1%} reasonable, "
                  f"range [{np.nanmin(interpolated_2d):.1f}, {np.nanmax(interpolated_2d):.1f}], "
                  f"mean {np.nanmean(interpolated_2d):.1f}")
            
        except Exception as e:
            print(f"  {method}: failed ({str(e)})")
            results[method] = None
    
    # Choose best method based on validity and reasonableness
    best_method = None
    best_result = None
    best_score = 0
    
    for method, result in results.items():
        if result is not None:
            # Score combines validity and reasonableness
            score = result['valid_fraction'] * 0.7 + result['reasonable_fraction'] * 0.3
            if score > best_score:
                best_score = score
                best_method = method
                best_result = result['data']
    
    if best_result is None:
        raise RuntimeError("All interpolation methods failed")
    
    print(f"Using {best_method} interpolation method (score: {best_score:.2f})")
    
    # Fill remaining NaN values
    if np.any(np.isnan(best_result)):
        print("Filling remaining NaN values...")
        nan_mask = np.isnan(best_result)
        
        try:
            nearest_result = griddata(
                point_coords, values, grid_points,
                method='nearest'
            ).reshape(x_centers.shape)
            
            best_result[nan_mask] = nearest_result[nan_mask]
        except:
            median_val = np.median(values)
            best_result[nan_mask] = median_val
            print(f"  Filled {nan_mask.sum()} cells with median value {median_val:.1f}")
    
    return best_result


def _apply_geological_constraints(thickness_array, original_thickness_values):
    """
    Apply geological constraints to ensure realistic thickness values.
    """
    import numpy as np
    
    # Get reasonable bounds from original data
    min_thickness = max(0.5, original_thickness_values.min())  # Minimum 0.5m
    max_thickness = original_thickness_values.max() * 1.2  # Allow 20% above max
    median_thickness = np.median(original_thickness_values)
    
    print(f"Applying geological constraints:")
    print(f"  Min thickness: {min_thickness:.1f} m")
    print(f"  Max thickness: {max_thickness:.1f} m")
    print(f"  Median thickness: {median_thickness:.1f} m")
    
    # Clip to reasonable range
    original_min = thickness_array.min()
    original_max = thickness_array.max()
    
    thickness_array = np.clip(thickness_array, min_thickness, max_thickness)
    
    # Apply smoothing to reduce artifacts
    from scipy import ndimage
    thickness_array = ndimage.gaussian_filter(thickness_array, sigma=0.5)
    
    # Ensure minimum thickness
    thickness_array = np.maximum(thickness_array, min_thickness)
    
    print(f"  Before constraints: {original_min:.1f} - {original_max:.1f} m")
    print(f"  After constraints: {thickness_array.min():.1f} - {thickness_array.max():.1f} m")
    print(f"  Mean thickness: {thickness_array.mean():.1f} m")
    
    return thickness_array

def interpolate_aquifer_thickness_to_grid_with_contour_densification(
    contour_gdf, modelgrid, thickness_column='aquifer_thickness', 
    contour_interval=2.0, plot_intermediate=False, plot_points=False, 
    figsize=(12, 12), buffer_distance=None):
    """
    Interpolate aquifer thickness by first densifying contour lines, then interpolating to grid.
    
    This two-step approach:
    1. Creates intermediate contour lines between existing ones
    2. Interpolates from the denser contour network to the model grid
    
    Parameters
    ----------
    contour_gdf : gpd.GeoDataFrame
        GeoDataFrame containing contour lines with aquifer thickness values
    modelgrid : flopy.discretization.StructuredGrid
        FloPy model grid object
    thickness_column : str, optional
        Column name containing aquifer thickness values
    contour_interval : float, optional
        Interval for intermediate contours (default: 2.0 m)
    plot_intermediate : bool, optional
        Whether to plot the intermediate contour step
    plot_points : bool, optional
        Whether to plot the final interpolation points
    figsize : tuple, optional
        Figure size for plotting
    buffer_distance : float, optional
        Buffer around grid extent. Auto-calculated if None.
    
    Returns
    -------
    np.ndarray
        2D array of interpolated aquifer thickness values on model grid
    """
    import numpy as np
    from scipy.interpolate import griddata
    from shapely.geometry import Point, Polygon
    import geopandas as gpd
    import matplotlib.pyplot as plt
    
    print("=== STEP 1: Densifying Contour Network ===")
    
    # Validate inputs
    if thickness_column not in contour_gdf.columns:
        raise ValueError(f"Column '{thickness_column}' not found in contour_gdf")
    
    # Get model grid extent and calculate buffer
    grid_extent = modelgrid.extent
    grid_width = grid_extent[1] - grid_extent[0]
    grid_height = grid_extent[3] - grid_extent[2]
    
    if buffer_distance is None:
        buffer_distance = max(200, 0.3 * min(grid_width, grid_height))
    
    # Create buffered search area
    search_polygon = Polygon([
        (grid_extent[0] - buffer_distance, grid_extent[2] - buffer_distance),
        (grid_extent[1] + buffer_distance, grid_extent[2] - buffer_distance),
        (grid_extent[1] + buffer_distance, grid_extent[3] + buffer_distance),
        (grid_extent[0] - buffer_distance, grid_extent[3] + buffer_distance)
    ])
    
    # Filter contours to search area
    search_gdf = gpd.GeoDataFrame([1], geometry=[search_polygon], crs=contour_gdf.crs)
    contours_in_area = gpd.clip(contour_gdf, search_gdf)
    
    if len(contours_in_area) == 0:
        contours_in_area = contour_gdf
    
    print(f"Using {len(contours_in_area)} original contours")
    print(f"Original thickness range: {contours_in_area[thickness_column].min():.1f} - {contours_in_area[thickness_column].max():.1f} m")
    
    # Create intermediate contours
    densified_contours = _create_intermediate_contours(
        contours_in_area, thickness_column, contour_interval, search_polygon
    )
    
    print(f"Created {len(densified_contours)} total contours (including {len(densified_contours) - len(contours_in_area)} intermediate)")
    
    # Optional visualization of intermediate step
    if plot_intermediate:
        _plot_contour_densification(contours_in_area, densified_contours, 
                                   thickness_column, modelgrid, figsize)
    
    print("\n=== STEP 2: Interpolating from Dense Contours to Grid ===")
    
    # Extract points from densified contour network
    points_for_interp = _extract_points_from_dense_contours(
        densified_contours, thickness_column, point_spacing=10
    )
    
    points_array = np.array(points_for_interp)
    print(f"Extracted {len(points_array)} interpolation points from dense contour network")
    
    # Optional visualization of interpolation points
    if plot_points:
        _plot_interpolation_points_with_grid(points_array, modelgrid, figsize)
    
    # Perform final interpolation to grid
    aquifer_thickness = _interpolate_dense_contours_to_grid(points_array, modelgrid)
    
    # Apply constraints
    aquifer_thickness = _apply_geological_constraints_improved(
        aquifer_thickness, contours_in_area[thickness_column]
    )
    
    return aquifer_thickness


def _create_intermediate_contours(contour_gdf, thickness_column, contour_interval, search_polygon):
    """
    Create intermediate contour lines between existing ones using surface interpolation.
    """
    import numpy as np
    from scipy.interpolate import griddata
    from shapely.geometry import LineString, MultiLineString
    import geopandas as gpd
    from shapely.ops import unary_union
    
    # Get thickness range and create intermediate levels
    min_thickness = contour_gdf[thickness_column].min()
    max_thickness = contour_gdf[thickness_column].max()
    
    # Create full range of contour levels
    intermediate_levels = np.arange(
        np.floor(min_thickness / contour_interval) * contour_interval,
        np.ceil(max_thickness / contour_interval) * contour_interval + contour_interval,
        contour_interval
    )
    
    print(f"Creating intermediate contours for levels: {intermediate_levels}")
    
    # Extract points from original contours for surface interpolation
    all_points = []
    all_values = []
    
    for idx, row in contour_gdf.iterrows():
        if row.geometry is None:
            continue
        
        thickness_value = row[thickness_column]
        geom = row.geometry
        
        if geom.geom_type == 'LineString':
            coords = list(geom.coords)
            for coord in coords[::2]:  # Sample every 2nd point for efficiency
                all_points.append([coord[0], coord[1]])
                all_values.append(thickness_value)
        elif geom.geom_type == 'MultiLineString':
            for line in geom.geoms:
                coords = list(line.coords)
                for coord in coords[::2]:
                    all_points.append([coord[0], coord[1]])
                    all_values.append(thickness_value)
    
    all_points = np.array(all_points)
    all_values = np.array(all_values)
    
    print(f"Using {len(all_points)} points from original contours for surface interpolation")
    
    # Create regular grid for surface interpolation
    bounds = search_polygon.bounds
    grid_spacing = min(
        (bounds[2] - bounds[0]) / 200,  # 200 points across
        (bounds[3] - bounds[1]) / 200
    )
    
    x_grid = np.arange(bounds[0], bounds[2] + grid_spacing, grid_spacing)
    y_grid = np.arange(bounds[1], bounds[3] + grid_spacing, grid_spacing)
    X_grid, Y_grid = np.meshgrid(x_grid, y_grid)
    
    # Interpolate surface
    print("Interpolating thickness surface...")
    try:
        Z_grid = griddata(all_points, all_values, (X_grid, Y_grid), method='linear')
        # Fill NaN with nearest neighbor
        nan_mask = np.isnan(Z_grid)
        if np.any(nan_mask):
            Z_nearest = griddata(all_points, all_values, (X_grid, Y_grid), method='nearest')
            Z_grid[nan_mask] = Z_nearest[nan_mask]
    except Exception as e:
        print(f"Surface interpolation failed: {e}")
        # Fallback: just use original contours
        return contour_gdf
    
    # Generate contours from interpolated surface
    print("Generating intermediate contour lines...")
    import matplotlib.pyplot as plt
    
    # Create contours using matplotlib
    fig, ax = plt.subplots(figsize=(1, 1))  # Small dummy figure
    contour_set = ax.contour(X_grid, Y_grid, Z_grid, levels=intermediate_levels)
    plt.close(fig)
    
    # Convert matplotlib contours to geodataframe
    new_contours = []
    
    # Updated approach for modern matplotlib
    try:
        # Try the new approach first (matplotlib >= 3.8)
        for level_idx, level in enumerate(intermediate_levels):
            # Get paths for this level
            if hasattr(contour_set, 'get_paths'):
                # For newer matplotlib versions
                for collection in contour_set.collections:
                    if collection.get_array() is not None:
                        level_value = collection.get_array()[0] if len(collection.get_array()) > 0 else level
                    else:
                        level_value = level
                    
                    for path in collection.get_paths():
                        if len(path.vertices) > 2:
                            coords = path.vertices.tolist()
                            if len(coords) > 1:
                                try:
                                    line_geom = LineString(coords)
                                    if line_geom.is_valid and line_geom.length > 0:
                                        new_contours.append({
                                            'geometry': line_geom,
                                            thickness_column: level_value,
                                            'source': 'intermediate'
                                        })
                                except Exception:
                                    continue
            else:
                # Fallback for older matplotlib versions
                for collection in contour_set.collections:
                    for path in collection.get_paths():
                        if len(path.vertices) > 2:
                            coords = path.vertices.tolist()
                            if len(coords) > 1:
                                try:
                                    line_geom = LineString(coords)
                                    if line_geom.is_valid and line_geom.length > 0:
                                        # Estimate level from position in collections
                                        level_idx = contour_set.collections.index(collection)
                                        if level_idx < len(intermediate_levels):
                                            level_value = intermediate_levels[level_idx]
                                        else:
                                            level_value = np.mean(intermediate_levels)
                                        
                                        new_contours.append({
                                            'geometry': line_geom,
                                            thickness_column: level_value,
                                            'source': 'intermediate'
                                        })
                                except Exception:
                                    continue
    
    except Exception as e:
        print(f"Error extracting contour paths: {e}")
        print("Falling back to alternative contour generation method...")
        
        # Alternative approach using skimage
        try:
            from skimage import measure
            
            # Generate contours using skimage
            for level in intermediate_levels:
                try:
                    contours = measure.find_contours(Z_grid, level)
                    for contour in contours:
                        if len(contour) > 2:
                            # Convert array indices back to coordinates
                            coords = []
                            for point in contour:
                                y_idx, x_idx = point
                                if 0 <= y_idx < len(y_grid) and 0 <= x_idx < len(x_grid):
                                    x_coord = x_grid[int(x_idx)]
                                    y_coord = y_grid[int(y_idx)]
                                    coords.append((x_coord, y_coord))
                            
                            if len(coords) > 2:
                                try:
                                    line_geom = LineString(coords)
                                    if line_geom.is_valid and line_geom.length > 0:
                                        new_contours.append({
                                            'geometry': line_geom,
                                            thickness_column: level,
                                            'source': 'intermediate'
                                        })
                                except Exception:
                                    continue
                except Exception:
                    continue
                    
        except ImportError:
            print("skimage not available, using simplified approach")
            # Simplified fallback: create synthetic contours by offsetting existing ones
            for idx, row in contour_gdf.iterrows():
                if row.geometry is not None:
                    original_thickness = row[thickness_column]
                    
                    # Create intermediate levels above and below
                    for offset in [-contour_interval, contour_interval]:
                        new_thickness = original_thickness + offset
                        if min_thickness <= new_thickness <= max_thickness:
                            # Create slightly offset geometry
                            try:
                                offset_geom = row.geometry.buffer(grid_spacing * 0.5).boundary
                                if hasattr(offset_geom, 'geoms'):
                                    for geom in offset_geom.geoms:
                                        if geom.geom_type == 'LineString':
                                            new_contours.append({
                                                'geometry': geom,
                                                thickness_column: new_thickness,
                                                'source': 'intermediate'
                                            })
                                elif offset_geom.geom_type == 'LineString':
                                    new_contours.append({
                                        'geometry': offset_geom,
                                        thickness_column: new_thickness,
                                        'source': 'intermediate'
                                    })
                            except Exception:
                                continue
    
    # Add original contours
    for idx, row in contour_gdf.iterrows():
        if row.geometry is not None and not row.geometry.is_empty:
            new_contours.append({
                'geometry': row.geometry,
                thickness_column: row[thickness_column],
                'source': 'original'
            })
    
    # Create new GeoDataFrame
    if new_contours:
        densified_gdf = gpd.GeoDataFrame(new_contours, crs=contour_gdf.crs)
        print(f"Successfully created {len(densified_gdf)} densified contours")
        return densified_gdf
    else:
        print("Warning: No intermediate contours created, using original")
        return contour_gdf


def _extract_points_from_dense_contours(contour_gdf, thickness_column, point_spacing=10):
    """
    Extract points from the densified contour network.
    """
    points_for_interp = []
    
    for idx, row in contour_gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        
        thickness_value = row[thickness_column]
        geom = row.geometry
        
        if geom.geom_type == 'LineString':
            # Sample points along line at specified spacing
            coords = _sample_line_at_spacing(geom, point_spacing)
            for x, y in coords:
                points_for_interp.append((x, y, thickness_value))
                
        elif geom.geom_type == 'MultiLineString':
            for line in geom.geoms:
                coords = _sample_line_at_spacing(line, point_spacing)
                for x, y in coords:
                    points_for_interp.append((x, y, thickness_value))
    
    return points_for_interp


def _sample_line_at_spacing(linestring, spacing):
    """
    Sample points along a LineString at regular spacing intervals.
    """
    if linestring.length == 0:
        return list(linestring.coords)
    
    # Calculate number of points
    num_points = max(3, int(linestring.length / spacing) + 1)
    
    # Sample at regular intervals
    distances = np.linspace(0, linestring.length, num_points)
    coords = []
    
    for dist in distances:
        try:
            point = linestring.interpolate(dist)
            coords.append((point.x, point.y))
        except:
            continue
    
    return coords


def _plot_contour_densification(original_contours, densified_contours, thickness_column, 
                               modelgrid, figsize):
    """
    Plot the original vs densified contour networks.
    """
    import matplotlib.pyplot as plt
    import flopy
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(figsize[0]*1.5, figsize[1]*0.8))
    
    # Left plot: Original contours
    original_contours.plot(ax=ax1, column=thickness_column, cmap='viridis', 
                          linewidth=2, legend=True)
    
    # Plot model grid
    pmv1 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax1)
    pmv1.plot_grid(linewidth=0.5, color='red', alpha=0.5)
    
    ax1.set_title(f"Original Contours ({len(original_contours)} lines)")
    ax1.set_xlabel("X-coordinate")
    ax1.set_ylabel("Y-coordinate")
    ax1.set_aspect('equal')
    
    # Right plot: Densified contours
    # Separate original and intermediate for different styling
    original_mask = densified_contours.get('source', 'original') == 'original'
    intermediate_mask = densified_contours.get('source', 'original') == 'intermediate'
    
    if 'source' in densified_contours.columns:
        # Plot intermediate contours (thinner, lighter)
        intermediate_contours = densified_contours[intermediate_mask]
        if len(intermediate_contours) > 0:
            intermediate_contours.plot(ax=ax2, column=thickness_column, cmap='viridis', 
                                     linewidth=0.8, alpha=0.6)
        
        # Plot original contours (thicker, darker)
        original_subset = densified_contours[original_mask]
        if len(original_subset) > 0:
            original_subset.plot(ax=ax2, column=thickness_column, cmap='viridis', 
                               linewidth=2, alpha=0.9, legend=True)
    else:
        # All contours with same styling
        densified_contours.plot(ax=ax2, column=thickness_column, cmap='viridis', 
                              linewidth=1.2, legend=True)
    
    # Plot model grid
    pmv2 = flopy.plot.PlotMapView(modelgrid=modelgrid, ax=ax2)
    pmv2.plot_grid(linewidth=0.5, color='red', alpha=0.5)
    
    ax2.set_title(f"Densified Contours ({len(densified_contours)} lines)")
    ax2.set_xlabel("X-coordinate") 
    ax2.set_ylabel("Y-coordinate")
    ax2.set_aspect('equal')
    
    plt.tight_layout()
    plt.show()


def _interpolate_dense_contours_to_grid(points_array, modelgrid):
    """
    Interpolate from dense contour points to model grid using robust methods.
    """
    from scipy.interpolate import griddata
    import numpy as np
    
    # Get model grid coordinates
    x_centers = modelgrid.xcellcenters
    y_centers = modelgrid.ycellcenters
    
    # Create grid points for interpolation
    x_flat = x_centers.flatten()
    y_flat = y_centers.flatten()
    grid_points = np.column_stack((x_flat, y_flat))
    
    # Extract coordinates and values
    point_coords = points_array[:, :2]
    values = points_array[:, 2]
    
    print(f"Final interpolation: {len(values)} points -> {len(grid_points)} grid cells")
    print(f"Point thickness range: {values.min():.1f} - {values.max():.1f} m")
    
    # Use linear interpolation (should work well with dense contour network)
    try:
        interpolated = griddata(point_coords, values, grid_points, method='linear')
        interpolated_2d = interpolated.reshape(x_centers.shape)
        
        # Fill any remaining NaN with nearest neighbor
        nan_mask = np.isnan(interpolated_2d)
        if np.any(nan_mask):
            print(f"Filling {nan_mask.sum()} NaN cells with nearest neighbor...")
            nearest_values = griddata(point_coords, values, grid_points, method='nearest')
            interpolated_2d[nan_mask] = nearest_values.reshape(x_centers.shape)[nan_mask]
        
        print(f"Interpolation successful: range [{np.nanmin(interpolated_2d):.1f}, {np.nanmax(interpolated_2d):.1f}]")
        return interpolated_2d
        
    except Exception as e:
        print(f"Linear interpolation failed: {e}")
        # Fallback to nearest neighbor
        print("Using nearest neighbor interpolation...")
        interpolated = griddata(point_coords, values, grid_points, method='nearest')
        return interpolated.reshape(x_centers.shape)


def _apply_geological_constraints_improved(thickness_array, original_thickness_values):
    """
    Apply improved geological constraints with gentler processing.
    """
    import numpy as np
    from scipy import ndimage
    
    # Get reasonable bounds from original data
    min_thickness = max(1.0, original_thickness_values.min() * 0.9)  # Allow 10% below min
    max_thickness = original_thickness_values.max() * 1.1  # Allow 10% above max
    median_thickness = np.median(original_thickness_values)
    
    print(f"Applying improved geological constraints:")
    print(f"  Min thickness: {min_thickness:.1f} m")
    print(f"  Max thickness: {max_thickness:.1f} m")
    print(f"  Median thickness: {median_thickness:.1f} m")
    
    # Store original values for comparison
    original_min = thickness_array.min()
    original_max = thickness_array.max()
    
    # Apply gentle clipping
    thickness_array = np.clip(thickness_array, min_thickness, max_thickness)
    
    # Apply very light smoothing to reduce small-scale noise
    thickness_array = ndimage.gaussian_filter(thickness_array, sigma=0.3)
    
    # Ensure minimum thickness
    thickness_array = np.maximum(thickness_array, min_thickness)
    
    print(f"  Before constraints: {original_min:.1f} - {original_max:.1f} m")
    print(f"  After constraints: {thickness_array.min():.1f} - {thickness_array.max():.1f} m")
    print(f"  Mean thickness: {thickness_array.mean():.1f} m")
    
    return thickness_array


