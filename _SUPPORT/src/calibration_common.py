"""
Common model and observations for all calibration demos.

This module provides a consistent "ground truth" and observations
that can be imported by all calibration demo notebooks.

The storyline:
- We have a simple 1D unconfined aquifer (Dupuit assumption)
- "True" parameters are K=5 m/d, N=0.004 m/d (4 mm/day recharge)
- We have 5 observation wells with measurement noise
- Students don't know the true parameters - they must calibrate

All demos use this same setup for consistency.
"""

import numpy as np

# =============================================================================
# DOMAIN PARAMETERS (FIXED - DO NOT CHANGE)
# =============================================================================

L = 1000      # Domain length [m]
H1 = 100      # Left boundary head (upgradient) [m]
H2 = 95       # Right boundary head (downgradient) [m]

# Legacy aliases for backwards compatibility
H0 = H1

# Spatial discretization
N_CELLS = 101
X_DOMAIN = np.linspace(0, L, N_CELLS)

# =============================================================================
# "TRUE" PARAMETERS (UNKNOWN TO STUDENTS)
# =============================================================================

K_TRUE = 5.0       # Hydraulic conductivity [m/d] - fine sand/silty sand
N_TRUE = 0.004     # Recharge rate [m/d] = 4 mm/day = 1460 mm/year

# Legacy alias
R_TRUE = N_TRUE

# Derived: the ratio N/K controls the solution shape
RATIO_TRUE = N_TRUE / K_TRUE

# =============================================================================
# OBSERVATIONS
# =============================================================================

# Observation well locations [m from left boundary]
X_OBS = np.array([150, 350, 500, 650, 850])
N_OBS = len(X_OBS)

# Measurement noise
NOISE_STD = 0.15  # Standard deviation [m]
RANDOM_SEED = 42  # For reproducibility

# =============================================================================
# THE GROUNDWATER MODEL (Dupuit equation for unconfined flow)
# =============================================================================

def gw_model_1d(K, N=N_TRUE, L=L, h1=H1, h2=H2, x=None):
    """
    Simple 1D steady-state unconfined groundwater model with recharge.

    Dupuit equation solution:
        h²(x) = h1² - (h1² - h2²) * x/L + (N/K) * x * (L - x)

    Solving for h:
        h(x) = sqrt(h1² - (h1² - h2²) * x/L + (N/K) * x * (L - x))

    Parameters
    ----------
    K : float
        Hydraulic conductivity [m/d]
    N : float, optional
        Recharge rate [m/d], default is N_TRUE
    L : float, optional
        Domain length [m], default is L
    h1 : float, optional
        Left boundary head [m], default is H1
    h2 : float, optional
        Right boundary head [m], default is H2
    x : array-like, optional
        Positions to evaluate [m], default is X_DOMAIN

    Returns
    -------
    x : ndarray
        Position array [m]
    h : ndarray
        Hydraulic head array [m]
    """
    if x is None:
        x = X_DOMAIN
    x = np.asarray(x)

    # Dupuit equation: h² = h1² - (h1² - h2²) * x/L + (N/K) * x * (L - x)
    h_squared = h1**2 - (h1**2 - h2**2) * (x / L) + (N / K) * x * (L - x)
    h = np.sqrt(h_squared)

    return x, h


def gw_model_2param(K, N, L=L, h1=H1, h2=H2, x=None):
    """
    Same model but with both K and N as explicit parameters.
    Used for equifinality demo.
    """
    return gw_model_1d(K, N, L, h1, h2, x)


# =============================================================================
# GENERATE OBSERVATIONS
# =============================================================================

def generate_observations(seed=RANDOM_SEED):
    """
    Generate synthetic observations from the true model with noise.

    Returns
    -------
    x_obs : ndarray
        Observation locations [m]
    h_obs : ndarray
        Observed heads [m] (with noise)
    h_true : ndarray
        True heads at observation locations [m] (no noise)
    """
    np.random.seed(seed)

    # True heads at observation locations
    _, h_all = gw_model_1d(K_TRUE, N_TRUE)
    obs_indices = [np.argmin(np.abs(X_DOMAIN - loc)) for loc in X_OBS]
    h_true = h_all[obs_indices]

    # Add measurement noise
    h_obs = h_true + np.random.normal(0, NOISE_STD, N_OBS)

    return X_OBS.copy(), h_obs, h_true


# Pre-generate the standard observations
X_OBS_STANDARD, H_OBS_STANDARD, H_TRUE_STANDARD = generate_observations()


# =============================================================================
# OBJECTIVE FUNCTION
# =============================================================================

def objective_function(K, N=N_TRUE, x_obs=None, h_obs=None):
    """
    Calculate Sum of Squared Residuals (SSR) for given parameters.

    Parameters
    ----------
    K : float
        Hydraulic conductivity [m/d]
    N : float, optional
        Recharge rate [m/d]
    x_obs : array-like, optional
        Observation locations, default is X_OBS_STANDARD
    h_obs : array-like, optional
        Observed heads, default is H_OBS_STANDARD

    Returns
    -------
    ssr : float
        Sum of squared residuals [m²]
    """
    if x_obs is None:
        x_obs = X_OBS_STANDARD
    if h_obs is None:
        h_obs = H_OBS_STANDARD

    _, h_sim = gw_model_1d(K, N, x=x_obs)
    residuals = h_obs - h_sim
    return np.sum(residuals**2)


def rmse(K, N=N_TRUE, x_obs=None, h_obs=None):
    """Calculate Root Mean Square Error."""
    if x_obs is None:
        x_obs = X_OBS_STANDARD
    if h_obs is None:
        h_obs = H_OBS_STANDARD

    _, h_sim = gw_model_1d(K, N, x=x_obs)
    residuals = h_obs - h_sim
    return np.sqrt(np.mean(residuals**2))


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_observations():
    """Print the standard observations."""
    print("Observation Wells:")
    print("-" * 40)
    print(f"{'Well':>6} {'x [m]':>8} {'h_obs [m]':>10} {'h_true [m]':>10}")
    print("-" * 40)
    for i, (x, ho, ht) in enumerate(zip(X_OBS_STANDARD, H_OBS_STANDARD, H_TRUE_STANDARD)):
        print(f"{i+1:>6} {x:>8.0f} {ho:>10.2f} {ht:>10.2f}")
    print("-" * 40)
    print(f"Noise std: {NOISE_STD} m")


def print_true_parameters():
    """Print the true (hidden) parameters."""
    print("TRUE PARAMETERS (unknown to students):")
    print(f"  K = {K_TRUE} m/d")
    print(f"  N = {N_TRUE} m/d = {N_TRUE*1000:.1f} mm/d = {N_TRUE*365*1000:.0f} mm/yr")
    print(f"  N/K ratio = {RATIO_TRUE:.6f}")


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("CALIBRATION DEMO - COMMON SETUP")
    print("=" * 50)
    print()
    print("Model: Dupuit equation for unconfined flow")
    print("  h²(x) = h1² - (h1² - h2²)*x/L + (N/K)*x*(L-x)")
    print()
    print_true_parameters()
    print()
    print_observations()
    print()

    # Test model
    x, h = gw_model_1d(K_TRUE)
    print(f"Model output range: h = {h.min():.2f} to {h.max():.2f} m")

    # Test objective function
    ssr_true = objective_function(K_TRUE, N_TRUE)
    print(f"SSR at true parameters: {ssr_true:.4f} m²")
    print(f"RMSE at true parameters: {rmse(K_TRUE, N_TRUE):.4f} m")
