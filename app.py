# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from PIL import Image as PILImage, ImageDraw

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="AI Circuit Tutor (Iterative XAI)", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Authentication
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    client = genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

# --- 2. HELPER FUNCTIONS ---
def draw_coordinate_grid(image):
    if image.mode != "RGB":
        image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    line_color = (255, 0, 0) 
    for i in range(0, 1001, 100):
        x_px, y_px = i * w / 1000, i * h / 1000
        draw.line([(x_px, 0), (x_px, 15)], fill=line_color, width=2)
        draw.line([(0, y_px), (15, y_px)], fill=line_color, width=2)
    return image

# --- 3. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "analysis_result" not in st.session_state: st.session_state.analysis_result = None

def reset_flow():
    st.session_state.step = 1
    st.session_state.components_df = pd.DataFrame()
    st.session_state.analysis_result = None

# --- 4. UI ---
st.title("🔌 AI Circuit Tutor: Human-in-the-Loop Debugging")

with st.sidebar:
    st.header("Inputs")
    task_id = st.text_input("Task Name", "Task 4b")
    schematic_file = st.file_uploader("Upload Schematic", type=["jpg", "png", "jpeg"])
    student_file = st.file_uploader("Upload Student Circuit", type=["jpg", "png", "jpeg"])
    if st.button("Reset Entire Process"): reset_flow(); st.rerun()

if schematic_file and student_file:
    raw_schematic = PILImage.open(schematic_file).convert("RGB")
    raw_student = PILImage.open(student_file).convert("RGB")

    # --- STEP 1: DETECTION ---
    if st.session_state.step == 1:
        col1, col2 = st.columns(2)
        col1.image(raw_schematic, caption="Reference Schematic")
        col2.image(draw_coordinate_grid(raw_student.copy()), caption="Student Breadboard")

        if st.button("🔍 Step 1: Detect Components", type="primary"):
            with st.spinner("AI locating components..."):
                prompt_seg = "Identify LDR, Resistor, LED, and 4-pin Push Button. Return JSON: 'name', 'center': [y,x], 'legs': [[y,x],...]"
                resp = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[raw_student, prompt_seg],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema={"type":"ARRAY", "items":{"type":"OBJECT", "properties":{
                            "name":{"type":"STRING"},
                            "center":{"type":"ARRAY", "items":{"type":"INTEGER"}},
                            "legs":{"type":"ARRAY", "items":{"type":"ARRAY", "items":{"type":"INTEGER"}}}
                        }}}
                    )
                )
                records = []
                for item in resp.parsed:
                    name, cy, cx = item.get('name', 'Comp'), item.get('center', [500, 500])[0], item.get('center', [500, 500])[1]
                    for i, (ly, lx) in enumerate(item.get('legs', [])):
                        records.append({"Component": f"{name} (Pin {i+1})", "CX": cx, "CY": cy, "LX": lx, "LY": ly})
                st.session_state.components_df = pd.DataFrame(records)
                st.session_state.step = 2
                st.rerun()

    # --- STEP 2: TUNING ---
    elif st.session_state.step == 2:
        st.subheader("⚙️ Step 2: Fine-Tune Component Pins")
        edit_col, img_col = st.columns([1, 1.5])
        updated_data = []
        
        with edit_col:
            for i, row in st.session_state.components_df.iterrows():
                with st.expander(f"📍 {row['Component']}"):
                    lx = st.slider(f"X_{i}", 0, 1000, int(row["LX"]), key=f"sl_x_{i}")
                    ly = st.slider(f"Y_{i}", 0, 1000, int(row["LY"]), key=f"sl_y_{i}")
                    updated_data.append({"Component": row["Component"], "CX": row["CX"], "CY": row["CY"], "LX": lx, "LY": ly})
            edited_df = pd.DataFrame(updated_data)

        with img_col:
            display_img = draw_coordinate_grid(raw_student.copy())
            draw = ImageDraw.Draw(display_img)
            w, h = display_img.size
            for _, r in edited_df.iterrows():
                start, end = (r["CX"] * w / 1000, r["CY"] * h / 1000), (r["LX"] * w / 1000, r["LY"] * h / 1000)
                draw.line([start, end], fill=(255, 165, 0), width=5)
                draw.ellipse([end[0]-6, end[1]-6, end[0]+6, end[1]+6], fill=(255, 255, 0), outline=(0,0,0))
            st.image(display_img, caption="Verify Orange Legs & Yellow Pins")

        if st.button("✅ Confirm & Analyze Circuit", type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.annotated_img = display_img
            st.session_state.step = 3
            st.rerun()

    # --- STEP 3: ANALYSIS & RETURN BUTTON ---
    elif st.session_state.step == 3:
        st.subheader("🧠 Step 3: Pedagogical Diagnosis")
        
        if st.session_state.analysis_result is None:
            with st.spinner("Evaluating circuit logic..."):
                coord_summary = st.session_state.components_df.to_string(index=False)
                analysis_prompt = f"Task: {task_id}. Button connects vertically/diagonally. Check loop. Data: {coord_summary}. Return JSON: 'feedback', 'error_locations': [[y,x]]"
                resp = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[raw_schematic, st.session_state.annotated_img, analysis_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema={"type":"OBJECT", "properties":{
                            "feedback":{"type":"STRING"},
                            "error_locations":{"type":"ARRAY", "items":{"type":"ARRAY", "items":{"type":"INTEGER"}}}
                        }}
                    )
                )
                st.session_state.analysis_result = resp.parsed

        # Display Final Diagnosis Image
        res = st.session_state.analysis_result
        diag_img = st.session_state.annotated_img.copy()
        draw = ImageDraw.Draw(diag_img)
        w, h = diag_img.size
        for ey, ex in res.get("error_locations", []):
            px, py = ex * w / 1000, ey * h / 1000
            draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=10)
        
        st.image(diag_img, caption="AI Diagnosis (Red = Check this area)")
        st.info(res.get("feedback"))

        # --- NAVIGATION BUTTONS ---
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("🔙 Back to Adjust Pins", use_container_width=True):
                st.session_state.analysis_result = None # Clear old feedback
                st.session_state.step = 2
                st.rerun()
        with col_nav2:
            if st.button("🎉 New Task", use_container_width=True):
                reset_flow()
                st.rerun()
