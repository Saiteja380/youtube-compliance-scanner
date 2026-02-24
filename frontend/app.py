import streamlit as st
import requests
import pandas as pd
import json

st.set_page_config(page_title="Compliance Scanner", layout="wide")

# --- CUSTOM CSS & STATIC FOOTER ---
# FIX: Moved the HTML footer up here so it renders instantly, before the app pauses to process the video.
st.markdown("""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 10px;
        width: 100%;
        text-align: center;
        color: #888;
        font-size: 24px;
        font-weight: bold;
        z-index: 100;
    }
    </style>
    <div class='footer'><span>サイテジャ</span></div>
""", unsafe_allow_html=True)

# --- 1. SESSION STATE INITIALIZATION ---
if "is_scanning" not in st.session_state:
    st.session_state.is_scanning = False
if "final_data" not in st.session_state:
    st.session_state.final_data = None
if "error_msg" not in st.session_state:
    st.session_state.error_msg = None
if "url_val" not in st.session_state:
    st.session_state.url_val = ""
if "kw_val" not in st.session_state:
    st.session_state.kw_val = "వ్యసనం, అలవాటు, ఫోన్ లోనే ఉండడం, పట్టుకుని కూర్చోవడం, అతిగా వాడటం"

# --- 2. THE UI HEADER ---
st.markdown("""
    <h1 style='display: flex; align-items: center; gap: 15px;'>
        <img src='https://upload.wikimedia.org/wikipedia/commons/0/09/YouTube_full-color_icon_%282017%29.svg' width='50'/> 
        Risk & Compliance Scanner
    </h1>
""", unsafe_allow_html=True)

# Render Inputs (Frozen during processing)
url_input = st.text_input("YouTube URL:", value=st.session_state.url_val, disabled=st.session_state.is_scanning)
keywords_input = st.text_input("Keywords (comma-separated):", value=st.session_state.kw_val, disabled=st.session_state.is_scanning)

col1, col2 = st.columns([1, 1])
with col1:
    scan_clicked = st.button("Scan Video", type="primary", disabled=st.session_state.is_scanning)
with col2:
    stop_clicked = st.button("Stop Process", type="secondary", disabled=not st.session_state.is_scanning)

# --- 3. STATE TRANSITIONS ---
if scan_clicked and url_input and keywords_input:
    st.session_state.is_scanning = True
    st.session_state.url_val = url_input
    st.session_state.kw_val = keywords_input
    st.session_state.final_data = None
    st.session_state.error_msg = None
    st.rerun()
    
if stop_clicked:
    st.session_state.is_scanning = False
    st.session_state.error_msg = "Scan manually aborted by user."
    st.rerun()

# --- 4. THE EXECUTION BLOCK ---
if st.session_state.is_scanning:
    progress_bar = st.empty()
    status_text = st.empty()
    
    with st.status("Initializing scan...", expanded=True) as status_ui:
        try:
            payload = {"url": st.session_state.url_val, "custom_keywords": st.session_state.kw_val}
            with requests.post("https://saviomarcus-youtube-scanner-api.hf.space/scan-video/", json=payload, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        msg = json.loads(line.decode('utf-8'))
                        if msg["status"] == "progress":
                            pct = msg.get("percent", 0)
                            step_desc = msg.get("step", "Processing...")
                            
                            status_ui.write(f"[{pct}%] {step_desc}")
                            progress_bar.progress(pct)
                            
                        elif msg["status"] == "complete":
                            st.session_state.final_data = msg["data"]
                            progress_bar.progress(100)
                            status_ui.update(label="Analysis Finished!", state="complete", expanded=False)
                            
            st.session_state.is_scanning = False
            st.rerun()
            
        except requests.exceptions.RequestException as e:
            st.session_state.error_msg = f"Backend Connection Error: {e}"
            st.session_state.is_scanning = False
            st.rerun()

# --- 5. DISPLAY RESULTS CONTAINER ---
if not st.session_state.is_scanning:
    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
        
    if st.session_state.final_data:
        final = st.session_state.final_data
        st.success(f"Processed as: {final['language'].upper()}")
        flags = final.get("flags", [])
        
        if flags:
            st.warning(f"⚠️ Found {len(flags)} matches.")
            df = pd.DataFrame(flags)
            df['timestamp'] = df['timestamp'].apply(lambda x: f"{int(x//60):02}:{int(x%60):02}")
            st.table(df)
        else:
            st.info("✅ No keywords detected.")
            
        with st.expander("📝 View Full Transcript"):
            st.text(final.get("full_transcript", "No transcript available."))