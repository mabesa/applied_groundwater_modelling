import os
import pandas as pd
import glob

import matplotlib.pyplot as plt
try:  # unified caption styling
    from style_utils import apply_caption_style, FIGURE_CAPTION_STYLE
except Exception:  # fallback if style_utils not available
    apply_caption_style = None
    FIGURE_CAPTION_STYLE = {}

# region data processing
def read_climate_data(data_path, station_string="Fluntern"):
    """
    Reads climate data for a specific station from a directory of MeteoSwiss 
    text files.

    Args:
        data_path (str): Path to the directory containing the climate data files.
        station_string (str, optional): String to search for in the station name. 
            Defaults to "Fluntern".

    Returns:
        pandas.DataFrame: A DataFrame containing the monthly climate data for 
            the specified station.
    
    Usage: 
    df = read_climate_data(data_path, station_string="Fluntern")    
    
    Details: 
    Climate data is downloaded from the Open Data Swiss repository:
    Author: Federal Office of Meterology and Climatology MeteoSwiss 
    Title: Climate normals
    url: https://opendata.swiss/en/dataset/klimanormwerte, 
    identifier: cf90489e-7a02-4490-a6ca-1b3d25d28e06@bundesamt-fur-meteorologie-und-klimatologie-meteoschweiz
    Accessed: 2025-05-01
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

def plot_climate_data(df, station_string="Fluntern", custom_title=None):
    """
    Plots cliamte data read with read_climate_data function.
    
    Args: 
        df (pandas.DataFrame): DataFrame containing the climate data.
        station_string (str, optional): String to search for in the station name. 
            Defaults to "Fluntern".
        custom_title (str, optional): Custom title for the plot which is 
            concatenated with the annual precipitation and mean temperature.
            Defaults to None, in which case a default title is used.

    Returns:
        tuple: A tuple containing the matplotlib.pyplot object and the figure object.
    
    Usage:
    plt, fig = plot_climate_data(df, station_string="Fluntern")
    
    Details:
    This function plots the climate data for a specific station, showing monthly precipitation 
    and temperature data. The y-axis for precipitation is inverted to show higher values at the top.
    The plot includes a bar chart for precipitation and a line chart for temperature, with shaded areas 
    representing the range between minimum and maximum temperatures.
    
    Note: 
    The function assumes that the DataFrame has been filtered to contain only the relevant station data.
    If no data is found for the specified station, it returns None.
    
    The function uses the following shortnames for the data:
    - 'rre150m0' for precipitation
    - 'tre200m0' for temperature
    - 'tre2dymn' for minimum temperature
    - 'tre2dymx' for maximum temperature
    
    The DataFrame should have the following structure:
    - 'station': Name of the station
    - 'shortname': Short name for the variable (e.g., 'rre150m0', 'tre200m0', etc.)
    - Monthly columns: 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    
    Example:
    df = read_climate_data(data_path, station_string="Fluntern")
    plt, fig = plot_climate_data(df, station_string="Fluntern")
    If custom_title is provided, it will be used as the title of the plot.
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
    precip_val = int(annual_precipitation.sum().round())
    mean_temp_val = round(annual_mean_temp.mean(), 1)
    if custom_title:
        base_title = custom_title.strip()
    else:
        base_title = f"Climate data for {station_string}"
    title = f"{base_title} Annual precipitation {precip_val} mm; mean temperature {mean_temp_val} °C"
    # Apply unified caption style (project-wide)
    if apply_caption_style:
        # Wrap at ~100 chars for readability
        apply_caption_style(ax1, title, pad=14, wrap=100)
    else:  # graceful fallback
        fs = FIGURE_CAPTION_STYLE.get('fontsize', 12)
        fw = FIGURE_CAPTION_STYLE.get('fontweight', 'bold')
        ax1.set_title(title, fontsize=fs, fontweight=fw)

    fig.tight_layout()  # Adjust layout to prevent labels from overlapping

    return plt, fig

# endregion