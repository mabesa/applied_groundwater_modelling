"""
Generate synthetic pumping test data for the Limmat Valley calibration notebook.

Uses the Theis analytical solution with added measurement noise to produce
realistic time-drawdown data from multiple observation wells at different
distances from the pumping well.

Parameters are consistent with a Limmat Valley gravel aquifer:
    - K_true = 300 m/d, b = 10 m  =>  T_true = 3000 m²/d
    - S_true = 1.0e-3 (early-time elastic storage)
    - Q = 3000 m³/d (~35 L/s)
    - Observation wells at r = 10, 30, 60, 100 m
    - Duration: 24 hours, ~90 log-spaced time steps per well

Outputs:
    - pumping_test_data.csv    (long format: time_min, well_id, distance_m, drawdown_m)
    - pumping_test_metadata.json  (Q, distances, b + hidden answer key)

Usage:
    python generate_pumping_test_data.py [--output_dir PATH]
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
from scipy.special import exp1


# ---------------------------------------------------------------------------
# Theis well function
# ---------------------------------------------------------------------------

def theis_drawdown(r, t, Q, T, S):
    """
    Calculate drawdown using the Theis solution.

    Parameters
    ----------
    r : float or array
        Radial distance from pumping well [m].
    t : float or array
        Time since pumping started [d].
    Q : float
        Pumping rate [m³/d] (positive = extraction).
    T : float
        Transmissivity [m²/d].
    S : float
        Storativity [-].

    Returns
    -------
    s : float or array
        Drawdown [m] (positive downward).
    """
    u = r ** 2 * S / (4.0 * T * t)
    W_u = exp1(u)  # scipy's exp1 is the Theis well function W(u)
    s = Q / (4.0 * np.pi * T) * W_u
    return s


# ---------------------------------------------------------------------------
# Aquifer parameters  (Limmat Valley gravel aquifer)
# ---------------------------------------------------------------------------

K_TRUE = 300.0      # hydraulic conductivity [m/d]
B_AQUIFER = 10.0    # aquifer thickness [m]
T_TRUE = K_TRUE * B_AQUIFER   # transmissivity [m²/d]  => 3000
S_TRUE = 1.0e-3     # storativity [-]
Q_PUMP = 3000.0     # pumping rate [m³/d]  (~35 L/s)

# Observation wells
WELL_DISTANCES = {
    "OW-1": 10.0,
    "OW-2": 30.0,
    "OW-3": 60.0,
    "OW-4": 100.0,
}

# Noise standard deviation per well [m]  (pressure transducer accuracy)
NOISE_STD = {
    "OW-1": 0.03,
    "OW-2": 0.025,
    "OW-3": 0.02,
    "OW-4": 0.02,
}

# Time parameters
DURATION_MIN = 24 * 60  # 24 hours in minutes
N_TIMES = 90            # number of time steps per well

RANDOM_SEED = 42


def generate_pumping_test_data(output_dir="."):
    """Generate pumping test CSV and metadata JSON."""

    rng = np.random.default_rng(RANDOM_SEED)

    # Log-spaced times (minutes), starting from 0.5 min to 1440 min
    times_min = np.logspace(np.log10(0.5), np.log10(DURATION_MIN), N_TIMES)
    times_day = times_min / (24 * 60)  # convert to days for Theis

    records = []
    for well_id, r in WELL_DISTANCES.items():
        s_analytical = theis_drawdown(r, times_day, Q_PUMP, T_TRUE, S_TRUE)
        noise = rng.normal(0, NOISE_STD[well_id], size=len(times_day))
        s_measured = s_analytical + noise
        # Ensure no negative drawdown at very early times
        s_measured = np.maximum(s_measured, 0.0)
        for tm, sm in zip(times_min, s_measured):
            records.append({
                "time_min": round(tm, 4),
                "well_id": well_id,
                "distance_m": r,
                "drawdown_m": round(sm, 5),
            })

    df = pd.DataFrame(records)

    # --- Write CSV ---
    csv_path = os.path.join(output_dir, "pumping_test_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"Wrote {len(df)} records to {csv_path}")

    # --- Write metadata JSON ---
    metadata = {
        "description": "Pumping test in the central Limmat Valley aquifer",
        "pumping_rate_m3_per_day": Q_PUMP,
        "aquifer_thickness_m": B_AQUIFER,
        "observation_wells": {
            wid: {"distance_m": d} for wid, d in WELL_DISTANCES.items()
        },
        "test_duration_min": DURATION_MIN,
        "_answer_key": {
            "T_true_m2_per_day": T_TRUE,
            "S_true": S_TRUE,
            "K_true_m_per_day": K_TRUE,
        },
    }
    json_path = os.path.join(output_dir, "pumping_test_metadata.json")
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Wrote metadata to {json_path}")

    return csv_path, json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate pumping test data")
    parser.add_argument(
        "--output_dir", default=".", help="Output directory for CSV and JSON"
    )
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    generate_pumping_test_data(args.output_dir)
