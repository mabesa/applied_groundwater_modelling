#!/usr/bin/env python3
"""
River Temperature and Air Temperature Data Extractor

Downloads AWEL river temperature yearbook PDFs for the Sihl and Limmat,
extracts daily temperature values, and downloads MeteoSwiss air temperature
data for Zürich/Fluntern.

Output files are saved to ~/applied_groundwater_modelling_data/limmat/.
"""

import os
import sys
import re
import calendar
import logging
import time
import traceback
from pathlib import Path

import pandas as pd
import requests
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTTextBox, LTTextLine, LAParams
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATIONS = {
    "0577": "Sihl",
    "0578": "Limmat",
}

START_YEAR = 1992
END_YEAR = 2024

BASE_URL = "https://hydroproweb.zh.ch/Karten/B3%20JB%20Wassertemp/Dokumente/"

OUTPUT_DIR = Path.home() / "applied_groundwater_modelling_data" / "limmat"

# Working directories (relative to script location)
SCRIPT_DIR = Path(__file__).resolve().parent
PDF_DIR = SCRIPT_DIR / "downloaded_pdfs"
DEBUG_DIR = SCRIPT_DIR / "debug_output"

METEOSWISS_URL = (
    "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/sma/"
    "ogd-smn_sma_d_historical.csv"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(SCRIPT_DIR / "river_temperature_extraction.log"),
        logging.StreamHandler(sys.stdout),
    ],
)


# ---------------------------------------------------------------------------
# PDF download
# ---------------------------------------------------------------------------

def build_pdf_url(station_id: str, year: int) -> str:
    year_suffix = year % 1000
    filename = f"{station_id}t{year_suffix:03d}.PDF"
    return f"{BASE_URL}{filename}"


def download_pdf(station_id: str, year: int) -> Path | None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    url = build_pdf_url(station_id, year)
    pdf_path = PDF_DIR / f"{station_id}t{year % 1000:03d}.PDF"

    if pdf_path.exists():
        logging.info(f"Already downloaded: {pdf_path.name}")
        return pdf_path

    logging.info(f"Downloading {url}")
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 500:
            pdf_path.write_bytes(resp.content)
            logging.info(f"Saved {pdf_path.name}")
            return pdf_path
        else:
            logging.warning(f"HTTP {resp.status_code} for {url}")
            return None
    except Exception as e:
        logging.error(f"Download error for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# PDF extraction — duplicated-value format (2001–2004, 2009+)
# ---------------------------------------------------------------------------

def _extract_duplicated_format(text: str, pdf_name: str, station_id: str, year: int):
    """
    Extract from PDFs where each temperature value appears duplicated (e.g. '4.94.9').
    Works for yearbooks from 2001–2004 and 2009 onwards.
    """
    pattern = r'[+\-]*(\d{1,2}\.\d)\1'
    matches = re.findall(pattern, text)

    if len(matches) < 100:
        return None, None  # Too few matches — not the duplicated format

    logging.info(f"{pdf_name}: found {len(matches)} duplicated temperature values")

    daily_rows = []
    monthly_rows = []
    idx = 0

    for month_num in range(1, 13):
        days = calendar.monthrange(year, month_num)[1]
        needed = days + 3  # daily values + mean/max/min

        if idx + needed > len(matches):
            logging.warning(
                f"{pdf_name}: month {month_num} needs {needed} values "
                f"but only {len(matches) - idx} remain (idx={idx})"
            )
            month_vals = [float(v) for v in matches[idx:]]
            idx = len(matches)
        else:
            month_vals = [float(v) for v in matches[idx : idx + needed]]
            idx += needed

        daily_vals = month_vals[:days]
        for day_num, temp in enumerate(daily_vals, start=1):
            daily_rows.append(
                {
                    "date": f"{year}-{month_num:02d}-{day_num:02d}",
                    "temperature": temp,
                    "station_id": station_id,
                    "station_name": STATIONS.get(station_id, station_id),
                }
            )

        summary_vals = month_vals[days : days + 3]
        if len(summary_vals) == 3:
            monthly_rows.append(
                {
                    "year": year,
                    "month": month_num,
                    "mean": summary_vals[0],
                    "max": summary_vals[1],
                    "min": summary_vals[2],
                    "station_id": station_id,
                    "station_name": STATIONS.get(station_id, station_id),
                }
            )

    return daily_rows, monthly_rows


# ---------------------------------------------------------------------------
# PDF extraction — layout-based format (1992–2000 old yearbooks)
# ---------------------------------------------------------------------------

def _extract_layout_format(pdf_path: Path, pdf_name: str, station_id: str, year: int):
    """
    Extract from old-format PDFs where values are NOT duplicated.
    Uses pdfminer's layout analysis to read text positions and reconstruct
    the month×day table by x-coordinate (column) and y-coordinate (row).
    """
    elements = []
    for page_layout in extract_pages(str(pdf_path), laparams=LAParams()):
        for element in page_layout:
            if isinstance(element, LTTextBox):
                for line in element:
                    if isinstance(line, LTTextLine):
                        text = line.get_text().strip()
                        if text:
                            elements.append((round(line.x0, 1), round(line.y0, 1), text))

    # Find temperature values: lines containing just a number like "4.6" or "18.9  +"
    temp_re = re.compile(r'^[+\-]?\s*(\d{1,2}\.\d)\s*[+\-]?\s*$')
    temp_elements = []
    for x, y, text in elements:
        m = temp_re.match(text)
        if m:
            temp_elements.append((round(x), y, float(m.group(1))))

    if len(temp_elements) < 100:
        return None, None  # Not enough values

    # Group by x-coordinate (column)
    columns = defaultdict(list)
    for x, y, val in temp_elements:
        columns[x].append((y, val))

    sorted_col_xs = sorted(columns.keys())
    if len(sorted_col_xs) != 12:
        logging.warning(f"{pdf_name}: layout extraction found {len(sorted_col_xs)} columns, expected 12")
        return None, None

    logging.info(f"{pdf_name}: layout extraction found {len(temp_elements)} values in 12 columns")

    daily_rows = []
    monthly_rows = []

    for i, col_x in enumerate(sorted_col_xs):
        month_num = i + 1
        days = calendar.monthrange(year, month_num)[1]

        # Sort by y descending (top of page = day 1)
        vals = sorted(columns[col_x], key=lambda v: -v[0])
        daily_vals = [v for _, v in vals[:days]]

        for day_num, temp in enumerate(daily_vals, start=1):
            daily_rows.append(
                {
                    "date": f"{year}-{month_num:02d}-{day_num:02d}",
                    "temperature": temp,
                    "station_id": station_id,
                    "station_name": STATIONS.get(station_id, station_id),
                }
            )

        # Summary values: next 3 after daily (mean, max, min)
        if len(vals) >= days + 3:
            summary = [v for _, v in vals[days : days + 3]]
            monthly_rows.append(
                {
                    "year": year,
                    "month": month_num,
                    "mean": summary[0],
                    "max": summary[1],
                    "min": summary[2],
                    "station_id": station_id,
                    "station_name": STATIONS.get(station_id, station_id),
                }
            )

    return daily_rows, monthly_rows


# ---------------------------------------------------------------------------
# PDF extraction — dispatcher
# ---------------------------------------------------------------------------

def extract_temperatures_from_pdf(pdf_path: Path, station_id: str, year: int):
    """
    Extract daily temperatures from an AWEL river temperature yearbook PDF.

    Tries the duplicated-value regex first (2001+ format), then falls back
    to layout-based extraction for older (1992–2000) PDFs.

    Returns (daily_df, monthly_df) or (None, None) on failure.
    """
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    text = extract_text(str(pdf_path))

    # Strip backtick and apostrophe characters
    text = text.replace("`", "").replace("\u2018", "").replace("\u2019", "")
    text = text.replace("\u0060", "").replace("\u00b4", "").replace("'", "")

    # Save raw text for debugging
    debug_path = DEBUG_DIR / f"{pdf_path.stem}_raw.txt"
    debug_path.write_text(text, encoding="utf-8")

    pdf_name = pdf_path.name

    # Try duplicated-value format first (fast, works for 2001+ PDFs)
    daily_rows, monthly_rows = _extract_duplicated_format(
        text, pdf_name, station_id, year
    )

    # Fall back to layout-based extraction for old-format PDFs
    if daily_rows is None:
        logging.info(f"{pdf_name}: trying layout-based extraction (old format)")
        daily_rows, monthly_rows = _extract_layout_format(
            pdf_path, pdf_name, station_id, year
        )

    if daily_rows is None or len(daily_rows) < 300:
        logging.warning(
            f"{pdf_name}: extraction failed or too few values "
            f"({len(daily_rows) if daily_rows else 0} rows)"
        )
        return None, None

    # Save extracted values for debugging
    debug_vals = DEBUG_DIR / f"{pdf_path.stem}_values.txt"
    debug_vals.write_text(
        f"Total daily rows: {len(daily_rows)}\n\n"
        + "\n".join(f"{r['date']}: {r['temperature']}" for r in daily_rows),
        encoding="utf-8",
    )

    daily_df = pd.DataFrame(daily_rows)
    daily_df["date"] = pd.to_datetime(daily_df["date"])
    monthly_df = pd.DataFrame(monthly_rows) if monthly_rows else pd.DataFrame()

    logging.info(
        f"{pdf_name}: extracted {len(daily_df)} daily rows, "
        f"{len(monthly_df)} monthly summaries"
    )
    return daily_df, monthly_df


# ---------------------------------------------------------------------------
# Process one station across all years
# ---------------------------------------------------------------------------

def process_station(station_id: str, start_year: int, end_year: int, delay: float = 0.5):
    all_daily = []
    all_monthly = []
    successful = []
    failed = []

    for year in range(start_year, end_year + 1):
        pdf_path = download_pdf(station_id, year)
        if pdf_path is None:
            failed.append(year)
            time.sleep(delay)
            continue

        try:
            daily_df, monthly_df = extract_temperatures_from_pdf(pdf_path, station_id, year)
            if daily_df is not None and not daily_df.empty:
                all_daily.append(daily_df)
                all_monthly.append(monthly_df)
                successful.append(year)
            else:
                failed.append(year)
        except Exception as e:
            logging.error(f"Error extracting {pdf_path.name}: {e}")
            logging.error(traceback.format_exc())
            failed.append(year)

        time.sleep(delay)

    logging.info(
        f"Station {station_id}: {len(successful)} years OK, {len(failed)} failed"
    )
    if failed:
        logging.info(f"  Failed years: {failed}")

    if all_daily:
        combined_daily = pd.concat(all_daily, ignore_index=True)
        combined_monthly = pd.concat(all_monthly, ignore_index=True)
        return combined_daily, combined_monthly
    return pd.DataFrame(), pd.DataFrame()


# ---------------------------------------------------------------------------
# Air temperature from MeteoSwiss
# ---------------------------------------------------------------------------

def download_air_temperature():
    """
    Download daily mean air temperature for Zürich/Fluntern (SMA) from
    MeteoSwiss Open Government Data.

    Returns a DataFrame with columns: date, temperature
    """
    logging.info(f"Downloading MeteoSwiss air temperature from {METEOSWISS_URL}")
    try:
        resp = requests.get(METEOSWISS_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to download MeteoSwiss data: {e}")
        return pd.DataFrame()

    from io import StringIO

    df = pd.read_csv(StringIO(resp.text), sep=";")
    logging.info(f"MeteoSwiss CSV: {len(df)} rows, columns: {list(df.columns)}")

    # Timestamps are in European format DD.MM.YYYY HH:MM — must specify explicitly
    df["date"] = pd.to_datetime(df["reference_timestamp"], format="%d.%m.%Y %H:%M")
    df["date"] = df["date"].dt.normalize()

    mask = (df["date"] >= "1990-01-01") & (df["date"] <= "2024-12-31")
    df = df.loc[mask].copy()

    result = df[["date", "tre200d0"]].rename(columns={"tre200d0": "temperature"})
    result = result.sort_values("date").reset_index(drop=True)

    logging.info(f"Air temperature: {len(result)} rows from {result['date'].min()} to {result['date'].max()}")
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(daily_df: pd.DataFrame, label: str, temp_min: float, temp_max: float):
    if daily_df.empty:
        logging.warning(f"Validation skipped for {label}: empty DataFrame")
        return

    logging.info(f"\n--- Validation: {label} ---")
    logging.info(f"  Total rows: {len(daily_df)}")

    # Check date range
    logging.info(f"  Date range: {daily_df['date'].min()} to {daily_df['date'].max()}")

    # Rows per year
    if "date" in daily_df.columns:
        per_year = daily_df.groupby(daily_df["date"].dt.year).size()
        short_years = per_year[per_year < 360]
        if not short_years.empty:
            logging.warning(f"  Years with < 360 rows:\n{short_years}")
        else:
            logging.info(f"  All years have >= 360 rows (min={per_year.min()}, max={per_year.max()})")

    # Temperature range
    temps = daily_df["temperature"]
    logging.info(f"  Temperature range: {temps.min():.1f} to {temps.max():.1f}")
    out_of_range = temps[(temps < temp_min) | (temps > temp_max)]
    if not out_of_range.empty:
        logging.warning(f"  {len(out_of_range)} values outside [{temp_min}, {temp_max}]")
    else:
        logging.info(f"  All values within [{temp_min}, {temp_max}]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    start_year = START_YEAR
    end_year = END_YEAR

    # Optional CLI overrides
    if len(sys.argv) > 1:
        start_year = int(sys.argv[1])
    if len(sys.argv) > 2:
        end_year = int(sys.argv[2])

    logging.info(f"Processing river temperatures for {start_year}–{end_year}")

    # ---- River temperatures ----
    for station_id, station_name in STATIONS.items():
        logging.info(f"\n{'='*60}")
        logging.info(f"Station {station_id} ({station_name})")
        logging.info(f"{'='*60}")

        daily_df, monthly_df = process_station(station_id, start_year, end_year)

        if not daily_df.empty:
            daily_path = OUTPUT_DIR / f"river_temperature_{station_name.lower()}.csv"
            daily_df.to_csv(daily_path, index=False)
            logging.info(f"Saved daily data: {daily_path}")

            monthly_path = OUTPUT_DIR / f"river_temperature_{station_name.lower()}_monthly.csv"
            monthly_df.to_csv(monthly_path, index=False)
            logging.info(f"Saved monthly data: {monthly_path}")

            validate(daily_df, f"{station_name} river temperature", temp_min=-1, temp_max=30)
        else:
            logging.error(f"No data extracted for station {station_id}")

    # ---- Air temperature ----
    logging.info(f"\n{'='*60}")
    logging.info("MeteoSwiss air temperature (Zürich/Fluntern)")
    logging.info(f"{'='*60}")

    air_df = download_air_temperature()
    if not air_df.empty:
        air_path = OUTPUT_DIR / "air_temperature_fluntern.csv"
        air_df.to_csv(air_path, index=False)
        logging.info(f"Saved air temperature: {air_path}")
        validate(air_df, "Fluntern air temperature", temp_min=-25, temp_max=40)
    else:
        logging.error("Failed to download air temperature data")

    # ---- Summary ----
    print("\n" + "=" * 60)
    print("Processing complete")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.glob("*temperature*.csv")):
        rows = sum(1 for _ in open(f)) - 1
        print(f"  {f.name}: {rows:,} rows")


if __name__ == "__main__":
    main()
