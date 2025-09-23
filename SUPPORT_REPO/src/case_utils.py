import os, pprint
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import yaml
import zipfile
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