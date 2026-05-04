# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime
import pytz
from PIL import Image as PILImage, ImageDraw, ImageOps 

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# --- TASK CONFIGURATION ---
TASKS = {
    "Task 1: Basic LED Circuit": "task1_led.png",
    "Task 2: Resistor in Series": "task2_series_led.png",
    "Task 3: Parallel LED Setup": "task3_parallel_led.png",
    "Task 4: Switch Control": "task4_switch.png",
    "Task 5: Exam 1": "task5.png",
}
DATA_FOLDER = "data"

# --- GOOGLE DRIVE INITIALIZATION ---
PARENT_FOLDER_ID = "15KqnkoChiywtxjahuXRg9NYIi7tdsxyc"
CSV_FILENAME = "circuit_audit_logs.csv"

@st.cache_resource
def init_drive():
    oauth_info = st.secrets["google_oauth"]
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
    return build('drive', 'v3', credentials=drive_creds)

drive_service = init_drive()

def pil_to_bytes(img):
    """Helper to convert PIL image to byte stream for Google Drive upload."""
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def save_to_drive(user_id, task_name, ai_feedback, images_dict):
    """Saves 4 images and updates the CSV log in Google Drive."""
    
    # 1. Setup Data Variables
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    hk_time_str = datetime.now(hk_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # Extract Task Number (e.g., "Task 4: Switch" -> "4")
    task_num = task_name.split(":")[0].replace("Task", "").strip()
    file_prefix = f"user{user_id}_task{task_num}"
    
    # 2. Upload Images to Google Drive
    for img_key, img_obj in images_dict.items():
        if img_obj is not None:
            try:
                img_bytes = pil_to_bytes(img_obj)
                file_name = f"{file_prefix}_{img_key}.png"
                img_metadata = {'name': file_name, 'parents': [PARENT_FOLDER_ID]}
                media_img = MediaIoBaseUpload(io.BytesIO(img_bytes), mimetype='image/png')
                drive_service.files().create(body=img_metadata, media_body=media_img).execute()
            except Exception as e:
                st.error(f"Failed to save {img_key} to Drive: {e}")

    # 3. Update the CSV
    new_row = {
        "User ID": user_id,
        "Time Uploaded": hk_time_str,
        "Image 1 Filename": f"{file_prefix}_1.png",
        "Image 4 Filename": f"{file_prefix}_4.png",
        "AI Output": ai_feedback
    }
    
    df_new = pd.DataFrame([new_row])

    # Check if the CSV already exists in Drive
    query = f"name='{CSV_FILENAME}' and '{PARENT_FOLDER_ID}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])

    try:
        if not items:
            # Create a new CSV file
            csv_bytes = df_new.to_csv(index=False).encode('utf-8')
            csv_metadata = {'name': CSV_FILENAME, 'parents': [PARENT_FOLDER_ID]}
            csv_media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype='text/csv', resumable=True)
            drive_service.files().create(body=csv_metadata, media_body=csv_media, fields='id').execute()
        else:
            # Download, append, and update existing CSV
            file_id = items[0]['id']
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            
            df_existing = pd.read_csv(fh)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            csv_bytes = df_combined.to_csv(index=False).encode('utf-8')
            
            csv_media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype='text/csv', resumable=True)
            drive_service.files().update(fileId=file_id, media_body=csv_media).execute()
            
        st.success(f"Successfully logged data to Drive for User {user_id}!")
    except Exception as e:
        st.error(f"Failed to update CSV in Drive: {e}")

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

def draw_pins_on_image(image, df_components):
    """Helper to draw pins/legs based on DataFrame coordinates."""
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    w, h = img_copy.size
    for _, r in df_components.iterrows():
        start = (r["CX"] * w / 1000, r["CY"] * h / 1000)
        end = (r["LX"] * w / 1000, r["LY"] * h / 1000)
        draw.line([start, end], fill=(255, 165, 0), width=5)
        draw.ellipse([end[0]-6, end[1]-6, end[0]+6, end[1]+6], fill=(255, 255, 0), outline=(0,0,0))
    return img_copy

def process_uploaded_image(uploaded_file):
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

# Store all 4 images for the Drive upload payload
if "img1_raw" not in st.session_state: st.session_state.img1_raw = None
if "img2_initial_ai" not in st.session_state: st.session_state.img2_initial_ai = None
if "img3_user_mod" not in st.session_state: st.session_state.img3_user_mod = None
if "img4_final_ai" not in st.session_state: st.session_state.img4_final_ai = None

def reset_flow():
    st.session_state.step = 1
    st.session_state.components_df = pd.DataFrame()
    st.session_state.analysis_result = None
    st.session_state.img1_raw = None
    st.session_state.img2_initial_ai = None
    st.session_state.img3_user_mod = None
    st.session_state.img4_final_ai = None

# --- 4. UI ---
st.title("🔌 AI Circuit Tutor: Human-in-the-Loop Debugging")

with st.sidebar:
    st.header("Setup")
    
    user_id_options = [f"{i:02d}" for i in range(51)]
    user_id = st.selectbox("Select User ID", user_id_options)
    
    selected_task = st.selectbox("Select Task", list(TASKS.keys()))
    
    schematic_path = os.path.join(DATA_FOLDER, TASKS[selected_task])
    if os.path.exists(schematic_path):
        raw_schematic = process_uploaded_image(schematic_path)
        st.image(raw_schematic, caption=f"Target Schematic: {TASKS[selected_task]}", use_container_width=True)
    else:
        st.error(f"File {TASKS[selected_task]} not found in {DATA_FOLDER}")
        st.stop()
    
    st.divider()
    
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
        raw_student = process_uploaded_image(io.BytesIO(student_file.getvalue()))
        # Save Image 1
        st.session_state.img1_raw = raw_student 
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
                - power rail (red: +ve and black: -ve)
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
                
                # Save Image 2 (Initial AI Output)
                st.session_state.img2_initial_ai = draw_pins_on_image(draw_coordinate_grid(raw_student.copy()), st.session_state.components_df)

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
            display_img = draw_pins_on_image(draw_coordinate_grid(raw_student.copy()), edited_df)
            st.image(display_img, caption="Verify Orange Legs & Yellow Pins")

        if st.button("✅ Confirm & Analyze Circuit", type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.img3_user_mod = display_img # Save Image 3 (User Modified)
            st.session_state.step = 3
            st.rerun()

    # --- STEP 3: ANALYSIS & DRIVE SAVE ---
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
                    contents=[raw_schematic, st.session_state.img3_user_mod, analysis_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema={"type":"OBJECT", "properties":{
                            "feedback":{"type":"STRING"},
                            "error_locations":{"type":"ARRAY", "items":{"type":"ARRAY", "items":{"type":"INTEGER"}}}
                        }}
                    )
                )
                st.session_state.analysis_result = resp.parsed

                # Generate and Save Image 4 (Final AI Output)
                res = st.session_state.analysis_result
                diag_img = st.session_state.img3_user_mod.copy()
                draw = ImageDraw.Draw(diag_img)
                w, h = diag_img.size
                for ey, ex in res.get("error_locations", []):
                    px, py = ex * w / 1000, ey * h / 1000
                    draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=10)
                
                st.session_state.img4_final_ai = diag_img

        st.image(st.session_state.img4_final_ai, caption="AI Diagnosis")
        st.info(st.session_state.analysis_result.get("feedback"))

        st.divider()
        
        # --- SAVE ACTIONS ---
        col_action1, col_action2, col_action3 = st.columns(3)
        
        with col_action1:
            if st.button("💾 Save Images & Logs to Drive", type="primary", use_container_width=True):
                with st.spinner("Uploading to Google Drive..."):
                    payload = {
                        "1": st.session_state.img1_raw,
                        "2": st.session_state.img2_initial_ai,
                        "3": st.session_state.img3_user_mod,
                        "4": st.session_state.img4_final_ai
                    }
                    save_to_drive(
                        user_id=user_id,
                        task_name=selected_task,
                        ai_feedback=st.session_state.analysis_result.get("feedback"),
                        images_dict=payload
                    )
                    
        with col_action2:
            if st.button("🔙 Back to Adjust Pins", use_container_width=True):
                st.session_state.analysis_result = None 
                st.session_state.img4_final_ai = None
                st.session_state.step = 2
                st.rerun()
                
        with col_action3:
            if st.button("🎉 New Task", use_container_width=True):
                reset_flow()
                st.rerun()
else:
    st.info("Please select a task and provide a photo of your circuit to begin.")
