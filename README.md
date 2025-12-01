# 🚀 Advanced C2 Keylogger (Cybersecurity Lab)

This project simulates an **Advanced Command & Control (C&C) Keylogger** system, developed as a cybersecurity laboratory exercise. Its purpose is to collect various events (**keystrokes, audio, screenshots**) from a victim machine, encrypt the data, exfiltrate it via HTTP to an attacker's server, and visualize the logs in real-time using a Streamlit dashboard.



---

## 🏗️ Project Structure

The project is divided into three main components, each residing in its own folder to simulate the network architecture:

### 1. 🖥️ Target (Victim) (Folder `cible/`)

Contains the Keylogger itself, intended to be executed on the victim's machine.

| File | Role |
| :--- | :--- |
| `keylogger.py` | The core keylogger logic: keystroke, audio, and screenshot capture, encryption, and dispatch. |
| `sender.py` | Module managing the data exfiltration (HTTP POST or TCP Socket) to the C2 server. |
| `config.py` | Centralized configuration file (Server URL, intervals, communication mode). |
| `requirements.txt` | Python dependencies required for the keylogger (e.g., `pynput`, `pyaudio`, `mss`, `cryptography`). |

### 2. 🗄️ Attacker (C2 Server) (Folder `attaquant/`)

Contains the C&C server (Flask REST API) and the real-time visualization interface (Streamlit).

| File/Folder | Role |
| :--- | :--- |
| `server.py` | The **Flask server** that receives HTTP POST requests from the victim. It handles data storage. |
| `controller.py` | The **Streamlit Dashboard** (the C2) for real-time log visualization and analysis. |
| `stockage/` | **Storage Folder**: Stores the decrypted logs, organized by `victim_id` (`events.jsonl`). |
| `requirements.txt` | Python dependencies for the attacker (e.g., `flask`, `streamlit`, `pandas`, `waitress`). |

### 3. ⚙️ Configuration (File `config.py`)

This file holds critical constants used by both components:

* **`SERVER_URL`**: The complete URL of the Flask server (`http://<ATTACKER_IP>:5000/log`).
* **`SEND_INTERVAL`**: Frequency of data packets sent (e.g., 5 seconds).
* **`AUDIO_RATE`**, **`SCREENSHOT_INTERVAL`**, etc.

---

## ⚙️ Build and Installation

This project is written in Python. Installation requires setting up virtual environments and installing dependencies.

### ⚠️ Prerequisites

* **Python 3.x** installed.
* **Virtual Environments** (recommended).
* **PyAudio** may require specific system libraries (e.g., `portaudio` on Linux) before the `pip install`.

### Step 1: C2 Server Configuration (Attacker)

1.  **Create and activate the virtual environment:**
    ```bash
    python3 -m venv venv_attacker
    source venv_attacker/bin/activate  # Linux/macOS
    .\venv_attacker\Scripts\activate   # Windows
    ```

2.  **Install dependencies:**
    ```bash
    cd attaquant/
    pip install -r requirements.txt
    ```

3.  **Launch the Flask Server:**
    The server must listen on the IP accessible by the victim (usually the host machine's IP or the VM's internal network IP).
    ```bash
    python server.py
    ```
    *Note: The server will run on `http://0.0.0.0:5000`.*

4.  **Launch the Streamlit Dashboard (Controller):**
    In a **separate terminal** (still within `venv_attacker` and the `attaquant/` folder):
    ```bash
    streamlit run controller.py
    ```

### Step 2: Keylogger Configuration (Target)

1.  **Update C2 IP Address:**
    Edit the file `cible/config.py` and replace `127.0.0.1` with the **actual IP address** of the attacker's server.

2.  **Install dependencies:**
    *If using a separate VM for the victim, repeat the virtual environment setup.*
    ```bash
    cd cible/
    pip install -r requirements.txt
    ```

3.  **Launch the Keylogger:**
    ```bash
    python keylogger.py
    ```
    The keylogger will immediately begin collecting and sending events to the configured C2 address.

---

## ✨ Implemented Features

The C2 Keylogger system implements several advanced features for data collection and analysis:

### 1. Multi-Event Collection

The keylogger simultaneously captures three types of events, each in a separate thread:

* **Keystrokes (`keyboard`)**: Records all pressed keys (characters and special keys like `Key.enter`).
* **Audio Clips (`audio`)**: Periodic recording of a **5-second** clip from the victim's microphone.
* **Screenshots (`screenshot`)**: Periodic capture of the primary screen, taken every **15 seconds**.

### 2. Security and Resilience

* **Local Encryption**: All collected data is immediately encrypted using **Fernet** (`cryptography`) and stored in the local log file (`logs/encrypted_log.jsonl`) on the victim's machine.
* **Event Buffer**: In case of failed HTTP communication (e.g., the attacker's server is down), events are stored in a local **buffer** (`logs/buffer.jsonl`) and are prioritized for re-submission in the next successful packet.

### 3. C2 Dashboard (Streamlit)

The attacker's interface (`controller.py`) provides a comprehensive and interactive view of the collected data:

* **Live Mode**: A `🔴 MODE LIVE` toggle enables a 2-second automatic refresh of the dashboard.
* **Metrics**: Displays the total number of events, keystrokes, audio clips, and screenshots collected.
* **Text Reconstruction**: The `reconstruct_text` function rebuilds the keystroke sequence, handling control keys (`backspace`, `enter`, `space`) to display the victim's typed text.
* **Audio Playback**: Raw audio clips (PCM 16-bit Base64) are decoded, provided with a WAV header, and are playable directly within the Streamlit interface.
* **Screenshot Visualization**: Images (PNG Base64) are decoded and displayed in a gallery format (3 images per row).
* **Graphical Analysis**: Charts showing activity over time and the frequency of the most used keys.

### 4. Extensions (Ready for Implementation)

The framework is ready for the implementation of additional functionalities (as required by the lab exercise):

* **Communication Switch (`switch_mode`)**: Logic is ready to be built around `INITIAL_COMM_MODE` in `config.py` to allow switching exfiltration protocols (HTTP by default, TCP/Socket option ready for implementation).
* **Remote Commands**: The Flask API can be extended to send specific commands back to the victim (e.g., stop audio capture, change the screenshot interval).