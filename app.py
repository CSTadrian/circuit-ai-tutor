# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

# AI & Google Auth Imports
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig
from google.oauth2 import service_account
from googleapiclient.discovery import build
# Use MediaIoBaseUpload for memory-based uploads (more reliable on Streamlit)
from googleapiclient.http import MediaIoBaseUpload 

# --- 1. CONFIGURATION ---
# IMPORTANT: Paste your Folder ID here (from the URL of your Drive folder)
DRIVE_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"

st.set_page_config(page_title="AI Circuit Tutor", layout="centered")

# --- 2. INITIALIZE SERVICES ---
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    PROJECT_ID = creds_info["project_id"]
    
    # Initialize Vertex AI (Gemini)
    vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
    # FIX: Changed from 2.5 to 1.5 (current stable version)
    model = GenerativeModel("gemini-2.5-pro") 
    
    # Initialize Google Drive Service
    drive_service = build('drive', 'v3', credentials=credentials)
else:
    st.error("GCP Service Account secrets not found in Streamlit Cloud!")
    st.stop()

# --- 3. SESSION STATE ---
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = {}
if 'saved' not in st.session_state:
    st.session_state.saved = False

# --- 4. HELPER FUNCTIONS ---
def upload_to_drive(file_bytes, file_name, mime_type='image/jpeg'):
    """Uploads bytes directly to Google Drive."""
    try:
        # Ensure DRIVE_FOLDER_ID is just the ID string
        folder_id = DRIVE_FOLDER_ID.split('/')[-1] 
        
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        
        file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id'
        ).execute()
        
        return file.get('id')
    except Exception as e:
        # This will show you if it's a Permission (403) or ID (404) error
        st.error(f"Drive Upload Error: {e}")
        return None

# --- 5. UI LAYOUT ---
st.title("🔌 AI Circuit Diagnostic Station")

with st.sidebar:
    st.header("Student Setup")
    student_number = st.text_input("Student Number", placeholder="e.g. 42")
    task_number = st.number_input("Task Number", min_value=1, max_value=10, value=1)
    option_choice = st.radio("Debug Mode", ["1: Direct Debug", "2: Socratic Debug"])
    
    if st.button("Reset Session"):
        for key in ["analysis_done", "current_analysis", "saved"]:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

img_file = st.camera_input("Capture your breadboard circuit")

# --- 6. CORE LOGIC ---
if img_file and student_number:
    ref_path = f"data2/circuit-{task_number}.jpg"

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found in repository.")
    else:
        # Load images
        schematic_img_ai = Image.load_from_file(ref_path)
        student_img_bytes = img_file.getvalue()
        student_img_ai = Image.from_bytes(student_img_bytes)

        if not st.session_state.analysis_done:
            with st.spinner("AI analyzing your circuit..."):
                try:
                    if "1" in option_choice:
                        prompt = """Compare the student's circuit photo with the reference schematic.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "MATCH or ERROR",
                          "error_analysis": "Detailed explanation",
                          "remediation_hints": "Suggestions"
                        }"""
                    else:
                        prompt = """Act as a Socratic tutor. Compare the circuits. Don't give the answer immediately.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "ERROR",
                          "error_analysis": "A guiding question",
                          "remediation_hints": "Think about..."
                        }"""
                    
                    response = model.generate_content(
                        [prompt, schematic_img_ai, student_img_ai], 
                        generation_config=GenerationConfig(response_mime_type="application/json")
                    )
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")

        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            st.subheader(f"Result: {data.get('match_status', 'Unknown')}")
            st.info(data.get('error_analysis', ''))
            st.write(f"💡 Hint: {data.get('remediation_hints', '')}")

            if st.button("Finalize and Save to Drive") and not st.session_state.saved:
                now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                ts = now_hkt.strftime('%Y%m%d_%H%M%S')
                
                with st.spinner("Uploading to Google Drive..."):
                    # 1. Upload Image
                    img_fn = f"std_{student_number}_task_{task_number}_{ts}.jpg"
                    drive_id = upload_to_drive(student_img_bytes, img_fn)

                    if drive_id:
                        # 2. Save Results as a CSV file to Drive
                        log_entry = {
                            "Timestamp": [now_hkt.strftime('%Y-%m-%d %H:%M:%S')],
                            "Student": [student_number],
                            "Task": [task_number],
                            "Status": [data.get('match_status')],
                            "Analysis": [data.get('error_analysis')],
                            "Drive_File_ID": [drive_id]
                        }
                        df = pd.DataFrame(log_entry)
                        csv_bytes = df.to_csv(index=False).encode('utf-8')
                        csv_fn = f"result_{student_number}_{ts}.csv"
                        upload_to_drive(csv_bytes, csv_fn, mime_type='text/csv')

                        st.session_state.saved = True
                        st.success(f"✅ Circuit & Results saved to Google Drive!")
                        st.balloons()
                        st.table(df)

st.divider()
st.caption("Circuit AI Tutor | Powered by Gemini 2.5 Pro & Google Drive API")
