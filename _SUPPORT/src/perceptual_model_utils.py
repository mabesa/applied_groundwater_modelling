"""
Utility functions for the perceptual model notebook.

This module packages complex data processing code to keep the notebook focused
on concepts rather than implementation details.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import geopandas as gpd


def load_and_display_climate_data(climate_data_path: str) -> tuple[pd.DataFrame, plt.Figure]:
    """
    Load climate data and create a visualization.

    Parameters
    ----------
    climate_data_path : str
        Path to the climate data directory or zip file

    Returns
    -------
    tuple
        (climate_norms DataFrame, matplotlib figure)
    """
    import climate_utils as cu

    # Handle zip files
    if climate_data_path.endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(climate_data_path, 'r') as zip_ref:
            extract_path = os.path.dirname(climate_data_path)
            zip_ref.extractall(extract_path)
        climate_data_path = extract_path

    # Read and process climate data
    climate_norms = cu.read_climate_data(climate_data_path)

    # Create plot
    fig, ax = cu.plot_climate_data(
        climate_norms,
        custom_title="Monthly average temperature and precipitation (Fluntern station, 1991-2020)"
    )

    return climate_norms, fig


def calculate_lateral_inflow(
    area_south_km2: float = 15.0,
    area_north_km2: float = 11.0,
    infiltration_fraction: float = 0.1,
    precipitation_mm_per_year: float = 1100.0
) -> dict:
    """
    Calculate lateral inflow from surrounding hills using water balance approach.

    Parameters
    ----------
    area_south_km2 : float
        Catchment area south of the valley (km²)
    area_north_km2 : float
        Catchment area north of the valley (km²)
    infiltration_fraction : float
        Fraction of precipitation that infiltrates (0-1)
    precipitation_mm_per_year : float
        Annual precipitation (mm/year)

    Returns
    -------
    dict
        Dictionary with inflow values in m³/year
    """
    # Convert to m³/year
    inflow_south = infiltration_fraction * area_south_km2 * 1e6  # km² to m², mm to m
    inflow_north = infiltration_fraction * area_north_km2 * 1e6

    return {
        'south_m3_per_year': inflow_south,
        'north_m3_per_year': inflow_north,
        'total_m3_per_year': inflow_south + inflow_north,
        'area_south_km2': area_south_km2,
        'area_north_km2': area_north_km2,
    }


def get_river_level_summary(data_path: str, start_year: int = 2010, end_year: int = 2020) -> dict:
    """
    Get summary statistics for river water levels.

    Parameters
    ----------
    data_path : str
        Path to river data directory
    start_year : int
        Start year for analysis
    end_year : int
        End year for analysis

    Returns
    -------
    dict
        Summary statistics for Sihl and Limmat rivers
    """
    import river_utils as ru
    return ru.get_river_level_summary(data_path, start_year, end_year)


def plot_river_aquifer_cross_sections() -> plt.Figure:
    """
    Create cross-section plots showing river-aquifer relationships.

    Returns
    -------
    plt.Figure
        Matplotlib figure with two subplots
    """
    import river_utils as ru

    # River and groundwater level data
    sihl_gw_mean = 400.8
    sihl_gw_high = 403.5
    sihl_river_mean = 412.347
    sihl_river_high = 413.439
    sihl_depth_mean = 0.3

    limmat_gw_mean = 399.5
    limmat_gw_high = 400.5
    limmat_river_mean = 400.285
    limmat_river_high = 401.822
    limmat_depth_mean = 0.7

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 14))
    fig.suptitle("River and Groundwater Level Cross-Sections", fontsize=16, y=0.95)

    ru.plot_cross_section(ax1, "a) River Sihl", sihl_gw_mean, sihl_gw_high,
                          sihl_river_mean, sihl_river_high, sihl_depth_mean)
    ru.plot_cross_section(ax2, "b) River Limmat", limmat_gw_mean, limmat_gw_high,
                          limmat_river_mean, limmat_river_high, limmat_depth_mean)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    return fig


def analyze_groundwater_concessions(
    wells_path: str,
    boundary_path: str,
    size_category: str = 'large'
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Analyze groundwater concessions within the model boundary.

    Parameters
    ----------
    wells_path : str
        Path to wells geopackage
    boundary_path : str
        Path to model boundary geopackage
    size_category : str
        'large' (>3000 l/min), 'medium' (300-3000 l/min), or 'all'

    Returns
    -------
    tuple
        (GeoDataFrame of filtered wells, summary statistics dict)
    """
    # Read data
    wells_gdf = gpd.read_file(wells_path, layer='GS_GRUNDWASSERFASSUNGEN_OGD_P')
    boundary_gdf = gpd.read_file(boundary_path)

    # Clip to boundary
    wells_gdf = wells_gdf.clip(boundary_gdf)

    # Add concession ID
    wells_gdf['concession_id'] = wells_gdf['GWR_ID'].str.split('_').str[0]

    # Filter out decommissioned wells
    is_decommissioned = wells_gdf['BESCHREIBUNG'].str.contains('aufgehoben', case=False, na=False)
    is_unused = wells_gdf['BESCHREIBUNG'].str.contains('ungenutzt', case=False, na=False)
    wells_active = wells_gdf[~is_decommissioned & ~is_unused].copy()

    # Filter by size category
    if size_category == 'large':
        phrase = "Grundwasserfassung mit Ertrag > 3000 l/min"
    elif size_category == 'medium':
        phrase = "Grundwasserfassung mit Ertrag 300 - 3000 l/min"
    else:
        phrase = ""

    if phrase:
        wells_valid = wells_active[
            wells_active['NUTZART'].notna() &
            wells_active['NUTZART'].astype(str).str.strip().ne("")
        ].copy()

        mask = wells_valid['BESCHREIBUNG'].str.contains(phrase, case=False, na=False)
        matching_wells = wells_valid[mask]
        concessions = matching_wells['concession_id'].dropna().astype(str).unique()
        filtered_wells = wells_valid[wells_valid['concession_id'].astype(str).isin(concessions)].copy()
    else:
        filtered_wells = wells_active.copy()

    # Summary statistics
    summary = {
        'total_concessions': wells_gdf['concession_id'].nunique(),
        'active_concessions': wells_active['concession_id'].nunique(),
        'filtered_concessions': filtered_wells['concession_id'].nunique() if len(filtered_wells) > 0 else 0,
        'size_category': size_category,
    }

    return filtered_wells, summary


def calculate_water_balance_summary(
    model_area_km2: float,
    sihl_area_m2: float,
    limmat_area_m2: float,
    q_riv_sihl: float,
    q_riv_limmat: float,
    inflow_south: float,
    inflow_north: float,
    outflow_lower_bound: float,
    outflow_upper_bound: float,
    pumping_m3_per_year: float = 7_600_000,
    net_recharge_mm_per_year: float = 200
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate and format water balance summary tables.

    Parameters
    ----------
    model_area_km2 : float
        Model domain area in km²
    sihl_area_m2 : float
        River Sihl area within model boundary (m²)
    limmat_area_m2 : float
        River Limmat area within model boundary (m²)
    q_riv_sihl : float
        Specific flux from Sihl (m/s)
    q_riv_limmat : float
        Specific flux from Limmat (m/s)
    inflow_south : float
        Lateral inflow from south (m³/year)
    inflow_north : float
        Lateral inflow from north (m³/year)
    outflow_lower_bound : float
        Lower bound of western outflow (m³/day)
    outflow_upper_bound : float
        Upper bound of western outflow (m³/day)
    pumping_m3_per_year : float
        Total groundwater pumping (m³/year)
    net_recharge_mm_per_year : float
        Net areal recharge rate (mm/year)

    Returns
    -------
    tuple
        (inflow_df, outflow_df) as pandas DataFrames
    """
    # Calculate fluxes
    net_recharge = (net_recharge_mm_per_year / 1000) * model_area_km2 * 1e6  # m³/year
    river_sihl_inflow = sihl_area_m2 * q_riv_sihl * 365 * 24 * 3600  # m³/year
    river_limmat_inflow = limmat_area_m2 * q_riv_limmat * 365 * 24 * 3600  # m³/year
    gw_outflow_west = (outflow_lower_bound + outflow_upper_bound) / 2 * 365  # m³/year

    # Create summary tables
    inflow_df = pd.DataFrame({
        "Component": [
            "Net areal recharge (R)",
            "Lateral inflow from south",
            "Lateral inflow from north",
            "River Sihl infiltration",
            "River Limmat infiltration",
        ],
        "Value (10^6 m³/year)": [
            round(net_recharge / 1e6, 1),
            round(inflow_south / 1e6, 1),
            round(inflow_north / 1e6, 1),
            round(river_sihl_inflow / 1e6, 1),
            round(river_limmat_inflow / 1e6, 1)
        ]
    })

    outflow_df = pd.DataFrame({
        "Component": [
            "Groundwater outflow (west)",
            "Groundwater pumping"
        ],
        "Value (10^6 m³/year)": [
            round(gw_outflow_west / 1e6, 1),
            round(pumping_m3_per_year / 1e6, 1)
        ]
    })

    return inflow_df, outflow_df


def estimate_river_aquifer_flux(
    leakage_coefficient: float,
    river_level: float,
    groundwater_level: float,
    river_area_m2: float
) -> dict:
    """
    Estimate flux between river and aquifer.

    Parameters
    ----------
    leakage_coefficient : float
        Leakage coefficient (1/s)
    river_level : float
        River water level (m a.s.l.)
    groundwater_level : float
        Groundwater level (m a.s.l.)
    river_area_m2 : float
        River bed area (m²)

    Returns
    -------
    dict
        Flux estimates in various units
    """
    q_specific = leakage_coefficient * (river_level - groundwater_level)  # m/s
    q_total_m3_per_s = q_specific * river_area_m2
    q_total_m3_per_year = q_total_m3_per_s * 365 * 24 * 3600

    return {
        'specific_flux_m_per_s': q_specific,
        'total_flux_m3_per_s': q_total_m3_per_s,
        'total_flux_m3_per_year': q_total_m3_per_year,
        'total_flux_million_m3_per_year': q_total_m3_per_year / 1e6,
    }
