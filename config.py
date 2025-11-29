"""
General config file for the Orrery
Contains constants and global variables which can be altered.
Can make things go wrong...  so...  good luck :)
"""

# --- Constants ---
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 800
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREY = (30, 30, 30) 
LIGHT_GREY = (135, 135, 135) 
AXIS_LABEL_COLOR = (50, 50, 50) 
ORBIT_GREY = (40, 40, 40) 
BLUE = (100, 149, 237)  
RED = (255, 100, 100)   
GREEN = (120, 138, 48) # #788a30 
YELLOW = (255, 255, 0)  
ORANGE = (255, 165, 0)
CYAN = (0, 255, 255)
DUSTY_RED = (180, 80, 80)
DARK_GREY = (50, 50, 50)

# Body type colors
BODY_TYPE_COLORS = {
    "Star": YELLOW,
    "Rocky body": (100,100,100), 
    "Metal-rich body": ORANGE,
    "High metal content world": RED,
    "Earth-like world": GREEN,
    "Icy body": CYAN,
    "Class I gas giant": BLUE, 
    "Class II gas giant": (120, 100, 200), 
    "Gas giant with water-based life": (100, 180, 237),
    "Gas giant with ammonia-based life": (150,150,100),
    "Helium-rich gas giant": (200,200,150),
    "Water world": (50,100,200),
    "Ammonia world": (150,100,50),
    "Rocky ice world": (200,220,255),
    "Barycentre": GREY,
    "Default": WHITE
}

# Scaling factors for visualization
PLANET_RADIUS_SCALE = 1000
STAR_BASE_RADIUS = 20
MIN_PLANET_RADIUS_PIXELS = 2
MAX_PLANET_RADIUS_PIXELS = 8 
DEFAULT_PLANE_RADIUS_AU = 50 
SCALE = 1

# Coordinate clamping limits for Pygame
COORD_MIN = -32760 
COORD_MAX = 32760
