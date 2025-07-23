import storage
import os
from modules.routes_data import routes_data

def url_decode(s):
    """Simple URL decoder for common characters."""
    s = s.replace("+", " ")
    s = s.replace("%7E", "~")
    s = s.replace("%7e", "~")  # Handle lowercase too
    s = s.replace("%20", " ")
    s = s.replace("%21", "!")
    s = s.replace("%22", '"')
    s = s.replace("%23", "#")
    s = s.replace("%24", "$")
    s = s.replace("%25", "%")
    s = s.replace("%26", "&")
    s = s.replace("%27", "'")
    s = s.replace("%28", "(")
    s = s.replace("%29", ")")
    s = s.replace("%2A", "*")
    s = s.replace("%2a", "*")
    s = s.replace("%2B", "+")
    s = s.replace("%2b", "+")
    s = s.replace("%2C", ",")
    s = s.replace("%2c", ",")
    s = s.replace("%2D", "-")
    s = s.replace("%2d", "-")
    s = s.replace("%2E", ".")
    s = s.replace("%2e", ".")
    s = s.replace("%2F", "/")
    s = s.replace("%2f", "/")
    return s

def load_html(filename="ferry_config.html"):
    """Load the HTML content for the ferry configuration page."""
    try:
        with open(f"/modules/HTML/{filename}", "r") as file:
            html_content = file.read()
        return html_content
    except Exception as e:
        print(f"Failed to load HTML file: {e}")
        return "<h1>Error: Unable to load the HTML file.</h1>"

def write_settings(route_id, route_name, stop_id, stop_name, headsign, color):
    """Write the ferry configuration to settings.toml."""
    try:
        print("Attempting to remount filesystem as writable...")
        storage.remount("/", readonly=False)
        print("Filesystem remounted as writable.")
        
        # Get existing settings using os.getenv
        ssid = os.getenv("CIRCUITPY_WIFI_SSID", "")
        password = os.getenv("CIRCUITPY_WIFI_PASSWORD", "")
        
        print(f"Writing settings to /settings.toml...")
        # Write all settings
        with open("/settings.toml", "w") as file:
            if ssid:
                file.write(f'CIRCUITPY_WIFI_SSID = "{ssid}"\n')
            if password:
                file.write(f'CIRCUITPY_WIFI_PASSWORD = "{password}"\n')
            file.write(f'CIRCUITPY_FERRY_ROUTE_ID = "{route_id}"\n')
            file.write(f'CIRCUITPY_FERRY_ROUTE_NAME = "{route_name}"\n')
            file.write(f'CIRCUITPY_FERRY_STOP_ID = "{stop_id}"\n')
            file.write(f'CIRCUITPY_FERRY_STOP_NAME = "{stop_name}"\n')
            file.write(f'CIRCUITPY_FERRY_HEADSIGN = "{headsign}"\n')
            file.write(f'CIRCUITPY_FERRY_COLOR = "{color}"\n')
            
        print("Ferry settings updated!")
        print("Remounting filesystem as readonly...")
        storage.remount("/", readonly=True)
        print("Filesystem remounted as readonly.")
        return True
    except Exception as e:
        print(f"Failed to write settings. Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        return False

def handle_ferry_config(request):
    """Handle ferry configuration requests."""
    
    # Build ferry_data from routes_data.py
    ferry_data = {}
    route_ids = {}  # Map from route code to full route ID
    for route_key, route_info in routes_data.items():
        # Extract route code (e.g., 'AS' from 'AS (Astoria)')
        route_code = route_key.split(' ')[0]
        # Use the full route key as the display name (e.g., 'AS (Astoria)')
        route_name = route_key
        # Store mapping from route code to full route ID
        route_ids[route_code] = route_info['id']
        # Build stops dictionary using stop_id as key and name as value
        stops = {}
        stop_ids = {}  # Map from short key to full stop_id
        for stop in route_info['stops']:
            # Use the last part after the last dash as the stop key (e.g., 'astoria' from 's-dr5r7-astoria')
            stop_key = stop['stop_id'].split('-')[-1]
            stops[stop_key] = stop['name']
            stop_ids[stop_key] = stop['stop_id']  # Store full stop_id
        ferry_data[route_code] = {
            'name': route_name,
            'stops': stops,
            'stop_ids': stop_ids,  # Add mapping to full stop IDs
            'headsigns': route_info.get('trip_headsigns', [])
        }
    
    # Check if this is a POST request (form submission)
    if "POST" in request:
        try:
            # Extract the body from the request
            body = request.split("\r\n\r\n")[1]
            # Parse the form data
            params = dict(pair.split("=") for pair in body.split("&"))
            
            route_id = url_decode(params.get("route", ""))
            stop_id = url_decode(params.get("stop_id", ""))
            headsign = url_decode(params.get("headsign", ""))
            
            # Get route and stop names from our data
            route_name = ""
            stop_name = ""
            route_color = ""
            full_route_id = route_id  # Default to the received route_id
            full_stop_id = stop_id  # Default to the received stop_id
            if route_id in ferry_data:
                route_name = ferry_data[route_id]['name']
                full_route_id = route_ids[route_id]  # Get full route ID
                # Get the color from routes_data
                for route_key, route_info in routes_data.items():
                    if route_info['id'] == route_ids[route_id]:
                        route_color = route_info.get('color', '')
                        break
                if stop_id in ferry_data[route_id]['stops']:
                    stop_name = ferry_data[route_id]['stops'][stop_id]
                    full_stop_id = ferry_data[route_id]['stop_ids'][stop_id]  # Get full stop ID
            
            print(f"Received ferry configuration: {route_id} → {full_route_id} ({route_name}), {stop_id} → {full_stop_id} ({stop_name}), headsign: {headsign}, color: {route_color}")
            
            if route_id and stop_id and headsign and write_settings(full_route_id, route_name, full_stop_id, stop_name, headsign, route_color):
                print("Successfully wrote ferry settings")
                success_page = load_html("ferry_config_success.html")
                return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(success_page)}\n\n{success_page}"
            
            print("Failed to write ferry settings - missing route, stop, or headsign")
            error_page = load_html("ferry_config_error.html")
            return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(error_page)}\n\n{error_page}"
            
        except Exception as e:
            print(f"Error processing ferry config request: {e}")
            error_page = load_html("ferry_config_error.html")
            return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(error_page)}\n\n{error_page}"
    
    # For GET requests, return the configuration page with route-specific stops
    try:
        # Check if a route was selected (from query parameters)
        selected_route = None
        if "?" in request:
            query_params = request.split("?")[1].split(" ")[0]  # Get query string before HTTP version
            if "route=" in query_params:
                selected_route = query_params.split("route=")[1].split("&")[0]
        
        main_page = load_html("ferry_config.html")
        
        # Generate route dropdown with auto-submit on change (sorted alphabetically by name)
        route_options = []
        # Sort routes by their display names alphabetically
        sorted_routes = sorted(ferry_data.items(), key=lambda x: x[1]['name'])
        for route_id, route_info in sorted_routes:
            selected = 'selected' if route_id == selected_route else ''
            route_options.append(f'<option value="{route_id}" {selected}>{route_info["name"]}</option>')
        
        old_route_html = '<select id="route" name="route" onchange="window.location.href=\'?route=\'+this.value"><option value="">Select a route</option></select>'
        
        new_route_html = f'<select id="route" name="route" onchange="window.location.href=\'?route=\'+this.value"><option value="">Select a route</option>{"".join(route_options)}</select>'
        
        if old_route_html in main_page:
            main_page = main_page.replace(old_route_html, new_route_html)
            print(f"Added route dropdown (selected: {selected_route or 'none'})")
        
        # Generate stops dropdown based on selected route (sorted alphabetically by name)
        stop_options = []
        if selected_route and selected_route in ferry_data:
            # Sort stops by their display names alphabetically
            sorted_stops = sorted(ferry_data[selected_route]['stops'].items(), key=lambda x: x[1])
            for stop_id, stop_name in sorted_stops:
                stop_options.append(f'<option value="{stop_id}">{stop_name}</option>')
        
        old_stop_html = '<select id="stop" name="stop_id"><option value="">Select a stop</option></select>'
        
        new_stop_html = f'<select id="stop" name="stop_id"><option value="">Select a stop</option>{"".join(stop_options)}</select>'
        
        if old_stop_html in main_page:
            main_page = main_page.replace(old_stop_html, new_stop_html)
            stops_count = len(stop_options) if stop_options else 0
            print(f"Added {stops_count} stops for route {selected_route or 'none'}")
        
        # Generate headsigns dropdown based on selected route
        headsign_options = []
        if selected_route and selected_route in ferry_data:
            for headsign in ferry_data[selected_route]['headsigns']:
                headsign_options.append(f'<option value="{headsign}">{headsign}</option>')
        
        old_headsign_html = '<select id="headsign" name="headsign"><option value="">Select a direction</option></select>'
        
        new_headsign_html = f'<select id="headsign" name="headsign"><option value="">Select a direction</option>{"".join(headsign_options)}</select>'
        
        if old_headsign_html in main_page:
            main_page = main_page.replace(old_headsign_html, new_headsign_html)
            headsigns_count = len(headsign_options) if headsign_options else 0
            print(f"Added {headsigns_count} headsigns for route {selected_route or 'none'}")
        
        return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(main_page)}\n\n{main_page}"
        
    except Exception as e:
        print(f"Error loading ferry config: {e}")
        # Fallback to basic test version
        main_page = load_html("ferry_config.html")
        return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(main_page)}\n\n{main_page}"