import adafruit_requests as requests
import json
import os
import ssl
from adafruit_datetime import datetime, timedelta
import wifi
import socketpool
import rtc
import time

# TransitLand API Base URL
TRANSITLAND_API_BASE = "https://transit.land/api/v2/rest"

def get_api_key():
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

# Your TransitLand API key
API_KEY = get_api_key()

# Feed Onestop ID and GTFS stop_id
FEED_ONESTOP_ID = "f-nycferry~rt"
STOP_ID = os.getenv("CIRCUITPY_FERRY_STOP_ID")
ROUTE_ID = os.getenv("CIRCUITPY_FERRY_ROUTE_ID")
HEADSIGN = os.getenv("CIRCUITPY_FERRY_HEADSIGN")

# Initialize requests session (will be set up when needed)
requests_session = None

def setup_requests():
    """Set up the requests session with CircuitPython networking."""
    global requests_session
    if requests_session is None:
        pool = socketpool.SocketPool(wifi.radio)
        ssl_context = ssl.create_default_context()
        requests_session = requests.Session(pool, ssl_context=ssl_context)
    return requests_session

def sync_time():
    """Sync the RTC with network time using a simple HTTP time API."""
    try:
        session = setup_requests()
        # Use worldtimeapi.org to get current time for New York
        url = "http://worldtimeapi.org/api/timezone/America/New_York"
        
        # print("Syncing time...")
        response = session.get(url)
        if response.status_code == 200:
            time_data = response.json()
            # Parse the datetime string: "2024-01-15T14:30:45.123456-05:00"
            datetime_str = time_data["datetime"]
            # Extract just the date and time parts (before the timezone offset)
            dt_part = datetime_str.split("+")[0].split("-05:00")[0].split("-04:00")[0]
            if "T" in dt_part:
                date_part, time_part = dt_part.split("T")
                year, month, day = map(int, date_part.split("-"))
                time_components = time_part.split(":")
                hour = int(time_components[0])
                minute = int(time_components[1])
                second = int(float(time_components[2]))  # Handle decimal seconds
                
                # Set the RTC
                current_time = time.struct_time((year, month, day, hour, minute, second, 0, 0, 0))
                rtc.RTC().datetime = current_time
                
                # print(f"Time synced to: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
                return True
        
        # print("Failed to sync time")
        return False
        
    except Exception as e:
        # print(f"Error syncing time: {e}")
        return False

def are_boats_running():
    """Check if boats are currently running (5am to 11pm)."""
    try:
        now = datetime.now()
        current_hour = now.hour
        
        # Boats run from 5am (05:00) to 11pm (23:00)
        # No boats from 11pm (23:00) to 5am (05:00)
        boats_running = 5 <= current_hour < 23
        
        # print(f"Current time: {now.hour:02d}:{now.minute:02d}, Boats running: {boats_running}")
        return boats_running
    except Exception as e:
        # print(f"Error checking boat schedule: {e}")
        # If we can't determine the time, assume boats are running to be safe
        return True

def fetch_next_departure(stop_onestop_id, trip_headsign, route_id):
    """Fetches the next departure for a specific stop, filtered by trip_headsign and route_id."""
    try:
        # Sync time before making API calls if clock is obviously wrong
        now = datetime.now()
        if now.year < 2020:  # Clock is obviously wrong
            # print("Clock needs syncing...")
            sync_time()
        
        # Check if boats are currently running (5am to 11pm)
        if not are_boats_running():
            # print("Boats are not running at this time (11pm-5am). Skipping API call.")
            return None
        
        session = setup_requests()
        stop_key = stop_onestop_id  # Use the stop onestop_id directly
        url = f"{TRANSITLAND_API_BASE}/stops/{stop_key}/departures?api_key={API_KEY}"

        # print(f"Making request to: {url}")
        response = session.get(url)
        if response.status_code != 200:
            # print(f"HTTP Error: {response.status_code}")
            return None
            
        departures_data = response.json()
        
        # Print the entire response for debugging
        # print("=== FULL API RESPONSE ===")
        # print(json.dumps(departures_data))
        # print("=== END API RESPONSE ===")

        stops = departures_data.get("stops", [])
        if not stops:
            # print(f"No stop information found for stop_key: {stop_key}")
            return None  # Return None if no stop information is found

        # print(f"Found {len(stops)} stops in response")
        all_departures = stops[0].get("departures", [])
        # print(f"Found {len(all_departures)} total departures")

        # Print details about each departure for debugging
        # print("=== ALL DEPARTURES ===")
        # for i, departure in enumerate(all_departures):
        #     trip_info = departure.get("trip", {})
        #     route_info = trip_info.get("route", {})
        #     print(f"Departure {i+1}:")
        #     print(f"  Trip Headsign: {trip_info.get('trip_headsign')}")
        #     print(f"  Route ID: {route_info.get('onestop_id')}")
        #     print(f"  Scheduled: {departure.get('departure', {}).get('scheduled')}")
        #     print(f"  Estimated: {departure.get('departure', {}).get('estimated')}")
        #     print("---")

        matching_departures = [
            departure for departure in all_departures
            if (departure.get("trip", {}).get("trip_headsign") == trip_headsign and
                departure.get("trip", {}).get("route", {}).get("onestop_id") == route_id)
        ]

        # print(f"Looking for trip_headsign: '{trip_headsign}' and route_id: '{route_id}'")
        # print(f"Found {len(matching_departures)} matching departures")

        if not matching_departures:
            # print(f"No departures found for stop {stop_key} with trip_headsign '{trip_headsign}' and route_id '{route_id}'.")
            return None  # Return None if no matching departures are found

        # Sort matching departures by scheduled time and take the first (next) departure
        next_departure = sorted(matching_departures, key=lambda x: x["departure"].get("scheduled"))[0]

        # Extract and print the estimated departure time
        estimated_departure = next_departure.get("departure", {}).get("estimated")

        # print(f"Next estimated departure time for '{trip_headsign}' on route '{route_id}' at stop {stop_key}:")
        # print(estimated_departure)  # Print the raw estimated value
        return estimated_departure

    except Exception as e:
        # print(f"Error fetching departures: {e}")
        return None  # Return None in case of an error


def time_to_next_departure(estimated_departure):
    """Calculates the time remaining until the next departure."""
    if estimated_departure is None:
        # print("No boats in the next hour.")
        return None

    try:
        # print(f"=== TIME CALCULATION DEBUG ===")
        # print(f"Estimated departure string: {estimated_departure}")
        
        # For CircuitPython, we'll use a simpler time parsing approach
        # Parse the HH:MM:SS format manually
        time_parts = estimated_departure.split(":")
        departure_hour = int(time_parts[0])
        departure_minute = int(time_parts[1])
        departure_second = int(time_parts[2]) if len(time_parts) > 2 else 0
        
        # print(f"Parsed departure time: {departure_hour}:{departure_minute}:{departure_second}")

        # Get current time
        now = datetime.now()
        # print(f"Current datetime: {now}")
        # print(f"Current time parts: {now.hour}:{now.minute}:{now.second}")
        
        # Create departure datetime for today
        departure_datetime = datetime(
            now.year, now.month, now.day,
            departure_hour, departure_minute, departure_second
        )
        
        # print(f"Departure datetime (today): {departure_datetime}")

        # Handle cases where departure time is on the next day
        if departure_datetime < now:
            # print("Departure time is in the past, adding 1 day")
            departure_datetime = departure_datetime + timedelta(days=1)
            # print(f"Departure datetime (next day): {departure_datetime}")
        # else:
            # print("Departure time is today")

        time_diff = departure_datetime - now
        # print(f"Time difference: {time_diff}")
        # print(f"Time difference in seconds: {time_diff.total_seconds()}")

        # Extract minutes remaining
        minutes_remaining = int(time_diff.total_seconds() // 60) + 1
        # print(f"Minutes remaining: {minutes_remaining}")
        # print(f"=== END TIME CALCULATION DEBUG ===")

        return minutes_remaining

    except (ValueError, TypeError, AttributeError) as e:
        # print(f"Error calculating time difference: {e}")
        return None


if __name__ == "__main__":
    # Example usage:
    next_departure_time = fetch_next_departure(STOP_ID, HEADSIGN, ROUTE_ID)
    minutes_left = time_to_next_departure(next_departure_time)

    if minutes_left is not None:
        print(f"Time to next departure: {minutes_left} minutes")
    else:
        print("No departure data available")