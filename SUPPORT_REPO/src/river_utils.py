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

# Try to import matplotlib, handle gracefully if not available
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError as e:
    print(f"Warning: matplotlib not available: {e}")
    MATPLOTLIB_AVAILABLE = False
    plt = None


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
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("matplotlib is required for plotting functions but is not available")
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
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("matplotlib is required for plotting functions but is not available")
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
