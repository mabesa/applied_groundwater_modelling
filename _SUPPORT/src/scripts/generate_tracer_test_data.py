"""
Generate synthetic tracer test data for the transport calibration notebook.

Uses the 1D ADE pulse solution with added measurement noise to produce
realistic breakthrough curves (BTCs) from multiple observation wells at
different distances from the injection point.

Parameters are consistent with a Limmat Valley gravel aquifer:
    - v_true = 12.2 m/d   (seepage velocity)
    - n_e_true = 0.18      (effective porosity)
    - alpha_L_true = 5.0 m  (longitudinal dispersivity)
    - q_darcy = 2.196 m/d  (Darcy flux = n_e * v)
    - Observation wells at x = 50, 150, 300 m
    - Injection: M = 500 g fluorescein, A = 200 m²
    - Well-specific sampling durations (0 to ~3x peak arrival)
    - ~120 time points per well

Outputs:
    - tracer_test_data.csv      (long format: time_d, well_id, distance_m, concentration_mg_L)
    - tracer_test_metadata.json (M, A, q_darcy, distances + hidden answer key)

Usage:
    python generate_tracer_test_data.py [--output_dir PATH]
"""

import argparse
import json
import os

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1D ADE pulse solution
# ---------------------------------------------------------------------------

def ade_pulse_1d(t, x, v, D_L, M, A, n_e):
    """
    Flux-averaged 1D ADE solution for an instantaneous pulse injection.

    This is the concentration measured at a well screen (flux-averaged),
    which follows the Inverse Gaussian distribution:

    C_f(x,t) = (M/A) * x / (n_e * sqrt(4*pi*D_L*t^3)) *
               exp(-(x - v*t)^2 / (4*D_L*t))

    The flux-averaged form (with t^{-3/2}) gives exact moments:
        t_bar = x/v,  sigma^2 = 2*D_L*x/v^3

    Compare to the resident-concentration form (with t^{-1/2}), which
    has biased first moments when integrated over finite windows.
    """
    t = np.asarray(t, dtype=float)
    c = np.zeros_like(t)
    pos = t > 0
    tp = t[pos]
    c[pos] = ((M / A) * x / (n_e * np.sqrt(4.0 * np.pi * D_L * tp**3))
              * np.exp(-(x - v * tp)**2 / (4.0 * D_L * tp)))
    return c


# ---------------------------------------------------------------------------
# True aquifer parameters  (Limmat Valley gravel aquifer)
# ---------------------------------------------------------------------------

V_TRUE = 12.2           # seepage velocity [m/d]
N_E_TRUE = 0.18         # effective porosity [-]
ALPHA_L_TRUE = 5.0      # longitudinal dispersivity [m]
D_L_TRUE = ALPHA_L_TRUE * V_TRUE   # dispersion coefficient [m²/d]  => 61
Q_DARCY = N_E_TRUE * V_TRUE        # Darcy flux [m/d]  => 2.196

# Injection parameters
M_INJECT = 500.0        # injected mass [g] (fluorescein)
A_CROSS = 200.0         # cross-sectional area [m²]

# Observation wells
WELL_DISTANCES = {
    "MW-1": 50.0,
    "MW-2": 150.0,
    "MW-3": 300.0,
}

# Well-specific sampling duration: 0.1 d to ~3x peak arrival time
# Peak arrival ≈ x / v (slightly before due to dispersion)
WELL_DURATION_FACTOR = 2.5   # sample until 2.5 × peak arrival time

# Noise: 2% of peak concentration per well (modern fluorometer accuracy)
NOISE_REL = 0.02

# Time parameters
N_TIMES = 120           # time points per well

RANDOM_SEED = 123


def generate_tracer_test_data(output_dir="."):
    """Generate tracer test CSV and metadata JSON."""

    rng = np.random.default_rng(RANDOM_SEED)

    records = []
    for well_id, x in WELL_DISTANCES.items():
        # Well-specific time range: realistic sampling window
        t_peak = x / V_TRUE
        t_end = min(WELL_DURATION_FACTOR * t_peak, 80.0)
        # Dense sampling: use 500 points, then select the detectable window
        times_dense = np.linspace(0.1, t_end, 500)

        c_dense = ade_pulse_1d(
            times_dense, x, V_TRUE, D_L_TRUE, M_INJECT, A_CROSS, N_E_TRUE
        )

        # Determine detectable window: where C > 1% of peak
        peak_c = c_dense.max()
        detection_limit = 0.01 * peak_c
        detectable = c_dense > detection_limit
        if detectable.any():
            idx_first = np.argmax(detectable)
            idx_last = len(detectable) - 1 - np.argmax(detectable[::-1])
            t_start = max(times_dense[idx_first] - 0.5, 0.1)
            t_stop = times_dense[idx_last] + 0.5
        else:
            t_start, t_stop = 0.1, t_end

        times_d = np.linspace(t_start, t_stop, N_TIMES)

        c_analytical = ade_pulse_1d(
            times_d, x, V_TRUE, D_L_TRUE, M_INJECT, A_CROSS, N_E_TRUE
        )

        # Noise proportional to peak concentration
        noise_std = NOISE_REL * peak_c
        noise = rng.normal(0, noise_std, size=len(times_d))
        c_measured = c_analytical + noise

        # Clamp to non-negative (fluorometer cannot read negative)
        c_measured = np.maximum(c_measured, 0.0)

        for td, cm in zip(times_d, c_measured):
            records.append({
                "time_d": round(td, 4),
                "well_id": well_id,
                "distance_m": x,
                "concentration_mg_L": round(cm, 6),
            })

    df = pd.DataFrame(records)

    # --- Write CSV ---
    csv_path = os.path.join(output_dir, "tracer_test_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"Wrote {len(df)} records to {csv_path}")

    # --- Write metadata JSON ---
    metadata = {
        "description": "Conservative dye tracer test in the central Limmat Valley aquifer",
        "tracer": "fluorescein",
        "injected_mass_g": M_INJECT,
        "cross_sectional_area_m2": A_CROSS,
        "darcy_flux_m_per_day": round(Q_DARCY, 3),
        "observation_wells": {
            wid: {"distance_m": d} for wid, d in WELL_DISTANCES.items()
        },
        "test_duration_d": "well-specific (see data)",
        "_answer_key": {
            "v_true_m_per_day": V_TRUE,
            "n_e_true": N_E_TRUE,
            "alpha_L_true_m": ALPHA_L_TRUE,
            "D_L_true_m2_per_day": D_L_TRUE,
        },
    }
    json_path = os.path.join(output_dir, "tracer_test_metadata.json")
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Wrote metadata to {json_path}")

    return csv_path, json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tracer test data")
    parser.add_argument(
        "--output_dir", default=".", help="Output directory for CSV and JSON"
    )
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    generate_tracer_test_data(args.output_dir)
