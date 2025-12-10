import pygame
import os
import math
import sys
import numpy as np
from config import *
from starfield import Starfield, resource_path
from physics import calculate_position_at_time, calculate_orbit_points, get_elite_time
import tkinter as tk
from tkinter import filedialog


# --- Pygame Specific Helper Functions ---
def initial_world_rotation(x, y, z):
    """
    Adjusts the raw 3D coordinates to match the screen's coordinate system.
    This function maps the simulation's Z-axis (up/down in space) to the screen's Y-axis...  because...  FDev.
    """
    x_new = x; y_new = -z; z_new = y
    return x_new, y_new, z_new

def project_3d_to_2d(x_3d, y_3d, z_3d, camera_z_offset=50, scale_factor=20, perspective_strength=0.005):
    """
    Projects a 3D point (x, y, z) onto a 2D plane (the screen).
    This is what creates the illusion of a 3D Orrery.
    
    The Math:
    To create the illusion of depth (perspective), things further away (larger z) should appear smaller
    and closer to the vanishing point (center of screen).
    
    Formula:
    Perspective Factor = 1 / (z * strength + offset)
    Projected X = x * scale * Perspective Factor
    Projected Y = y * scale * Perspective Factor
    """
    epsilon = 1e-6 
    # The divisor represents the "distance" from the camera.
    divisor = (z_3d * perspective_strength) + camera_z_offset + epsilon
    if divisor <= epsilon: perspective = 0.0001 
    else: perspective = 1.0 / divisor
    
    projected_x_component = x_3d * scale_factor * perspective
    projected_y_component = y_3d * scale_factor * perspective
    
    # Center the coordinates on the screen (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    sx_float = SCREEN_WIDTH // 2 + projected_x_component
    sy_float = SCREEN_HEIGHT // 2 + projected_y_component 

    # Clamp values to prevent Pygame from crashing with huge numbers (trial and error)
    if not math.isfinite(sx_float): sx_final = COORD_MAX if sx_float > 0 else COORD_MIN 
    else: sx_final = int(max(COORD_MIN, min(sx_float, COORD_MAX)))
    if not math.isfinite(sy_float): sy_final = COORD_MAX if sy_float > 0 else COORD_MIN
    else: sy_final = int(max(COORD_MIN, min(sy_float, COORD_MAX)))
    return sx_final, sy_final, perspective

# --- Main Orrery Class ---
class Orrery:
    """
    The main simulation class.
    
    Functions:
    1.  **Data Management**: Stores the list of celestial bodies and their properties.
    2.  **State Management**: Tracks camera position, zoom, and selected orbit center.
    3.  **Update Loop**: Recalculates body positions for the current time.
    4.  **Render Loop**: Draws the bodies, orbits, and UI to the screen.
    """
    def __init__(self, api_body_data, system_name="Unknown System", system_coords=None):
        self.celestial_bodies = []
        self.current_system_name = system_name
        self.system_coords = system_coords if system_coords else {'x': 0, 'y': 0, 'z': 0}
        self.camera_rotation_x = 0 # Changes camera position, but we need to confirm Z axis direction.  Weirdly flips.
        self.camera_rotation_y = 0  
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.plane_radius_au = DEFAULT_PLANE_RADIUS_AU 
        self.main_star_id = None
        self.main_star_id = None
        self.starfield = Starfield(None)
        self.cached_stars = []
        self.process_api_data(api_body_data)
        
        # Orbit Center State
        self.orbit_center_body_id = None
        self.orbit_center_name = "System Origin"
        self.current_focus_offset_au = np.array([0.0, 0.0, 0.0])
        self.body_screen_coords = {} # {body_id: (x, y, radius)}
        self.star_screen_coords = [] # List of (x, y, name)

        # Initialize scrap for clipboard operations - Required for Linux fallback
        pygame.scrap.init()

        projection_scale_factor_for_display = 20 
        camera_z_offset_for_display = 50       

        if self.plane_radius_au > 0:
            target_screen_radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) * 10
            denominator = self.plane_radius_au * projection_scale_factor_for_display
            if denominator == 0: self.camera_zoom = 1.0
            else: self.camera_zoom = (target_screen_radius * camera_z_offset_for_display) / denominator
            self.camera_zoom = max(0.01, self.camera_zoom)
        else:
            self.camera_zoom = 0.1 

        # --- UI State ---
        self.input_text = ""
        self.input_active = False
        self.info_text = f"Bodies: {len(self.celestial_bodies)} | Plane: {self.plane_radius_au:.2f} AU"
        
        # UI Layout
        bottom_bar_height = 40
        self.bottom_bar_rect = pygame.Rect(0, SCREEN_HEIGHT - bottom_bar_height, SCREEN_WIDTH, bottom_bar_height)
        
        input_width = 300
        input_height = 30
        margin = 5
        
        # Go button (green box) - Far right bottom corner
        go_button_width = 40
        self.go_button_rect = pygame.Rect(SCREEN_WIDTH - go_button_width, SCREEN_HEIGHT - bottom_bar_height, go_button_width, bottom_bar_height)

        # Toggle Names Button
        toggle_button_width = 40
        self.toggle_names_button_rect = pygame.Rect(SCREEN_WIDTH - go_button_width - toggle_button_width, SCREEN_HEIGHT - bottom_bar_height, toggle_button_width, bottom_bar_height)
        self.label_display_mode = 0 # 0: Name, 1: Type, 2: Atmosphere, 3: Off

        # Input box in bottom bar
        # Widen to fill space up to buttons (with some margin)
        available_width = SCREEN_WIDTH - go_button_width - toggle_button_width - (margin * 2)
        self.input_rect = pygame.Rect(margin, SCREEN_HEIGHT - bottom_bar_height + margin, available_width, input_height)
        
        # Info text (Bodies | Plane) - move to top left under system name, aligned with it
        # System name is at (25, 25), so we align x to 25.
        self.info_rect = pygame.Rect(25, 55, 300, 30) 

        # --- Time Shift UI ---
        self.time_acceleration_factor = 0.0 # 0 means 1x speed (normal), modified by slider
        self.slider_width = SCREEN_WIDTH - 40 # 20 pixels margin on each side
        self.slider_height = 1 # Thinner line
        self.slider_rect = pygame.Rect((SCREEN_WIDTH - self.slider_width) // 2, SCREEN_HEIGHT - 60, self.slider_width, self.slider_height)
        self.slider_handle_radius = 10
        self.slider_handle_pos = self.slider_rect.centerx
        self.dragging_slider = False
        
        # Reset Time Button (Blue box) - Left of Toggle Names button
        reset_button_width = 40
        self.reset_time_button_rect = pygame.Rect(SCREEN_WIDTH - go_button_width - toggle_button_width - reset_button_width, SCREEN_HEIGHT - bottom_bar_height, reset_button_width, bottom_bar_height)
 
        # Star Visibility Button (Dusty Red box) - Left of Reset Time button
        star_button_width = 40
        self.star_visibility_button_rect = pygame.Rect(SCREEN_WIDTH - go_button_width - toggle_button_width - reset_button_width - star_button_width, SCREEN_HEIGHT - bottom_bar_height, star_button_width, bottom_bar_height)
        self.star_visibility_mode = 2 # 0: Stars+Names, 1: Stars Only, 2: Off - Default to Off

        # Load button assets
        try:
            # Wrap the paths like this:
            self.go_button_img = pygame.image.load(resource_path(os.path.join("assets", "go_button.png"))).convert_alpha()
            self.name_button_img = pygame.image.load(resource_path(os.path.join("assets", "name_button.png"))).convert_alpha()
            self.time_button_img = pygame.image.load(resource_path(os.path.join("assets", "time_button.png"))).convert_alpha()
            self.starfield_button_img = pygame.image.load(resource_path(os.path.join("assets", "starfield_button.png"))).convert_alpha()
        except Exception as e:
            print(f"Error loading assets: {e}")

            # Fallback to surfaces of same size if load fails (or just let it crash/handle gracefully)
            self.go_button_img = None
            self.name_button_img = None
            self.time_button_img = None
            self.starfield_button_img = None

    def reset_view(self):
        """This bit resets the camera view to the default state."""
        self.camera_rotation_x = 0
        self.camera_rotation_y = 0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.orbit_center_body_id = None
        self.orbit_center_name = "System Origin"
        
        projection_scale_factor_for_display = 20 
        camera_z_offset_for_display = 50       

        if self.plane_radius_au > 0:
            target_screen_radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) * 10
            denominator = self.plane_radius_au * projection_scale_factor_for_display
            if denominator == 0: self.camera_zoom = 1.0
            else: self.camera_zoom = (target_screen_radius * camera_z_offset_for_display) / denominator
            self.camera_zoom = max(0.01, self.camera_zoom)
        else:
            self.camera_zoom = 0.1

    def process_api_data(self, api_body_data):
        """
        Important:  Takes the raw JSON data from the API and converts it into a structured list of bodies.
        This is still being developed, needs a lot more work on different system types
        
        Key tasks:
        1.  Identify the Main Star (the root of the system).
        2.  Determine parent-child relationships (who orbits whom).
        3.  Extract physical properties (radius, type, atmosphere).
        4.  Extract orbital elements (semi-major axis, eccentricity, etc.).
        5.  Pre-calculate the static orbit path for visualization.
        """
        if not api_body_data:
            # print("Warning: No body data provided to Orrery.") # Optional: suppress warning if expected
            return

        # 1. Identify Main Star
        for body_entry in api_body_data:
            if body_entry.get('mainStar', False) or body_entry.get('isMainStar', False):
                self.main_star_id = body_entry.get('bodyId')
                break
        if self.main_star_id is None:
            for body_entry in api_body_data:
                if body_entry.get('type') == 'Star' and body_entry.get('bodyId') == 0:
                    self.main_star_id = 0; break
        if self.main_star_id is None:
             for body_entry in api_body_data:
                 if body_entry.get('type') == 'Star':
                     self.main_star_id = body_entry.get('bodyId'); break
        
        if self.main_star_id is None:
             for body_entry in api_body_data:
                 if body_entry.get('bodyId') == 0:
                     self.main_star_id = 0; break

        if self.main_star_id is None:
            print("CRITICAL: Main star ID could not be determined.")
            self.main_star_id = 0

        print(f"Main star ID: {self.main_star_id}")
        max_sma_au_for_plane = 0.0
        
        # 2. Process all bodies and determine hierarchy
        temp_bodies = []
        
        for body_entry in api_body_data:
            body_id = body_entry.get('bodyId')
            
            # Determine Parent ID and Depth
            parent_id = None
            depth = 0
            
            parents_info = body_entry.get('parents')
            if parents_info and isinstance(parents_info, list) and len(parents_info) > 0:
                immediate_parent_dict = parents_info[0]
                if immediate_parent_dict:
                    parent_id = list(immediate_parent_dict.values())[0]
                depth = len(parents_info)
            else:
                if body_id == self.main_star_id:
                    depth = 0
                    parent_id = None
                else:
                    depth = 1
                    parent_id = self.main_star_id

            body_data_dict = {
                "id": body_id,
                "parent_id": parent_id,
                "depth": depth,
                "name": body_entry.get('name', 'N/A'),
                "type": body_entry.get('subType', body_entry.get('type', 'Unknown')),
                "raw_data": body_entry,
                "current_pos_au": np.array([0.0, 0.0, 0.0]), 
                "orbit_center_pos_au": np.array([0.0, 0.0, 0.0]),
                "orbit_path_au": np.empty((0,3)) 
            }
            
            # Atmosphere Logic (need to add more visible markers...  soon...  maybe...)
            atm_type = body_entry.get('atmosphereType')
            if atm_type is None or atm_type == "None":
                comp = body_entry.get('atmosphereComposition')
                if comp and isinstance(comp, dict):
                    # Sort by percentage descending
                    sorted_comp = sorted(comp.items(), key=lambda item: item[1], reverse=True)
                    # Take top 2
                    top_elements = [f"{k}" for k, v in sorted_comp[:2]]
                    if top_elements:
                        atm_type = ", ".join(top_elements)
                    else:
                        atm_type = "No Atmosphere"
                else:
                    atm_type = "No Atmosphere"
            
            body_data_dict["atmosphere"] = atm_type

            if body_entry.get('type') == "Star":
                solar_radius = body_entry.get('solarRadius', 1.0)
                body_data_dict["radius_pixels"] = STAR_BASE_RADIUS * math.sqrt(max(0.1, solar_radius))
            elif body_entry.get('type') == "Barycentre":
                body_data_dict["radius_pixels"] = 3 # Small visible anchor for barycentres (normally hidden)
                body_data_dict["type"] = "Barycentre"
            else:
                planet_km_radius = body_entry.get('radius', 1000.0)
                body_data_dict["radius_pixels"] = max(MIN_PLANET_RADIUS_PIXELS, min(MAX_PLANET_RADIUS_PIXELS, planet_km_radius * PLANET_RADIUS_SCALE))

            body_data_dict['semiMajorAxis'] = body_entry.get('semiMajorAxis')
            body_data_dict['orbitalEccentricity'] = body_entry.get('orbitalEccentricity')
            body_data_dict['orbitalInclination'] = body_entry.get('orbitalInclination')
            body_data_dict['ascendingNode'] = body_entry.get('ascendingNode') 
            body_data_dict['argOfPeriapsis'] = body_entry.get('argOfPeriapsis')
            body_data_dict['orbitalPeriod'] = body_entry.get('orbitalPeriod')
            
            timestamps = body_entry.get('timestamps', {})
            body_data_dict['meanAnomalyAtEpoch'] = body_entry.get('meanAnomaly') 
            body_data_dict['epochTimestamp'] = timestamps.get('meanAnomaly', timestamps.get('distanceToArrival')) 

            if body_data_dict['semiMajorAxis'] is not None:
                if isinstance(body_data_dict['semiMajorAxis'], (int, float)):
                     if depth == 1: # Only consider top-level bodies for plane size...  maybe...  dunno...  best guess.
                        max_sma_au_for_plane = max(max_sma_au_for_plane, body_data_dict['semiMajorAxis'])
                
                if all(isinstance(body_data_dict.get(k), (int, float)) for k in 
                       ['semiMajorAxis', 'orbitalEccentricity', 'orbitalInclination', 'ascendingNode', 'argOfPeriapsis']):
                    body_data_dict["orbit_path_au"] = calculate_orbit_points(
                        body_data_dict['semiMajorAxis'], body_data_dict['orbitalEccentricity'],
                        body_data_dict['orbitalInclination'], body_data_dict['ascendingNode'],
                        body_data_dict['argOfPeriapsis'], num_points=480
                    )
                else:
                    # print(f"Warning: Missing or invalid orbital elements for orbit path of {body_data_dict['name']}")
                    pass

            temp_bodies.append(body_data_dict)

        # Sort bodies by depth so parents are processed before children
        temp_bodies.sort(key=lambda x: x['depth'])
        self.celestial_bodies = temp_bodies

        if max_sma_au_for_plane > 0:
            self.plane_radius_au = max_sma_au_for_plane * 1.3
        elif self.celestial_bodies and self.celestial_bodies[0]['type'] == 'Star': 
             self.plane_radius_au = self.celestial_bodies[0]['raw_data'].get('solarRadius', 1.0) * 0.05 * SCALE 
        else:
            self.plane_radius_au = DEFAULT_PLANE_RADIUS_AU
        print(f"Loaded {len(self.celestial_bodies)} bodies. Plane radius (AU): {self.plane_radius_au:.2f}")
        
        # Update starfield cache
        self.cached_stars = self.starfield.calculate_star_positions(self.system_coords, self.plane_radius_au * 1.2, exclude_name=self.current_system_name)

    def camera_view_rotation(self, x, y, z, angle_x_deg, angle_y_deg):
        """ Rotates a 3D point (already in the rotated world space) by camera view angles. """
        rad_x = math.radians(angle_x_deg)
        rad_y = math.radians(angle_y_deg) 
        y_pitched = y * math.cos(rad_x) - z * math.sin(rad_x)
        z_pitched = y * math.sin(rad_x) + z * math.cos(rad_x)
        x_pitched = x 
        x_yawed = x_pitched * math.cos(rad_y) + z_pitched * math.sin(rad_y)
        z_yawed = -x_pitched * math.sin(rad_y) + z_pitched * math.cos(rad_y)
        y_yawed = y_pitched
        return x_yawed, y_yawed, z_yawed
    
    def select_starfield_file(self):
        """Opens a file dialog to select the starfield CSV."""
        root = tk.Tk()
        root.withdraw() # Hide the main window
        file_path = filedialog.askopenfilename(title="Select Starfield .CSV", filetypes=[("CSV Files", "*.csv")])
        root.destroy()
        return file_path

    def handle_ui_event(self, event):
        """Handles UI events for the input box and buttons."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.input_rect.collidepoint(event.pos):
                self.input_active = True
                self.input_text = "" # Auto-clear on click
            elif self.go_button_rect.collidepoint(event.pos):
                self.input_active = False
                return "RESET_VIEW"
            elif self.toggle_names_button_rect.collidepoint(event.pos):
                self.label_display_mode = (self.label_display_mode + 1) % 4
                self.input_active = False
            elif self.reset_time_button_rect.collidepoint(event.pos):
                self.input_active = False
                return "RESET_TIME"
            elif self.star_visibility_button_rect.collidepoint(event.pos):
                self.input_active = False
                if event.button == 1:
                    # Left Click: Cycle Mode Only
                    self.star_visibility_mode = (self.star_visibility_mode - 1) % 3
                elif event.button == 3:
                    # Right Click: Load File
                    filename = self.select_starfield_file()
                    if filename:
                        self.starfield.load_data(filename)
                        # Recalculate cache with new data
                        self.cached_stars = self.starfield.calculate_star_positions(self.system_coords, self.plane_radius_au * 1.2, exclude_name=self.current_system_name)
                        self.star_visibility_mode = 1 # Force On
                    else:
                        pass
            else:
                handle_rect = pygame.Rect(self.slider_handle_pos - self.slider_handle_radius, self.slider_rect.centery - self.slider_handle_radius, self.slider_handle_radius * 2, self.slider_handle_radius * 2)
                # attempt to allow clicking slightly outside the exact handle...
                expanded_handle_rect = handle_rect.inflate(20, 20)
                if expanded_handle_rect.collidepoint(event.pos):
                    self.dragging_slider = True
                    self.input_active = False
                else:
                    self.input_active = False
        
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging_slider = False
                # Snap back to center
                self.slider_handle_pos = self.slider_rect.centerx
                self.time_acceleration_factor = 0.0

        if event.type == pygame.MOUSEMOTION:
            if self.dragging_slider:
                self.slider_handle_pos = max(self.slider_rect.left, min(self.slider_rect.right, event.pos[0]))
                
                # Calculate acceleration based on distance from center
                center_x = self.slider_rect.centerx
                distance = self.slider_handle_pos - center_x
                max_dist = self.slider_width / 2
                
                normalized_dist = distance / max_dist # -1.0 to 1.0
                
                # Deadzone near center
                if abs(normalized_dist) < 0.05:
                    self.time_acceleration_factor = 0.0
                else:
                    # Exponential curve: sign * (abs(normalized)^exponent) * max_speed
                    # Let's say max speed is very fast, e.g., 1 year per second?
                    # 1 year = 31,536,000 seconds.
                    # At 60 FPS, 1 frame = 1/60 sec, so we need a huge multiplier, let's try max multiplier = 10^7
                    max_multiplier = 10000000 
                    exponent = 5 # Higher exponent for finer control near center.
                    
                    self.time_acceleration_factor = (abs(normalized_dist) ** exponent) * max_multiplier
                    if normalized_dist < 0:
                        self.time_acceleration_factor *= -1

        
        if event.type == pygame.KEYDOWN:
            if self.input_active:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    self.input_active = False
                    return "SEARCH_SYSTEM"
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                    # Handle paste into text box using pyperclip (Cross-platform friendly)
                    # Handle paste into text box using pygame.scrap (Cross-platform friendly)
                    text_to_paste = None
                    try:
                        content = pygame.scrap.get(pygame.SCRAP_TEXT)
                        if content:
                            # content is bytes on Linux usually
                            text_to_paste = content.decode('utf-8').strip('\x00')
                            # Basic sanitization
                            text_to_paste = "".join(ch for ch in text_to_paste if ch.isprintable())
                            self.input_text += text_to_paste
                    except Exception as e:
                        print(f"Error pasting text with pygame.scrap: {e}")
                else:
                    self.input_text += event.unicode
        return None

    def handle_right_click(self, mouse_pos):
        """Handles right-click to set orbit center."""
        clicked_body_id = None
        clicked_body_name = None
        
        for body_id, (bx, by, br) in self.body_screen_coords.items():
            # Simple circle collision
            dist = math.hypot(mouse_pos[0] - bx, mouse_pos[1] - by)
            # Allow a little extra margin for clicking small bodies, trial and error...  seems to work.
            hit_radius = max(br, 5) 
            if dist <= hit_radius:
                clicked_body_id = body_id
                # Find name
                for b in self.celestial_bodies:
                    if b['id'] == body_id:
                        clicked_body_name = b['name']
                        break
                break
        
        if clicked_body_id is not None:
            self.orbit_center_body_id = clicked_body_id
            self.orbit_center_name = clicked_body_name
            print(f"Orbit center set to: {self.orbit_center_name}")
            self.pan_offset_x = 0
            self.pan_offset_y = 0
            return ("SET_FOCUS", self.orbit_center_name)
        
        # Check Starfield Clicks
        for sx, sy, star_name in self.star_screen_coords:
             # Simple point collision with small radius
             if math.hypot(mouse_pos[0] - sx, mouse_pos[1] - sy) < 10:
                 return ("LOAD_SYSTEM", star_name)
        
        return None

    def update_system_data(self, api_body_data, system_name, system_coords):
        """Updates the orrery with new system data."""
        self.celestial_bodies = []
        self.current_system_name = system_name
        self.system_coords = system_coords
        self.main_star_id = None
        self.orbit_center_body_id = None
        self.orbit_center_name = "System Origin"
        self.current_focus_offset_au = np.array([0.0, 0.0, 0.0])
        self.process_api_data(api_body_data)
        self.info_text = f"Bodies: {len(self.celestial_bodies)} | Plane: {self.plane_radius_au:.2f} AU"
        self.input_text = system_name

    def update(self, current_time_dt):
        """
        Updates positions of celestial bodies based on current time.
        
        This method is called every frame.
        1.  Iterates through all bodies.
        2.  Calls `physics.calculate_position_at_time` to get the local position (relative to parent).
        3.  Adds the parent's absolute position to get the body's absolute position in the system.
        4.  Applies the 'Orbit Center' offset if the user has focused on a specific body.
        """
        body_positions = {} 
        
        for body in self.celestial_bodies:
            body_id = body['id']
            parent_id = body['parent_id']
            
            local_pos = np.array([0.0, 0.0, 0.0])
            
            if body.get('semiMajorAxis') is not None:
                 pos = calculate_position_at_time(
                    body.get('semiMajorAxis'), body.get('orbitalEccentricity'),
                    body.get('orbitalInclination'), body.get('ascendingNode'),
                    body.get('argOfPeriapsis'), body.get('orbitalPeriod'),
                    body.get('meanAnomalyAtEpoch'), body.get('epochTimestamp'),
                    current_time_dt
                )
                 if pos is not None:
                     local_pos = pos
                 else:
                     sma = body.get('semiMajorAxis', 0)
                     local_pos = np.array([sma * 0.5 if sma else 0, 0.0, 0.0])
            
            parent_pos = np.array([0.0, 0.0, 0.0])
            if parent_id is not None:
                parent_pos = body_positions.get(parent_id, np.array([0.0, 0.0, 0.0]))
            
            absolute_pos = local_pos + parent_pos
            body_positions[body_id] = absolute_pos
            
            body['current_pos_au'] = absolute_pos
            body['orbit_center_pos_au'] = parent_pos

        # Apply Orbit Center Offset if active
        if self.orbit_center_body_id is not None:
            center_offset = body_positions.get(self.orbit_center_body_id, np.array([0.0, 0.0, 0.0]))
            self.current_focus_offset_au = center_offset
            for body in self.celestial_bodies:
                body['current_pos_au'] = body['current_pos_au'] - center_offset
                body['orbit_center_pos_au'] = body['orbit_center_pos_au'] - center_offset
        else:
            self.current_focus_offset_au = np.array([0.0, 0.0, 0.0])


    def draw(self, screen, main_font, axis_label_font):
        """
        Renders the entire scene.
        
        Steps:
        1.  Clear screen.
        2.  Draw the reference grid (plane) if no specific body is focused.
        3.  Prepare a list of 'drawable objects' (bodies and orbit paths).
        4.  Sort objects by Z-depth (painter's algorithm) so far objects are drawn behind close ones.
        5.  Iterate and draw:
            - Project 3D coordinates to 2D screen coordinates.
            - Draw circles for bodies and lines for orbits.
            - Draw text labels.
        6.  Draw the UI overlay (buttons, sliders, info text).
        """
        screen.fill(BLACK)
        self.body_screen_coords = {} # Reset frame hit detection
        self.star_screen_coords = [] # Reset star hit detection
        current_plane_radius = self.plane_radius_au # Use AU value for 3D calculations
        
        if self.orbit_center_body_id is None:
            plane_points_orig_3d = []
            num_plane_points = 120
            for i in range(num_plane_points + 1): 
                angle = (i / num_plane_points) * 2 * math.pi
                x_orig = current_plane_radius * math.cos(angle) # Radius in AU
                y_orig = current_plane_radius * math.sin(angle) # Radius in AU
                z_orig = 0 
                x_world, y_world, z_world = initial_world_rotation(x_orig, y_orig, z_orig)
                plane_points_orig_3d.append((x_world, y_world, z_world))

            projected_plane_points_panned = []
            for x_world, y_world, z_world in plane_points_orig_3d:
                rx_cam, ry_cam, rz_cam = self.camera_view_rotation(x_world, y_world, z_world, self.camera_rotation_x, self.camera_rotation_y)
                sx_proj, sy_proj, _ = project_3d_to_2d(rx_cam, ry_cam, rz_cam, scale_factor=self.camera_zoom, camera_z_offset=50, perspective_strength=0.001) 
                projected_plane_points_panned.append((sx_proj + self.pan_offset_x, sy_proj + self.pan_offset_y))
            
            if len(projected_plane_points_panned) > 1:
                pygame.draw.lines(screen, WHITE, True, projected_plane_points_panned, 3)
        
        if self.orbit_center_body_id is None:
            axis_length_au = current_plane_radius * 0.9 
            label_offset_au = current_plane_radius * 0.95
            axes_definitions = [
                {"name": "X", "start_orig": (-axis_length_au, 0, 0), "end_orig": (axis_length_au, 0, 0), "label_pos_orig": (label_offset_au, 0, 0)},
                {"name": "Z", "start_orig": (0, -axis_length_au, 0), "end_orig": (0, axis_length_au, 0), "label_pos_orig": (0, -label_offset_au, 0)},
            ]
            for axis_def in axes_definitions:
                s_world_x, s_world_y, s_world_z = initial_world_rotation(axis_def["start_orig"][0], axis_def["start_orig"][1], axis_def["start_orig"][2])
                e_world_x, e_world_y, e_world_z = initial_world_rotation(axis_def["end_orig"][0], axis_def["end_orig"][1], axis_def["end_orig"][2])
                rs_cam_x, rs_cam_y, rs_cam_z = self.camera_view_rotation(s_world_x, s_world_y, s_world_z, self.camera_rotation_x, self.camera_rotation_y)
                re_cam_x, re_cam_y, re_cam_z = self.camera_view_rotation(e_world_x, e_world_y, e_world_z, self.camera_rotation_x, self.camera_rotation_y)
                s_sx_proj, s_sy_proj, _ = project_3d_to_2d(rs_cam_x, rs_cam_y, rs_cam_z, scale_factor=self.camera_zoom, camera_z_offset=50, perspective_strength=0.01) 
                e_sx_proj, e_sy_proj, _ = project_3d_to_2d(re_cam_x, re_cam_y, re_cam_z, scale_factor=self.camera_zoom, camera_z_offset=50, perspective_strength=0.01)
                pygame.draw.line(screen, GREY, (s_sx_proj + self.pan_offset_x, s_sy_proj + self.pan_offset_y), (e_sx_proj + self.pan_offset_x, e_sy_proj + self.pan_offset_y), 1)
                l_world_x, l_world_y, l_world_z = initial_world_rotation(axis_def["label_pos_orig"][0], axis_def["label_pos_orig"][1], axis_def["label_pos_orig"][2])
                rl_cam_x, rl_cam_y, rl_cam_z = self.camera_view_rotation(l_world_x, l_world_y, l_world_z, self.camera_rotation_x, self.camera_rotation_y)
                l_sx_proj, l_sy_proj, _ = project_3d_to_2d(rl_cam_x, rl_cam_y, rl_cam_z, scale_factor=self.camera_zoom, camera_z_offset=50, perspective_strength=0.01)
                label_surface = axis_label_font.render(axis_def["name"], True, AXIS_LABEL_COLOR)
                label_rect = label_surface.get_rect(center=(l_sx_proj + self.pan_offset_x, l_sy_proj + self.pan_offset_y))
                screen.blit(label_surface, label_rect)

        drawable_objects = []
        for body in self.celestial_bodies:
            pos_au = body['current_pos_au'] 
            body_x_world, body_y_world, body_z_world = initial_world_rotation(pos_au[0], pos_au[1], pos_au[2])
            cam_rot_x, cam_rot_y, cam_rot_z = self.camera_view_rotation(body_x_world, body_y_world, body_z_world, self.camera_rotation_x, self.camera_rotation_y)
            drawable_objects.append({"type": "body", "data": body, "x_cam": cam_rot_x, "y_cam": cam_rot_y, "z_cam": cam_rot_z})

            if body["orbit_path_au"].size > 0:
                orbit_points_cam_space = [] 
                orbit_center = body['orbit_center_pos_au']
                for orb_p_au in body["orbit_path_au"]:
                    abs_x = orb_p_au[0] + orbit_center[0]
                    abs_y = orb_p_au[1] + orbit_center[1]
                    abs_z = orb_p_au[2] + orbit_center[2]
                    
                    ox_world, oy_world, oz_world = initial_world_rotation(abs_x, abs_y, abs_z)
                    rox_cam, roy_cam, roz_cam = self.camera_view_rotation(ox_world, oy_world, oz_world, self.camera_rotation_x, self.camera_rotation_y)
                    orbit_points_cam_space.append((rox_cam, roy_cam, roz_cam))
                avg_z_orbit_cam = sum(p[2] for p in orbit_points_cam_space) / len(orbit_points_cam_space) if orbit_points_cam_space else 0
                drawable_objects.append({"type": "orbit", "points_cam_space": orbit_points_cam_space, "z_cam": avg_z_orbit_cam})

        drawable_objects.sort(key=lambda obj: obj["z_cam"], reverse=True)

        for obj in drawable_objects:
            if obj["type"] == "body":
                body_data = obj["data"]
                sx_proj, sy_proj, perspective_scale = project_3d_to_2d(obj["x_cam"], obj["y_cam"], obj["z_cam"], 
                                                                     scale_factor=self.camera_zoom, camera_z_offset=50)
                sx = sx_proj + self.pan_offset_x
                sy = sy_proj + self.pan_offset_y
                color_key = body_data.get("type", "Default")
                color = BODY_TYPE_COLORS.get(color_key, BODY_TYPE_COLORS["Default"])
                body_radius_pixels = body_data.get("radius_pixels", MIN_PLANET_RADIUS_PIXELS)
                scaled_radius = max(1, int(body_radius_pixels * perspective_scale**0.5)) 
                pygame.draw.circle(screen, color, (sx, sy), scaled_radius)
                
                # Store for hit detection
                self.body_screen_coords[body_data['id']] = (sx, sy, scaled_radius)
                
                if scaled_radius > 0.01 and self.label_display_mode != 3: 
                    label_text = ""
                    if self.label_display_mode == 0:
                        label_text = body_data["name"]
                    elif self.label_display_mode == 1:
                        label_text = body_data["type"]
                    elif self.label_display_mode == 2:
                        label_text = body_data.get("atmosphere", "N/A")
                        if label_text is None: label_text = "N/A"

                    if label_text:
                        name_surface = main_font.render(label_text, True, LIGHT_GREY)
                        name_rect = name_surface.get_rect(center=(sx, sy + scaled_radius + 8)) 
                        screen.blit(name_surface, name_rect)

            elif obj["type"] == "orbit":
                projected_orbit_points_panned = []
                for ox_cam, oy_cam, oz_cam in obj["points_cam_space"]:
                    osx_proj, osy_proj, _ = project_3d_to_2d(ox_cam, oy_cam, oz_cam, 
                                                           scale_factor=self.camera_zoom, camera_z_offset=50)
                    projected_orbit_points_panned.append((osx_proj + self.pan_offset_x, osy_proj + self.pan_offset_y))
                
                if len(projected_orbit_points_panned) > 1:
                    pygame.draw.lines(screen, ORBIT_GREY, False, projected_orbit_points_panned, 1)

        # --- Draw Starfield ---
        # Stars are projected onto a sphere around the SYSTEM ORIGIN.
        # If we are panning (orbit_center_body_id is set), we need to adjust their relative position.
        
        if self.star_visibility_mode != 2: # If not OFF
            for star in self.cached_stars:
                # Position relative to system origin
                pos_local = star['pos_local'] # (x, y, z)
                
                # Adjust for camera focus (if we are looking at a planet, the system origin moves away)
                # current_focus_offset_au is the vector from System Origin to Camera Focus.
                # So position relative to Camera Focus is: pos_local - current_focus_offset_au
                
                rel_x = pos_local[0] - self.current_focus_offset_au[0]
                rel_y = pos_local[1] - self.current_focus_offset_au[1]
                rel_z = pos_local[2] - self.current_focus_offset_au[2]
                
                # Rotate to World Space (Pygame coordinates)
                wx, wy, wz = initial_world_rotation(rel_x, rel_y, rel_z)
                
                # Rotate by Camera View
                cx, cy, cz = self.camera_view_rotation(wx, wy, wz, self.camera_rotation_x, self.camera_rotation_y)
                
                # Project to 2D
                sx_proj, sy_proj, perspective = project_3d_to_2d(cx, cy, cz, scale_factor=self.camera_zoom, camera_z_offset=50, perspective_strength=0.001)
                
                sx = sx_proj + self.pan_offset_x
                sy = sy_proj + self.pan_offset_y
                
                # Draw Star (Small dot)
                # Only draw if in front of camera (roughly) - perspective check? 
                
                if perspective > 0.0001:
                    pygame.draw.circle(screen, WHITE, (sx, sy), 1)
                    
                    if self.star_visibility_mode == 0: # Stars + Names
                        # Draw Name
                        name_surface = main_font.render(star['name'], True, DARK_GREY)
                        # Center text below star
                        name_rect = name_surface.get_rect(center=(sx, sy + 10))
                        screen.blit(name_surface, name_rect)
                    
                    # Cache for click detection
                    self.star_screen_coords.append((sx, sy, star['name']))

        # --- UI Drawing ---
        ui_font = pygame.font.Font(None, 28)
        
        input_bg_color = MID_GREY if self.input_active else WHITE
        
        # Bottom White Bar (now dynamic)
        pygame.draw.rect(screen, input_bg_color, self.bottom_bar_rect)
        pygame.draw.rect(screen, input_bg_color, self.input_rect)
        
        if self.input_text == "" and not self.input_active:
            text_surface = ui_font.render("Enter System Name", True, LIGHT_GREY)
        else:
            text_surface = ui_font.render(self.input_text, True, BLACK)

        screen.blit(text_surface, (self.input_rect.x + 5, self.input_rect.y + 5))
        self.input_rect.w = max(300, text_surface.get_width() + 10) 
        
        # Go Button
        pygame.draw.rect(screen, GREEN, self.go_button_rect)
        if self.go_button_img:
            screen.blit(self.go_button_img, self.go_button_rect)

        # Toggle Names Button
        pygame.draw.rect(screen, BLUE, self.toggle_names_button_rect)
        if self.name_button_img:
            screen.blit(self.name_button_img, self.toggle_names_button_rect)

        # Reset Time Button
        pygame.draw.rect(screen, DUSTY_RED, self.reset_time_button_rect)
        if self.time_button_img:
            screen.blit(self.time_button_img, self.reset_time_button_rect)

        # Star Visibility Button
        pygame.draw.rect(screen, LIGHT_GREY, self.star_visibility_button_rect)
        if self.starfield_button_img:
            screen.blit(self.starfield_button_img, self.star_visibility_button_rect)

        # Slider
        pygame.draw.rect(screen, WHITE, self.slider_rect) # Thin line
        pygame.draw.circle(screen, WHITE, (int(self.slider_handle_pos), self.slider_rect.centery), self.slider_handle_radius, 3)
        
        # Info Box
        info_surface = ui_font.render(self.info_text, True, WHITE)
        screen.blit(info_surface, (25, 55))

        # Orbit Center Text
        center_text_surface = ui_font.render(f"Orbit Centre | {self.orbit_center_name}", True, WHITE)
        screen.blit(center_text_surface, (25, 85))

        # Coordinates Display
        # Convert AU offset to Light Years (1 LY = 63241.1 AU)
        au_to_ly = 1.0 / 63241.1
        
        # Ensure system_coords are floats
        sys_x = float(self.system_coords.get('x', 0))
        sys_y = float(self.system_coords.get('z', 0))
        sys_z = float(self.system_coords.get('y', 0))
        
        # Calculate final coordinates
        # Spansh/EDSM coords are usually Light Years.
        # Our offset is in AU.
        final_x = sys_x + (self.current_focus_offset_au[0] * au_to_ly)
        final_y = sys_y + (self.current_focus_offset_au[1] * au_to_ly)
        final_z = sys_z + (self.current_focus_offset_au[2] * au_to_ly)
        
        # Swap of Y and Z for display (ED coordinate system quirk, might not be correct, need to check)
        # And format "EDx | ... EDy[z] | ... EDz[y] | ..." (Sequence reordered)
        coords_text = f"EDx [x] | {final_x:.6f}  EDy [z] | {final_z:.6f}  EDz [y] | {-final_y:.6f}  "
        coords_surface = ui_font.render(coords_text, True, WHITE)
        screen.blit(coords_surface, (25, 115))

        # Distance Display
        # 1 AU = 499.00478 Light Seconds
        au_to_ls = 499.00478
        
        # Distance to System Origin (0,0,0)
        # current_focus_offset_au is the vector from Origin to Current Focus.
        # So magnitude is the distance.
        dist_origin_au = np.linalg.norm(self.current_focus_offset_au)
        dist_origin_ls = dist_origin_au * au_to_ls
        
        # Distance to Main Star
        dist_main_star_ls = 0.0
        if self.main_star_id is not None:
            # Find main star body
            main_star_body = next((b for b in self.celestial_bodies if b['id'] == self.main_star_id), None)
            if main_star_body:
                # current_pos_au is already relative to the current focus (camera center)
                # so magnitude is the distance from camera focus to main star.
                dist_ms_au = np.linalg.norm(main_star_body['current_pos_au'])
                dist_main_star_ls = dist_ms_au * au_to_ls
        
        dist_text_origin = f"Distance to Origin | {dist_origin_ls:.6f}ls"
        dist_surface_origin = ui_font.render(dist_text_origin, True, WHITE)
        screen.blit(dist_surface_origin, (25, 145))

        dist_text_ms = f"Distance to Main Star | {dist_main_star_ls:.6f}ls"
        dist_surface_ms = ui_font.render(dist_text_ms, True, WHITE)
        screen.blit(dist_surface_ms, (25, 175))

        status_box_rect = pygame.Rect(20, 20, 300, 30)
        # pygame.draw.rect(screen, BLACK, status_box_rect, 1) # Optional background
        display_time = getattr(self, 'current_simulation_time_str', get_elite_time())
        status_text_surface = ui_font.render(f"{self.current_system_name} | {display_time}", True, WHITE)
        screen.blit(status_text_surface, (status_box_rect.x + 5, status_box_rect.y + 5))
        
        pygame.display.flip()

    def get_time_acceleration(self):
        return self.time_acceleration_factor

