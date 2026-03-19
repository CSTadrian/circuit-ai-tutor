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
from googleapiclient.http import MediaFileUpload

# --- 1. CONFIGURATION ---
# REPLACE with your Google Drive Folder ID
DRIVE_FOLDER_ID = "https://drive.google.com/drive/folders/1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"

st.set_page_config(page_title="AI Circuit Tutor", layout="centered")

# --- 2. INITIALIZE SERVICES (Vertex AI & Google Drive) ---
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    PROJECT_ID = creds_info["project_id"]
    
    # Initialize Vertex AI (Gemini)
    vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
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
    """Uploads bytes to Google Drive folder."""
    try:
        # Create a temporary local file for the API to read
        temp_path = f"temp_{file_name}"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
            
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(temp_path, mimetype=mime_type, resumable=True)
        
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return file.get('id')
    except Exception as e:
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
    # Path to your reference images in GitHub
    ref_path = f"data2/circuit-{task_number}.jpg"

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found in repository.")
    else:
        # Load images for AI
        schematic_img_ai = Image.load_from_file(ref_path)
        student_img_bytes = img_file.getvalue()
        student_img_ai = Image.from_bytes(student_img_bytes)

        # AI Analysis Phase
        if not st.session_state.analysis_done:
            with st.spinner("AI analyzing your circuit..."):
                try:
                    if "1" in option_choice:
                        prompt = """
                        Compare the student's circuit photo with the reference schematic.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "MATCH or ERROR",
                          "error_analysis": "Detailed explanation of what is wrong or right",
                          "remediation_hints": "Suggestions for the student"
                        }
                        """
                    else:
                        prompt = """
                        Act as a Socratic tutor. Compare the circuits. 
                        Don't give the answer immediately.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "ERROR",
                          "error_analysis": "A guiding question to help the student find the mistake",
                          "remediation_hints": "Think about the polarity of the LED..."
                        }
                        """
                    
                    response = model.generate_content(
                        [prompt, schematic_img_ai, student_img_ai], 
                        generation_config=GenerationConfig(response_mime_type="application/json")
                    )
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")

        # Display Results & Save
        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            st.subheader(f"Result: {data.get('match_status', 'Unknown')}")
            st.info(data.get('error_analysis', ''))
            st.write(f"💡 Hint: {data.get('remediation_hints', '')}")

            if st.button("Finalize and Save to Drive") and not st.session_state.saved:
                # Time handling (HKT)
                now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                ts = now_hkt.strftime('%Y%m%d_%H%M%S')
                img_fn = f"std_{student_number}_task_{task_number}_{ts}.jpg"

                with st.spinner("Uploading to Google Drive..."):
                    # 1. Upload Image to Drive
                    drive_id = upload_to_drive(student_img_bytes, img_fn)

                    if drive_id:
                        # 2. Create Log Entry
                        log_entry = {
                            "Timestamp": now_hkt.strftime('%Y-%m-%d %H:%M:%S'),
                            "Student": student_number,
                            "Task": task_number,
                            "Status": data.get('match_status'),
                            "Analysis": data.get('error_analysis'),
                            "Drive_File_ID": drive_id
                        }
                        
                        # Note: To keep it simple and avoid "Billing" errors, 
                        # we just display the log or you can append to a CSV in Drive.
                        # For now, we confirm the image is safe.
                        st.session_state.saved = True
                        st.success(f"✅ Circuit saved to Google Drive! (ID: {drive_id})")
                        st.balloons()
                        
                        # Optional: Show the data that would be in the CSV
                        st.table(pd.DataFrame([log_entry]))

# --- 7. FOOTER ---
st.divider()
st.caption("Circuit AI Tutor | Powered by Gemini 1.5 Pro & Google Drive API")
