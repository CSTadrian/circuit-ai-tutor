# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from PIL import Image as PILImage, ImageDraw, ImageFont

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="AI Circuit Tutor (Enhanced Button Logic)", layout="wide")
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
    """Draws a 0-1000 scale. Fixed with RGB conversion to prevent TypeErrors."""
    if image.mode != "RGB":
        image = image.convert("RGB")
    
    draw = ImageDraw.Draw(image)
    w, h = image.size
    line_color = (255, 0, 0) 
    
    for i in range(0, 1001, 100):
        x_px, y_px = i * w / 1000, i * h / 1000
        draw.line([(x_px, 0), (x_px, 15)], fill=line_color, width=2)
        draw.line([(0, y_px), (15, y_px)], fill=line_color, width=2)
        draw.text((x_px + 2, 2), str(i), fill=(255, 255, 255))
        draw.text((2, y_px + 2), str(i), fill=(255, 255, 255))
    return image

# --- 3. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()

def reset_flow():
    st.session_state.step = 1
    st.session_state.components_df = pd.DataFrame()

# --- 4. UI ---
st.title("🔌 AI Circuit Tutor: Tactical Button Logic")

with st.sidebar:
    st.header("Inputs")
    task_id = st.text_input("Task Name", "Task 4b")
    schematic_file = st.file_uploader("Upload Schematic", type=["jpg", "png", "jpeg"])
    student_file = st.file_uploader("Upload Student Circuit", type=["jpg", "png", "jpeg"])
    if st.button("Reset"): reset_flow(); st.rerun()

if schematic_file and student_file:
    raw_schematic = PILImage.open(schematic_file).convert("RGB")
    raw_student = PILImage.open(student_file).convert("RGB")

    # --- STEP 1: DETECTION ---
    if st.session_state.step == 1:
        col1, col2 = st.columns(2)
        col1.image(raw_schematic, caption="Reference Schematic")
        col2.image(draw_coordinate_grid(raw_student.copy()), caption="Student Breadboard")

        if st.button("🔍 Step 1: Detect Components", type="primary"):
            with st.spinner("AI locating components and legs..."):
                # Updated prompt to specifically look for the button and its pins
                prompt_seg = """
                Identify each component: LDR, Resistor, LED, and especially the 4-pin Push Button.
                For the Push Button, ensure you identify all 4 metal legs.
                Return JSON:
                - 'name': component name
                - 'center': [y, x] of body (0-1000)
                - 'legs': list of [y, x] for each metal leg (0-1000)
                """
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
                    name = item.get('name', 'Comp')
                    cy, cx = item.get('center', [500, 500])
                    for i, (ly, lx) in enumerate(item.get('legs', [])):
                        records.append({"Component": f"{name} (Pin {i+1})", "CX": cx, "CY": cy, "LX": lx, "LY": ly})
                st.session_state.components_df = pd.DataFrame(records)
                st.session_state.step = 2
                st.rerun()

    # --- STEP 2: VISUALIZATION & TUNING ---
    elif st.session_state.step == 2:
        st.subheader("⚙️ Step 2: Confirm Pin Connections")
        edit_col, img_col = st.columns([1, 1.5])
        updated_data = []
        
        with edit_col:
            for i, row in st.session_state.components_df.iterrows():
                with st.expander(f"📍 {row['Component']}"):
                    lx = st.slider(f"X_{i}", 0, 1000, int(row["LX"]))
                    ly = st.slider(f"Y_{i}", 0, 1000, int(row["LY"]))
                    updated_data.append({"Component": row["Component"], "CX": row["CX"], "CY": row["CY"], "LX": lx, "LY": ly})
            edited_df = pd.DataFrame(updated_data)

        with img_col:
            display_img = draw_coordinate_grid(raw_student.copy())
            draw = ImageDraw.Draw(display_img)
            w, h = display_img.size
            for _, r in edited_df.iterrows():
                # Visualizing "Orange Legs" and "Yellow Pins" clearly for AI and User
                start = (r["CX"] * w / 1000, r["CY"] * h / 1000)
                end = (r["LX"] * w / 1000, r["LY"] * h / 1000)
                draw.line([start, end], fill=(255, 165, 0), width=5) # Bright Orange
                draw.ellipse([end[0]-6, end[1]-6, end[0]+6, end[1]+6], fill=(255, 255, 0), outline=(0,0,0)) # Yellow Tip
            st.image(display_img, caption="Annotated Pins (Orange Lines = Legs)")

        if st.button("✅ Analyze Circuit Logic", type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.annotated_img = display_img
            st.session_state.step = 3
            st.rerun()

    # --- STEP 3: ANALYSIS WITH BUTTON LOGIC ---
    elif st.session_state.step == 3:
        st.subheader("🧠 Step 3: AI Pedagogical Feedback")
        coord_summary = st.session_state.components_df.to_string(index=False)

        with st.spinner("Analyzing button connectivity..."):
            # The core prompt change for your specific button
            analysis_prompt = f"""
            Identify errors in the student's circuit for Task: {task_id}.
            
            BUTTON LOGIC RULES:
            The button used in this project connects pins in two ways when pressed:
            1. VERTICAL: Pins aligned top-to-bottom on the same side are connected.
            2. DIAGONAL: Current flows diagonally from one corner pin to the opposite corner pin.
            Confirm that the student's connections to the button pins follow either the vertical or diagonal path to complete the circuit loop.
            
            COORDINATE DATA (Legs marked in Orange):
            {coord_summary}
            
            Check if components are in the correct breadboard rows/rails based on the schematic.
            Return JSON with 'feedback' and 'error_locations' [[y, x]].
            """

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
            result = resp.parsed
            st.info(result.get("feedback"))
            
            # Draw Red Error Circles
            final_img = st.session_state.annotated_img.copy()
            draw = ImageDraw.Draw(final_img)
            w, h = final_img.size
            for ey, ex in result.get("error_locations", []):
                px, py = ex * w / 1000, ey * h / 1000
                draw.ellipse([px-20, py-20, px+20, py+20], outline="red", width=8)
            st.image(final_img, caption="AI Diagnosis")
