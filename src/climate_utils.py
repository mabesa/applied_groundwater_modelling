import os
import pandas as pd
import glob
import numpy as np
import pyet 

import matplotlib.pyplot as plt

# region data processing
def read_climate_data(data_path, station_string="Zuerich-Fluntern"):
    """
    Reads climate data for a specific station from a directory of MeteoSwiss text files.

    Args:
        data_path (str): Path to the directory containing the climate data files.
        station_string (str, optional): String to search for in the station name. Defaults to "Fluntern".

    Returns:
        pandas.DataFrame: A DataFrame containing the monthly climate data for the specified station.
    
    Usage: 
    df = read_climate_data(data_path, station_string="Fluntern")    
    
    Details: 
    Climate data is downloaded from MeteoSwiss 
    url: https://opendata.swiss/en/dataset/klimanormwerte, 
    identifier: cf90489e-7a02-4490-a6ca-1b3d25d28e06@bundesamt-fur-meteorologie-und-klimatologie-meteoschweiz
    """

    # Test if the data_path exists
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"The specified data path does not exist: {data_path}")

    all_files = glob.glob(os.path.join(data_path, 'climate-reports-normtables_*.txt'))
    
    if not all_files:
        raise FileNotFoundError(f"No climate data files found in {data_path}")

    all_data = []
    for filepath in all_files:
        # Extract varname from filename
        filename = os.path.basename(filepath)
        varname = filename.split('-')[-2].split('_')[1]

        try:
            # Read the variable name from line 6
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                try:
                    with open(filepath, 'r', encoding='latin-1') as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    with open(filepath, 'r', encoding='cp1252') as f:
                        lines = f.readlines()
            try:
                varname_long = lines[6].strip()  # Line 6 (index 5)
                #print(f"Extracted varname: {varname_long}")
            except IndexError:
                print(f"Warning: Could not extract varname from {filename}. Skipping file.")
                continue

            # Read the data from line 8 onwards
            try:
                df = pd.read_csv(filepath, skiprows=7, sep=r'\t', encoding='utf-8', engine='python')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(filepath, skiprows=7, sep=r'\t', encoding='latin-1', engine='python')
                except UnicodeDecodeError:
                    df = pd.read_csv(filepath, skiprows=7, sep=r'\t', encoding='cp1252', engine='python')

            # Filter for the specified station
            station_data = df[df['Station'].str.contains(station_string, na=False)]

            if station_data.empty:
                print(f"Station {station_string} not found in {filename}")
                continue

            # Extract monthly data
            monthly_values = station_data[
                ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 
                 'Oct', 'Nov', 'Dec']
                 ].values.flatten().tolist()
            
            # Create a dictionary for the current file
            file_data = {
                'shortname': varname,
                'longname': varname_long,
                'station': station_string,
                'Jan': monthly_values[0],
                'Feb': monthly_values[1],
                'Mar': monthly_values[2],
                'Apr': monthly_values[3],
                'May': monthly_values[4],
                'Jun': monthly_values[5],
                'Jul': monthly_values[6],
                'Aug': monthly_values[7],
                'Sep': monthly_values[8],
                'Oct': monthly_values[9],
                'Nov': monthly_values[10],
                'Dec': monthly_values[11]
            }
            all_data.append(file_data)
        
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

    # Create DataFrame
    df = pd.DataFrame(all_data)
    if df.empty:
        return pd.DataFrame()  # Return an empty DataFrame if no data was loaded
    
    return df

# endregion 

# region visualization

def plot_climate_data(df, station_string="Fluntern"):
    """
    Plots cliamte data read with read_climate_data function.
    
    Args: 
        df (pandas.DataFrame): DataFrame containing the climate data.
        station_string (str, optional): String to search for in the station name. Defaults to "Fluntern".
    """

    # Filter DataFrame for the specified station
    df = df[df['station'].str.contains(station_string, na=False)]
    if df.empty:
        print(f"No data found for station {station_string}.")
        return None, None

    # Extract precipitation and temperature data
    # The correct syntax is to put the closing bracket after 'shortname'
    precipitation = df.loc[
        df['shortname'] == 'rre150m0', 
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 
        'Nov', 'Dec']].T
    temperature = df.loc[
        df['shortname'] == 'tre200m0', 
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 
        'Nov', 'Dec']].T
    temp_min = df.loc[
        df['shortname'] == 'tre2dymn', 
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 
         'Nov', 'Dec']].T
    temp_max = df.loc[
        df['shortname'] == 'tre2dymx', 
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 
         'Nov', 'Dec']].T

    # Sum precipation over the year
    annual_precipitation = precipitation.sum(axis=1)
    # Calculate the annual mean temperature
    annual_mean_temp = temperature.mean(axis=1)

    # Create the plot
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot precipitation as blue bars with inverted y-axis
    ax1.bar(precipitation.index, precipitation.iloc[:, 0], color='darkblue', 
            alpha=0.7, label='Precipitation')
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Precipitation (mm)', color='darkblue')
    ax1.tick_params(axis='y', labelcolor='darkblue')
    ax1.invert_yaxis()  # Invert the y-axis for precipitation

    # Create a second y-axis for temperature
    ax2 = ax1.twinx()

    # Add shaded area between min and max temperatures
    ax2.fill_between(temp_min.index, temp_min.iloc[:, 0], temp_max.iloc[:, 0], 
                 color='red', alpha=0.2, label='Temperature Range')

    # Plot temperature as a red line
    ax2.plot(temperature.index, temperature, color='red', alpha=0.7, 
             label='Temperature')
    ax2.set_ylabel('Temperature (°C)', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.set_ylim(0, 30)  # Set y-axis limits for temperature

    # Add legend for both axes
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')

    # Set title and legend
    plt.title(f'Figure 4: Climate Data for Fluntern\nPrecipitation: {annual_precipitation.sum().round().astype(int)} mm/a\nMean temperature: {annual_mean_temp.mean().round(1)} °C')
    fig.tight_layout()  # Adjust layout to prevent labels from overlapping

    return plt, fig

# endregion

# region evapotranspiration
def calculate_pet_fao56(
    climate_df,
    lat,
    elevation,
    station_string="Fluntern",
    tmean_sc='tre200m0',
    tmin_sc='tre2dymn',
    tmax_sc='tre2dymx',
    wind_sc='fkl010m0',
    rh_sc='ure200m0',
    ea_sc='pva200m0',
    ea_conversion_factor=0.1,
    rs_sc='gre000m0',
    rs_conversion_factor=0.0864,
    anemo_height=2.0
    ):
    """
    Calculates monthly potential evapotranspiration (PET) using the FAO-56 method.
    // ... existing docstring ...
    """
    month_cols = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    original_month_index = pd.Index(month_cols)

    # Create a dummy DatetimeIndex for a representative year (e.g., 2001, a non-leap year)
    # pyet often expects a DatetimeIndex for its internal calculations
    datetime_index = pd.to_datetime([f'2001-{i:02d}-01' for i in range(1, 13)])

    station_df = climate_df[climate_df['station'].str.contains(station_string, na=False)]
    if station_df.empty:
        print(f"Warning: No data found for station {station_string}. Cannot calculate PET.")
        return pd.Series(dtype=float)

    def get_monthly_series(df, shortname, columns, dt_index):
        if shortname is None:
            return pd.Series([np.nan]*len(columns), index=dt_index, dtype=float)
        data_row = df[df['shortname'] == shortname]
        if data_row.empty:
            return pd.Series([np.nan]*len(columns), index=dt_index, dtype=float)
        try:
            values = data_row[columns].iloc[0].astype(float).values
            return pd.Series(values, index=dt_index, dtype=float)
        except ValueError:
            return pd.Series([np.nan]*len(columns), index=dt_index, dtype=float)

    tmean_series = get_monthly_series(station_df, tmean_sc, month_cols, datetime_index)
    tmin_series = get_monthly_series(station_df, tmin_sc, month_cols, datetime_index)
    tmax_series = get_monthly_series(station_df, tmax_sc, month_cols, datetime_index)
    wind_series = get_monthly_series(station_df, wind_sc, month_cols, datetime_index)
    
    rs_series_raw = get_monthly_series(station_df, rs_sc, month_cols, datetime_index)
    rs_input_series = None
    if not rs_series_raw.isnull().all():
        rs_input_series = rs_series_raw * rs_conversion_factor
    else:
        print(f"Info: Solar radiation data ('{rs_sc}') not found or invalid for {station_string}.")

    ea_series_raw = get_monthly_series(station_df, ea_sc, month_cols, datetime_index)
    ea_input_series = None
    if not ea_series_raw.isnull().all():
        ea_input_series = ea_series_raw * ea_conversion_factor
        print(f"Info: Using actual vapor pressure data ('{ea_sc}') for {station_string}.")
    else:
        print(f"Info: Actual vapor pressure data ('{ea_sc}') not found or invalid for {station_string}.")

    rh_series_raw = get_monthly_series(station_df, rh_sc, month_cols, datetime_index)
    rh_input_series = None
    if not rh_series_raw.isnull().all():
        rh_input_series = rh_series_raw 
        if ea_input_series is not None and not ea_input_series.isnull().all(): # Check if ea_input_series has data
             print(f"Info: Both ea and rh available; pyet will prioritize ea for {station_string}.")
        else:
            print(f"Info: Using relative humidity data ('{rh_sc}') for {station_string}.")
    elif ea_input_series is None or ea_input_series.isnull().all(): # Neither ea nor rh data found
         print(f"Info: Neither actual vapor pressure ('{ea_sc}') nor relative humidity ('{rh_sc}') data found for {station_string}. Pyet will estimate from Tmin if available.")

    if tmean_series.isnull().all():
        print(f"Warning: Mean temperature data ('{tmean_sc}') is missing or invalid for {station_string}. Cannot calculate PET.")
        return pd.Series(dtype=float)
    if np.isnan(lat) or np.isnan(elevation):
        print(f"Warning: Latitude or elevation is NaN. Cannot calculate PET.")
        return pd.Series(dtype=float)

    # Ensure optional series are None if all NaN, otherwise pass the series
    def prep_optional_series(series):
        return series if (series is not None and not series.isnull().all()) else None

    pet_daily_mm_day = pyet.pm_fao56(
        tmean=tmean_series, # This is mandatory and should have data
        wind=prep_optional_series(wind_series),
        rs=prep_optional_series(rs_input_series),
        ea=prep_optional_series(ea_input_series),
        rh=prep_optional_series(rh_input_series) if (ea_input_series is None or ea_input_series.isnull().all()) else None,
        tmax=prep_optional_series(tmax_series),
        tmin=prep_optional_series(tmin_series),
        elevation=elevation,
        lat=lat
    )

    if pet_daily_mm_day is None or (isinstance(pet_daily_mm_day, pd.Series) and pet_daily_mm_day.isnull().all()):
        print(f"Warning: pyet.pm_fao56 returned no valid data for {station_string}.")
        return pd.Series(dtype=float)

    # Ensure pet_daily_mm_day is a Series and set its index back to original month names
    if not isinstance(pet_daily_mm_day, pd.Series):
        # This case might be unlikely if inputs are series, but good for safety
        pet_daily_mm_day_series = pd.Series(pet_daily_mm_day, index=datetime_index)
    else:
        pet_daily_mm_day_series = pet_daily_mm_day
    
    pet_daily_mm_day_series.index = original_month_index # Revert to Jan, Feb, ... index

    days_in_month = pd.Series(
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
        index=original_month_index # Ensure this index matches
    )
    pet_monthly_mm = pet_daily_mm_day_series * days_in_month
    pet_monthly_mm.name = "PET_mm_month"

    return pet_monthly_mm

# endregion

# region plot montly PET
def plot_monthly_pet(pet_series, station_name=""):
    """
    Plots monthly potential evapotranspiration (PET) as a bar chart.

    Args:
        pet_series (pd.Series): A pandas Series containing monthly PET data,
                                 with month names (e.g., 'Jan', 'Feb') as index
                                 and PET values (mm/month) as data.
        station_name (str, optional): Name of the station for the plot title. 
                                      Defaults to an empty string.

    Returns:
        tuple: (matplotlib.pyplot, matplotlib.figure.Figure)
               Returns (None, None) if pet_series is empty or not a Series.
    """
    if not isinstance(pet_series, pd.Series) or pet_series.empty:
        print("Warning: Input PET data is empty or not a pandas Series. Cannot plot.")
        return None, None

    fig, ax = plt.subplots(figsize=(10, 6))

    # Calculate annual PET
    annual_pet = pet_series.sum()

    # Create the bar chart
    bar_label = f'Monthly PET\nAnnual Total: {annual_pet:.2f} mm'
    ax.bar(pet_series.index, pet_series.values, color='skyblue', alpha=0.8, label=bar_label)

    # Set labels and title
    ax.set_xlabel('Month')
    ax.set_ylabel('Potential Evapotranspiration (mm/month)')
    
    title = 'Monthly Potential Evapotranspiration'
    if station_name:
        title += f' for {station_name}'
    ax.set_title(title)
    
    # Add a legend
    ax.legend()

    # Improve layout
    fig.tight_layout()

    return plt, fig
# endregion