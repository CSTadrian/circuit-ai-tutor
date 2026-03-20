# Note: This is a Python (Streamlit) code block. 
# Please copy the code below into your app.py file.

import streamlit as st
import pandas as pd
import json
import os
import io
import hashlib
import time
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
if 'last_feedback' not in st.session_state: st.session_state.last_feedback = ""

# --- 4. DRIVE LOGGING LOGIC ---
def get_file_id_by_name(name):
    query = f"name = '{name}' and '{DRIVE_FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

def save_to_central_csv(new_row_df):
    try:
        file_id = get_file_id_by_name(LOG_FILE_NAME)
        if file_id:
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
    """Resumable upload to prevent BrokenPipeError"""
    try:
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

# --- 5. UI LAYOUT ---
st.title("🔌 AI Circuit Diagnostic Station")

with st.sidebar:
    st.header("Student Setup")
    student_number = st.text_input("Student Number", placeholder="e.g. 42")
    task_number = st.number_input("Task Number", 1, 10, 1)
    mode_choice = st.radio("Learning Mode", ["1: Direct Debug (Fast)", "2: Socratic Tutor (Guided)"])
    
    if st.button("Reset Session"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# --- CAMERA SELECTION ---
st.subheader("Step 1: Take a Clear Photo")
input_method = st.tabs(["📷 Back Camera", "🤳 Selfie Camera", "📁 Upload File"])

img_file = None
with input_method[0]:
    back_cam_file = st.file_uploader("Tap to open Back Camera", type=['jpg', 'jpeg', 'png'], key="back_cam")
    if back_cam_file: img_file = back_cam_file
with input_method[1]:
    selfie_file = st.camera_input("Quick Selfie Capture", key="selfie_cam")
    if selfie_file: img_file = selfie_file
with input_method[2]:
    up_file = st.file_uploader("Select from Gallery", type=['jpg', 'jpeg', 'png'], key="gallery_up")
    if up_file: img_file = up_file

# --- 6. CORE LOGIC ---
if img_file and student_number:
    img_bytes = img_file.getvalue()
    current_hash = hashlib.md5(img_bytes).hexdigest()

    if st.session_state.last_img_hash != current_hash:
        st.session_state.analysis_done = False
        st.session_state.saved = False
        st.session_state.socratic_step = 1
        st.session_state.socratic_history = []
        st.session_state.socratic_complete = False
        st.session_state.last_feedback = ""
        st.session_state.last_img_hash = current_hash

    ref_path = f"data2/circuit-{task_number}.jpg"

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found.")
    else:
        if not st.session_state.analysis_done:
            with st.spinner("AI analyzing circuit..."):
                try:
                    ref_img = Image.load_from_file(ref_path)
                    std_img = Image.from_bytes(img_bytes)
                    
                    # ENHANCED SOCRATIC PROMPT STRUCTURE
                    prompt = """Compare the student's breadboard with the reference schematic.
                    If there is an error, generate 3 Socratic questions following this EXACT structure:
                    1. OBSERVATION: Ask the student to look at a specific component or row where the error is. (e.g., 'Look at the LED. Which row is the long leg in?')
                    2. COMPARISON: Ask the student to compare that specific spot to the schematic. (e.g., 'In the schematic, should that leg connect to the resistor or the ground rail?')
                    3. CORRECTION: Ask what they need to move to fix it. (e.g., 'So, which hole should you move the wire to?')

                    [OUTPUT FORMAT - JSON ONLY]
                    {
                      "match_status": "MATCH or ERROR",
                      "error_analysis": "Brief technical description of the error",
                      "remediation_hints": "Direct fix for the teacher's reference",
                      "socratic_questions": ["Observation Question", "Comparison Question", "Correction Question"]
                    }"""
                    
                    response = model.generate_content([prompt, ref_img, std_img], 
                        generation_config=GenerationConfig(response_mime_type="application/json", temperature=0.1))
                    st.session_state.current_analysis = json.loads(response.text)
                    st.session_state.analysis_done = True
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")

        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            
            if mode_choice.startswith("1"):
                st.subheader("Direct Feedback")
                if data['match_status'] == "MATCH":
                    st.success("✅ Circuit Matches Schematic!")
                else:
                    st.warning(f"⚠️ {data['error_analysis']}")
                    st.info(f"💡 Hint: {data['remediation_hints']}")
                st.session_state.socratic_complete = True
            
            else:
                # SOCRATIC UI FLOW
                if not st.session_state.socratic_complete:
                    st.subheader(f"Step {st.session_state.socratic_step}: Guided Debugging")
                    
                    # Progress Bar
                    st.progress(st.session_state.socratic_step / 3)
                    
                    questions = data.get('socratic_questions', ["Check your wiring."]*3)
                    current_q = questions[st.session_state.socratic_step - 1]
                    
                    # Display the "Tutor" message
                    st.chat_message("assistant").write(current_q)
                    
                    # Show feedback from previous answer if exists
                    if st.session_state.last_feedback:
                        st.info(f"✨ {st.session_state.last_feedback}")

                    with st.form(key=f"soc_form_{st.session_state.socratic_step}"):
                        user_ans = st.text_input("Your answer:", key=f"input_{st.session_state.socratic_step}")
                        submit = st.form_submit_button("Send Answer")
                        
                        if submit and user_ans:
                            # Evaluate the answer
                            eval_prompt = f"""
                            Error Context: {data['error_analysis']}
                            Tutor Question: {current_q}
                            Student Answer: {user_ans}
                            
                            Is the student correct? Provide a very short encouraging feedback.
                            [JSON ONLY] {{'correct': bool, 'feedback': 'string'}}
                            """
                            eval_resp = model.generate_content(eval_prompt, generation_config=GenerationConfig(response_mime_type="application/json"))
                            eval_data = json.loads(eval_resp.text)
                            
                            st.session_state.socratic_history.append(f"Step {st.session_state.socratic_step}: {user_ans}")
                            st.session_state.last_feedback = eval_data['feedback']
                            
                            if st.session_state.socratic_step < 3:
                                st.session_state.socratic_step += 1
                                st.rerun()
                            else:
                                st.session_state.socratic_complete = True
                                st.rerun()
                else:
                    st.success("🎉 Great job! You've successfully debugged the circuit.")
                    st.write("**Your Debugging Journey:**")
                    for h in st.session_state.socratic_history:
                        st.write(f"- {h}")

            # SAVE LOGIC
            if st.session_state.socratic_complete and not st.session_state.saved:
                if st.button("Finalize and Save to Drive"):
                    now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                    ts = now_hkt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    with st.spinner("Uploading to Drive..."):
                        img_fn = f"std_{student_number}_task_{task_number}_{now_hkt.strftime('%H%M%S')}.jpg"
                        drive_img_id = upload_image(img_bytes, img_fn)
                        
                        if drive_img_id:
                            dialogue_log = " || ".join(st.session_state.socratic_history)
                            new_entry = pd.DataFrame([{
                                "Timestamp": ts, "Student": student_number, "Task": task_number,
                                "Mode": mode_choice, "Status": data['match_status'],
                                "Photo_Name": img_fn, "AI_Analysis": data['error_analysis'],
                                "Dialogue_History": dialogue_log,
                                "Image_Link": f"https://drive.google.com/open?id={drive_img_id}"
                            }])
                            
                            if save_to_central_csv(new_entry):
                                st.session_state.saved = True
                                st.balloons()
                                st.success(f"Saved successfully!")

elif img_file and not student_number:
    st.warning("Please enter your Student Number in the sidebar.")

st.divider()
st.caption("Circuit AI Tutor | Socratic Scaffolding v2.0")
