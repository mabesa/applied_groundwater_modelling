import os, pprint
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import yaml
import zipfile

from shapely.geometry import Point, Polygon
import geopandas as gpd
from typing import Tuple, List, Dict, Optional

import flopy
from flopy.utils import HeadFile, CellBudgetFile

plt.rcParams['figure.figsize'] = (8, 6)
def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def unzip_file(zip_path, extract_to=None):
    print(f"Checking zip file: {zip_path}")
    print(f"File size: {os.path.getsize(zip_path)} bytes")
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)
    print(f"Extracting to: {extract_to}")
    # Check if it's a valid zip file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            print("✓ Zip file is valid")
            files = zip_ref.namelist()
            print(f"Contains {len(files)} files:")
            for f in files[:5]:  # Show first 5 files
                print(f"  {f}")
            if len(files) > 5:
                print(f"  ... and {len(files)-5} more")
                
            # Try extraction
            extract_path = os.path.dirname(zip_path)
            zip_ref.extractall(extract_path)
            print(f"✓ Extraction successful to {extract_path}")
            
    except zipfile.BadZipFile as e:
        print(f"✗ Bad zip file: {e}")
        
        # Check first few bytes
        with open(zip_path, 'rb') as f:
            header = f.read(10)
            print(f"File header: {header.hex()}")
            print(f"As text: {header}")
            
        raise e   
    
def get_scenario_for_group(config_path, group_number):
    """
    Load the YAML config and return the scenario parameters for the given group number.
    
    Parameters:
    -----------
    config_path : str
        Path to the case_config.yaml file
    group_number : int
        Group number (0-8)
        
    Returns:
    --------
    dict
        Scenario parameters for the group, or None if not found
    """
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Find the scenario with id matching the group number
    scenarios = cfg.get('scenarios', {}).get('options', [])
    
    for scenario in scenarios:
        if scenario.get('id') == group_number:
            return scenario
    
    return None


# Default location of the (all-groups) transport case-study config, relative
# to the repo root. Overridable per-call (``config_path``) or via the
# ``AGM_TRANSPORT_CONFIG`` env var (useful for tests / alternate deployments).
_DEFAULT_TRANSPORT_CONFIG = (
    Path(__file__).resolve().parents[2] / "PROJECT" / "workspace" / "template" / "case_config_transport.yaml"
)
AGM_TRANSPORT_CONFIG_ENV_VAR = "AGM_TRANSPORT_CONFIG"


def _resolve_transport_config_path(config_path=None) -> Path:
    """Resolve the transport config path: explicit arg > env var > default."""
    if config_path is not None:
        return Path(config_path)
    env_value = os.environ.get(AGM_TRANSPORT_CONFIG_ENV_VAR)
    if env_value:
        return Path(env_value)
    return _DEFAULT_TRANSPORT_CONFIG


def _require_numeric(value, group, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"group {group}: field {field!r} must be numeric, got {value!r}")
    return value


def _get_required(block, key, group, field_label):
    if key not in block or block[key] is None:
        raise ValueError(f"group {group}: missing required field {field_label!r}")
    return block[key]


def _require_block(entry, key, group):
    block = entry.get(key)
    if not isinstance(block, dict):
        raise ValueError(f"group {group}: missing or invalid {key!r} block")
    return block


def _lint_doublet(entry, group):
    doublet = _require_block(entry, "doublet", group)
    for key in ("injection_easting", "injection_northing", "extraction_easting", "extraction_northing"):
        value = _get_required(doublet, key, group, f"doublet.{key}")
        _require_numeric(value, group, f"doublet.{key}")

    pumping_rate = _get_required(doublet, "pumping_rate_m3_d", group, "doublet.pumping_rate_m3_d")
    _require_numeric(pumping_rate, group, "doublet.pumping_rate_m3_d")
    if pumping_rate <= 0:
        raise ValueError(
            f"group {group}: field 'doublet.pumping_rate_m3_d' must be > 0, got {pumping_rate!r}"
        )

    recirc = _get_required(doublet, "recirculation_fraction", group, "doublet.recirculation_fraction")
    _require_numeric(recirc, group, "doublet.recirculation_fraction")
    if not (0 <= recirc <= 1):
        raise ValueError(
            f"group {group}: field 'doublet.recirculation_fraction' must be in [0, 1], got {recirc!r}"
        )
    return doublet


_VALID_SOURCE_TYPES = {"point", "line", "area"}
_VALID_SOURCE_RELEASE_TYPES = {"pulse", "continuous"}


def _lint_source(entry, group):
    source = _require_block(entry, "source", group)
    source_type = _get_required(source, "type", group, "source.type")
    if source_type not in _VALID_SOURCE_TYPES:
        raise ValueError(
            f"group {group}: field 'source.type' must be one of "
            f"{sorted(_VALID_SOURCE_TYPES)!r}, got {source_type!r}"
        )
    release_type = _get_required(source, "release_type", group, "source.release_type")
    if release_type not in _VALID_SOURCE_RELEASE_TYPES:
        raise ValueError(
            f"group {group}: field 'source.release_type' must be one of "
            f"{sorted(_VALID_SOURCE_RELEASE_TYPES)!r}, got {release_type!r}"
        )

    location = source.get("location")
    if not isinstance(location, dict):
        raise ValueError(f"group {group}: missing or invalid 'source.location' block")
    for key in ("easting", "northing", "layer"):
        value = _get_required(location, key, group, f"source.location.{key}")
        _require_numeric(value, group, f"source.location.{key}")

    duration = _get_required(source, "duration_days", group, "source.duration_days")
    _require_numeric(duration, group, "source.duration_days")
    if duration < 1:
        raise ValueError(f"group {group}: field 'source.duration_days' must be >= 1, got {duration!r}")

    concentration = _get_required(source, "concentration_mg_L", group, "source.concentration_mg_L")
    _require_numeric(concentration, group, "source.concentration_mg_L")
    return source


def _lint_simulation(entry, group):
    simulation = _require_block(entry, "simulation", group)
    duration = _get_required(simulation, "duration_days", group, "simulation.duration_days")
    _require_numeric(duration, group, "simulation.duration_days")
    if duration <= 0:
        raise ValueError(f"group {group}: field 'simulation.duration_days' must be > 0, got {duration!r}")

    output_times = simulation.get("output_times_days")
    if not isinstance(output_times, list) or len(output_times) == 0:
        raise ValueError(f"group {group}: field 'simulation.output_times_days' must be a non-empty list")
    for t in output_times:
        _require_numeric(t, group, "simulation.output_times_days")
    if any(b <= a for a, b in zip(output_times, output_times[1:])):
        raise ValueError(
            f"group {group}: field 'simulation.output_times_days' must be strictly increasing, "
            f"got {output_times!r}"
        )
    return simulation


def _lint_monitoring(entry, group):
    monitoring = _require_block(entry, "monitoring", group)
    threshold = _get_required(monitoring, "threshold_mg_L", group, "monitoring.threshold_mg_L")
    _require_numeric(threshold, group, "monitoring.threshold_mg_L")
    return monitoring


def lint_transport_config(config_path=None, groups=range(13)):
    """
    Validate per-group scenario coverage in the transport case-study config.

    Loads ``case_config_transport.yaml`` (default path resolved from the repo
    layout, overridable via ``config_path`` or the ``AGM_TRANSPORT_CONFIG``
    env var) and, for each requested group id, asserts that exactly one
    ``transport_scenarios.options`` entry exists with a complete and valid
    ``doublet``, ``source``, ``simulation`` and ``monitoring``
    block.

    Parameters
    ----------
    config_path : str or Path, optional
        Path to ``case_config_transport.yaml``. If None, uses the
        ``AGM_TRANSPORT_CONFIG`` env var if set, else the repo default at
        ``PROJECT/workspace/template/case_config_transport.yaml``.
    groups : iterable of int, default range(13)
        Group ids to validate.

    Returns
    -------
    dict
        ``{group_id: {...resolved values...}}`` coverage report, one entry
        per successfully validated group.

    Raises
    ------
    ValueError
        On any missing/invalid field, or a group id with zero or more than
        one matching config entry. The message names the group and the
        offending field/reason.
    """
    path = _resolve_transport_config_path(config_path)
    if not Path(path).is_file():
        raise ValueError(f"transport config file not found: {path}")

    cfg = load_yaml(path)
    options = (cfg or {}).get("transport_scenarios", {}).get("options", [])
    if not isinstance(options, list):
        raise ValueError(f"'transport_scenarios.options' must be a list, got {type(options)!r}")

    by_id = {}
    for entry in options:
        gid = entry.get("id") if isinstance(entry, dict) else None
        if gid is None:
            continue
        by_id.setdefault(gid, []).append(entry)

    report = {}
    for group in groups:
        matches = by_id.get(group, [])
        if len(matches) == 0:
            raise ValueError(f"group {group}: no matching 'transport_scenarios.options' entry with id == {group}")
        if len(matches) > 1:
            raise ValueError(
                f"group {group}: expected exactly one 'transport_scenarios.options' entry with "
                f"id == {group}, found {len(matches)}"
            )
        entry = matches[0]

        doublet = _lint_doublet(entry, group)
        source = _lint_source(entry, group)
        simulation = _lint_simulation(entry, group)
        monitoring = _lint_monitoring(entry, group)

        report[group] = {
            "id": group,
            "title": entry.get("title"),
            "doublet": doublet,
            "source": source,
            "simulation": simulation,
            "monitoring": monitoring,
        }

    return report


def filter_wells_by_concession(wells_gdf, concession_id):
    """Filter wells by concession ID."""
    # Work on a copy to avoid SettingWithCopyWarning
    wells_filtered = wells_gdf.copy()
    
    # Normalize / helper columns
    wells_filtered.loc[:, 'GWR_PREFIX'] = (
        wells_filtered['GWR_ID']
        .astype(str)
        .str.split('_', n=1).str[0]
        .str.strip()
        .str.lower()
    )
    
    # Only keep wells where GWR_PREFIX values start with 'b010' (code for Limmat valley aquifer)
    limmat_mask = wells_filtered['GWR_PREFIX'].str.startswith('b010')
    wells_filtered = wells_filtered[limmat_mask].copy()
    
    # Replace 'b010' with '' in GWR_PREFIX
    wells_filtered.loc[:, 'GWR_PREFIX'] = wells_filtered['GWR_PREFIX'].str.replace('b010', '', regex=False)
    
    # Now we get the wells for our concession
    concession_mask = wells_filtered['GWR_PREFIX'] == str(concession_id).lower()
    return wells_filtered[concession_mask].copy()

def plot_wells_on_model(m, wells_gdf, concession_id, modelgrid=None, source_point=None):
    """
    Plot wells on the model grid with proper rotation handling.
    
    Parameters:
    -----------
    m : flopy.modflow.Modflow
        The MODFLOW model object
    wells_gdf : geopandas.GeoDataFrame
        GeoDataFrame containing well locations and attributes
    concession_id : int or str
        The concession ID for labeling
    modelgrid : flopy.discretization.StructuredGrid, optional
        Override modelgrid (if None, uses m.modelgrid)
    source_point : geopandas.GeoDataFrame, optional
        GeoDataFrame containing the contamination source location
    """
    fig, ax = plt.subplots(figsize=(14, 12))

    # Use the model's own modelgrid if not provided
    grid_to_use = modelgrid if modelgrid is not None else m.modelgrid
    
    # Create PlotMapView object with the model (this handles rotation automatically)
    pmv = flopy.plot.PlotMapView(model=m, modelgrid=grid_to_use, ax=ax)

    # Plot the model grid
    pmv.plot_grid(alpha=0.4, color='white', linewidth=0.3)

    # Plot ibound - this should work with rotation
    if hasattr(m, 'bas6') and hasattr(m.bas6, 'ibound'):
        ibound_array = m.bas6.ibound.array
    if len(ibound_array.shape) > 2:
        ibound_layer = ibound_array[0]  # Use first layer
    else:
        ibound_layer = ibound_array
    # Plot with RdYlBu colormap and no masking to show all values
    pmv.plot_array(ibound_layer, alpha=0.4, cmap='RdYlBu', vmin=-1, vmax=1)

    # For wells, we need to ensure they're in the right coordinate system
    # Transform wells to model coordinates if needed
    wells_transformed = wells_gdf.copy()
    
    # If the modelgrid has rotation/offset, we might need coordinate transformation
    '''if hasattr(grid_to_use, 'get_local_coords'):
        # Convert real-world coords to local model coords
        local_coords = grid_to_use.get_local_coords(
            wells_gdf.geometry.x.values, 
            wells_gdf.geometry.y.values
        )
        wells_transformed.geometry = gpd.points_from_xy(local_coords[0], local_coords[1])
        wells_transformed.crs = None  # Local coordinates'''
    
    # Plot wells with different colors for different types
    well_types = wells_gdf['FASSART'].unique() if 'FASSART' in wells_gdf.columns else ['Unknown']
    colors = ['red', 'blue', 'green', 'orange']

    for i, well_type in enumerate(well_types):
        if 'FASSART' in wells_gdf.columns:
            wells_subset = wells_transformed[wells_gdf['FASSART'] == well_type]
        else:
            wells_subset = wells_transformed
    
        wells_subset.plot(ax=ax, color=colors[i % len(colors)], 
                         markersize=150, marker='o', 
                         label=f'{well_type}', alpha=0.9, edgecolor='black')

    # Add well ID labels using transformed coordinates
    for idx, (orig_row, trans_row) in enumerate(zip(wells_gdf.itertuples(), wells_transformed.itertuples())):
        ax.annotate(orig_row.GWR_ID.split('_')[-1],
                    xy=(trans_row.geometry.x, trans_row.geometry.y),
                    xytext=(8, 8), textcoords='offset points',
                    fontsize=9, ha='left', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

    # Plot source point if provided
    if source_point is not None:
        source_transformed = source_point.copy()
        source_transformed.plot(ax=ax, color='orange', markersize=200, 
                               marker='*', label='Contamination Source', 
                               alpha=0.95, edgecolor='black', linewidth=2, zorder=5)
        # Add label for source
        for idx, row in source_transformed.iterrows():
            ax.annotate('SOURCE',
                        xy=(row.geometry.x, row.geometry.y),
                        xytext=(10, -15), textcoords='offset points',
                        fontsize=11, fontweight='bold', ha='left', va='top',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='orange', 
                                 alpha=0.7, edgecolor='black', linewidth=1.5))

    # Formatting
    ax.legend(loc='upper right')
    ax.set_xlabel('X coordinate (m)')
    ax.set_ylabel('Y coordinate (m)')
    ax.set_title(f'Concession {concession_id} Wells on MODFLOW Grid\n'
                 f'Model: {m.name} | Grid: {m.dis.nrow}×{m.dis.ncol} cells')
    ax.set_aspect('equal')

    plt.tight_layout()
    return fig, ax



def recarray_from_wells(wells):
    dtype = [('k', int), ('i', int), ('j', int), ('flux', float)]
    arr = np.zeros((len(wells),), dtype=dtype)
    for idx, w in enumerate(wells):
        arr[idx] = (w['layer'], w['row'], w['col'], w['rate'])
    return arr

def summarize_budget(cbc_path, terms, kstpkper=(0,0)):
    cbc = CellBudgetFile(cbc_path)
    out = {}
    for t in terms:
        try:
            data = cbc.get_data(text=t, kstpkper=kstpkper)
            if data:
                out[t] = float(np.sum(data[0]))
            else:
                out[t] = None
        except Exception:
            out[t] = None
    return out

def sample_heads(hds_path, lrc_list, kstpkper=None):
    hf = HeadFile(hds_path)
    arr = hf.get_data(kstpkper=kstpkper) if kstpkper is not None else hf.get_data()[-1]
    samples = []
    for (k,i,j) in lrc_list:
        samples.append({'k':k, 'i':i, 'j':j, 'head': float(arr[k, i, j])})
    return samples


# ---------------------------------------------------------------------------
# REMOVED 2026-08-31 -- the telescoping / submodel machinery (546 lines).
#
# `BoundaryHeadExtractor`, `plot_submodel_extent_on_parent_model` and
# `extract_boundary_heads_from_clipped_polygon` cut a rectangular window out of
# a parent model and drove it with extracted boundary heads. This course does
# NOT do telescopic modelling: every scenario runs the same regional model,
# refined locally around the corridor of interest. Nothing referenced any of it
# -- zero callers repo-wide -- and it was structured-grid code (row/col, delr,
# delc) against a model that has been DISV/unstructured since the MF6 rewrite,
# so it could not have run against the current grid in any case.
#
# It is deleted rather than left dormant because its presence is what kept
# suggesting a submodel exists. Recover from git history if ever needed.
# ---------------------------------------------------------------------------
