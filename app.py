# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import io  
from PIL import Image as PILImage, ImageDraw, ImageOps 

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- TASK CONFIGURATION ---
TASKS = {
    "Task 1: Basic LED Circuit": "task1_led.png",
    "Task 2: Resistor in Series": "task2_series_led.png",
    "Task 3: Parallel LED Setup": "task3_parallel_led.png",
    "Task 4: Switch Control": "task4_switch.png",
    "Task 5: Exam 1": "task5.png",
}
DATA_FOLDER = "data"

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="AI Circuit Tutor", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Authentication
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    client = genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

# --- Hide the Streamlit main menu and footer ---
hide_menu_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    </style>
    """
st.markdown(hide_menu_style, unsafe_allow_html=True)

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

def process_uploaded_image(uploaded_file):
    """Ensures image is upright, in RGB format, and resized."""
    img = PILImage.open(uploaded_file)
    img = ImageOps.exif_transpose(img) 
    img = img.convert("RGB")
    max_size = (1600, 1600)
    img.thumbnail(max_size, PILImage.Resampling.LANCZOS)
    return img
    
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
    st.header("Setup")
    
    # User ID Selection
    user_id_options = [f"{i:02d}" for i in range(51)]
    user_id = st.selectbox("Select User ID", user_id_options)
    
    # Task Selection
    selected_task = st.selectbox("Select Task", list(TASKS.keys()))
    
    # --- UPDATED: PREVIEW SCHEMATIC IMMEDIATELY ---
    schematic_path = os.path.join(DATA_FOLDER, TASKS[selected_task])
    if os.path.exists(schematic_path):
        # We load it here for the sidebar preview
        raw_schematic = process_uploaded_image(schematic_path)
        st.image(raw_schematic, caption=f"Target Schematic: {TASKS[selected_task]}", use_container_width=True)
    else:
        st.error(f"File {TASKS[selected_task]} not found in {DATA_FOLDER}")
        st.stop()
    
    st.divider()
    
    # Student Circuit Input
    input_method = st.radio("Student Circuit Input:", ["Upload File", "Take Photo"])
    student_file = None
    if input_method == "Upload File":
        student_file = st.file_uploader("Upload Student Circuit", type=["jpg", "png", "jpeg"])
    else:
        student_file = st.camera_input("Take a photo of the breadboard")

    if st.button("Reset Entire Process"): 
        reset_flow()
        st.rerun()

# --- MAIN LOOP ---
if student_file:
    try:
        # We already defined raw_schematic in the sidebar logic above
        raw_student = process_uploaded_image(io.BytesIO(student_file.getvalue()))
    except Exception as e:
        st.error(f"Error loading student image: {e}")
        st.stop()
        
    # --- STEP 1: DETECTION ---
    if st.session_state.step == 1:
        st.markdown(f"### Current User: **{user_id}** | Task: **{selected_task}**")
        col1, col2 = st.columns(2)
        col1.image(raw_schematic, caption="Reference Schematic")
        col2.image(draw_coordinate_grid(raw_student.copy()), caption="Student Breadboard")

        if st.button("🔍 Step 1: Detect Components", type="primary"):
            with st.spinner("AI locating components..."):
                prompt_seg = """
                Identify components on the breadboard. Specifically locate:
                - slide-switch
                - 4-pin Push Button
                - LDR
                - LED 
                - 220µF capacitor
                - resistor (Read the color bands to specify if it is '5-band 300ohm', '1000 ohm', or '10k ohm')
                
                Return JSON: 'name', 'center': [y,x], 'legs': [[y,x],...]
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

    # --- STEP 3: ANALYSIS ---
    elif st.session_state.step == 3:
        st.subheader("🧠 Step 3: Pedagogical Diagnosis")
        
        if st.session_state.analysis_result is None:
            with st.spinner("Evaluating circuit logic..."):
                coord_summary = st.session_state.components_df.to_string(index=False)
                analysis_prompt = f"""
                Task: {selected_task}. 
                Check if the student's circuit (annotated) matches the logic of the reference schematic.
                
                RULES:
                - 4-pin push button: HORIZONTAL flow when open. VERTICAL/DIAGONAL when pressed.
                
                Data: {coord_summary}. 
                Return JSON: 'feedback', 'error_locations': [[y,x]]
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
                st.session_state.analysis_result = resp.parsed

        res = st.session_state.analysis_result
        diag_img = st.session_state.annotated_img.copy()
        draw = ImageDraw.Draw(diag_img)
        w, h = diag_img.size
        for ey, ex in res.get("error_locations", []):
            px, py = ex * w / 1000, ey * h / 1000
            draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=10)
        
        st.image(diag_img, caption="AI Diagnosis")
        st.info(res.get("feedback"))

        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("🔙 Back to Adjust Pins", use_container_width=True):
                st.session_state.analysis_result = None 
                st.session_state.step = 2
                st.rerun()
        with col_nav2:
            if st.button("🎉 New Task", use_container_width=True):
                reset_flow()
                st.rerun()
else:
    st.info("Please select a task and provide a photo of your circuit to begin.")
