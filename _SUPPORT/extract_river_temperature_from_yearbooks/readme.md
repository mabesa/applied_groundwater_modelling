# River and Air Temperature Data Extractor

Downloads and extracts temperature data for the transport model:

- **River temperature** (Sihl & Limmat) from AWEL yearbook PDFs (1992–2024)
- **Air temperature** (Zürich/Fluntern) from MeteoSwiss open data (1990–2024)

## Requirements

```bash
uv run --with pdfminer.six --with requests python river_temperature_extractor.py
```

Or install into the project environment:

```bash
uv add pdfminer.six requests
```

## Usage

Default (1992–2024):

```bash
uv run --with pdfminer.six --with requests python river_temperature_extractor.py
```

Custom year range:

```bash
uv run --with pdfminer.six --with requests python river_temperature_extractor.py 2000 2020
```

## Data sources

| Dataset | Station | Source | Format |
|---------|---------|--------|--------|
| River temp (Sihl) | 0577 | AWEL Yearbooks | PDF → extracted |
| River temp (Limmat) | 0578 | AWEL Yearbooks | PDF → extracted |
| Air temp (Fluntern) | SMA | MeteoSwiss SMN | CSV download |

## Output

All files are saved to `~/applied_groundwater_modelling_data/limmat/`:

| File | Description |
|------|-------------|
| `river_temperature_sihl.csv` | Daily Sihl temperature (date, temperature, station_id, station_name) |
| `river_temperature_limmat.csv` | Daily Limmat temperature |
| `river_temperature_sihl_monthly.csv` | Monthly statistics (mean, max, min) for validation |
| `river_temperature_limmat_monthly.csv` | Monthly statistics for validation |
| `air_temperature_fluntern.csv` | Daily air temperature (date, temperature) |

## PDF extraction algorithm

AWEL yearbook PDFs contain a table with months as columns and days as rows. The pdfminer library extracts text column-by-column, so values arrive month-by-month in sequence.

Each temperature value appears duplicated in the PDF text (e.g., `4.94.9` for 4.9°C). The extraction regex `[+\-]*(\d{1,2}\.\d)\1` uses a backreference to match only these duplicated values, cleanly separating temperatures from day-of-month references.

For each month, the first N values (where N = days in month) are daily temperatures, followed by 3 summary values (mean, max, min).

## Debugging

The script creates `debug_output/` with raw PDF text and extracted values for each file, useful for diagnosing extraction issues.
