# 🚀 Advanced C2 Keylogger (Cybersecurity Lab)

This project simulates an **Advanced Command & Control (C&C) Keylogger** system, developed as a cybersecurity laboratory exercise. Its purpose is to collect various events (**keystrokes, audio, screenshots**) from a victim machine, encrypt the data, exfiltrate it via HTTP to an attacker's server, and visualize the logs in real-time using a Streamlit dashboard.

---

## 🏗️ Project Structure

The project is divided into three main components, each residing in its own top-level folder:

### 1. 🖥️ Target (Victim) (Folder `victime/`)

| File | Role |
| :--- | :--- |
| `keylogger.py` | The core keylogger logic: capture, encryption, and dispatch. |
| `sender.py` | Module managing the data exfiltration (HTTP POST or TCP Socket). |
| **`config.py`** | **CRITICAL:** Centralized configuration file. Must be edited with the Attacker's IP. |

### 2. 🗄️ Attacker (C2 Server Receiver) (Folder `attaquant/`)

| File/Folder | Role |
| :--- | :--- |
| `server_http.py` | The **Flask server** that receives and decrypts HTTP POST requests from the victim. |
| `stockage/` | **Storage Folder**: Stores the final decrypted logs. (Ignored by Git). |

### 3. 📊 Controller (C2 Dashboard) (Folder `controller/`)

| File | Role |
| :--- | :--- |
| `dashboard.py` | The **Streamlit Dashboard** (the C2) for real-time visualization and analysis. |

### 4. 📄 Root Configuration

| File | Rôle |
| :--- | :--- |
| `requirements.txt` | **Single file** listing all necessary Python dependencies for Cible, Attaquant, and Controller. |
| **`.gitignore`** | Excludes temporary Python files, virtual environments (`venv`), and all log/storage directories. |

---

## ⚙️ Compilation, Installation, and Launch

### ⚠️ Prerequisites

* **Python 3.x** installed.
* **Virtual Environments** (recommended).
* **PyAudio** may require specific system libraries (e.g., `portaudio` on Linux) before the `pip install`.

### Step 1: Initial Setup and C2 Configuration

1.  **Update C2 IP Address:**
    Edit the file **`victime/config.py`** and replace the default IP in the `SERVER_URL` variable with the **actual IP address** of your attacker VM (e.g., `http://192.168.1.10:5000/log`).

2.  **Install Dependencies:**
    Using the single root `requirements.txt` file, install all dependencies in the respective virtual environments.

    ```bash
    # Create and activate environment (e.g., for Attacker and Controller)
    python3 -m venv venv_project
    source venv_project/bin/activate

    # Install all dependencies using the root file
    pip install -r requirements.txt
    ```

3.  **Launch the C2 Server and Controller:**
    Launch the receiver and the dashboard in separate terminals.

    ```bash
    # Terminal 1: Launch the Flask Server (Receiver)
    cd attaquant/
    python server.py
    
    # Terminal 2: Launch the Streamlit Dashboard (Controller Interface)
    cd controller/
    streamlit run controller.py
    ```

### Step 2: Launching the Keylogger (Victim)

Execute the Python script on the target machine:

```bash
cd cible/
python keylogger.py
```

-----

## 📦 Creating a Standalone Executable (`.exe` or `.pkg`)

To run the keylogger without requiring Python installation on the victim machine, use **PyInstaller**. This step is typically done on the operating system matching the victim.

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
| **macOS (`.pkg`)** | `pyinstaller --onefile --add-data "config.py:." keylogger.py` | `dist/keylogger` |

**Command Breakdown:**

  * **`--onefile`**: Packages everything into a single executable file.
  * **`--windowed` (Windows only)**: Prevents the console window from opening, running the application silently in the background.
  * **`--add-data`**: **Crucial step\!** Embeds the `config.py` file into the executable.

The final executable file will be located in the **`dist`** folder (e.g., `victime/dist/keylogger.exe`).

-----

## ✨ Implemented Features

### 1\. Multi-Event Collection

  * **Keystrokes (`keyboard`)**: Records all pressed keys.
  * **Audio Clips (`audio`)**: Periodic recording of a **5-second** clip from the microphone.
  * **Screenshots (`screenshot`)**: Periodic capture of the primary screen, taken every **15 seconds**.

### 2\. Security and Resilience

  * **Local Encryption**: All data is immediately encrypted using **Fernet** and stored locally.
  * **Event Buffer**: Events are buffered locally (`logs/buffer.jsonl`) and re-sent automatically if the C2 server is temporarily unreachable, ensuring data persistence.

### 3\. C2 Dashboard (Streamlit)

  * **Live Mode**: Automatic data refresh for real-time monitoring.
  * **Text Reconstruction**: Rebuilds the user's typed text from keystrokes (handling special keys like backspace and enter).
  * **Media Visualization**: Includes features for audio playback and visualization of decoded screenshots.

### 4\. Extensions (Ready for Implementation)

  * **Communication Switch (`switch_mode`)**: Framework ready for implementing protocol switching (e.g., HTTP to TCP).
  * **Remote Commands**: Potential to extend the Flask API to send specific commands back to the victim.

