import wifi
import storage
import time
from modules.ferry_config import handle_ferry_config

def scan_wifi_networks():
    """Scan for available Wi-Fi networks and return a list of SSIDs."""
    try:
        print("Scanning for Wi-Fi networks...")
        networks = []
        for network in wifi.radio.start_scanning_networks():
            if network.ssid and network.ssid not in [n['ssid'] for n in networks]:
                networks.append({
                    'ssid': network.ssid,
                    'rssi': network.rssi,
                    'channel': network.channel
                })
        wifi.radio.stop_scanning_networks()
        
        # Sort by signal strength (higher RSSI = stronger signal)
        networks.sort(key=lambda x: x['rssi'], reverse=True)
        print(f"Found {len(networks)} networks")
        return networks
    except Exception as e:
        print(f"Failed to scan networks: {e}")
        return []

def load_html(filename="wifi_config.html", networks=None):
    """Load the HTML content for the Wi-Fi configuration page."""
    try:
        with open(f"/modules/HTML/{filename}", "r") as file:
            html_content = file.read()
        
        print(f"DEBUG: Loading {filename}, networks: {networks is not None}")
        
        # If we have networks data and this is the wifi config page, inject the dropdown
        if networks is not None and filename == "wifi_config.html":
            print(f"DEBUG: Processing {len(networks)} networks")
            
            # Limit to top 5 networks and make HTML very compact
            limited_networks = networks[:5]
            print(f"DEBUG: Limited to {len(limited_networks)} networks")
            
            # Build compact network options
            options_html = '<option value="">Select network...</option>'
            for network in limited_networks:
                ssid = network["ssid"]
                # Truncate network names more aggressively
                if len(ssid) > 20:
                    ssid = ssid[:17] + "..."
                options_html += f'<option value="{network["ssid"]}">{ssid}</option>'
            options_html += '<option value="__custom__">Custom...</option>'
            
            # Create very compact form HTML - minimal whitespace
            new_form = f'<form method="POST" action="/"><label for="wifi_name">WiFi Name:</label><select id="wifi_name" name="wifi_name">{options_html}</select><label for="wifi_password">WiFi Password:</label><input type="password" id="wifi_password" name="wifi_password"><input type="submit" value="Connect"></form>'
            
            # Replace the entire form
            form_start = html_content.find('<form')
            form_end = html_content.find('</form>') + 7
            
            if form_start != -1 and form_end != -1:
                html_content = html_content[:form_start] + new_form + html_content[form_end:]
                print("DEBUG: Replaced entire form")
                print(f"DEBUG: New form length: {len(new_form)}")
            else:
                print("DEBUG: ERROR - Could not find form tags")
                return html_content
            
            print(f"DEBUG: Final HTML length: {len(html_content)}")
            
            # Verify all components are present
            if 'wifi_password' in html_content and 'type="password"' in html_content:
                print("DEBUG: Password field confirmed")
            if 'type="submit"' in html_content:
                print("DEBUG: Submit button confirmed")
        
        return html_content
    except Exception as e:
        print(f"Failed to load HTML file: {e}")
        return "<h1>Error: Unable to load the HTML file.</h1>"

def write_settings(ssid, password):
    """Write the new Wi-Fi credentials to settings.toml."""
    try:
        storage.remount("/", readonly=False)
        print("Filesystem remounted as writable.")
        with open("/settings.toml", "w") as file:
            file.write(f'CIRCUITPY_WIFI_SSID = "{ssid}"\n')
            file.write(f'CIRCUITPY_WIFI_PASSWORD = "{password}"\n')
        print("Settings updated!")
        storage.remount("/", readonly=True)
        return True
    except Exception as e:
        print(f"Failed to write settings: {e}")
        return False

def test_wifi_connection(ssid, password):
    """Test Wi-Fi connection with the provided credentials."""
    try:
        print(f"Attempting to connect to Wi-Fi network '{ssid}'...")
        wifi.radio.connect(ssid, password)
        print("Connected to Wi-Fi!")
        print("Testing internet connectivity...")
        response_time = wifi.radio.ping("8.8.8.8")  # Google's public DNS
        if response_time is not None:
            print(f"Internet connectivity confirmed (ping: {response_time} ms).")
            return True
        else:
            print("Ping failed. No internet connectivity.")
            return False
    except Exception as e:
        print(f"Failed to connect to Wi-Fi: {e}")
        return False

def handle_wifi_config_request(request):
    """Handle the Wi-Fi configuration request and return appropriate response."""
    if "POST /" in request:
        try:
            body = request.split("\r\n\r\n")[1]
            params = {k: v for k, v in [pair.split("=") for pair in body.split("&")]}
            ssid = params.get("wifi_name", "").replace("+", " ")
            password = params.get("wifi_password", "")

            # If user selected "Enter custom network...", show them a custom input page
            if ssid == "__custom__":
                custom_html = '''<!DOCTYPE html>
<html>
<head>
    <title>Custom WiFi Network</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 20px; background-color: #f0f0f0; }
        h1 { color: #333; margin-top: 20px; margin-bottom: 30px; }
        form { display: inline-block; padding: 30px; background-color: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); width: 85%; max-width: 400px; margin: 0 auto; }
        label { font-size: 18px; display: block; margin-bottom: 10px; }
        input[type="text"], input[type="password"] { padding: 10px; font-size: 16px; width: 100%; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
        input[type="submit"] { padding: 10px 20px; font-size: 16px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; width: 100%; }
        input[type="submit"]:hover { background-color: #45a049; }
    </style>
</head>
<body>
    <h1>Enter Custom WiFi Network</h1>
    <form method="POST" action="/">
        <label for="wifi_name">WiFi Name:</label>
        <input type="text" id="wifi_name" name="wifi_name" placeholder="Enter network name...">
        <label for="wifi_password">WiFi Password:</label>
        <input type="password" id="wifi_password" name="wifi_password">
        <input type="submit" value="Connect">
    </form>
</body>
</html>'''
                return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(custom_html)}\n\n{custom_html}"

            if test_wifi_connection(ssid, password):
                if write_settings(ssid, password):
                    # Return the populated ferry configuration page
                    ferry_page = handle_ferry_config("GET / HTTP/1.1")
                    # Extract just the HTML content from the ferry response (remove HTTP headers)
                    # Handle both \r\n\r\n and \n\n separators
                    if "\r\n\r\n" in ferry_page:
                        ferry_html = ferry_page.split("\r\n\r\n", 1)[1]
                    elif "\n\n" in ferry_page:
                        ferry_html = ferry_page.split("\n\n", 1)[1]
                    else:
                        # If no double newlines found, assume no headers and use full response
                        ferry_html = ferry_page
                    return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(ferry_html)}\n\n{ferry_html}"
            
            # If we get here, either connection failed or settings write failed
            error_page = load_html("wifi_config_error.html")
            return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(error_page)}\n\n{error_page}"
            
        except Exception as e:
            print(f"Error processing request: {e}")
            error_page = load_html("wifi_config_error.html")
            return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(error_page)}\n\n{error_page}"
    
    # For GET requests, scan for networks and return the main configuration page
    networks = scan_wifi_networks()
    main_page = load_html("wifi_config.html", networks)
    return f"HTTP/1.1 200 OK\nContent-Type: text/html\nContent-Length: {len(main_page)}\n\n{main_page}"