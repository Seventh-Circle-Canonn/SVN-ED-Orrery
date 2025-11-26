import requests
import urllib.parse
import json
import sys

def fetch_system_data(system_name_input):
    """
    Fetches system body data directly from Spansh (Elite Dangerous Database).
    
    The process involves two API calls:
    1.  **Search**: Query `api/systems/field_values/system_names` to find the unique ID (id64) 
        associated with the system name (e.g., "Sol").
    2.  **Dump**: Use the `id64` to query `api/dump/{id64}` to get the full JSON dump of the system,
        which includes all celestial bodies and their orbital data.
        
    Returns:
        tuple: (list of bodies, system coordinates dict)
    """
    print(f"Attempting to fetch data for system: {system_name_input}")
    
    if not system_name_input: 
        print("Location name cannot be empty.")
        return []

    # --- Step 1: Search for the System ID64 ---
    # We finally found a way to use Spansh systems search...  seems to work great...
    search_url = "https://spansh.co.uk/api/systems/field_values/system_names"
    params = {
        'q': system_name_input
    }

    try:
        # User-Agent is important so Spansh knows it's a script, not a bot attack...  or something...
        headers = {'User-Agent': 'Canonn-Orrery-Python-Client/Seventh_Circle-(testing)'}  #  Need to put in a user name input thingy.
        
        # 1. SEARCH REQUEST
        search_response = requests.get(search_url, params=params, headers=headers, timeout=10)
        search_response.raise_for_status()
        search_results = search_response.json()
        
        system_id64 = None
        
        # Format: {"min_max": [{"id":null,"id64":...,"name":"Sol",...}], "values": [...]}
        if 'min_max' in search_results:
            for result in search_results['min_max']:
                if result.get('name', '').lower() == system_name_input.lower():
                    system_id64 = result.get('id64')
                    break
            
            # Fallback: If no exact match, try the first result but give warning.
            if not system_id64 and len(search_results['min_max']) > 0:
                first_result = search_results['min_max'][0]
                print(f"Exact match not found. Defaulting to top result: {first_result.get('name')}")
                system_id64 = first_result.get('id64')

        if not system_id64:
            print(f"System '{system_name_input}' not found in Spansh database.")
            return []

        print(f"Found System ID64: {system_id64}")

        # --- Step 2: Fetch System Dump ---
        # Now we use the ID to get the full data, big file, lots of stuff...
        dump_url = f'https://spansh.co.uk/api/dump/{system_id64}'
        dump_response = requests.get(dump_url, headers=headers, timeout=15)
        dump_response.raise_for_status()
        
        spansh_system_data = dump_response.json()
        print(f"Successfully connected to Spansh dump for {system_name_input}.")

        # The dump format usually has the bodies inside specific keys
        system_coords = {'x': 0, 'y': 0, 'z': 0}
        if 'system' in spansh_system_data:
             coords = spansh_system_data['system'].get('coords')
             if coords: system_coords = coords
             
             if 'bodies' in spansh_system_data['system']:
                return spansh_system_data['system']['bodies'], system_coords
        
        if 'bodies' in spansh_system_data:
            # Try to find coords at top level if not in 'system'
            coords = spansh_system_data.get('coords')
            if coords: system_coords = coords
            return spansh_system_data['bodies'], system_coords
        else:
            print("Error: Spansh data does not contain expected 'bodies' structure.")
            return [], {'x': 0, 'y': 0, 'z': 0}

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error during API request: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: Could not connect. Check internet or URL. Details: {e}")
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: The request timed out. Details: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        
    return []
