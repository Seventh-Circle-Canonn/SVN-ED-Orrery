import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import pandas as pd
import numpy as np

#data_input = 'guardian_ruins_data.csv'
#data_input = 'guardian_ruins_beta_only_data.csv'
data_input = 'braintree_data.csv'

def main():
    try:
        df = pd.read_csv(data_input, header=None, names=['Name', 'X', 'Y', 'Z', 'Code', 'Region'])
    except FileNotFoundError:
        print(f"Error: '{data_input}' not found.")
        return

    stars_x = df['X'].values
    stars_y = df['Y'].values
    stars_z = df['Z'].values
    
    fig, ax = plt.subplots(figsize=(12, 6))
    plt.subplots_adjust(bottom=0.25) # Make room for sliders
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    ax.grid(True, color='grey', linestyle='-', linewidth=0.5, alpha=0.5)
    ax.tick_params(axis='x', colors='grey', labelsize=6)
    ax.tick_params(axis='y', colors='grey', labelsize=6)
    ax.spines['bottom'].set_color('grey')
    ax.spines['top'].set_color('grey')
    ax.spines['left'].set_color('grey')
    ax.spines['right'].set_color('grey')

    # Initial Origin (0)
    # Gamma Velorum: 1099, -146, -133
    # Potential: 2743, -727.41, 29.44
    initial_x = 0
    initial_y = 0
    initial_z = 0

    scat = ax.scatter([], [], s=1, c='white', edgecolors='none')
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_xticks(np.arange(-180, 181, 30))
    ax.set_yticks(np.arange(-90, 91, 30))
    ax.set_xlabel("Azimuth (Degrees)", color='grey')
    ax.set_ylabel("Elevation (Degrees)", color='grey')

    def update_plot(origin_x, origin_y, origin_z):
        # Relative coordinates
        # Stupid ED Coordinates: Y is Up/Down. X is Left/Right. Z is Forward/Back.
        dx = stars_x - origin_x
        dy = stars_y - origin_y  # Y is Elevation component sigh...
        dz = stars_z - origin_z
        r = np.sqrt(dx**2 + dy**2 + dz**2)
        r[r == 0] = 1e-9

        # Elevation (Phi): Angle from XZ plane (Horizontal)
        # sin(phi) = y / r
        # phi = arcsin(y / r)
        elev_rad = np.arcsin(dy / r)
        elev_deg = np.degrees(elev_rad)

        # Azimuth (Theta): Angle in XZ plane
        # usually measured from Z (North) or X (East). 
        # let's use arctan2(x, z) which corresponds to bearing from North (Z) if X is East.
        az_rad = np.arctan2(dx, dz)
        az_deg = np.degrees(az_rad)

        data = np.stack((az_deg, elev_deg), axis=-1)
        scat.set_offsets(data)
        ax.set_title(f"{data_input} skymap | Origin: {origin_x:.2f} / {origin_y:.2f} / {origin_z:.2f}", color='white', fontsize=12)
        fig.canvas.draw_idle()

    x_min, x_max = stars_x.min(), stars_x.max()
    y_min, y_max = stars_y.min(), stars_y.max()
    z_min, z_max = stars_z.min(), stars_z.max()
    buffer = 5000
    axcolor = 'grey'
    slider_color = 'grey'
    ax_x = plt.axes([0.2, 0.1, 0.65, 0.03], facecolor=axcolor)
    ax_y = plt.axes([0.2, 0.06, 0.65, 0.03], facecolor=axcolor)
    ax_z = plt.axes([0.2, 0.02, 0.65, 0.03], facecolor=axcolor)
    slider_x = Slider(ax_x, 'X', x_min - buffer, x_max + buffer, valinit=initial_x, color=slider_color)
    slider_y = Slider(ax_y, 'Y', y_min - buffer, y_max + buffer, valinit=initial_y, color=slider_color)
    slider_z = Slider(ax_z, 'Z', z_min - buffer, z_max + buffer, valinit=initial_z, color=slider_color)

    slider_x.label.set_color('grey')
    slider_y.label.set_color('grey')
    slider_z.label.set_color('grey')
    slider_x.valtext.set_color('grey')
    slider_y.valtext.set_color('grey')
    slider_z.valtext.set_color('grey')

    def on_change(val):
        update_plot(slider_x.val, slider_y.val, slider_z.val)

    slider_x.on_changed(on_change)
    slider_y.on_changed(on_change)
    slider_z.on_changed(on_change)
    update_plot(initial_x, initial_y, initial_z)
    plt.show()

if __name__ == "__main__":
    main()
