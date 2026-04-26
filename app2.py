# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from PIL import Image as PILImage, ImageDraw

# --- SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="AI Circuit Explorer", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview" # Or gemini-3.1-pro-preview if available in your region

# Authentication Logic
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    PROJECT_ID = creds_info["project_id"]

    client = genai.Client(
        vertexai=True, 
        project=PROJECT_ID, 
        location="global", # Update based on your project location
        credentials=credentials
    )
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

# --- 2. SESSION STATE MANAGEMENT ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "raw_student_img" not in st.session_state: st.session_state.raw_student_img = None

def reset_flow():
    st.session_state.step = 1
    st.session_state.components_df = pd.DataFrame()

# --- 3. UI: SIDEBAR SETUP ---
st.title("🔌 AI Circuit Explorer: Learning by Discovery")

with st.sidebar:
    st.header("1. Select Your Mission")
    tasks = {
        "Task A: Light the LED": "Build a circuit where the LED stays ON constantly.",
        "Task B: The Power Switch": "Use the Slide-Switch to turn one LED ON and OFF.",
        "Task C: The Alternator": "Use the Slide-Switch to swap between a Red LED and a Green LED."
    }
    selected_task_name = st.selectbox("Current Task", list(tasks.keys()), on_change=reset_flow)
    task_description = tasks[selected_task_name]
    
    st.info(f"**Goal:** {task_description}")
    
    st.divider()
    st.subheader("2. Upload Your Work")
    student_file = st.file_uploader("Upload Photo of Breadboard", type=["jpg", "png", "jpeg"], on_change=reset_flow)

    if st.button("Reset Process"):
        reset_flow()
        st.rerun()

# --- MAIN FLOW ---
if student_file:
    st.session_state.raw_student_img = PILImage.open(student_file).convert("RGB")

    # STEP 1: AI LEAD DETECTION
    if st.session_state.step == 1:
        st.image(st.session_state.raw_student_img, caption="Your Circuit", use_container_width=True)

        if st.button("🔍 Step 1: Detect My Components", type="primary"):
            with st.spinner("AI is looking for components and legs..."):
                prompt_seg = """
                Identify each component on this breadboard. 
                For every component (Resistor, LED, Slide-Switch, Battery wires), return:
                - 'name': The name of the part.
                - 'center': [y, x] of the part body.
                - 'legs': A list of [y, x] coordinates where the metal legs enter the breadboard holes.
                Scale all coordinates 0-1000.
                """
                
                try:
                    resp = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[st.session_state.raw_student_img, prompt_seg],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema={
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "name": {"type": "STRING"},
                                        "center": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                                        "legs": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "INTEGER"}}}
                                    }
                                }
                            }
                        )
                    )
                    
                    records = []
                    parsed_data = resp.parsed if hasattr(resp, 'parsed') else json.loads(resp.text)
                    for comp_idx, item in enumerate(parsed_data):
                        name = item.get('name', f"Part_{comp_idx}")
                        cy, cx = item.get('center', [500, 500])
                        for leg_idx, (ly, lx) in enumerate(item.get('legs', [])):
                            records.append({
                                "Component": f"{name} (Pin {leg_idx+1})",
                                "Center_X": cx, "Center_Y": cy, "Leg_X": lx, "Leg_Y": ly
                            })
                    
                    st.session_state.components_df = pd.DataFrame(records)
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Detection failed: {e}")

    # STEP 2: FINE-TUNING
    elif st.session_state.step == 2:
        st.subheader("⚙️ Step 2: Confirm Your Connections")
        st.info("The AI guessed where your wires are. Adjust the sliders so the orange dots match the exact holes you used.")

        edit_col, img_col = st.columns([1, 1.5])
        updated_data = []
        
        with edit_col:
            for i, row in st.session_state.components_df.iterrows():
                with st.expander(f"📍 {row['Component']}", expanded=False):
                    new_lx = st.slider(f"X (Horiz)", 0, 1000, int(row["Leg_X"]), key=f"x_{i}")
                    new_ly = st.slider(f"Y (Vert)", 0, 1000, int(row["Leg_Y"]), key=f"y_{i}")
                    updated_data.append({**row, "Leg_X": new_lx, "Leg_Y": new_ly})
            edited_df = pd.DataFrame(updated_data)
        
        with img_col:
            display_img = st.session_state.raw_student_img.copy()
            draw = ImageDraw.Draw(display_img)
            w, h = display_img.size
            for _, r in edited_df.iterrows():
                start = (r["Center_X"] * w / 1000, r["Center_Y"] * h / 1000)
                end = (r["Leg_X"] * w / 1000, r["Leg_Y"] * h / 1000)
                draw.line([start, end], fill="orange", width=5)
                draw.ellipse([end[0]-8, end[1]-8, end[0]+8, end[1]+8], fill="yellow", outline="orange")
            st.image(display_img, use_container_width=True)

        if st.button("✅ My Map is Correct! Analyze My Logic", type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.annotated_img = display_img
            st.session_state.step = 3
            st.rerun()

    # STEP 3: SOCRATIC ANALYSIS (No functions revealed)
    elif st.session_state.step == 3:
        st.subheader("🧠 Step 3: Experimental Feedback")
        st.image(st.session_state.annotated_img, width=500)
        
        with st.spinner("Thinking like a scientist..."):
            # SYSTEM 2 PROMPT: Strict instructions to be a Socratic guide
            analysis_prompt = f"""
            TASK: {task_description}
            
            Analyze the image. The orange lines show where the student has plugged their components.
            
            PEDAGOGICAL RULES:
            1. DO NOT tell the student how a slide-switch works (e.g., do not mention that the middle pin is common).
            2. DO NOT tell them which pin is 'wrong'.
            3. Use SOCRATIC questioning. Ask them to trace the path of electricity.
            4. If the circuit is wrong, point out a 'mystery' (e.g., 'I see electricity enters Row 10, but where does it go after it hits that switch pin?').
            5. Encourage them to try different slider positions to see what happens.
            
            The goal is for the student to use System 2 thinking to discover the switch's internal logic through trial and error.
            """

            try:
                final_response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[st.session_state.annotated_img, analysis_prompt],
                    config=types.GenerateContentConfig(temperature=0.7)
                )
                
                st.chat_message("assistant").write(final_response.text)
                
                if st.button("I want to try again / Fix my circuit"):
                    st.session_state.step = 1
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Analysis failed: {e}")
else:
    st.info("Pick a Task in the sidebar and upload a photo to start your experiment!")
