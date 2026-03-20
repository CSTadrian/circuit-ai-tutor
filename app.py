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
DRIVE_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"

st.set_page_config(page_title="AI Circuit Tutor", layout="centered", page_icon="🔌")

# --- 2. INITIALIZE SERVICES ---
@st.cache_resource
def init_services():
    creds_info = st.secrets["gcp_service_account"]
    vertex_creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=vertex_creds)
    # Using Gemini 2.5 Pro for better reasoning in Socratic mode
    model = GenerativeModel("gemini-2.5-pro")

    oauth_info = st.secrets["google_oauth"]
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    drive_creds = Credentials(
        token=None,
        refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"],
        client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    if not drive_creds.valid:
        drive_creds.refresh(Request())
    drive_service = build('drive', 'v3', credentials=drive_creds)
    
    return model, drive_service

model, drive_service = init_services()

# --- 3. SESSION STATE ---
# Existing states
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state: st.session_state.current_analysis = {}
if 'saved' not in st.session_state: st.session_state.saved = False
if 'last_img_hash' not in st.session_state: st.session_state.last_img_hash = None

# New Socratic states
if 'socratic_step' not in st.session_state: st.session_state.socratic_step = 1
if 'feedback_msg' not in st.session_state: st.session_state.feedback_msg = ""
if 'socratic_complete' not in st.session_state: st.session_state.socratic_complete = False

# --- 4. HELPER FUNCTIONS ---
def upload_to_drive(file_bytes, file_name, mime_type='image/jpeg'):
    try:
        folder_id = DRIVE_FOLDER_ID.split('/')[-1] 
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
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
    option_choice = st.radio("Learning Mode", ["1: Direct Debug (Fast)", "2: Socratic Tutor (Scaffolded)"])
    
    if st.button("Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

img_file = st.camera_input("Capture your breadboard circuit")

# --- 6. CORE LOGIC ---
if img_file and student_number:
    img_bytes = img_file.getvalue()
    current_hash = hashlib.md5(img_bytes).hexdigest()

    # Reset state if a new photo is taken
    if st.session_state.last_img_hash != current_hash:
        st.session_state.analysis_done = False
        st.session_state.saved = False
        st.session_state.socratic_step = 1
        st.session_state.feedback_msg = ""
        st.session_state.socratic_complete = False
        st.session_state.last_img_hash = current_hash

    ref_path = f"data2/circuit-{task_number}.jpg"

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found.")
    else:
        # --- PHASE A: VISION ANALYSIS ---
        if not st.session_state.analysis_done:
            with st.spinner("AI is examining your circuit..."):
                try:
                    schematic_img_ai = Image.load_from_file(ref_path)
                    student_img_ai = Image.from_bytes(img_bytes)

                    if "1" in option_choice:
                        # Standard Prompt
                        prompt = """Compare the student's circuit photo with the reference schematic.
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "MATCH or ERROR",
                          "error_analysis": "Detailed explanation",
                          "remediation_hints": "Direct fix instructions"
                        }"""
                    else:
                        # Socratic Scaffolding Prompt
                        prompt = """Act as a Socratic Engineering Tutor. Compare the student's circuit with the schematic.
                        If there is an error, create a 3-step scaffolding plan. 
                        DO NOT give the answer.
                        
                        [OUTPUT FORMAT - JSON ONLY]
                        {
                          "match_status": "ERROR",
                          "actual_error_internal": "Hidden description of the real error for the AI to use later",
                          "scaffolding": {
                            "step1": "Conceptual question (e.g., 'Look at the power rail, where should the current go?')",
                            "step2": "Observational question (e.g., 'Compare your resistor placement to the schematic.')",
                            "step3": "Specific question (e.g., 'Which specific pin is your jumper wire connected to?')"
                          }
                        }"""
                    
                    response = model.generate_content(
                        [prompt, schematic_img_ai, student_img_ai], 
                        generation_config=GenerationConfig(response_mime_type="application/json", temperature=0.1)
                    )
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")

        # --- PHASE B: DISPLAY & INTERACTION ---
        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            
            # If the circuit is actually perfect
            if data.get('match_status') == "MATCH":
                st.success("✅ Perfect! Your circuit matches the schematic.")
                st.session_state.socratic_complete = True
            
            # OPTION 1: DIRECT DEBUG
            elif "1" in option_choice:
                st.warning("⚠️ Discrepancy Found")
                st.info(data.get('error_analysis'))
                st.subheader("How to fix it:")
                st.write(data.get('remediation_hints'))
                st.session_state.socratic_complete = True

            # OPTION 2: SOCRATIC SCAFFOLDING
            else:
                st.subheader(f"Step {st.session_state.socratic_step} of 3: Investigation")
                scaffold = data.get('scaffolding', {})
                
                # Get current question based on step
                current_q = scaffold.get(f"step{st.session_state.socratic_step}")
                st.info(f"**Tutor asks:** {current_q}")

                # Student Input
                with st.form(key=f"socratic_form_{st.session_state.socratic_step}"):
                    student_ans = st.text_input("Your observation:", placeholder="Type your answer here...")
                    submit_ans = st.form_submit_button("Check my answer")

                if submit_ans and student_ans:
                    # AI evaluates the answer
                    eval_prompt = f"""
                    Context: A student is debugging a circuit. 
                    The real error is: {data.get('actual_error_internal')}
                    The tutor asked: {current_q}
                    The student answered: {student_ans}

                    Task: Determine if the student is on the right track for this specific step.
                    [OUTPUT FORMAT - JSON ONLY]
                    {{
                      "is_correct": true/false,
                      "feedback": "A short encouraging remark or a tiny nudge if wrong"
                    }}
                    """
                    with st.spinner("Tutor is thinking..."):
                        eval_resp = model.generate_content(eval_prompt, generation_config=GenerationConfig(response_mime_type="application/json"))
                        eval_result = json.loads(eval_resp.text)
                    
                    if eval_result['is_correct']:
                        st.session_state.feedback_msg = f"✅ {eval_result['feedback']}"
                        if st.session_state.socratic_step < 3:
                            st.session_state.socratic_step += 1
                            st.rerun()
                        else:
                            st.session_state.socratic_complete = True
                            st.balloons()
                    else:
                        st.error(f"❌ {eval_result['feedback']}")

                if st.session_state.feedback_msg:
                    st.success(st.session_state.feedback_msg)

            # --- PHASE C: SAVE TO DRIVE ---
            if st.session_state.socratic_complete:
                st.divider()
                if not st.session_state.saved:
                    if st.button("Finalize and Save Progress"):
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
                                    "Mode": [option_choice],
                                    "Drive_File_ID": [drive_id]
                                }
                                pd.DataFrame(log_entry).to_csv("temp.csv", index=False)
                                with open("temp.csv", "rb") as f:
                                    upload_to_drive(f.read(), f"result_{student_number}_{ts}.csv", 'text/csv')

                                st.session_state.saved = True
                                st.success(f"✅ Submission successful!")
                else:
                    st.success("Results archived in Google Drive. You may start a new task.")

elif img_file and not student_number:
    st.warning("Please enter your Student Number in the sidebar first.")

st.divider()
st.caption("Circuit AI Tutor | Educational Scaffolding Mode Enabled")
