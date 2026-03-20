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
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# --- 1. CONFIGURATION ---
DRIVE_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"
LOG_FILE_NAME = "circuit_ai_0321.csv"

st.set_page_config(page_title="AI Circuit Tutor", layout="centered", page_icon="🔌")

# --- 2. INITIALIZE SERVICES ---
@st.cache_resource
def init_services():
    creds_info = st.secrets["gcp_service_account"]
    vertex_creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=vertex_creds)
    model = GenerativeModel("gemini-2.5-pro")  

    oauth_info = st.secrets["google_oauth"]
    from google.oauth2.credentials import Credentials
    drive_creds = Credentials(
        token=None,
        refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"],
        client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    from google.auth.transport.requests import Request
    if not drive_creds.valid:
        drive_creds.refresh(Request())
    drive_service = build('drive', 'v3', credentials=drive_creds)
    
    return model, drive_service

model, drive_service = init_services()

# --- 3. SESSION STATE ---
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state: st.session_state.current_analysis = {}
if 'saved' not in st.session_state: st.session_state.saved = False
if 'last_img_hash' not in st.session_state: st.session_state.last_img_hash = None
if 'socratic_step' not in st.session_state: st.session_state.socratic_step = 1
if 'socratic_history' not in st.session_state: st.session_state.socratic_history = []
if 'socratic_complete' not in st.session_state: st.session_state.socratic_complete = False

# --- 4. DRIVE APPEND LOGIC ---
def get_file_id_by_name(name):
    query = f"name = '{name}' and '{DRIVE_FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

def save_to_central_csv(new_row_df):
    try:
        file_id = get_file_id_by_name(LOG_FILE_NAME)
        
        if file_id:
            # Download existing
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            existing_df = pd.read_csv(fh)
            updated_df = pd.concat([existing_df, new_row_df], ignore_index=True)
        else:
            updated_df = new_row_df

        # Upload/Update
        csv_buffer = io.BytesIO()
        updated_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        media = MediaIoBaseUpload(csv_buffer, mimetype='text/csv', resumable=True)
        
        if file_id:
            drive_service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata = {'name': LOG_FILE_NAME, 'parents': [DRIVE_FOLDER_ID]}
            drive_service.files().create(body=file_metadata, media_body=media).execute()
        return True
    except Exception as e:
        st.error(f"CSV Update Error: {e}")
        return False

def upload_image(file_bytes, file_name):
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg')
    file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- 5. UI ---
st.title("🔌 AI Circuit Diagnostic Station")

with st.sidebar:
    st.header("Setup")
    student_number = st.text_input("Student Number")
    task_number = st.number_input("Task", 1, 10, 1)
    mode = st.radio("Mode", ["1: Direct Debug", "2: Socratic Tutor"])
    if st.button("Reset Session"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

img_file = st.camera_input("Capture Breadboard")

if img_file and student_number:
    img_bytes = img_file.getvalue()
    current_hash = hashlib.md5(img_bytes).hexdigest()

    if st.session_state.last_img_hash != current_hash:
        st.session_state.analysis_done = False
        st.session_state.saved = False
        st.session_state.socratic_step = 1
        st.session_state.socratic_history = []
        st.session_state.socratic_complete = False
        st.session_state.last_img_hash = current_hash

    ref_path = f"data2/circuit-{task_number}.jpg"

    if os.path.exists(ref_path):
        # --- ANALYSIS ---
        if not st.session_state.analysis_done:
            with st.spinner("Analyzing..."):
                try:
                    ref_img = Image.load_from_file(ref_path)
                    std_img = Image.from_bytes(img_bytes)
                    
                    prompt = """Compare student circuit with schematic. 
                    If Mode 2: Provide 3 scaffolding questions (Conceptual, Observational, Specific).
                    [OUTPUT JSON] {
                        "match_status": "MATCH/ERROR",
                        "error_description": "...",
                        "fix": "...",
                        "scaffolding": {"q1": "...", "q2": "...", "q3": "..."}
                    }"""
                    
                    response = model.generate_content([prompt, ref_img, std_img], 
                        generation_config=GenerationConfig(response_mime_type="application/json"))
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
                except Exception as e: st.error(f"AI Error: {e}")

        # --- DISPLAY ---
        if st.session_state.analysis_done:
            res = st.session_state.current_analysis
            
            if mode.startswith("1"):
                st.subheader("Direct Feedback")
                if res['match_status'] == "MATCH": st.success("Perfect Match!")
                else: 
                    st.warning(res['error_description'])
                    st.info(f"Fix: {res['fix']}")
                st.session_state.socratic_complete = True
            else:
                st.subheader(f"Socratic Step {st.session_state.socratic_step}/3")
                q_key = f"q{st.session_state.socratic_step}"
                current_q = res.get('scaffolding', {}).get(q_key, "Look closely at your connections.")
                
                st.info(f"**Tutor:** {current_q}")
                
                with st.form(key=f"step_{st.session_state.socratic_step}"):
                    ans = st.text_input("Your Answer:")
                    if st.form_submit_button("Submit"):
                        # AI Evaluate Answer
                        eval_p = f"Error: {res['error_description']}. Tutor asked: {current_q}. Student said: {ans}. Is student correct? [JSON] {{'correct': bool, 'feedback': '...'}}"
                        eval_r = model.generate_content(eval_p, generation_config=GenerationConfig(response_mime_type="application/json"))
                        eval_js = json.loads(eval_r.text)
                        
                        # Save to history
                        st.session_state.socratic_history.append(f"Q: {current_q} | A: {ans} | Result: {eval_js['feedback']}")
                        
                        if eval_js['correct']:
                            if st.session_state.socratic_step < 3: 
                                st.session_state.socratic_step += 1
                                st.rerun()
                            else: 
                                st.session_state.socratic_complete = True
                                st.success("Great job debugging!")
                        else: st.error(eval_js['feedback'])

            # --- FINAL SAVE ---
            if st.session_state.socratic_complete and not st.session_state.saved:
                if st.button("Finalize & Save to Drive"):
                    now = datetime.now(timezone.utc) + timedelta(hours=8)
                    ts = now.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Upload Image
                    img_fn = f"img_{student_number}_{task_number}_{now.strftime('%H%M%S')}.jpg"
                    img_id = upload_image(img_bytes, img_fn)
                    
                    # Prepare CSV Row
                    dialogue = " | ".join(st.session_state.socratic_history) if st.session_state.socratic_history else "N/A"
                    new_data = pd.DataFrame([{
                        "Timestamp": ts,
                        "Student_ID": student_number,
                        "Task": task_number,
                        "Mode": mode,
                        "Status": res['match_status'],
                        "AI_Analysis": res['error_description'],
                        "Socratic_Dialogue": dialogue,
                        "Image_ID": img_id
                    }])
                    
                    if save_to_central_csv(new_data):
                        st.session_state.saved = True
                        st.balloons()
                        st.success("Data appended to circuit_ai_0321.csv")

st.divider()
st.caption("Circuit Tutor | Centralized Logging Enabled")
