from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_display_text import label
import terminalio
import displayio
import board

# Initialize MatrixPortal as a global variable with higher bit depth
matrixportal = MatrixPortal(bit_depth=4)

def display_boat_idle():
    """
    Display a boat image in the center of the 64x32 matrix during idle states.
    This is shown during configuration and when no ferry data is available.
    """
    # print("Displaying boat idle state...")
    
    try:
        # Initialize a new MatrixPortal instance specifically for boat display
        from adafruit_matrixportal.matrix import Matrix
        
        # Create matrix display with higher bit depth for more vibrant colors
        matrix = Matrix(bit_depth=4)  # More colors, more vibrant
        
        # Optional: Increase brightness for more vibrant colors (0.0 to 1.0)
        # matrix.display.brightness = 0.8  # Uncomment if you want brighter display
        
        # Create a new group for the boat display
        boat_group = displayio.Group()
        
        # Get the ferry color from settings, default to teal
        import os
        ferry_color = os.getenv("CIRCUITPY_FERRY_COLOR", "teal")
        # print(f"Using ferry color: {ferry_color}")
        
        # Try to load the boat bitmap (prefer .bmp for better compatibility)
        boat_bitmap = None
        
        # Try the specified color first
        try:
            boat_bitmap = displayio.OnDiskBitmap(f"boats/{ferry_color}.bmp")
            # print(f"Loaded {ferry_color}.bmp")
        except (OSError, ValueError) as e:
            # print(f"Could not load {ferry_color}.bmp: {e}")
            # Fallback to .png if .bmp doesn't work
            try:
                boat_bitmap = displayio.OnDiskBitmap(f"boats/{ferry_color}.png")
                # print(f"Loaded {ferry_color}.png")
            except (OSError, ValueError) as e:
                # print(f"Could not load {ferry_color}.png: {e}")
                
                # If specified color fails and it's not teal, try teal as backup
                if ferry_color != "teal":
                    # print("Falling back to teal boat")
                    try:
                        boat_bitmap = displayio.OnDiskBitmap("boats/teal.bmp")
                        # print("Loaded teal.bmp (fallback)")
                    except (OSError, ValueError) as e:
                        # print(f"Could not load teal.bmp: {e}")
                        try:
                            boat_bitmap = displayio.OnDiskBitmap("boats/teal.png")
                            # print("Loaded teal.png (fallback)")
                        except (OSError, ValueError) as e:
                            # print(f"Could not load teal.png: {e}")
                            # print("Could not load any boat image, falling back to text")
                            display_ferry_config("BOAT")
                            return
                else:
                    # print("Could not load any boat image, falling back to text")
                    display_ferry_config("BOAT")
                    return
        
        # Create a TileGrid to display the bitmap
        boat_tilegrid = displayio.TileGrid(
            boat_bitmap,
            pixel_shader=boat_bitmap.pixel_shader
        )
        
        # Center the boat on the 64x32 display
        # Assuming the boat image is small, we'll center it
        display_width = 64
        display_height = 32
        boat_tilegrid.x = (display_width - boat_bitmap.width) // 2
        boat_tilegrid.y = (display_height - boat_bitmap.height) // 2
        
        # Add the boat to the group and display it
        boat_group.append(boat_tilegrid)
        matrix.display.root_group = boat_group
        
        # print(f"Boat image displayed at position ({boat_tilegrid.x}, {boat_tilegrid.y})")
        # print(f"Boat bitmap size: {boat_bitmap.width}x{boat_bitmap.height}")
        
    except Exception as e:
        # print(f"Error displaying boat: {e}")
        # import traceback
        # traceback.print_exception(e)
        # Fallback to text display
        try:
            display_ferry_config("BOAT")
        except:
            # print("Even fallback text display failed")
            pass

def display_ferry_config(ferry_config):
    """
    Display the ferry configuration value on the MatrixPortal LED display.
    
    Args:
        ferry_config (str): The ferry configuration value to display
    """
    # print(f"Ferry Configuration: {ferry_config}")
    
    # Add text to the display
    matrixportal.add_text(
        text_font=terminalio.FONT,
        text_position=(5, 8),  # y=8 centers vertically on 16px tall display
        text_color=0xFFFFFF
    )
    
    # Set the text
    matrixportal.set_text(f"Ferry: {ferry_config}")
    
    # Keep the display active
    while True:
        matrixportal.refresh()
