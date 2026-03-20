# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import io
import hashlib
from datetime import datetime, timedelta, timezone

# AI & Google Auth Imports
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload 

# --- 1. CONFIGURATION ---
# Ensure this folder is SHARED with your service account email as an "Editor"
DRIVE_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"

st.set_page_config(page_title="AI Circuit Tutor", layout="centered", page_icon="🔌")

# --- 2. INITIALIZE SERVICES ---
import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
# ... other imports ...

@st.cache_resource
def init_services():
    # 1. Setup Gemini (Still uses Service Account)
    creds_info = st.secrets["gcp_service_account"]
    vertex_creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=vertex_creds)
    model = GenerativeModel("gemini-1.5-pro")

    # 2. Setup Google Drive (Uses OAuth User Credentials)
    oauth_info = st.secrets["google_oauth"]
    drive_creds = Credentials(
        token=None, # Will be refreshed
        refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"],
        client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    
    # Refresh the token if it's expired
    if not drive_creds.valid:
        drive_creds.refresh(Request())
        
    drive_service = build('drive', 'v3', credentials=drive_creds)
    
    return model, drive_service

model, drive_service = init_services()

# --- 3. SESSION STATE ---
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = {}
if 'saved' not in st.session_state:
    st.session_state.saved = False
if 'last_img_hash' not in st.session_state:
    st.session_state.last_img_hash = None

# --- 4. HELPER FUNCTIONS ---
def upload_to_drive(file_bytes, file_name, mime_type='image/jpeg'):
    """Uploads bytes directly to Google Drive."""
    try:
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
        # This is where the 403 error was caught. 
        # Sharing the folder with the service account email fixes this.
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
        for key in ["analysis_done", "current_analysis", "saved", "last_img_hash"]:
            if key in st.session_state:
                st.session_state[key] = False if "done" in key or "saved" in key else None
        st.rerun()

img_file = st.camera_input("Capture your breadboard circuit")

# --- 6. CORE LOGIC ---
if img_file and student_number:
    # Use MD5 hash to detect if a new photo was taken
    img_bytes = img_file.getvalue()
    current_hash = hashlib.md5(img_bytes).hexdigest()

    if st.session_state.last_img_hash != current_hash:
        st.session_state.analysis_done = False
        st.session_state.saved = False
        st.session_state.last_img_hash = current_hash

    ref_path = f"data2/circuit-{task_number}.jpg"

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found.")
    else:
        # Trigger Analysis
        if not st.session_state.analysis_done:
            with st.spinner("AI analyzing your circuit..."):
                try:
                    schematic_img_ai = Image.load_from_file(ref_path)
                    student_img_ai = Image.from_bytes(img_bytes)

                    # PROMPTS REMAIN UNCHANGED AS REQUESTED
                    if "1" in option_choice:
                        prompt = """Compare the student's circuit photo with the reference schematic.
                        Identify missing wires, wrong resistor values, or incorrect pin connections.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "MATCH or ERROR",
                          "error_analysis": "Detailed explanation of what is wrong",
                          "remediation_hints": "Direct instructions to fix it"
                        }"""
                    else:
                        prompt = """Act as a Socratic tutor. Compare the student's circuit with the schematic. 
                        If there is an error, do not give the answer. Ask a guiding question.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "ERROR",
                          "error_analysis": "A guiding question about a specific part of the circuit",
                          "remediation_hints": "A 'Think about...' hint"
                        }"""
                    
                    response = model.generate_content(
                        [prompt, schematic_img_ai, student_img_ai], 
                        generation_config=GenerationConfig(
                            response_mime_type="application/json",
                            temperature=0.2
                        )
                    )
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")

        # Display Results
        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            status = data.get('match_status', 'Unknown')
            
            if status == "MATCH":
                st.success("✅ Circuit Matches Schematic!")
            else:
                st.warning("⚠️ Discrepancy Found")

            st.subheader("Analysis")
            st.info(data.get('error_analysis', 'No analysis provided.'))
            
            st.subheader("Tutor Hint")
            st.write(f"💡 {data.get('remediation_hints', 'No hints available.')}")

            # Save to Drive Logic
            if not st.session_state.saved:
                if st.button("Finalize and Save to Drive"):
                    now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                    ts = now_hkt.strftime('%Y%m%d_%H%M%S')
                    
                    with st.spinner("Uploading to Google Drive..."):
                        img_fn = f"std_{student_number}_task_{task_number}_{ts}.jpg"
                        drive_id = upload_to_drive(img_bytes, img_fn)

                        if drive_id:
                            log_entry = {
                                "Timestamp": [now_hkt.strftime('%Y-%m-%d %H:%M:%S')],
                                "Student": [student_number],
                                "Task": [task_number],
                                "Status": [status],
                                "Analysis": [data.get('error_analysis')],
                                "Drive_File_ID": [drive_id]
                            }
                            df = pd.DataFrame(log_entry)
                            csv_bytes = df.to_csv(index=False).encode('utf-8')
                            csv_fn = f"result_{student_number}_{ts}.csv"
                            upload_to_drive(csv_bytes, csv_fn, mime_type='text/csv')

                            st.session_state.saved = True
                            st.success(f"✅ Data saved successfully!")
                            st.balloons()
            else:
                st.success("Submission complete. Results are in Google Drive.")

elif img_file and not student_number:
    st.warning("Please enter your Student Number in the sidebar before capturing.")

st.divider()
st.caption("Circuit AI Tutor | Powered by Gemini 2.5 Pro & Google Drive API")
