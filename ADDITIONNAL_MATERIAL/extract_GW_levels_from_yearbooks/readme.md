# Multi-Year Groundwater Data Downloader and Extractor

This script downloads all available groundwater data for multiple wells from 1970 to the present year, processes the data, and saves it in CSV format.

## Requirements

Install the required packages:

```bash
pip install requests pandas pdfminer.six
```

## Usage

### Basic Usage

Run the script with default settings (processes years 1970 to present):

```bash
python multi-year-downloader.py
```

### Specify Custom Year Range

```bash
python multi-year-downloader.py 1980 2020
```

### Enable Parallel Processing

Process multiple wells simultaneously (be careful with server load):

```bash
python multi-year-downloader.py 1970 2023 3
```

The third parameter specifies the number of worker threads (default: 1).

## Output

The script creates three directories:

- `downloaded_pdfs/`: Downloaded PDF files
- `extracted_data/`: Extracted CSV files
- `debug_output/`: Debug information

For each successful year and well, the script generates:

1. `G_xxx_yyyy_long_format.csv`: Data in long format
2. `G_xxx_yyyy_pivot_format.csv`: Data in pivot format
3. `G_xxx_yyyy_metadata.csv`: Site information

The script also creates:

- `all_wells_long_format.csv`: Combined data from all wells
- `all_wells_metadata.csv`: Combined metadata
- `processing_statistics.csv`: Summary of successful and failed downloads

## Performance Tips

1. **Network Load**: The script adds a delay between downloads to avoid overloading the server.

2. **Parallel Processing**: Use with caution! While processing multiple wells in parallel can speed up the process, it increases the load on the server and might lead to connection issues.

3. **Resume Capability**: If the script is interrupted, you can restart it with a later start year to pick up where it left off.

## Statistics

The script generates a summary of which years were successfully downloaded for each well. This information is saved in `processing_statistics.csv` and also printed to the console at the end of processing.

## Monitoring Progress

The script logs its progress to:

- Console output
- `groundwater_download_extraction.log` file

You can monitor these to track the downloading and processing status.