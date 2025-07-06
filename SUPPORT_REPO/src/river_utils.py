"""
River utilities for analyzing and visualizing river water level data.

This module provides functions to load and visualize river water level data
from the Sihl and Limmat rivers in the Zurich area.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Tuple, Optional, Dict, Any, Union

import matplotlib.pyplot as plt
from ipywidgets import interactive, FloatSlider



def read_river_level_data(data_path: str, station_id: str) -> pd.DataFrame:
    """
    Read river water level data from CSV files.
    
    Parameters
    ----------
    data_path : str
        Path to the directory containing the river data files
    station_id : str
        Station ID ('2099' for Limmat or '2176' for Sihl)
    
    Returns
    -------
    pd.DataFrame
        DataFrame with datetime index and water level values
    """
    filename = f"{station_id}_Pegel_Tagesmittel_2000-01-01_2024-12-31.csv"
    filepath = os.path.join(data_path, filename)
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"River level data file not found: {filepath}")
    
    # Read CSV file, skipping header lines and using semicolon separator
    # Try different encodings to handle German characters
    encodings_to_try = ['windows-1252', 'iso-8859-1', 'cp1252', 'utf-8']
    
    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(filepath, sep=';', skiprows=8, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError(f"Could not decode file {filepath} with any of the tried encodings: {encodings_to_try}")
    
    # Convert timestamp to datetime
    df['Zeitstempel'] = pd.to_datetime(df['Zeitstempel'])
    
    # Set datetime as index
    df.set_index('Zeitstempel', inplace=True)
    
    # Select relevant columns and rename for clarity
    df = df[['Wert', 'Gewässer']].copy()
    df.columns = ['water_level_m', 'river']
    
    # Convert water level to numeric (handle any potential string values)
    df['water_level_m'] = pd.to_numeric(df['water_level_m'], errors='coerce')
    
    return df


def calculate_yearly_statistics(df: pd.DataFrame, 
                               start_year: Optional[int] = None, 
                               end_year: Optional[int] = None) -> pd.DataFrame:
    """
    Calculate yearly statistics (mean, min, max, percentiles) for each day of year.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with datetime index and water level data
    start_year : int, optional
        Start year for analysis (default: use all available data)
    end_year : int, optional
        End year for analysis (default: use all available data)
    
    Returns
    -------
    pd.DataFrame
        DataFrame with day of year as index and statistical measures as columns
    """
    # Filter data by year range if specified
    if start_year is not None:
        df = df[df.index.year >= start_year]
    if end_year is not None:
        df = df[df.index.year <= end_year]
    
    # Add day of year column
    df_copy = df.copy()
    df_copy['day_of_year'] = df_copy.index.dayofyear
    
    # Calculate statistics for each day of year
    yearly_stats = df_copy.groupby('day_of_year')['water_level_m'].agg([
        'mean', 'min', 'max', 'std',
        lambda x: x.quantile(0.25),  # 25th percentile
        lambda x: x.quantile(0.75),  # 75th percentile
        'count'
    ]).round(3)
    
    # Rename lambda columns
    yearly_stats.columns = ['mean', 'min', 'max', 'std', 'q25', 'q75', 'count']
    
    return yearly_stats


def plot_yearly_river_levels(data_path: str, 
                            start_year: Optional[int] = None,
                            end_year: Optional[int] = None,
                            figsize: Tuple[int, int] = (12, 8)) -> Tuple[Any, Any]:
    """
    Plot typical yearly evolution of river water levels for Sihl and Limmat rivers.
    
    Parameters
    ----------
    data_path : str
        Path to the directory containing the river data files
    start_year : int, optional
        Start year for analysis (default: 2010)
    end_year : int, optional
        End year for analysis (default: 2020)
    figsize : tuple
        Figure size (width, height) in inches
    
    Returns
    -------
    tuple
        Matplotlib figure and axes objects
    """
    # Set default years if not provided
    if start_year is None:
        start_year = 2010
    if end_year is None:
        end_year = 2020
    
    # Load data for both rivers
    sihl_data = read_river_level_data(data_path, '2176')
    limmat_data = read_river_level_data(data_path, '2099')
    
    # Calculate yearly statistics
    sihl_stats = calculate_yearly_statistics(sihl_data, start_year, end_year)
    limmat_stats = calculate_yearly_statistics(limmat_data, start_year, end_year)
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)
    
    # Define colors
    sihl_color = '#1f77b4'  # Blue
    limmat_color = '#ff7f0e'  # Orange
    
    # Plot Sihl river
    ax1.plot(sihl_stats.index, sihl_stats['mean'], color=sihl_color, linewidth=2, 
             label='Mean water level')
    ax1.fill_between(sihl_stats.index, sihl_stats['q25'], sihl_stats['q75'], 
                     color=sihl_color, alpha=0.3, label='25th-75th percentile')
    ax1.fill_between(sihl_stats.index, sihl_stats['min'], sihl_stats['max'], 
                     color=sihl_color, alpha=0.1, label='Min-Max range')
    
    ax1.set_ylabel('Water level (m a.s.l.)', fontsize=12)
    ax1.set_title(f'River Sihl - Zurich, Sihlhölzli (Station 2176)\n'
                  f'Typical yearly evolution ({start_year}-{end_year})', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    
    # Plot Limmat river
    ax2.plot(limmat_stats.index, limmat_stats['mean'], color=limmat_color, linewidth=2, 
             label='Mean water level')
    ax2.fill_between(limmat_stats.index, limmat_stats['q25'], limmat_stats['q75'], 
                     color=limmat_color, alpha=0.3, label='25th-75th percentile')
    ax2.fill_between(limmat_stats.index, limmat_stats['min'], limmat_stats['max'], 
                     color=limmat_color, alpha=0.1, label='Min-Max range')
    
    ax2.set_ylabel('Water level (m a.s.l.)', fontsize=12)
    ax2.set_xlabel('Day of year', fontsize=12)
    ax2.set_title(f'River Limmat - Zurich, Unterhard (Station 2099)\n'
                  f'Typical yearly evolution ({start_year}-{end_year})', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')
    
    # Set x-axis to show months
    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    ax2.set_xticks(month_starts)
    ax2.set_xticklabels(month_labels)
    ax2.set_xlim(1, 365)
    
    plt.tight_layout()
    
    return fig, (ax1, ax2)


def get_river_level_summary(data_path: str, 
                           start_year: Optional[int] = None,
                           end_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Get summary statistics for river water levels.
    
    Parameters
    ----------
    data_path : str
        Path to the directory containing the river data files
    start_year : int, optional
        Start year for analysis (default: use all available data)
    end_year : int, optional
        End year for analysis (default: use all available data)
    
    Returns
    -------
    dict
        Dictionary containing summary statistics for both rivers
    """
    # Load data for both rivers
    sihl_data = read_river_level_data(data_path, '2176')
    limmat_data = read_river_level_data(data_path, '2099')
    
    # Filter by year range if specified
    if start_year is not None:
        sihl_data = sihl_data[sihl_data.index.year >= start_year]
        limmat_data = limmat_data[limmat_data.index.year >= start_year]
    if end_year is not None:
        sihl_data = sihl_data[sihl_data.index.year <= end_year]
        limmat_data = limmat_data[limmat_data.index.year <= end_year]
    
    # Calculate summary statistics
    sihl_summary = {
        'mean': sihl_data['water_level_m'].mean(),
        'min': sihl_data['water_level_m'].min(),
        'max': sihl_data['water_level_m'].max(),
        'std': sihl_data['water_level_m'].std(),
        'range': sihl_data['water_level_m'].max() - sihl_data['water_level_m'].min(),
        'data_points': len(sihl_data),
        'station_name': 'Zurich, Sihlhölzli',
        'station_id': '2176'
    }
    
    limmat_summary = {
        'mean': limmat_data['water_level_m'].mean(),
        'min': limmat_data['water_level_m'].min(),
        'max': limmat_data['water_level_m'].max(),
        'std': limmat_data['water_level_m'].std(),
        'range': limmat_data['water_level_m'].max() - limmat_data['water_level_m'].min(),
        'data_points': len(limmat_data),
        'station_name': 'Zurich, Unterhard',
        'station_id': '2099'
    }
    
    return {
        'sihl': sihl_summary,
        'limmat': limmat_summary,
        'analysis_period': {
            'start_year': start_year or sihl_data.index.year.min(),
            'end_year': end_year or sihl_data.index.year.max()
        }
    }


def plot_combined_river_levels(data_path: str, 
                              start_year: Optional[int] = None,
                              end_year: Optional[int] = None,
                              figsize: Tuple[int, int] = (12, 6)) -> Tuple[Any, Any]:
    """
    Plot typical yearly evolution of both rivers on the same plot for comparison.
    
    Parameters
    ----------
    data_path : str
        Path to the directory containing the river data files
    start_year : int, optional
        Start year for analysis (default: 2010)
    end_year : int, optional
        End year for analysis (default: 2020)
    figsize : tuple
        Figure size (width, height) in inches
    
    Returns
    -------
    tuple
        Matplotlib figure and axes objects
    """
    # Set default years if not provided
    if start_year is None:
        start_year = 2010
    if end_year is None:
        end_year = 2020
    
    # Load data for both rivers
    sihl_data = read_river_level_data(data_path, '2176')
    limmat_data = read_river_level_data(data_path, '2099')
    
    # Calculate yearly statistics
    sihl_stats = calculate_yearly_statistics(sihl_data, start_year, end_year)
    limmat_stats = calculate_yearly_statistics(limmat_data, start_year, end_year)
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    
    # Define colors
    sihl_color = '#1f77b4'  # Blue
    limmat_color = '#ff7f0e'  # Orange
    
    # Plot both rivers
    ax.plot(sihl_stats.index, sihl_stats['mean'], color=sihl_color, linewidth=2, 
            label='Sihl - Mean water level')
    ax.fill_between(sihl_stats.index, sihl_stats['q25'], sihl_stats['q75'], 
                    color=sihl_color, alpha=0.3, label='Sihl - 25th-75th percentile')
    
    ax.plot(limmat_stats.index, limmat_stats['mean'], color=limmat_color, linewidth=2, 
            label='Limmat - Mean water level')
    ax.fill_between(limmat_stats.index, limmat_stats['q25'], limmat_stats['q75'], 
                    color=limmat_color, alpha=0.3, label='Limmat - 25th-75th percentile')
    
    ax.set_ylabel('Water level (m a.s.l.)', fontsize=12)
    ax.set_xlabel('Day of year', fontsize=12)
    ax.set_title(f'Typical yearly evolution of river water levels\n'
                 f'Sihl and Limmat rivers, Zurich ({start_year}-{end_year})', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    
    # Set x-axis to show months
    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    ax.set_xticks(month_starts)
    ax.set_xticklabels(month_labels)
    ax.set_xlim(1, 365)
    
    plt.tight_layout()
    
    return fig, ax


def plot_river_aquifer_interaction():
    """
    Generates an interactive plot to illustrate river-aquifer interaction
    and the corresponding flux vs. head relationship.
    """
    def create_plot(h_aq, h_riv):
        # Create a figure with two subplots, sharing the y-axis
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7), 
                                       gridspec_kw={'width_ratios': [3, 1]},
                                       sharey=True)
        fig.subplots_adjust(wspace=0.05)

        # --- Plot 1: Cross-section ---
        
        # Static elements
        r_bot = 10  # Riverbed bottom elevation
        aquifer_bottom = 0
        river_banks = [45, 55]

        # Aquifer material
        ax1.fill_between([0, 100], aquifer_bottom, r_bot, color='sandybrown', alpha=0.4, label='Aquifer')
        ax1.axhline(r_bot, color='saddlebrown', linestyle='--', linewidth=2, label=f'Riverbed Bottom (R_bot = {r_bot}m)')

        # River channel
        ax1.fill_between(river_banks, r_bot, 20, color='lightgrey')
        
        # Water in aquifer
        ax1.fill_between([0, 100], aquifer_bottom, h_aq, color='lightblue', alpha=0.7)
        ax1.axhline(h_aq, color='blue', linestyle='-', linewidth=2, label=f'Aquifer Head (H_aq = {h_aq:.1f}m)')

        # Water in river
        ax1.fill_between(river_banks, r_bot, h_riv, color='blue', alpha=0.6)
        ax1.axhline(h_riv, xmin=0.45, xmax=0.55, color='darkblue', linestyle='-', linewidth=2, label=f'River Stage (H_riv = {h_riv:.1f}m)')

        ax1.set_ylim(7, 16)
        ax1.set_xlim(0, 100)
        ax1.set_xlabel("Horizontal Distance (m)")
        ax1.set_ylabel("Elevation / Head (m)")
        
        # --- Logic for conditions and arrows ---
        if h_aq > h_riv:
            # 1. Gaining Stream
            condition_title = "Gaining Stream (Connected)"
            equation = r'$Q_{riv} \propto (H_{riv} - H_{aq})$'
            # Arrow shows head difference
            ax1.annotate("", xy=(40, h_riv), xytext=(40, h_aq),
                         arrowprops=dict(arrowstyle='<->', color='green', lw=2))
            ax1.text(30, (h_riv + h_aq)/2, 'ΔH', color='green', ha='center', va='center')

        elif h_aq > r_bot:
            # 2. Losing Stream (Connected)
            condition_title = "Losing Stream (Connected)"
            equation = r'$Q_{riv} \propto (H_{riv} - H_{aq})$'
            # Arrow shows head difference
            ax1.annotate("", xy=(60, h_aq), xytext=(60, h_riv),
                         arrowprops=dict(arrowstyle='<->', color='red', lw=2))
            ax1.text(70, (h_riv + h_aq)/2, 'ΔH', color='red', ha='center', va='center')

        else: # h_aq <= r_bot
            # 3. Losing Stream (Disconnected)
            condition_title = "Losing Stream (Disconnected)"
            equation = r'$Q_{riv} \propto (H_{riv} - R_{bot})$'
            # Arrow shows head difference relative to riverbed bottom
            ax1.annotate("", xy=(60, r_bot), xytext=(60, h_riv),
                         arrowprops=dict(arrowstyle='<->', color='darkred', lw=2))
            ax1.text(70, (h_riv + r_bot)/2, 'ΔH', color='darkred', ha='center', va='center')
            # Vadose zone
            ax1.fill_between([0, 100], h_aq, r_bot, color='ivory', alpha=0.8, label='Vadose Zone')

        ax1.set_title(f"{condition_title}\n{equation}", fontsize=14)
        ax1.legend(loc='upper left')
        ax1.grid(True, linestyle=':', alpha=0.6)

        # --- Plot 2: Flux vs. Head Relationship ---
        c_riv = 2.0 # Assume a conductance value for plotting
        
        # Calculate flux for a range of aquifer heads
        h_aq_range = np.linspace(7, 16, 100)
        q_riv = np.zeros_like(h_aq_range)
        
        # Apply conditional logic for flux calculation
        connected_mask = h_aq_range > r_bot
        q_riv[connected_mask] = c_riv * (h_riv - h_aq_range[connected_mask])
        q_riv[~connected_mask] = c_riv * (h_riv - r_bot)

        ax2.plot(q_riv, h_aq_range, color='black', lw=2)
        
        # Plot the current point on the curve
        current_q = c_riv * (h_riv - h_aq) if h_aq > r_bot else c_riv * (h_riv - r_bot)
        ax2.plot(current_q, h_aq, 'ro', markersize=10, label='Current State')

        ax2.set_xlabel("Flux into GW (Q_riv)")
        ax2.set_title("Flux Relationship")
        ax2.grid(True, linestyle=':', alpha=0.6)
        ax2.axhline(r_bot, color='saddlebrown', linestyle='--', lw=2)
        ax2.axhline(h_riv, color='darkblue', linestyle='--', lw=2, alpha=0.5)
        ax2.axvline(0, color='grey', linestyle='-', lw=1)
        
        # Add annotations for key points on the flux plot
        ax2.text(ax2.get_xlim()[0]*0.9, r_bot + 0.1, 'R_bot', color='saddlebrown', va='bottom')
        ax2.text(ax2.get_xlim()[0]*0.9, h_riv + 0.1, 'H_riv', color='darkblue', va='bottom')
        
        plt.show()

    # Create interactive sliders
    interactive_plot = interactive(create_plot,
                                   h_aq=FloatSlider(min=7.0, max=16.0, step=0.2, value=11, description='Aquifer Head (H_aq)'),
                                   h_riv=FloatSlider(min=10.0, max=15.0, step=0.2, value=12, description='River Stage (H_riv)'))
    
    return interactive_plot


def plot_cross_section(ax, title, gw_mean, gw_high, river_mean, river_high, typical_depth):
    """Helper function to plot a single river cross-section."""
    # Define a generic topography for the cross-section
    x = np.linspace(0, 100, 200)
    river_banks = [40, 60]
    
    # Calculate riverbed elevation based on mean water level and depth
    river_bed_elevation = river_mean - typical_depth
    bank_elevation = max(river_high, gw_high) + 2 # Ensure banks are above high water
    
    # Create a simple rectangular channel shape for clarity
    topo = np.full_like(x, bank_elevation)
    river_mask = (x >= river_banks[0]) & (x <= river_banks[1])
    topo[river_mask] = river_bed_elevation
    
    # Plot aquifer material
    ax.fill_between(x, 0, topo, color='sandybrown', alpha=0.5, label='Aquifer Material')
    
    # --- Plot Groundwater Levels ---
    # Fill area for mean groundwater level
    ax.fill_between(x, 0, gw_mean, color='lightblue', alpha=0.6)
    # Fill area for high groundwater level (difference)
    ax.fill_between(x, gw_mean, gw_high, color='cornflowerblue', alpha=0.7)
    
    # Plot lines for groundwater levels
    ax.axhline(gw_mean, color='blue', linestyle='-', lw=1.5, label=f'GW Mean: {gw_mean} m')
    ax.axhline(gw_high, color='blue', linestyle='--', lw=1.5, label=f'GW High: {gw_high} m')

    # --- Plot River Water Levels ---
    river_x = np.linspace(river_banks[0], river_banks[1], 50)
    # Fill area for mean river level
    ax.fill_between(river_x, river_bed_elevation, river_mean, color='blue', alpha=0.8)
    # Fill area for high river level (difference)
    ax.fill_between(river_x, river_mean, river_high, color='darkblue', alpha=0.8)

    # Plot lines for river levels
    ax.plot(river_x, np.full_like(river_x, river_mean), color='cyan', linestyle='-', lw=2, label=f'River Mean: {river_mean} m')
    ax.plot(river_x, np.full_like(river_x, river_high), color='cyan', linestyle='--', lw=2, label=f'River High: {river_high} m')

    # --- Formatting ---
    ax.set_title(title, fontsize=14, weight='bold')
    ax.set_xlabel("Horizontal Distance (m)")
    ax.set_ylabel("Elevation (m a.s.l.)")
    ax.grid(True, linestyle=':', alpha=0.7)
    ax.legend(loc='upper right')
    
    # Set y-limits to be consistent and appropriate
    all_levels = [gw_mean, gw_high, river_mean, river_high, river_bed_elevation]
    ax.set_ylim(min(all_levels) - 2, max(all_levels) + 3)
    ax.set_xlim(x.min(), x.max())







