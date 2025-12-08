import pygame
import sys
from config import *
from physics import get_elite_time, get_elite_current_time_dt
from api_client import fetch_system_data
from renderer import Orrery

def main():
    """
    The Main Entry Point.
    
    Sets up the Pygame window, initializes the simulation, and runs the main game loop.
    
    The Game Loop:
    1.  **Event Handling**: Checks for mouse clicks, key presses, and window events.
    2.  **Time Management**: Updates the simulation time.
        - If the slider is used, time accelerates (or reverses).
        - Otherwise, time flows at 1x real-time speed.
        
    3.  **Update**: Calls `orrery_sim.update()` to move the planets.
    4.  **Draw**: Calls `orrery_sim.draw()` to render the frame.
    """
    # system_name_input = input("Enter system location name: ")
    # body_data_from_api = fetch_system_data(system_name_input)
    
    # if not body_data_from_api:
    #     print("No data found or error occurred. Exiting.")
    #     sys.exit()
    
    current_elite_time_str = get_elite_time() 
    print(f"Current Universal Time: {current_elite_time_str}")
    
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(f"Orrery | No System Loaded |")
    
    # Windows Dark Mode Title Bar Hack
    try:
        import ctypes
        from ctypes import windll, byref, c_int, c_void_p
        
        hwnd = pygame.display.get_wm_info()['window']
        
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        value = c_int(2)
        value = c_int(1)
        
        # Attempt to apply for Windows 11 / recent Win 10
        windll.dwmapi.DwmSetWindowAttribute(c_void_p(hwnd), c_int(DWMWA_USE_IMMERSIVE_DARK_MODE), byref(value), ctypes.sizeof(value))
        
        # Fallback for older Win 10 versions if the above didn't work (though it fails silently usually)
        windll.dwmapi.DwmSetWindowAttribute(c_void_p(hwnd), c_int(19), byref(value), ctypes.sizeof(value))
        
    except Exception as e:
        print(f"Could not apply dark mode to title bar: {e}")
    # ----------------------------------------

    clock = pygame.time.Clock()
    main_body_font = pygame.font.Font(None, 16) 
    axis_label_font = pygame.font.Font(None, 22) 
    orrery_sim = Orrery(None, system_name="No System Loaded", system_coords={'x':0, 'y':0, 'z':0})
    
    running = True
    left_mouse_dragging = False
    middle_mouse_dragging = False 
    last_mouse_pos = None
    last_middle_click_time = 0
 
    current_time_for_orrery = get_elite_current_time_dt() 
    from datetime import timedelta

    while running:
        dt_ms = clock.tick(FPS)
        dt_seconds = dt_ms / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # UI Event Handling
            ui_action = orrery_sim.handle_ui_event(event)
            if ui_action == "SEARCH_SYSTEM":
                system_to_find = orrery_sim.input_text
                if system_to_find:
                    print(f"Searching for: {system_to_find}")
                    new_body_data, system_coords = fetch_system_data(system_to_find)
                    if new_body_data:
                        orrery_sim.update_system_data(new_body_data, system_to_find, system_coords)
                        pygame.display.set_caption(f"Orrery | {system_to_find} |")
                    else:
                        orrery_sim.info_text = "System not found or no data."
            elif ui_action == "RESET_VIEW":
                orrery_sim.reset_view()
            elif ui_action == "RESET_TIME":
                current_time_for_orrery = get_elite_current_time_dt()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: 
                    if not orrery_sim.input_rect.collidepoint(event.pos) and \
                       not orrery_sim.go_button_rect.collidepoint(event.pos) and \
                       not orrery_sim.toggle_names_button_rect.collidepoint(event.pos) and \
                       not orrery_sim.reset_time_button_rect.collidepoint(event.pos) and \
                       not orrery_sim.slider_rect.inflate(0, 20).collidepoint(event.pos): # *slider area
                        left_mouse_dragging = True
                        last_mouse_pos = event.pos
                elif event.button == 2: 
                    current_time = pygame.time.get_ticks()
                    if last_middle_click_time and (current_time - last_middle_click_time < 500):
                        orrery_sim.reset_view()
                        last_middle_click_time = 0
                    else:
                        last_middle_click_time = current_time
                        middle_mouse_dragging = True
                        last_mouse_pos = event.pos
                elif event.button == 3:
                    action_result = orrery_sim.handle_right_click(event.pos)
                    if action_result:
                        action_type = action_result[0]
                        payload = action_result[1]
                        
                        if action_type == "LOAD_SYSTEM":
                            system_to_find = payload
                            print(f"Navigating to star: {system_to_find}")
                            new_body_data, system_coords = fetch_system_data(system_to_find)
                            if new_body_data:
                                orrery_sim.update_system_data(new_body_data, system_to_find, system_coords)
                                pygame.display.set_caption(f"Orrery | {system_to_find} |")
                            else:
                                print(f"Could not load data for {system_to_find}")
                        elif action_type == "SET_FOCUS":
                            pass # Already handled in renderer, but we could log it here
                elif event.button == 4: 
                    orrery_sim.camera_zoom *= 1.1
                elif event.button == 5: 
                    orrery_sim.camera_zoom /= 1.1
                    orrery_sim.camera_zoom = max(0.01, orrery_sim.camera_zoom) 
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1: 
                    left_mouse_dragging = False
                elif event.button == 2: 
                    middle_mouse_dragging = False
                if not left_mouse_dragging and not middle_mouse_dragging: 
                    last_mouse_pos = None
            if event.type == pygame.MOUSEMOTION:
                if left_mouse_dragging and last_mouse_pos:
                    dx = event.pos[0] - last_mouse_pos[0]
                    dy = event.pos[1] - last_mouse_pos[1]
                    orrery_sim.camera_rotation_y += dx * 0.5 
                    orrery_sim.camera_rotation_x -= dy * 0.5 
                    orrery_sim.camera_rotation_x = max(-89, min(89, orrery_sim.camera_rotation_x))
                    last_mouse_pos = event.pos
                elif middle_mouse_dragging and last_mouse_pos: 
                    mouse_dx = event.pos[0] - last_mouse_pos[0]
                    mouse_dy = event.pos[1] - last_mouse_pos[1]
                    orrery_sim.pan_offset_x += mouse_dx
                    orrery_sim.pan_offset_y += mouse_dy
                    last_mouse_pos = event.pos
        
        # Time Update Logic
        acceleration = orrery_sim.get_time_acceleration()
        if acceleration != 0:
            current_time_for_orrery += timedelta(seconds=dt_seconds * acceleration)
        else:
            current_time_for_orrery += timedelta(seconds=dt_seconds)
        
        orrery_sim.current_simulation_time_str = current_time_for_orrery.strftime('%d-%m-%Y %H:%M:%S UTC')
        
        orrery_sim.update(current_time_for_orrery)
        
        orrery_sim.draw(screen, main_body_font, axis_label_font) 
        # clock.tick(FPS) # Moved to top


    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
