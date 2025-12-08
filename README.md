SVN ED Orrery

A Python-based 3D Orrery simulation for Elite Dangerous. This tool fetches live system data from the Spansh API and renders an interactive 3D model of celestial bodies and their orbits.  It can also plot a list of surround star systems by loading a .csv file of systems.

Features:

Real-Time Data: Fetches system bodies directly from Spansh.
Orbital Physics: Plots stored system data as orbital elements (Eccentricity, Inclination, Periapsis, etc.).
Elite Dangerous Time: Simulation is now synced to the current in-game year (UTC + 1286 years).
Interactive 3D View: Pan, zoom, and rotate around the system.
Time Control: Accelerate time forward or backward using the UI slider to watch orbits in motion.
Body Info: Toggle labels for Names, Types, and Atmosphere composition.
Star Info:  Toggle starfield, Names, Points.

Installation

Clone the repository: 

git clone https://github.com/Seventh-Circle-Canonn/SVN-ED-Orrery.git

cd SVN-ED-Orrery

Install dependencies:

This project requires Python 3. You can install the required libraries using pip:

pip install -r requirements.txt

Dependencies: pygame, numpy, requests, datetime.

Run the Simulation:

python main.py

NOTE:  I personally run it in VSCode, but there are windows and linux .exe's in the dist folder.  You can create your own .exe via pyinstaller.

pyinstaller --noconsole --onefile --name "SVN-EDOrrery" --clean main.py

(note: if on linux you'll likely be using a virtual environment for the libraries.  Make sure you sign into the VE before running, i.e. source .venv/bin/activate .

Controls:

The simulation uses mouse and keyboard inputs for navigation:

Orbit Camera: Left Mouse Click + Drag

Pan Camera: Middle Mouse Click + Drag

Zoom Camera: Mouse Wheel

Set Orbit Center: Right Click on a planet/star

Reset View: Double Middle Click or left-click green box.

Search System: Type in the bottom-left white box + Enter

Time Warp: Drag the slider at the bottom centre left and right

Load .csv:  Right-click red box.

Buttons Generally:  Green = Zoom to Extents, Grey = Toggle Body Names, Blue = Reset Time, Red = Toggle Starfield Names.

How it Works:

API Client (api_client.py): Connects to Spansh to search for a system ID, then downloads the full system dump (JSON) containing all body data.

Physics Engine (physics.py): Converts orbital elements (semi-major axis, mean anomaly, etc.) into 3D Cartesian coordinates (x, y, z) for any given timestamp.

Renderer (renderer.py): Handles the Pygame window, projects the 3D coordinates onto the 2D screen, and manages the UI overlay.

Credits

Data Source: Spansh.co.uk (The Spansh API).
Developed by: Seventh_Circle
