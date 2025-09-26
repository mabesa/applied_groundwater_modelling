import numpy as np
import matplotlib.pyplot as plt
import flopy

import re

def test_regex_patterns(sample_lines):
    """
    Test different regex patterns against your sample lines to find what works.
    """
    
    # Test sample lines
    test_lines = [
        "    DRY(  3,103)   DRY(  3,104)   DRY(  3,105)   DRY(  3,106)   DRY(  3,107)",
        "    DRY(  3,108)   DRY(  3,109)   DRY(  3,110)   DRY(  3,111)   DRY(  3,112)",
        "    DRY(  3,113)   DRY(  3,114)   DRY(  3,115)   DRY(  3,116)   DRY(  3,117)"
    ]
    
    # Different patterns to try
    patterns = {
        'original': r"DRY\(\s*(\d+),\s*(\d+)\)",
        'flexible_spaces': r"DRY\(\s*(\d+),\s*(\d+)\)",
        'exact_spaces': r"DRY\(\s+(\d+),(\d+)\)",
        'very_flexible': r"DRY\(\s*(\d+)\s*,\s*(\d+)\s*\)",
        'simple': r"DRY\((\d+),(\d+)\)",
    }
    
    print("Testing different regex patterns:")
    print("=" * 50)
    
    for pattern_name, pattern in patterns.items():
        print(f"\nPattern '{pattern_name}': {pattern}")
        compiled_pattern = re.compile(pattern)
        
        total_matches = 0
        for i, line in enumerate(test_lines):
            matches = compiled_pattern.findall(line)
            total_matches += len(matches)
            if matches:
                print(f"  Line {i+1}: Found {len(matches)} matches")
                for match in matches[:3]:  # Show first 3 matches
                    print(f"    → ({match[0]}, {match[1]})")
            else:
                print(f"  Line {i+1}: No matches")
        
        print(f"  Total matches: {total_matches}")

def debug_list_file_parsing(list_file_path):
    """
    Debug function to examine your actual list file and test pattern matching.
    """
    
    print("Debugging list file parsing...")
    print("=" * 50)
    
    # Read file and look for DRY lines
    dry_lines = []
    with open(list_file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if 'DRY(' in line:
                dry_lines.append((line_num, line.strip()))
                if len(dry_lines) <= 5:  # Show first 5 DRY lines
                    print(f"Line {line_num}: {repr(line.strip())}")
    
    print(f"\nFound {len(dry_lines)} lines containing 'DRY('")
    
    if not dry_lines:
        print("No lines with 'DRY(' found. Check if:")
        print("- The model actually had dry cells")
        print("- The list file is complete")
        print("- The file path is correct")
        return []
    
    # Test patterns on actual data
    print(f"\nTesting patterns on first DRY line:")
    first_line = dry_lines[0][1]
    print(f"Sample line: {repr(first_line)}")
    
    patterns = {
        'flexible': r"DRY\(\s*(\d+),\s*(\d+)\)",
        'exact': r"DRY\(\s+(\d+),(\d+)\)",
        'very_simple': r"DRY\((\d+),(\d+)\)"
    }
    
    working_pattern = None
    for name, pattern in patterns.items():
        matches = re.findall(pattern, first_line)
        print(f"  Pattern '{name}': {len(matches)} matches")
        if matches:
            print(f"    First few: {matches[:3]}")
            if working_pattern is None:
                working_pattern = pattern
    
    if working_pattern:
        print(f"\nUsing working pattern: {working_pattern}")
        return extract_dry_cells_with_pattern(list_file_path, working_pattern)
    else:
        print("\nNo patterns worked! Manual parsing needed.")
        return manual_parse_dry_cells(list_file_path)

def extract_dry_cells_with_pattern(list_file_path, pattern):
    """
    Extract dry cells using a specific regex pattern.
    """
    compiled_pattern = re.compile(pattern)
    dry_cells = []
    
    with open(list_file_path, 'r') as f:
        for line in f:
            if 'DRY(' in line:
                matches = compiled_pattern.findall(line)
                for row_str, col_str in matches:
                    row_1based, col_1based = int(row_str), int(col_str)
                    dry_cells.append((row_1based - 1, col_1based - 1))  # Convert to 0-based
    
    print(f"Extracted {len(dry_cells)} dry cells")
    if dry_cells:
        print(f"Sample: {dry_cells[:5]}")
    
    return dry_cells

def manual_parse_dry_cells(list_file_path):
    """
    Manual parsing approach if regex fails.
    """
    print("Attempting manual parsing...")
    
    dry_cells = []
    with open(list_file_path, 'r') as f:
        for line in f:
            if 'DRY(' in line:
                # Split by 'DRY(' and process each part
                parts = line.split('DRY(')
                for part in parts[1:]:  # Skip first empty part
                    if ')' in part:
                        coords = part.split(')')[0]
                        if ',' in coords:
                            try:
                                row_str, col_str = coords.split(',')
                                row = int(row_str.strip())
                                col = int(col_str.strip())
                                dry_cells.append((row - 1, col - 1))  # Convert to 0-based
                            except ValueError:
                                continue
    
    print(f"Manual parsing found {len(dry_cells)} dry cells")
    return dry_cells

def fix_dry_cell_extraction(list_file_path):
    """
    Robust dry cell extraction that tries multiple approaches.
    """
    
    # First try the debug approach
    dry_cells = debug_list_file_parsing(list_file_path)
    
    if not dry_cells:
        print("Trying alternative patterns...")
        
        # Try some specific patterns for MODFLOW format
        alternative_patterns = [
            r"DRY\(\s*(\d+)\s*,\s*(\d+)\s*\)",  # Most flexible
            r"DRY\(\s+(\d+),\s*(\d+)\s*\)",     # Space before first number
            r"DRY\(\s*(\d+),(\d+)\s*\)",        # Space after comma optional
        ]
        
        for i, pattern in enumerate(alternative_patterns):
            try:
                test_cells = extract_dry_cells_with_pattern(list_file_path, pattern)
                if test_cells:
                    print(f"Success with pattern {i+1}!")
                    dry_cells = test_cells
                    break
            except:
                continue
    
    return dry_cells

def visualize_dry_cells_simple(mf, dry_cells_list, figsize=(12, 8)):
    """
    Visualize dry cells from a list of (row, col) tuples on the model grid.
    
    Parameters:
    -----------
    mf : flopy.modflow.Modflow
        Your MODFLOW model object
    dry_cells_list : list of tuples
        List of (row, col) coordinates in 0-based indexing
    """
    
    # Create boolean mask from your dry cell list
    nrow, ncol = mf.dis.nrow, mf.dis.ncol
    dry_mask = np.zeros((nrow, ncol), dtype=bool)
    
    for row, col in dry_cells_list:
        if 0 <= row < nrow and 0 <= col < ncol:
            dry_mask[row, col] = True
    
    # Create the plot
    fig, ax = plt.subplots(figsize=figsize)
    modelmap = flopy.plot.PlotMapView(model=mf, ax=ax)
    
    # Plot grid and boundary conditions
    modelmap.plot_grid(alpha=0.3, color='lightgray', linewidth=0.5)
    
    # Plot boundary conditions
    if mf.get_package('CHD'):
        modelmap.plot_bc('CHD', color='blue', alpha=0.7, label='CHD')
    if mf.get_package('WEL'):
        modelmap.plot_bc('WEL', color='red', alpha=0.7, label='Wells') 
    if mf.get_package('RIV'):
        modelmap.plot_bc('RIV', color='cyan', alpha=0.7, label='River')
    
    # Plot dry cells
    dry_array = np.where(dry_mask, 1, np.nan)
    im = modelmap.plot_array(dry_array, cmap='Reds', alpha=0.8, 
                            vmin=0, vmax=1)
    
    # Formatting
    ax.set_xlabel('X coordinate (m)')
    ax.set_ylabel('Y coordinate (m)')
    ax.set_title(f'MODFLOW Dry Cells\n({len(dry_cells_list)} cells dried during simulation)')
    ax.legend(loc='upper right')
    ax.set_aspect('equal')
    
    # Add statistics
    total_cells = nrow * ncol
    dry_count = len(dry_cells_list)
    stats_text = f'Dry: {dry_count:,} / {total_cells:,} ({dry_count/total_cells*100:.1f}%)'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', 
            facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    return fig, ax

def visualize_dry_cells(mf, dry_mask, figsize=(12, 8)):
    """
    Visualize dry cells on the model grid with boundary conditions.
    
    Parameters:
    -----------
    mf : flopy.modflow.Modflow
        MODFLOW model object
    dry_mask : numpy.ndarray
        Boolean array indicating dry cells
    figsize : tuple
        Figure size for matplotlib
    """
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot model grid
    modelmap = flopy.plot.PlotMapView(model=mf, ax=ax)
    
    # Plot grid lines
    modelmap.plot_grid(alpha=0.3, color='lightgray', linewidth=0.5)
    
    # Plot boundary conditions
    if mf.get_package('CHD'):
        modelmap.plot_bc('CHD', color='blue', label='CHD', alpha=0.7)
    
    if mf.get_package('WEL'):
        modelmap.plot_bc('WEL', color='red', label='Wells', alpha=0.7)
        
    if mf.get_package('RIV'):
        modelmap.plot_bc('RIV', color='cyan', label='River', alpha=0.7)
    
    # Overlay dry cells
    dry_array = np.where(dry_mask, 1, np.nan)
    im = modelmap.plot_array(dry_array, cmap='Reds', alpha=0.8, 
                            vmin=0, vmax=1, label='Dry cells')
    
    # Add colorbar for dry cells
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, label='Dry cells')
    cbar.set_ticks([0, 1])
    cbar.set_ticklabels(['Wet', 'Dry'])
    
    # Formatting
    ax.set_xlabel('X coordinate (m)')
    ax.set_ylabel('Y coordinate (m)')
    ax.set_title('MODFLOW Model Grid: Cells Going Dry\n(Red areas indicate cells that dried during simulation)')
    ax.legend(loc='upper right')
    ax.set_aspect('equal')
    
    # Add statistics text
    total_cells = dry_mask.size
    dry_count = np.sum(dry_mask)
    dry_percentage = (dry_count / total_cells) * 100
    
    stats_text = f'Dry cells: {dry_count:,} / {total_cells:,} ({dry_percentage:.1f}%)'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', 
            facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    return fig, ax

