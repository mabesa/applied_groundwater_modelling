#!/usr/bin/env python3
"""
Multi-Year Groundwater Data Downloader and Extractor

This script downloads groundwater PDF files for multiple wells across a range of years,
then extracts the data and saves it to CSV files.
"""

import os
import sys
import re
import glob
import pandas as pd
import logging
import requests
import calendar
from datetime import datetime
from collections import defaultdict
from urllib.parse import quote
import time
import traceback
import concurrent.futures

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("groundwater_download_extraction.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Create necessary directories
OUTPUT_DIR = "extracted_data"
PDF_DIR = "downloaded_pdfs"
DEBUG_DIR = "debug_output"

for directory in [OUTPUT_DIR, PDF_DIR, DEBUG_DIR]:
    os.makedirs(directory, exist_ok=True)

def download_pdf(well_id, year, base_url="https://hydroproweb.zh.ch/Karten/JB%20GW%20Pegel/Dokumente/"):
    """
    Download a PDF file for a specific well ID and year.
    Try different format variants for well IDs with special characters.
    """
    variants = [well_id]
    
    # Create variants by replacing hyphens with underscores and vice versa
    if '-' in well_id:
        variants.append(well_id.replace('-', '_'))
    if '_' in well_id:
        variants.append(well_id.replace('_', '-'))

    # If the well_id contains a letter, try with '-' and '_' replaced by '' as well 
    if any(c.isalpha() for c in well_id):
        variants.append(re.sub(r'[-_]', '', well_id))
    
    # If well_id contains a letter but no special characters, try with '-' and 
    # '_' added between the letter and the number parts of the well_id.
    if any(c.isalpha() for c in well_id) and '-' not in well_id and '_' not in well_id:
        well_id_parts = re.match(r'([a-zA-Z]+)(\d+)', well_id)
        if well_id_parts:
            variants.append(f"{well_id_parts.group(1)}_{well_id_parts.group(2)}")
            variants.append(f"{well_id_parts.group(1)}-{well_id_parts.group(2)}")

    # Try each variant
    for variant in variants:
        # URL encode the variant to handle special characters
        encoded_id = quote(f"G_{variant}")
        url = f"{base_url}{encoded_id}_{year}.pdf"
        
        logging.info(f"Trying to download: {url}")
        
        try:
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200 and response.headers.get('Content-Type') == 'application/pdf':
                # Save the PDF
                pdf_path = os.path.join(PDF_DIR, f"G_{variant}_{year}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                logging.info(f"Successfully downloaded: {pdf_path}")
                return pdf_path
            else:
                logging.warning(f"Failed to download variant {variant}: Status {response.status_code}")
        except Exception as e:
            logging.error(f"Error downloading {url}: {str(e)}")
    
    logging.warning(f"All download attempts failed for well ID: {well_id}, year: {year}")
    return None

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file using pdfminer.six"""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
    except ImportError:
        logging.error("pdfminer.six not installed. Run: pip install pdfminer.six")
        sys.exit(1)

def extract_groundwater_data(pdf_path):
    """Extract groundwater data using vertical column organization"""
    logging.info(f"Processing {pdf_path}")
    
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    
    # Save raw text for inspection
    debug_path = os.path.join(DEBUG_DIR, f"{os.path.basename(pdf_path)}_raw.txt")
    with open(debug_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(text)
    
    # Extract site information
    site_info = {}
    lines = text.split('\n')
    
    # Extract well ID from filename
    filename = os.path.basename(pdf_path)
    id_match = re.search(r'G_([^_]+)_\d{4}', filename)
    if id_match:
        site_info['well_id'] = id_match.group(1)
    
    for i, line in enumerate(lines[:30]):
        if "Pegel" in line:
            site_match = re.search(r'Pegel\s+([^,]+)', line)
            if site_match:
                site_info['site_id'] = site_match.group(1).strip()
            
            location_match = re.search(r'Gemeinde\s+([^\n]+)', line)
            if location_match:
                site_info['location'] = location_match.group(1).strip()
        
        elif "Koordinaten:" in line:
            # Extract coordinates using regex with groups for the two coordinate parts
            coord_match = re.search(r'Koordinaten:\s*(\d[\d\s\']*)\s*\/\s*(\d[\d\s\']*)', line)
            if coord_match:
                # Remove spaces and apostrophes from each coordinate
                x_coord = re.sub(r'[\s\']', '', coord_match.group(1))
                y_coord = re.sub(r'[\s\']', '', coord_match.group(2))
            
                # Store as integers or strings depending on your needs
                site_info['x_coord'] = x_coord  # or int(x_coord) if you need integers
                site_info['y_coord'] = y_coord  # or int(y_coord) if you need integers
            
                # Log the extracted coordinates for debugging
                logging.debug(f"Extracted coordinates: x={x_coord}, y={y_coord}")
        
        elif re.match(r'^\d{4}$', line.strip()):  # Year (e.g., "2023")
            site_info['year'] = line.strip()
    
    # If year wasn't found, extract from filename
    if 'year' not in site_info:
        year_match = re.search(r'_(\d{4})\.pdf$', pdf_path)
        if year_match:
            site_info['year'] = year_match.group(1)
        else:
            # Use current year as fallback
            site_info['year'] = str(datetime.now().year)
    
    # Define months
    months = ['JAN', 'FEB', 'MAR', 'APR', 'MAI', 'JUN', 'JUL', 'AUG', 'SEP', 'OKT', 'NOV', 'DEZ']
    
    # Extract month columns with values
    month_data = defaultdict(list)
    
    # Identify month blocks by looking for month names
    month_locations = []
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if line_strip in months:
            month_locations.append((i, line_strip))
    
    logging.info(f"Found month headers at lines: {[loc[0] for loc in month_locations]}")
    
    # Filter out duplicate or likely incorrect month headers
    filtered_locations = []
    prev_line = -100  # Initialize with a value that's far from any actual line
    
    for i, (line_idx, month) in enumerate(month_locations):
        # Skip if too close to previous month header
        if line_idx - prev_line < 10:  # Assuming at least 10 lines between month headers
            continue
        
        # Skip if this is likely a mistaken match
        # Check if there are several lines with value pattern after this header
        values_after = 0
        for j in range(1, 10):  # Check next 10 lines
            if line_idx + j < len(lines):
                if re.search(r'[+\-\*]?\d{3}\.\d{2}', lines[line_idx + j].strip()):
                    values_after += 1
        
        if values_after >= 3:  # If at least 3 value lines follow, this is likely a real month header
            filtered_locations.append((line_idx, month))
            prev_line = line_idx
    
    if len(filtered_locations) != 12:
        logging.warning(f"Found {len(filtered_locations)} month headers instead of expected 12")
    
    month_locations = filtered_locations
    
    # Extract values for each month
    for i, (line_idx, month) in enumerate(month_locations):
        next_idx = line_idx + 32  # Default to 31 days + 1 for safety
        
        # If there's another month after this one, set the boundary
        if i + 1 < len(month_locations):
            next_idx = month_locations[i+1][0]
        
        # Extract the block of lines for this month
        month_block = lines[line_idx+1:next_idx]
        
        # Process each line in this month's block
        for line in month_block:
            # Ignore empty lines
            if not line.strip():
                continue
            
            # Extract value - match numbers like 399.92, ignoring +, -, * symbols
            value_match = re.search(r'[+\-\*]?(\d{3}\.\d{2})', line.strip())
            if value_match:
                value = float(value_match.group(1))  # Just the number part
                month_data[month].append(value)
    
    # Debug: Save extracted values by month
    debug_values_path = os.path.join(DEBUG_DIR, f"{os.path.basename(pdf_path)}_values.txt")
    with open(debug_values_path, "w") as f:
        for month in months:
            f.write(f"{month}: {month_data[month]}\n")
    
    # Build data table with days and months
    data = []
    year = int(site_info['year'])
    
    # Check if it's a leap year
    is_leap_year = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
    
    for month_idx, month in enumerate(months):
        values = month_data[month]
        
        # Get the correct number of days for this month
        month_num = months.index(month) + 1
        if month_num == 2:  # February
            days_in_month = 29 if is_leap_year else 28
        else:
            days_in_month = calendar.monthrange(year, month_num)[1]
        
        # Add data for this month, respecting the actual number of days
        for day, value in enumerate(values, start=1):
            if day <= days_in_month:  # Only include valid days for this month
                row = {
                    'day': day,
                    'month': month,
                    'value': value
                }
                
                # Add site information
                for key, val in site_info.items():
                    row[key] = val
                
                # Add a properly formatted date
                row['date'] = f"{year}-{month_num:02d}-{day:02d}"
                
                data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    logging.info(f"Extracted {len(df)} daily measurements")
    
    # Create a pivot table format (days as rows, months as columns)
    pivot_df = df.pivot(index='day', columns='month', values='value')
    
    # Reorder columns to standard month order
    pivot_df = pivot_df.reindex(columns=months)
    
    return df, pivot_df, site_info

def process_pdf(pdf_path):
    """Process a single PDF file and save results to CSV"""
    filename = os.path.basename(pdf_path)
    site_id = os.path.splitext(filename)[0]  # Remove .pdf extension
    
    try:
        # Extract data
        long_df, pivot_df, site_info = extract_groundwater_data(pdf_path)
        
        if not long_df.empty and not pivot_df.empty:
            # Save to CSV in long format (all data in rows)
            long_output_path = os.path.join(OUTPUT_DIR, f"{site_id}_long_format.csv")
            long_df.to_csv(long_output_path, index=False)
            
            # Save to CSV in pivot format (days as rows, months as columns)
            pivot_output_path = os.path.join(OUTPUT_DIR, f"{site_id}_pivot_format.csv")
            pivot_df.to_csv(pivot_output_path)
            
            # Also save site metadata
            site_df = pd.DataFrame([site_info])
            metadata_path = os.path.join(OUTPUT_DIR, f"{site_id}_metadata.csv")
            site_df.to_csv(metadata_path, index=False)
            
            logging.info(f"Saved data for {site_id} to {OUTPUT_DIR}")
            return True
        else:
            logging.error(f"Failed to extract data from {pdf_path}")
            return False
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {str(e)}")
        logging.error(traceback.format_exc())
        return False

def process_single_well_year(well_id, year):
    """Process a single well for a specific year"""
    logging.info(f"Processing well ID: {well_id}, year: {year}")
    
    # Download the PDF
    pdf_path = download_pdf(well_id, year)
    
    if pdf_path:
        # Process the PDF
        return process_pdf(pdf_path)
    
    return False

def process_well_range(well_id, start_year, end_year, delay=1):
    """Process a well ID for a range of years"""
    successful_years = []
    failed_years = []
    
    for year in range(start_year, end_year + 1):
        success = process_single_well_year(well_id, year)
        
        if success:
            successful_years.append(year)
        else:
            failed_years.append(year)
        
        # Add a small delay to avoid overloading the server
        time.sleep(delay)
    
    logging.info(f"Well {well_id} - Successful years: {successful_years}")
    logging.info(f"Well {well_id} - Failed years: {failed_years}")
    
    return successful_years, failed_years

def process_multiple_wells(well_ids, start_year, end_year, max_workers=1):
    """
    Process multiple wells for a range of years.
    Can use parallel processing if max_workers > 1.
    """
    all_results = {}
    
    if max_workers > 1:
        # Use parallel processing (one well at a time, but multiple wells in parallel)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_well_range, well_id, start_year, end_year): well_id
                for well_id in well_ids
            }
            
            for future in concurrent.futures.as_completed(futures):
                well_id = futures[future]
                try:
                    successful, failed = future.result()
                    all_results[well_id] = {'successful': successful, 'failed': failed}
                except Exception as e:
                    logging.error(f"Error processing well {well_id}: {str(e)}")
    else:
        # Process wells sequentially
        for well_id in well_ids:
            try:
                successful, failed = process_well_range(well_id, start_year, end_year)
                all_results[well_id] = {'successful': successful, 'failed': failed}
            except Exception as e:
                logging.error(f"Error processing well {well_id}: {str(e)}")
    
    # Summarize results
    total_successful = sum(len(result['successful']) for result in all_results.values())
    total_failed = sum(len(result['failed']) for result in all_results.values())
    
    logging.info(f"Processing complete. Total successful: {total_successful}, Total failed: {total_failed}")
    
    # Try to combine all data
    if total_successful > 0:
        combine_data()
    
    # Save processing statistics
    save_statistics(all_results, start_year, end_year)
    
    return all_results

def save_statistics(results, start_year, end_year):
    """Save processing statistics to a CSV file"""
    stats = []
    
    for well_id, data in results.items():
        successful_years = data['successful']
        failed_years = data['failed']
        
        stats.append({
            'well_id': well_id,
            'successful_years': len(successful_years),
            'failed_years': len(failed_years),
            'total_years_attempted': end_year - start_year + 1,
            'earliest_year': min(successful_years) if successful_years else None,
            'latest_year': max(successful_years) if successful_years else None,
            'success_rate': len(successful_years) / (end_year - start_year + 1) if successful_years else 0,
            'successful_years_list': ','.join(map(str, successful_years)),
            'failed_years_list': ','.join(map(str, failed_years))
        })
    
    stats_df = pd.DataFrame(stats)
    stats_df.to_csv(os.path.join(OUTPUT_DIR, "processing_statistics.csv"), index=False)
    logging.info(f"Saved processing statistics to {os.path.join(OUTPUT_DIR, 'processing_statistics.csv')}")

def combine_data():
    """Combine all extracted data into single files"""
    try:
        # Combine long format files
        all_long_files = glob.glob(os.path.join(OUTPUT_DIR, "*_long_format.csv"))
        if all_long_files:
            all_long_data = pd.concat([pd.read_csv(f) for f in all_long_files])
            all_long_data.to_csv(os.path.join(OUTPUT_DIR, "all_wells_long_format.csv"), index=False)
        
        # Combine metadata
        all_metadata_files = glob.glob(os.path.join(OUTPUT_DIR, "*_metadata.csv"))
        if all_metadata_files:
            all_metadata = pd.concat([pd.read_csv(f) for f in all_metadata_files])
            all_metadata.to_csv(os.path.join(OUTPUT_DIR, "all_wells_metadata.csv"), index=False)
        
        logging.info("Combined data from all wells")
    except Exception as e:
        logging.error(f"Error combining data: {str(e)}")

def main():
    """Main function to run the script"""
    # List of well IDs to process
    well_ids = [
        "481", "516", "53_2", "83-1", "3625", "3601", "B5-3"
    ]
    
    # Default years to process
    start_year = 1970
    end_year = datetime.now().year
    
    # Parse command-line arguments
    if len(sys.argv) > 1:
        try:
            start_year = int(sys.argv[1])
        except ValueError:
            print(f"Invalid start year: {sys.argv[1]}. Using default: {start_year}")
    
    if len(sys.argv) > 2:
        try:
            end_year = int(sys.argv[2])
        except ValueError:
            print(f"Invalid end year: {sys.argv[2]}. Using default: {end_year}")
    
    # Optional parameter for parallel processing
    max_workers = 1  # Default: process sequentially
    if len(sys.argv) > 3:
        try:
            max_workers = int(sys.argv[3])
        except ValueError:
            print(f"Invalid number of workers: {sys.argv[3]}. Using default: {max_workers}")
    
    logging.info(f"Starting processing for {len(well_ids)} wells from {start_year} to {end_year}")
    if max_workers > 1:
        logging.info(f"Using parallel processing with {max_workers} workers")
    
    # Process all wells for the specified range of years
    results = process_multiple_wells(well_ids, start_year, end_year, max_workers)
    
    # Print summary
    print("\nProcessing Summary:")
    print("===================")
    for well_id, data in results.items():
        successful = data['successful']
        if successful:
            print(f"Well {well_id}: {len(successful)} years available ({min(successful)}-{max(successful)})")
        else:
            print(f"Well {well_id}: No data available")
    
    print(f"\nAll data has been saved to: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()