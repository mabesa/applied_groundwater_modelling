import os
import requests
from tqdm.notebook import tqdm

# Find path to project root directory from both the src and the home folder
try: 
    # Try to add from src folder
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
except NameError:
    # If __file__ is not defined, assume running from home folder
    project_root = os.path.expanduser("~")
# Add the project root to the system path
if project_root not in os.sys.path:
    os.sys.path.append(project_root)

from config import CASE_STUDY, DATA_SOURCE, DATA_URLS

def get_data_urls():
    """Get data URLs based on current case study and data source settings."""
    if CASE_STUDY not in DATA_URLS:
        raise ValueError(f"Unknown case study: {CASE_STUDY}")
    
    if DATA_SOURCE not in DATA_URLS[CASE_STUDY]:
        raise ValueError(f"Data source '{DATA_SOURCE}' not available for case study '{CASE_STUDY}'")
    
    return DATA_URLS[CASE_STUDY][DATA_SOURCE]

def get_default_data_folder():
    """Get the default data folder for the current case study."""
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, "applied_groundwater_modelling_data", CASE_STUDY)

def download_named_file(name, dest_folder=None, data_type=None):
    """
    Download a named file from the configured data source.
    
    Args:
        name: Name of the file/dataset to download
        dest_folder: Destination folder (if None, uses default structure)
        data_type: Type of data (climate, groundwater, rivers, geology) for organization
    
    Returns:
        Path to the downloaded file
    """
    # Get the appropriate URLs for current case study and data source
    url_dict = get_data_urls()
    
    if name not in url_dict:
        raise ValueError(f"No URL configured for '{name}' in {DATA_SOURCE} data for case study '{CASE_STUDY}'.")

    file_info = url_dict[name]
    url = file_info['url']
    filename = file_info['filename']
    
    # Determine destination folder
    if dest_folder is None:
        dest_folder = get_default_data_folder()
        if data_type:
            dest_folder = os.path.join(dest_folder, data_type)
    
    dest_path = os.path.join(dest_folder, filename)
    os.makedirs(dest_folder, exist_ok=True)

    if os.path.exists(dest_path):
        print(f"{filename} already exists in {dest_folder}.")
        return dest_path

    print(f"Downloading {filename} from {DATA_SOURCE} for case study '{CASE_STUDY}'...")
    print(f"URL: {url[:50]}..." if len(url) > 50 else f"URL: {url}")
    
    try:
        r = requests.get(url, stream=True)
        if r.status_code != 200:
            raise Exception(f"Download failed: {r.status_code}")

        total = int(r.headers.get('content-length', 0))
        with open(dest_path, 'wb') as f, tqdm(
            desc=filename,
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in r.iter_content(chunk_size=1024):
                size = f.write(chunk)
                bar.update(size)

        print(f"Download complete: {dest_path}")
        return dest_path
        
    except Exception as e:
        print(f"Error downloading {filename}: {e}")
        # Clean up partial file if it exists
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise

def get_data_path(data_type=None):
    """
    Get the path to data folder for the current case study.
    
    Args:
        data_type: Optional data type subdirectory (climate, groundwater, etc.)
    
    Returns:
        Path to the data folder
    """
    base_path = get_default_data_folder()
    if data_type:
        return os.path.join(base_path, data_type)
    return base_path

def list_available_datasets():
    """List all available datasets for the current case study and data source."""
    try:
        url_dict = get_data_urls()
        print(f"Available datasets for '{CASE_STUDY}' from '{DATA_SOURCE}':")
        for name in url_dict.keys():
            print(f"  - {name}")
    except Exception as e:
        print(f"Error listing datasets: {e}")

