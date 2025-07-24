import os
import time
import wifi
import socketpool
import displayio
from modules.wifi_config import handle_wifi_config_request
from modules.ferry_config import handle_ferry_config, load_html as load_ferry_html
from modules.print import display_ferry_config, display_boat_idle
# Add imports for matrix display and ferry data
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_display_text import label
import terminalio
from modules.transitland import fetch_next_departure, time_to_next_departure
# Add bitmap font support for custom fonts
try:
    from adafruit_bitmap_font import bitmap_font
    CUSTOM_FONT_AVAILABLE = True
except ImportError:
    CUSTOM_FONT_AVAILABLE = False
    # print("Custom font support not available")

def get_secrets():
    """Read API key from secrets.toml file."""
    try:
        # Simple parser for secrets.toml since CircuitPython may not have toml module
        with open("secrets.toml", "r") as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if line.startswith("CIRCUITPY_API_KEY"):
                # Parse line like: CIRCUITPY_API_KEY = "value"
                if "=" in line:
                    value = line.split("=", 1)[1].strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    return value
        return ""
    except Exception as e:
        print(f"Error reading secrets.toml: {e}")
        return ""

def has_internet():
    try:
        pool = socketpool.SocketPool(wifi.radio)
        # Try to resolve a well-known host (Google DNS)
        addr_info = pool.getaddrinfo("8.8.8.8", 80)
        return True
    except Exception as e:
        # print(f"No internet connection: {e}")
        return False

def serve_page(client, html):
    response = f"HTTP/1.1 200 OK\nContent-Type: text/html\n\n{html}"
    client.send(response.encode("utf-8"))

def create_server(pool):
    """Create server socket."""
    # Try to stop any existing AP
    try:
        wifi.radio.stop_ap()
    except:
        pass
    
    # Start fresh AP
    wifi.radio.start_ap(ssid="Commute Clock NYC", password="ferry123", channel=6)
    print("AP started at 192.168.4.1")
    print("Connect to 'Commute Clock NYC' WiFi (password: ferry123) to configure")
    
    # Create and bind server
    server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    server.setblocking(True)
    server.bind(("192.168.4.1", 80))
    server.listen(1)
    return server

def display_ferry_times():
    """Display ferry countdown times on the matrix after configuration is complete."""
    
    try:
        # Initialize display components ONCE at the start
        from adafruit_matrixportal.matrix import Matrix
        from adafruit_display_text import label
        
        matrix = Matrix(bit_depth=4)
        
        # Clear the display buffer to prevent artifacts
        matrix.display.root_group = None
        matrix.display.refresh()
        
        text_group = displayio.Group()
        
        # Load fonts once
        number_font = terminalio.FONT
        min_font = terminalio.FONT
        
        if CUSTOM_FONT_AVAILABLE:
            try:
                number_font = bitmap_font.load_font("fonts/MatrixChunky8.bdf")
            except Exception:
                pass
        
        # Get ferry settings once
        ferry_color = os.getenv("CIRCUITPY_FERRY_COLOR", "teal")
        stop_id = os.getenv("CIRCUITPY_FERRY_STOP_ID")
        route_id = os.getenv("CIRCUITPY_FERRY_ROUTE_ID") 
        headsign = os.getenv("CIRCUITPY_FERRY_HEADSIGN")
        
        # Load boat bitmap once
        boat_bitmap = None
        boat_tilegrid = None
        
        try:
            # Try to load boat image
            try:
                boat_bitmap = displayio.OnDiskBitmap(f"boats/{ferry_color}.bmp")
            except (OSError, ValueError):
                try:
                    boat_bitmap = displayio.OnDiskBitmap(f"boats/{ferry_color}.png")
                except (OSError, ValueError):
                    if ferry_color != "teal":
                        try:
                            boat_bitmap = displayio.OnDiskBitmap("boats/teal.bmp")
                        except (OSError, ValueError):
                            try:
                                boat_bitmap = displayio.OnDiskBitmap("boats/teal.png")
                            except (OSError, ValueError):
                                pass
            
            if boat_bitmap:
                boat_tilegrid = displayio.TileGrid(
                    boat_bitmap,
                    pixel_shader=boat_bitmap.pixel_shader
                )
                boat_tilegrid.y = 2  # Fixed y position
                text_group.append(boat_tilegrid)
        except Exception:
            pass
        
        # Create text labels once
        number_label = label.Label(
            number_font,
            text="0",
            color=0xFFFFFF,
            scale=2,
            x=2,
            y=24
        )
        
        min_label = label.Label(
            min_font,
            text="min",
            color=0xFFFFFF,
            scale=1,
            x=20,  # Will be adjusted based on number width
            y=26
        )
        
        # Don't add the labels initially - start in idle mode
        # Set the display group once
        matrix.display.root_group = text_group
        
        print("Starting ferry time display...")
        
        # Current state tracking - start in idle mode to avoid showing "0 min"
        current_mode = "boat_idle"
        
        # Initialize boat position for idle mode
        if boat_tilegrid:
            display_width = 64
            display_height = 32
            boat_tilegrid.x = (display_width - boat_bitmap.width) // 2
            boat_tilegrid.y = (display_height - boat_bitmap.height) // 2
        
        while True:
            try:
                # Fetch ferry data
                next_departure_time = fetch_next_departure(stop_id, headsign, route_id)
                minutes_left = time_to_next_departure(next_departure_time)
                
                if minutes_left is not None and minutes_left > 0:
                    # Switch to ferry time mode if needed
                    if current_mode != "ferry_time":
                        # Show the ferry time elements
                        if boat_tilegrid in text_group:
                            text_group.remove(boat_tilegrid)
                        if number_label not in text_group:
                            text_group.append(number_label)
                        if min_label not in text_group:
                            text_group.append(min_label)
                        if boat_tilegrid:
                            text_group.append(boat_tilegrid)
                        current_mode = "ferry_time"
                    
                    # Update number text
                    number_label.text = str(minutes_left)
                    
                    # Calculate and update boat position if available
                    if boat_tilegrid:
                        display_width = 64
                        boat_width = boat_bitmap.width
                        clamped_minutes = max(1, min(30, minutes_left))
                        
                        left_pos = 2
                        right_pos = display_width - boat_width - 2
                        boat_x = left_pos + (right_pos - left_pos) * (30 - clamped_minutes) / 29
                        boat_tilegrid.x = int(boat_x)
                        # Move boat up 8 rows when showing time
                        boat_tilegrid.y = 2
                    
                    # Update min label position based on number width
                    base_number_width = number_label.bounding_box[2]
                    scaled_number_width = base_number_width * 2
                    min_label.x = 2 + scaled_number_width
                    
                else:
                    # Switch to boat idle mode if needed
                    if current_mode != "boat_idle":
                        # Hide text labels, show only boat
                        if number_label in text_group:
                            text_group.remove(number_label)
                        if min_label in text_group:
                            text_group.remove(min_label)
                        if boat_tilegrid and boat_tilegrid not in text_group:
                            text_group.append(boat_tilegrid)
                        current_mode = "boat_idle"
                    
                    # Center the boat for idle display
                    if boat_tilegrid:
                        display_width = 64
                        display_height = 32
                        boat_tilegrid.x = (display_width - boat_bitmap.width) // 2
                        boat_tilegrid.y = (display_height - boat_bitmap.height) // 2
                
                # Sleep for 45 seconds
                time.sleep(45)
                
            except Exception as e:
                print(f"Error updating ferry display: {e}")
                # Show error on display
                number_label.text = "ERR"
                if number_label not in text_group:
                    text_group.append(number_label)
                if min_label in text_group:
                    text_group.remove(min_label)
                time.sleep(60)
                
    except Exception as e:
        print(f"Error initializing matrix display: {e}")
        import traceback
        traceback.print_exception(e)
        print("Falling back to console-only mode...")
        
        # Fall back to console-only mode
        while True:
            try:
                stop_id = os.getenv("CIRCUITPY_FERRY_STOP_ID")
                route_id = os.getenv("CIRCUITPY_FERRY_ROUTE_ID") 
                headsign = os.getenv("CIRCUITPY_FERRY_HEADSIGN")
                
                next_departure_time = fetch_next_departure(stop_id, headsign, route_id)
                minutes_left = time_to_next_departure(next_departure_time)
                
                if minutes_left is not None:
                    print(f"Next ferry in {minutes_left} minutes")
                else:
                    print("No ferry data available")
                    try:
                        display_boat_idle()
                    except Exception as e:
                        pass
                    
                time.sleep(45)
            except Exception as e:
                print(f"Error fetching ferry data: {e}")
                import traceback
                traceback.print_exception(e)
                time.sleep(60)


def main():
    # Get environment variables with default values
    ssid = os.getenv("CIRCUITPY_WIFI_SSID", "")
    password = os.getenv("CIRCUITPY_WIFI_PASSWORD", "")
    ferry_route_id = os.getenv("CIRCUITPY_FERRY_ROUTE_ID", "")
    ferry_stop_id = os.getenv("CIRCUITPY_FERRY_STOP_ID", "")
    ferry_headsign = os.getenv("CIRCUITPY_FERRY_HEADSIGN", "")
    api_key = get_secrets()  # Read API key from secrets.toml
    
    # Debug: Print all configuration values
    print("=== CONFIGURATION DEBUG ===")
    print(f"SSID: '{ssid}' (length: {len(ssid)})")
    print(f"Password: {'*' * len(password)} (length: {len(password)})")
    print(f"Ferry Route ID: '{ferry_route_id}' (length: {len(ferry_route_id)})")
    print(f"Ferry Stop ID: '{ferry_stop_id}' (length: {len(ferry_stop_id)})")
    print(f"Ferry Headsign: '{ferry_headsign}' (length: {len(ferry_headsign)})")
    print(f"API Key (from secrets.toml): '{api_key[:10] if len(api_key) >= 10 else api_key}...' (length: {len(api_key)})")
    print("=== END CONFIGURATION DEBUG ===")
    
    # Start the configuration server
    pool = socketpool.SocketPool(wifi.radio)
    server = create_server(pool)
    if not server:
        print("Failed to create server")
        return

    print("Server running...")

    # Determine initial state based on environment variables
    if not ssid or not password:
        state = "wifi_config"
        print("Starting in WiFi config mode")
        # Show boat idle display during WiFi configuration
        display_boat_idle()
    else:
        state = "ferry_config"
        print("Starting in ferry config mode")
        # Show boat idle display during ferry configuration
        display_boat_idle()

    while True:
        try:
            # Wait for client connections
            server.settimeout(1.0)  # 1 second timeout
            try:
                client, addr = server.accept()
                client.setblocking(True)
            except OSError:
                # Timeout occurred, continue waiting
                continue
                
            request_buffer = bytearray(1024)
            bytes_received = client.recv_into(request_buffer)
            if bytes_received > 0:
                request = str(request_buffer[:bytes_received], "utf-8")
                # print(f"Request: {request}")

                # --- WiFi Config State ---
                if state == "wifi_config":
                    response = handle_wifi_config_request(request)
                    
                    # Send response in chunks for better mobile compatibility
                    try:
                        response_bytes = response.encode("utf-8")
                        # Send in smaller chunks for mobile browsers
                        chunk_size = 1024
                        for i in range(0, len(response_bytes), chunk_size):
                            chunk = response_bytes[i:i + chunk_size]
                            client.send(chunk)
                            time.sleep(0.01)  # Small delay between chunks
                    except Exception as e:
                        print(f"Error sending response: {e}")
                        # Fallback to single send
                        try:
                            client.send(response.encode("utf-8"))
                        except:
                            pass
                    # Check if we got the ferry config page (indicating successful WiFi connection)
                    if "Ferry Configuration" in response or "NYC Ferry Configuration" in response:
                        ssid = os.getenv("CIRCUITPY_WIFI_SSID", "")
                        password = os.getenv("CIRCUITPY_WIFI_PASSWORD", "")
                        if ssid and password:
                            state = "ferry_config"
                            print("Transitioning to ferry config mode")
                            # Show boat idle display during ferry configuration
                            display_boat_idle()

                # --- Ferry Config State ---
                elif state == "ferry_config":
                    response = handle_ferry_config(request)
                    # print(f"Response: {response}")
                    
                    # Send response in chunks for better mobile compatibility
                    try:
                        response_bytes = response.encode("utf-8")
                        # Send in smaller chunks for mobile browsers
                        chunk_size = 1024
                        for i in range(0, len(response_bytes), chunk_size):
                            chunk = response_bytes[i:i + chunk_size]
                            client.send(chunk)
                            time.sleep(0.01)  # Small delay between chunks
                    except Exception as e:
                        print(f"Error sending response: {e}")
                        # Fallback to single send
                        try:
                            client.send(response.encode("utf-8"))
                        except:
                            pass
                    
                    # Use same logic as ferry_config.py to detect successful form submission
                    is_ferry_form_submission = False
                    if "POST" in request:
                        try:
                            # Extract the body from the request (same as ferry_config.py)
                            body = request.split("\r\n\r\n")[1]
                            # Parse the form data
                            params = dict(pair.split("=") for pair in body.split("&"))
                            
                            # URL decode the values (simplified version)
                            route_id = params.get("route", "").replace("+", " ")
                            stop_id = params.get("stop_id", "").replace("+", " ")
                            headsign = params.get("headsign", "").replace("+", " ")
                            
                            # Same check as ferry_config.py: all three must have values
                            is_ferry_form_submission = bool(route_id and stop_id and headsign)
                            # print(f"Form values: route='{route_id}', stop_id='{stop_id}', headsign='{headsign}'")
                            # print(f"Form submission detected: {is_ferry_form_submission}")
                            
                        except Exception as e:
                            # print(f"Error parsing form data: {e}")
                            pass
                    
                    if is_ferry_form_submission:
                        # print("Ferry form submitted with valid data!")
                        
                        # Ensure the response is fully sent before any delays
                        try:
                            # Force the response to be sent immediately
                            time.sleep(0.1)  # Small delay to ensure send completes
                        except:
                            pass
                        
                        # Give mobile browsers more time to receive and display the success page
                        # Mobile browsers often need longer to process AP responses
                        # print("Waiting 8 seconds for client to receive success page...")
                        time.sleep(8)
                        
                        # Close client first
                        try:
                            client.close()
                        except:
                            pass
                        
                        # Stop AP
                        try:
                            wifi.radio.stop_ap()
                            print("AP stopped. Setup complete.")
                        except Exception as e:
                            print(f"Error stopping AP: {e}")
                        
                        print("Connecting to WiFi for ferry data...")
                        
                        # Get latest WiFi credentials
                        ssid = os.getenv("CIRCUITPY_WIFI_SSID")
                        password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
                        
                        try:
                            # print(f"Attempting to connect to WiFi SSID: {ssid}")
                            wifi.radio.connect(ssid, password)
                            print("Connected to WiFi successfully")
                            
                            if has_internet():
                                print("Internet connection confirmed")
                                try:
                                    server.close()
                                    print("Server closed successfully")
                                except Exception as e:
                                    print(f"Error closing server: {e}")
                                
                                print("Starting ferry times display after WiFi connection...")
                                display_ferry_times()
                                return  # Exit main function
                            else:
                                print("No internet connection available")
                                return
                        except Exception as e:
                            print(f"Failed to connect to WiFi: {e}")
                            return
                        
            # Close client if we haven't already
            try:
                client.close()
            except:
                pass
                    
        except Exception as e:
            print(f"Error handling request: {e}")
            try:
                client.close()
            except:
                pass

if __name__ == "__main__":
    main()