import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime, timedelta, timezone
from PIL import Image as PILImage
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig
from google.oauth2 import service_account

# --- 1. INITIALIZATION & AUTH ---
st.set_page_config(page_title="AI Circuit Tutor", layout="wide")

if "gcp_service_account" in st.secrets:
    creds_info = dict(st.secrets["gcp_service_account"])
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    PROJECT_ID = creds_info["project_id"]
    vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found! Please configure TOML secrets.")
    st.stop()

# Use gemini-1.5-pro for high-reasoning circuit analysis
model = GenerativeModel("gemini-1.5-pro")

# --- 2. SESSION STATE MANAGEMENT ---
if 'socratic_round' not in st.session_state:
    st.session_state.socratic_round = 0
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = {}
if 'session_logs' not in st.session_state:
    st.session_state.session_logs = []

# --- 3. HELPER FUNCTIONS ---
def process_image(uploaded_file):
    """Resizes and compresses image with High Quality settings."""
    img = PILImage.open(uploaded_file)
    
    # --- CHANGE 1: Increase the resolution ---
    # 2048px is '2K' resolution. It is usually the "sweet spot" for Gemini 
    # to see small circuit components without crashing the server.
    img.thumbnail((2048, 2048)) 
    
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    buf = io.BytesIO()
    
    # --- CHANGE 2: Increase JPEG Quality ---
    # Changed from 85 to 95 (near lossless)
    img.save(buf, format="JPEG", quality=95, subsampling=0) 
    
    return buf.getvalue()

# --- 4. UI LAYOUT ---
st.title("🔌 AI Circuit Diagnostic Station")

with st.sidebar:
    st.header("📋 Student Info")
    student_id = st.text_input("Student ID", placeholder="e.g. 42")
    task_num = st.number_input("Task Number", min_value=1, max_value=10, value=1)
    mode = st.radio("Mode", ["Direct Debug", "Socratic Debug"])
    
    st.divider()
    if st.button("Reset Everything"):
        st.session_state.clear()
        st.rerun()
    
    # Teacher Section: Download Logs
    if st.session_state.session_logs:
        st.divider()
        st.subheader("Teacher Tools")
        log_df = pd.DataFrame(st.session_state.session_logs)
        csv = log_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download All Session Logs", csv, "class_logs.csv", "text/csv")

# --- 5. IMAGE INPUT (The iPad Fix) ---
col_cam, col_file = st.columns(2)
with col_cam:
    cam_file = st.camera_input("Option A: Use Browser Camera")
with col_file:
    up_file = st.file_uploader("Option B: Upload/Take Photo (Best for iPad/Tablets)", type=['jpg', 'jpeg', 'png'])

# Determine which image to use
active_file = up_file if up_file else cam_file

# --- 6. CORE LOGIC ---
if active_file and student_id:
    # 1. Prepare Reference Image
    ref_path = f"data2/circuit-{task_num}.jpg"
    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_path} not found.")
        st.stop()
    
    ref_img_ai = Image.load_from_file(ref_path)
    
    # 2. Process Student Image
    student_img_bytes = process_image(active_file)
    student_img_ai = Image.from_bytes(student_img_bytes)

    # --- MODE: DIRECT ---
    if mode == "Direct Debug" and not st.session_state.analysis_done:
        with st.spinner("Analyzing circuit..."):
            prompt = """
            You are a Senior Electronic Engineer. Compare Image 1 (Reference) to Image 2 (Student Breadboard).
            Identify if the student's circuit is CORRECT or INCORRECT.
            Provide a concise error analysis and remediation hints.
            [OUTPUT FORMAT - JSON ONLY]
            {
              "match_status": "CORRECT/INCORRECT",
              "error_analysis": "...",
              "remediation_hints": "..."
            }
            """
            try:
                res = model.generate_content(
                    [prompt, ref_img_ai, student_img_ai],
                    generation_config=GenerationConfig(response_mime_type="application/json")
                )
                st.session_state.current_analysis = json.loads(res.text)
                st.session_state.analysis_done = True
            except Exception as e:
                st.error(f"API Error: {e}")

    # --- MODE: SOCRATIC ---
    elif mode == "Socratic Debug" and not st.session_state.analysis_done:
        if st.session_state.socratic_round < 3:
            st.subheader(f"Step {st.session_state.socratic_round + 1} of 3: Investigation")
            
            # Generate Socratic Question
            q_prompt = f"""
            Compare Image 1 (Ref) and Image 2 (Student). 
            Round {st.session_state.socratic_round + 1}. 
            Ask one helpful question to guide the student to find their own mistake. 
            History: {st.session_state.chat_history}
            """
            q_res = model.generate_content([q_prompt, ref_img_ai, student_img_ai])
            ai_q = q_res.text
            
            st.info(f"**AI:** {ai_q}")
            
            with st.form(key=f"soc_{st.session_state.socratic_round}"):
                ans = st.text_input("Your response:")
                if st.form_submit_button("Submit"):
                    st.session_state.chat_history.append({"Q": ai_q, "A": ans})
                    st.session_state.socratic_round += 1
                    st.rerun()
        else:
            # Final Analysis
            with st.spinner("Finalizing diagnosis..."):
                final_prompt = f"""
                Based on the circuit images and this dialogue: {st.session_state.chat_history},
                provide a final diagnosis in JSON.
                """
                res = model.generate_content(
                    [final_prompt, ref_img_ai, student_img_ai],
                    generation_config=GenerationConfig(response_mime_type="application/json")
                )
                st.session_state.current_analysis = json.loads(res.text)
                st.session_state.analysis_done = True

    # --- 7. DISPLAY RESULTS & LOGGING ---
    if st.session_state.analysis_done:
        data = st.session_state.current_analysis
        st.success(f"Analysis Complete: {data['match_status']}")
        
        c1, c2 = st.columns(2)
        c1.metric("Status", data['match_status'])
        c2.write(f"**Hints:** {data['remediation_hints']}")
        
        st.write(f"**Detailed Analysis:** {data['error_analysis']}")

        if st.button("✅ Save & Finish"):
            # Create log entry
            log_entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "student_id": student_id,
                "task": task_num,
                "status": data['match_status'],
                "history": str(st.session_state.chat_history)
            }
            st.session_state.session_logs.append(log_entry)
            st.success("Record added to session log. Teacher can download the CSV from the sidebar.")
            st.balloons()
