import csv
import math
import numpy as np
import os

class Starfield:
    def __init__(self, data_file="starfield_data.csv"):
        self.stars = []
        self.load_data(data_file)

    def load_data(self, filename):
        """Loads star data from a CSV file."""
        if not os.path.exists(filename):
            print(f"Error: Starfield data file '{filename}' not found.")
            return

        try:
            with open(filename, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                # Assuming no header, or if there is, we might need to skip it.
                # The user description implies raw data columns, but usually CSVs have headers.
                # Let's peek or just try to parse. If it fails, we skip.
                # User said: "name in the first column, x data in the second column, y data in the third column (which in our orrery is actually z), and z data in the fourth"
                
                for row in reader:
                    if len(row) < 4:
                        continue
                    
                    try:
                        name = row[0].strip()
                        # Skip header if present
                        if name.lower() == "name" or name.lower() == "system": 
                            continue
                            
                        x = float(row[1])
                        # User mapping: 
                        # Col 2: X -> x
                        # Col 3: Y (actually Z) -> z
                        # Col 4: Z -> y
                        z = float(row[2]) 
                        y = -float(row[3]) # Invert Y (Source Z) as per user request (flipped on XY plane)
                        
                        self.stars.append({
                            "name": name,
                            "pos": np.array([x, y, z])
                        })
                    except ValueError:
                        continue # Skip rows with non-numeric data (like headers)
                        
            print(f"Loaded {len(self.stars)} stars for starfield.")
            
        except Exception as e:
            print(f"Error loading starfield data: {e}")

    def calculate_star_positions(self, system_origin, radius):
        """
        Calculates the positions of stars on a sphere around the system origin.
        
        Args:
            system_origin (dict or list): {'x': val, 'y': val, 'z': val} or [x, y, z] of the current system.
            radius (float): The radius of the sphere (AU).
            
        Returns:
            list: List of dicts with 'name' and 'pos_local' (x, y, z relative to system center).
        """
        if not self.stars:
            return []

        # Ensure system_origin is a numpy array
        if isinstance(system_origin, dict):
            origin = np.array([float(system_origin.get('x', 0)), float(system_origin.get('y', 0)), float(system_origin.get('z', 0))])
        else:
            origin = np.array(system_origin, dtype=float)

        projected_stars = []
        
        for star in self.stars:
            # Vector from current system to the star
            # Star position is absolute in the galaxy (presumably light years or similar unit as system coords)
            # We want to project this direction onto a sphere of `radius` around the origin.
            
            # Vector difference
            vec = star['pos'] - origin
            
            # Normalize
            dist = np.linalg.norm(vec)
            if dist == 0:
                continue # Should not happen unless we are AT the star
                
            unit_vec = vec / dist
            
            # Scale to radius
            local_pos = unit_vec * radius
            
            projected_stars.append({
                "name": star['name'],
                "pos_local": local_pos # This is (x, y, z) relative to the system center (0,0,0 in local space)
            })
            
        return projected_stars
