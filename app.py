# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from PIL import Image as PILImage
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig
from google.oauth2 import service_account
from pathlib import Path

# --- 1. INITIALIZATION & CONFIG ---
# Setup local storage directories
DATA_DIR = Path("captured_data")
IMAGE_DIR = DATA_DIR / "images"
LOG_FILE = DATA_DIR / "circuit_logs.csv"

DATA_DIR.mkdir(exist_ok=True)
IMAGE_DIR.mkdir(exist_ok=True)

if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    PROJECT_ID = creds_info["project_id"]
    vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found! Check your Streamlit Cloud settings.")
    st.stop()

# Using gemini-1.5-pro for high-reasoning diagnostic tasks
model = GenerativeModel("gemini-1.5-pro")

st.set_page_config(page_title="AI Circuit Tutor", layout="centered")

# --- 2. SESSION STATE MANAGEMENT ---
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

# --- 3. UI LAYOUT ---
st.title("🔌 AI Circuit Diagnostic Station")

with st.sidebar:
    st.header("Student Setup")
    student_number = st.text_input("Student Number (1-70)", placeholder="e.g. 42")
    task_number = st.number_input("Task Number", min_value=1, max_value=10, value=1)
    option_choice = st.radio("Debug Mode", ["1: Direct Debug", "2: Socratic Debug"])

    if st.button("Reset Session"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# --- 4. IMAGE CAPTURE ---
img_file = st.camera_input("Capture your breadboard circuit")

# --- 5. CORE LOGIC ---
if img_file and student_number:
    base_folder = "data2"
    ref_image_name = f"circuit-{task_number}.jpg"
    ref_path = os.path.join(base_folder, ref_image_name)

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_image_name} not found in '{base_folder}' folder.")
    else:
        # Load images for AI using RAW bytes
        schematic_img_ai = Image.load_from_file(ref_path)
        student_img_bytes = img_file.getvalue() # Raw resolution bytes
        student_img_ai = Image.from_bytes(student_img_bytes)

        # --- MODE 1: DIRECT DEBUG ---
        if "1" in option_choice and not st.session_state.analysis_done:
            with st.spinner("Analyzing circuit..."):
                mode_text = "Direct Debug Mode: Provide concise diagnosis and correction."
                prompt = f"""
                You are a Senior Electronic Systems Diagnostic Engineer. Your task is to validate a student's breadboard circuit (Image 2) against a reference schematic (Image 1).
                Mode: {mode_text}
                [OUTPUT FORMAT - JSON ONLY]
                {{
                  "schematic_netlist": "...",
                  "student_netlist": "...",
                  "match_status": "CORRECT" or "INCORRECT",
                  "error_analysis": "...",
                  "remediation_hints": "...",
                  "follow_up_QA": "None"
                }}
                """
                response = model.generate_content(
                    [prompt, schematic_img_ai, student_img_ai],
                    generation_config=GenerationConfig(response_mime_type="application/json")
                )
                st.session_state.current_analysis = json.loads(response.text)
                st.session_state.analysis_done = True

        # --- MODE 2: SOCRATIC DEBUG ---
        elif "2" in option_choice and not st.session_state.analysis_done:
            if st.session_state.socratic_round < 3:
                st.subheader(f"Socratic Round {st.session_state.socratic_round + 1} of 3")
                q_prompt = f"""
                Socratic Debug Mode, Round {st.session_state.socratic_round + 1}.
                Compare Image 1 (Reference) and Image 2 (Student).
                Ask ONE guiding question only to help the student find their own error. Do not give the answer.
                """
                q_response = model.generate_content([q_prompt, schematic_img_ai, student_img_ai])
                ai_question = q_response.text
                st.info(f"**AI Question:** {ai_question}")

                with st.form(key=f"round_{st.session_state.socratic_round}"):
                    student_ans = st.text_input("Your Answer:")
                    submit_ans = st.form_submit_button("Submit Answer")
                    if submit_ans and student_ans:
                        st.session_state.chat_history += f"Q: {ai_question} | A: {student_ans}\n"
                        st.session_state.socratic_round += 1
                        st.rerun()
            else:
                with st.spinner("Finalizing analysis..."):
                    final_prompt = f"""
                    Provide final diagnosis and remediation hints after 3 rounds of Socratic dialogue.
                    Student History: {st.session_state.chat_history}
                    [OUTPUT FORMAT - JSON ONLY]
                    {{
                      "schematic_netlist": "...",
                      "student_netlist": "...",
                      "match_status": "CORRECT" or "INCORRECT",
                      "error_analysis": "...",
                      "remediation_hints": "...",
                      "follow_up_QA": "{st.session_state.chat_history}"
                    }}
                    """
                    final_res = model.generate_content(
                        [final_prompt, schematic_img_ai, student_img_ai],
                        generation_config=GenerationConfig(response_mime_type="application/json")
                    )
                    st.session_state.current_analysis = json.loads(final_res.text)
                    st.session_state.analysis_done = True

        # --- 6. DISPLAY RESULTS & AUTO-SAVE ---
        if st.session_state.analysis_done:
            data = st.session_state.current_analysis
            st.divider()
            st.subheader(f"Result: {data['match_status']}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Analysis**")
                st.write(data['error_analysis'])
            with col2:
                st.markdown("**Hint**")
                st.info(data['remediation_hints'])

            if st.button("Finalize and Save Entry") and not st.session_state.saved:
                # 1. Generate Timestamps and Filenames
                now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                ts_filename = now_hkt.strftime('%Y%m%d_%H%M%S')
                img_filename = f"std_{student_number}_task_{task_number}_{ts_filename}.jpg"
                img_save_path = IMAGE_DIR / img_filename

                # 2. Save Raw Image
                with open(img_save_path, "wb") as f:
                    f.write(student_img_bytes)

                # 3. Prepare Data Row
                new_row = {
                    "Timestamp": now_hkt.strftime('%Y-%m-%d %H:%M:%S'),
                    "Student_ID": student_number,
                    "Task_No": task_number,
                    "Mode": option_choice,
                    "Match_Status": data['match_status'],
                    "AI_Analysis": data['error_analysis'],
                    "AI_Hints": data['remediation_hints'],
                    "Socratic_History": data.get("follow_up_QA", ""),
                    "Image_Path": str(img_save_path),
                    "Schematic_Netlist": data.get("schematic_netlist", ""),
                    "Student_Netlist": data.get("student_netlist", "")
                }

                # 4. Save to CSV (Append mode)
                df = pd.DataFrame([new_row])
                if not LOG_FILE.exists():
                    df.to_csv(LOG_FILE, index=False)
                else:
                    df.to_csv(LOG_FILE, mode='a', header=False, index=False)

                st.session_state.saved = True
                st.success(f"Data and Raw Image saved to {img_save_path}")
                st.balloons()

            if st.session_state.saved:
                st.info("Record logged. You can download the current session log below.")
                with open(LOG_FILE, "rb") as file:
                    st.download_button("Download Master CSV Log", file, "circuit_logs.csv", "text/csv")
