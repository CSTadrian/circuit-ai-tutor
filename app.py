# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig
from google.oauth2 import service_account
from google.cloud import storage # New import for permanent saving
from pathlib import Path

# --- 1. INITIALIZATION & CONFIG ---
# Replace this with the name of the Bucket you created in Google Cloud Console
BUCKET_NAME = "your-unique-bucket-name-here" 

DATA_DIR = Path("temp_captured_data")
IMAGE_DIR = DATA_DIR / "images"
LOG_FILE = DATA_DIR / "circuit_logs.csv"
DATA_DIR.mkdir(exist_ok=True)
IMAGE_DIR.mkdir(exist_ok=True)

if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    PROJECT_ID = creds_info["project_id"]
    
    # Initialize Vertex AI
    vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
    
    # Initialize Cloud Storage Client
    storage_client = storage.Client(credentials=credentials, project=PROJECT_ID)
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

model = GenerativeModel("gemini-1.5-pro")

st.set_page_config(page_title="AI Circuit Tutor", layout="centered")

# --- 2. SESSION STATE ---
if 'socratic_round' not in st.session_state:
    st.session_state.socratic_round = 0
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = ""
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = {}
if 'saved' not in st.session_state:
    st.session_state.saved = False

# --- 3. UI ---
st.title("🔌 AI Circuit Diagnostic Station")

with st.sidebar:
    st.header("Student Setup")
    student_number = st.text_input("Student Number", placeholder="e.g. 42")
    task_number = st.number_input("Task Number", min_value=1, max_value=10, value=1)
    option_choice = st.radio("Debug Mode", ["1: Direct Debug", "2: Socratic Debug"])
    if st.button("Reset Session"):
        for key in st.session_state.keys(): del st.session_state[key]
        st.rerun()

img_file = st.camera_input("Capture your breadboard circuit")

# --- 4. CLOUD UPLOAD FUNCTION ---
def upload_to_gcs(local_path, cloud_path):
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(cloud_path)
        blob.upload_from_filename(local_path)
        return True
    except Exception as e:
        st.error(f"Cloud Upload Failed: {e}")
        return False

# --- 5. CORE LOGIC ---
if img_file and student_number:
    base_folder = "data2"
    ref_path = os.path.join(base_folder, f"circuit-{task_number}.jpg")

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found.")
    else:
        schematic_img_ai = Image.load_from_file(ref_path)
        student_img_bytes = img_file.getvalue() # RAW IMAGE DATA
        student_img_ai = Image.from_bytes(student_img_bytes)

        # MODE 1 & 2 Logic (Simplified for brevity, same as your logic)
        if not st.session_state.analysis_done:
            if "1" in option_choice:
                with st.spinner("Analyzing..."):
                    prompt = "Analyze this circuit. [OUTPUT FORMAT - JSON ONLY] { 'match_status': '...', 'error_analysis': '...', 'remediation_hints': '...' }"
                    response = model.generate_content([prompt, schematic_img_ai, student_img_ai], 
                                                     generation_config=GenerationConfig(response_mime_type="application/json"))
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
            elif "2" in option_choice:
                # ... (Socratic Logic remains same as previous version)
                pass 

        # --- 6. DISPLAY & PERMANENT SAVE ---
        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            st.subheader(f"Result: {data.get('match_status', 'Unknown')}")
            st.write(data.get('error_analysis', ''))

            if st.button("Finalize and Save to Cloud") and not st.session_state.saved:
                now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                ts = now_hkt.strftime('%Y%m%d_%H%M%S')
                
                # Filenames
                img_fn = f"std_{student_number}_task_{task_number}_{ts}.jpg"
                local_img_path = str(IMAGE_DIR / img_fn)
                
                # 1. Save Raw Image Locally
                with open(local_img_path, "wb") as f:
                    f.write(student_img_bytes)

                # 2. Save CSV Locally
                new_row = {
                    "Timestamp": now_hkt.strftime('%Y-%m-%d %H:%M:%S'),
                    "Student": student_number,
                    "Task": task_number,
                    "Status": data.get('match_status'),
                    "Analysis": data.get('error_analysis'),
                    "Image_File": img_fn
                }
                df = pd.DataFrame([new_row])
                df.to_csv(LOG_FILE, mode='a', header=not LOG_FILE.exists(), index=False)

                # 3. UPLOAD TO GOOGLE CLOUD STORAGE (Permanent)
                success_img = upload_to_gcs(local_img_path, f"images/{img_fn}")
                success_csv = upload_to_gcs(str(LOG_FILE), "logs/circuit_logs.csv")

                if success_img and success_csv:
                    st.success("✅ Data saved permanently to Google Cloud Storage!")
                    st.session_state.saved = True
                    st.balloons()
                else:
                    st.warning("⚠️ Saved locally, but Cloud Upload failed. Check Bucket Name.")

            if st.session_state.saved:
                with open(LOG_FILE, "rb") as f:
                    st.download_button("Download Session Log", f, "logs.csv")
