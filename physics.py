import numpy as np
from datetime import datetime, timezone

"""
PHYSICS MODULE
--------------
This module handles all the orbital mechanics calculations required to position celestial bodies
in 3D space at a specific time.

Key Concepts:
1.  **Orbital Elements**: A set of 6 numbers that uniquely define an orbit.
    - Semi-Major Axis (a): The size of the orbit.
    - Eccentricity (e): The shape of the orbit (0 = circle, 0 < e < 1 = ellipse).
    - Inclination (i): The tilt of the orbit relative to the reference plane.
    - Longitude of Ascending Node (Omega): The rotation of the orbit around the Z-axis.
    - Argument of Periapsis (omega): The orientation of the ellipse within the orbital plane.
    - Mean Anomaly at Epoch (M0): The position of the body at a specific reference time (t0).

2.  **Kepler's Equation**: Relates time to position in the orbit.
    - Mean Anomaly (M): A "fictitious" angle that grows linearly with time.
    - Eccentric Anomaly (E): The actual geometric angle from the center of the ellipse.
    - True Anomaly (nu): The angle from the focus (where the star is) to the body.
    
    The equation is: M = E - e * sin(E)
    Since we know M (from time) and want E, we must solve this transcendental equation numerically.

3.  **Coordinate Transformation**:
    - We first calculate position in the 2D "Orbital Plane" (x', y').
    - We then rotate this 2D plane in 3D space using the orbital elements (i, Omega, omega)
      to get the final Heliocentric Ecliptic coordinates (x, y, z).
"""

def get_elite_time():
    now_utc = datetime.now(timezone.utc)
    elite_year = now_utc.year + 1286
    elite_time = now_utc.replace(year=elite_year)
    return elite_time.strftime('%d-%m-%Y %H:%M:%S UTC')

def get_elite_current_time_dt():
    now_utc = datetime.now(timezone.utc)
    try:
        elite_time_dt = now_utc.replace(year=now_utc.year + 1286)
    except ValueError:
        elite_time_dt = now_utc.replace(year=now_utc.year + 1286, day=28)
    return elite_time_dt

def solve_kepler_equation(mean_anomaly_rad, eccentricity, tolerance=1e-9, max_iterations=100):
    """
    Solves Kepler's Equation: M = E - e * sin(E) for E (Eccentric Anomaly).

    We know 'M' (Mean Anomaly) because it flows linearly with time.
    We need 'E' (Eccentric Anomaly) to calculate the actual (x, y) coordinates.
    There is no simple algebraic formula to get E from M, so we use an iterative guess-and-check method
    called the Newton-Raphson method.

    Args:
        mean_anomaly_rad (float): The Mean Anomaly in radians (M).
        eccentricity (float): The orbital eccentricity (e).
        tolerance (float): How precise we want the result to be.
        max_iterations (int): Safety limit to prevent infinite loops.

    Returns:
        float: The Eccentric Anomaly (E) in radians.
    """
    # Initial Guess for E
    # For low eccentricity, M is a good guess for E.
    # For high eccentricity, Pi is a safer starting point to ensure convergence.
    if eccentricity < 0.8:
        E = mean_anomaly_rad
    else:
        E = np.pi
        
    # Newton-Raphson Iteration
    # We want to find the root of f(E) = E - e*sin(E) - M = 0
    # The derivative is f'(E) = 1 - e*cos(E)
    # The next guess is: E_new = E_old - f(E_old) / f'(E_old)
    for _ in range(max_iterations):
        f_E = E - eccentricity * np.sin(E) - mean_anomaly_rad
        fp_E = 1 - eccentricity * np.cos(E)
        
        # Safety check: if derivative is too close to zero, stop to avoid division by zero
        if abs(fp_E) < 1e-10: 
            break 
            
        delta_E = f_E / fp_E
        E -= delta_E
        
        # If the change is tiny, we found the answer!
        if abs(delta_E) < tolerance:
            return E
            
    return E

def calculate_position_at_time(
    semi_major_axis, eccentricity, inclination_deg,
    lon_asc_node_deg, arg_periapsis_deg, orbital_period_days,
    mean_anomaly_epoch_deg, epoch_t0_str, current_time_dt
):
    """
    Calculates the 3D position (x, y, z) of a body at a specific time.

    This is the heart of the Orrery. It takes the static orbital elements and a dynamic time,
    and returns where the body is in space.

    Steps:
    1. Convert all angles from degrees to radians.
    2. Calculate the time difference (delta_t) between the reference Epoch (t0) and Now.
    3. Calculate the Mean Anomaly (M) for Now. M increases linearly with time.
    4. Solve Kepler's Equation to get Eccentric Anomaly (E).
    5. Calculate True Anomaly (nu) and Radius (r) from E.
    6. Calculate position in the 2D Orbital Plane (xp, yp).
    7. Rotate (xp, yp) into 3D space (x, y, z) using the orientation elements (i, Omega, omega).
    """
    # Validate inputs
    if semi_major_axis is None or eccentricity is None or inclination_deg is None or \
       lon_asc_node_deg is None or arg_periapsis_deg is None or \
       orbital_period_days is None or mean_anomaly_epoch_deg is None or \
       epoch_t0_str is None or current_time_dt is None or orbital_period_days == 0:
        return np.array([0,0,0]) 

    # 1. Convert Degrees to Radians (Math functions expect radians)
    i_rad = np.radians(inclination_deg)      # Inclination
    omega_rad = np.radians(arg_periapsis_deg)# Argument of Periapsis
    Omega_rad = np.radians(lon_asc_node_deg) # Longitude of Ascending Node
    M0_rad = np.radians(mean_anomaly_epoch_deg) # Mean Anomaly at Epoch

    # 2. Parse Epoch Time (t0)
    try:
        if 'T' in epoch_t0_str and 'Z' in epoch_t0_str:
            t0_dt = datetime.strptime(epoch_t0_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        elif '+' in epoch_t0_str:
            t0_dt = datetime.strptime(epoch_t0_str.split('+')[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else: # Fallback for ISO format without Z or + (assuming UTC)
            t0_dt = datetime.fromisoformat(epoch_t0_str).replace(tzinfo=timezone.utc)
    except Exception:
        t0_dt = current_time_dt 

    # 3. Calculate Mean Anomaly (M) at current time
    # How much time has passed since the reference epoch.
    delta_t_seconds = (current_time_dt - t0_dt).total_seconds()
    delta_t_days = delta_t_seconds / (24 * 60 * 60)
    
    # Mean Motion (n) = radians per day
    n_rad_per_day = 2 * np.pi / orbital_period_days
    
    # Current M = Starting M + (Speed * Time)
    current_M_rad = (M0_rad + n_rad_per_day * delta_t_days) % (2 * np.pi)
    if current_M_rad < 0: current_M_rad += 2 * np.pi

    # 4. Solve Kepler's Equation to get Eccentric Anomaly (E)
    E_rad = solve_kepler_equation(current_M_rad, eccentricity)
    
    # 5. Calculate True Anomaly (nu)
    # This is the actual angle of the body from the periapsis (closest point to star)
    cos_E = np.cos(E_rad)
    sin_E = np.sin(E_rad)
    
    # sqrt(1 - e^2) term appears often in ellipse math
    sqrt_1_minus_e_sq = np.sqrt(max(0, 1 - eccentricity**2)) 
    
    nu_rad = np.arctan2(sqrt_1_minus_e_sq * sin_E, cos_E - eccentricity)
    nu_rad = nu_rad % (2 * np.pi) # Normalize to [0, 2*pi)
        
    # 6. Calculate Radius (r) and 2D Orbital Plane Coordinates (xp, yp)
    # r = distance from the star
    r_au = semi_major_axis * (1 - eccentricity * cos_E) 
    
    # Position in the flat plane of the orbit (before tilting)
    xp = r_au * np.cos(nu_rad)
    yp = r_au * np.sin(nu_rad)
    
    # 7. Rotate to 3D Heliocentric Ecliptic Coordinates
    # We apply 3 rotations in sequence:
    # 1. Rotate by argument of periapsis (omega) around Z
    # 2. Rotate by inclination (i) around X
    # 3. Rotate by longitude of ascending node (Omega) around Z
    # The formulas below are the combined rotation matrix applied to (xp, yp, 0)
    
    x = xp * (np.cos(omega_rad) * np.cos(Omega_rad) - np.sin(omega_rad) * np.sin(Omega_rad) * np.cos(i_rad)) \
      - yp * (np.sin(omega_rad) * np.cos(Omega_rad) + np.cos(omega_rad) * np.sin(Omega_rad) * np.cos(i_rad))
      
    y = xp * (np.cos(omega_rad) * np.sin(Omega_rad) + np.sin(omega_rad) * np.cos(Omega_rad) * np.cos(i_rad)) \
      + yp * (-np.sin(omega_rad) * np.sin(Omega_rad) + np.cos(omega_rad) * np.cos(Omega_rad) * np.cos(i_rad))
      
    z = xp * (np.sin(omega_rad) * np.sin(i_rad)) \
      + yp * (np.cos(omega_rad) * np.sin(i_rad))
      
    return np.array([x, y, z])

def calculate_orbit_points(
    semi_major_axis, eccentricity, inclination_deg,
    lon_asc_node_deg, arg_periapsis_deg, num_points=120 
):
    """
    Generates a list of 3D points representing the entire orbital path.
    Used for drawing the orbit lines (ellipses) on screen.
    
    Instead of calculating for a specific time, this function iterates through 
    the full 360 degrees (0 to 2*pi) of the True Anomaly to trace the shape.
    """
    if semi_major_axis is None or eccentricity is None or inclination_deg is None or \
       lon_asc_node_deg is None or arg_periapsis_deg is None:
        return np.empty((0,3)) 

    # Convert to radians
    i = np.radians(inclination_deg)
    omega = np.radians(arg_periapsis_deg)
    Omega = np.radians(lon_asc_node_deg)
    
    # Create a list of angles from 0 to 2pi
    nu_anomalies = np.linspace(0, 2 * np.pi, num_points)
    
    # Handle parabolic/hyperbolic cases (not supported, return empty)
    if abs(1 - eccentricity**2) < 1e-9 and eccentricity >=1:
        if eccentricity >= 1: return np.empty((0,3))

    # Calculate distance r for each angle nu using the polar equation of an ellipse:
    # r = a(1-e^2) / (1 + e*cos(nu))
    r_distances = semi_major_axis * (1 - eccentricity**2) / (1 + eccentricity * np.cos(nu_anomalies))
    
    # Coordinates in the 2D orbital plane
    xp_coords = r_distances * np.cos(nu_anomalies)
    yp_coords = r_distances * np.sin(nu_anomalies)
    
    # Transformation to 3D heliocentric ecliptic coordinates (same rotation logic as above)
    x_coords = xp_coords * (np.cos(omega) * np.cos(Omega) - np.sin(omega) * np.sin(Omega) * np.cos(i)) \
             - yp_coords * (np.sin(omega) * np.cos(Omega) + np.cos(omega) * np.sin(Omega) * np.cos(i))
    y_coords = xp_coords * (np.cos(omega) * np.sin(Omega) + np.sin(omega) * np.cos(Omega) * np.cos(i)) \
             + yp_coords * (-np.sin(omega) * np.sin(Omega) + np.cos(omega) * np.cos(Omega) * np.cos(i))
    z_coords = xp_coords * (np.sin(omega) * np.sin(i)) \
             + yp_coords * (np.cos(omega) * np.sin(i))
             
    return np.array([x_coords, y_coords, z_coords]).T
