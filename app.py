# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import io
import pytz
import cv2
import numpy as np
from datetime import datetime
from PIL import Image as PILImage, ImageDraw, ImageOps 

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# --- 1. CONFIGURATION & TASK SETUP ---
TASKS = {
    "Task 1: Basic LED Circuit": "task1_led.png",
    "Task 2: Resistor in Series": "task2_series_led.png",
    "Task 3: Parallel LED Setup": "task3_parallel_led.png",
    "Task 4: Switch Control": "task4_switch.png",
    "Task 5: Exam 1": "task5.png",
}
DATA_FOLDER = "data"
MODEL_ID = "gemini-3.1-pro-preview"

# Google Drive Config
PARENT_FOLDER_ID = "1_cn9lfvMLaozDTx8pvU6LP62J9AVFrvz"
CSV_FILENAME = "circuit_audit_logs.csv"

# --- 2. AUTHENTICATION & INITIALIZATION ---
@st.cache_resource
def init_drive():
    """Initializes Google Drive API via OAuth secrets."""
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

# Initialize Clients
drive_service = init_drive()

if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    client = genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

# --- 3. UI CUSTOMIZATION (Hiding Menus) ---
st.set_page_config(page_title="AI Circuit Tutor", layout="wide")
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)


# --- 4. IMAGE, COMPUTER VISION & DRIVE HELPERS ---
def detect_horizontal_rows(pil_img):
    """
    Finds the exact CENTER of the breadboard holes by 
    calculating the centroids of detected blobs.
    """
    img_cv = np.array(pil_img)
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_cv

    # 1. Pre-process: Blur slightly to remove noise, then threshold
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # Using OTSU to automatically find the best 'darkness' level for the holes
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 2. Find Contours (the 'blobs' representing the holes)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    y_centers = []
    height, width = gray.shape

    for cnt in contours:
        # Filter by area so we only pick up breadboard holes, not big components
        area = cv2.contourArea(cnt)
        if 5 < area < 500:  # Adjust based on how close the camera is
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                # This is the 'Center of Mass' formula
                # cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                y_centers.append(cY)

    if not y_centers:
        return []

    # 3. Group the Y-centers into rows
    y_centers.sort()
    unique_rows = []
    if y_centers:
        current_row_group = [y_centers[0]]
        
        # If two hole-centers are within 10 pixels of each other, 
        # they belong to the same horizontal row.
        row_threshold = height * 0.015 # 1.5% of image height
        
        for i in range(1, len(y_centers)):
            if y_centers[i] - current_row_group[-1] < row_threshold:
                current_row_group.append(y_centers[i])
            else:
                # Average the Y-coordinates of this row to find the MID-LINE
                unique_rows.append(int(np.mean(current_row_group)))
                current_row_group = [y_centers[i]]
        unique_rows.append(int(np.mean(current_row_group)))

    # 4. Filter out 'phantom' rows (rows with too few holes to be real)
    # A real breadboard row should have many holes.
    # (Optional: count occurrences in current_row_group before appending)

    # Convert to your 0-1000 coordinate system
    return [int((y / height) * 1000) for y in unique_rows]
    
def process_uploaded_image(uploaded_file):
    """
    Android-Proof Processor:
    1. Fixes rotation (exif_transpose)
    2. Resizes to 1600px max side to prevent mobile browser memory crashes
    3. Standardizes to RGB
    """
    try:
        img = PILImage.open(uploaded_file)
        img = ImageOps.exif_transpose(img) 
        img = img.convert("RGB")
        
        # Max resolution for stability and AI cost-efficiency
        max_res = (1600, 1600)
        img.thumbnail(max_res, PILImage.Resampling.LANCZOS)
        return img
    except Exception as e:
        st.error(f"Image Loading Error: {e}")
        return None

def draw_coordinate_grid(image, snap_rows=None):
    """Draws red axis marks and optional pale blue Hough Transform rows."""
    draw = ImageDraw.Draw(image)
    w, h = image.size
    
    # Draw Pale Blue Hough Rows First
    if snap_rows:
        for ry in snap_rows:
            y_px = ry * h / 1000
            draw.line([(0, y_px), (w, y_px)], fill=(173, 216, 230), width=2)
            
    # Draw Red Axis Lines
    for i in range(0, 1001, 100):
        x_px, y_px = i * w / 1000, i * h / 1000
        draw.line([(x_px, 0), (x_px, 15)], fill=(255, 0, 0), width=2)
        draw.line([(0, y_px), (15, y_px)], fill=(255, 0, 0), width=2)
    return image

def draw_pins_on_image(image, df_components):
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    w, h = img_copy.size
    for _, r in df_components.iterrows():
        start = (r["CX"] * w / 1000, r["CY"] * h / 1000)
        end = (r["LX"] * w / 1000, r["LY"] * h / 1000)
        draw.line([start, end], fill=(255, 165, 0), width=5)
        draw.ellipse([end[0]-6, end[1]-6, end[0]+6, end[1]+6], fill=(255, 255, 0), outline=(0,0,0))
    return img_copy

def save_to_drive(user_id, task_name, ai_feedback, images_dict):
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    hk_time_str = datetime.now(hk_tz).strftime('%Y-%m-%d %H:%M:%S')
    task_num = task_name.split(":")[0].replace("Task", "").strip()
    file_prefix = f"user{user_id}_task{task_num}"

    # Upload Images
    for img_key, img_obj in images_dict.items():
        if img_obj:
            buf = io.BytesIO()
            img_obj.save(buf, format='PNG')
            img_metadata = {'name': f"{file_prefix}_{img_key}.png", 'parents': [PARENT_FOLDER_ID]}
            media = MediaIoBaseUpload(io.BytesIO(buf.getvalue()), mimetype='image/png')
            drive_service.files().create(body=img_metadata, media_body=media).execute()

    # Log to CSV
    new_row = pd.DataFrame([{
        "User ID": user_id, "Time": hk_time_str, 
        "Raw": f"{file_prefix}_1.png", "Final": f"{file_prefix}_4.png", 
        "Feedback": ai_feedback
    }])

    query = f"name='{CSV_FILENAME}' and '{PARENT_FOLDER_ID}' in parents and trashed=false"
    items = drive_service.files().list(q=query, fields="files(id)").execute().get('files', [])

    if not items:
        csv_bytes = new_row.to_csv(index=False).encode('utf-8')
        meta = {'name': CSV_FILENAME, 'parents': [PARENT_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype='text/csv')
        drive_service.files().create(body=meta, media_body=media).execute()
    else:
        file_id = items[0]['id']
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        MediaIoBaseDownload(fh, request).next_chunk()
        fh.seek(0)
        df_combined = pd.concat([pd.read_csv(fh), new_row], ignore_index=True)
        media = MediaIoBaseUpload(io.BytesIO(df_combined.to_csv(index=False).encode('utf-8')), mimetype='text/csv')
        drive_service.files().update(fileId=file_id, media_body=media).execute()
    st.success("Successfully logged to Drive!")

# --- 5. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "analysis_result" not in st.session_state: st.session_state.analysis_result = None
if "hough_rows" not in st.session_state: st.session_state.hough_rows = []
for i in range(1, 5): 
    if f"img{i}" not in st.session_state: st.session_state[f"img{i}"] = None

def reset_flow():
    for key in ["step", "components_df", "analysis_result", "img1", "img2", "img3", "img4"]:
        if "df" in key: st.session_state[key] = pd.DataFrame()
        elif "step" in key: st.session_state[key] = 1
        else: st.session_state[key] = None
    st.session_state.hough_rows = []

# --- 6. MAIN UI ---
st.title("🔌 AI Circuit Tutor")

with st.sidebar:
    st.header("Setup")
    user_id = st.selectbox("Select User ID", [f"{i:02d}" for i in range(51)])
    selected_task = st.selectbox("Select Task", list(TASKS.keys()))
    
    # Load Schematic
    path = os.path.join(DATA_FOLDER, TASKS[selected_task])
    if os.path.exists(path):
        raw_schematic = process_uploaded_image(path)
        st.image(raw_schematic, caption="Target Schematic")
    else:
        st.error(f"Missing {TASKS[selected_task]}")
        st.stop()
    
    student_file = st.file_uploader("Upload Student Photo", type=["jpg", "png", "jpeg", "webp"])
    if st.button("Reset Process"): 
        reset_flow()
        st.rerun()

# --- 7. APPLICATION LOGIC ---
if student_file:
    # Always process the student image into img1 if it exists
    if st.session_state.img1 is None:
        st.session_state.img1 = process_uploaded_image(io.BytesIO(student_file.getvalue()))
    
    raw_student = st.session_state.img1

    # Detect horizontal rows once when the image is first loaded
    if not st.session_state.hough_rows:
        st.session_state.hough_rows = detect_horizontal_rows(raw_student)

    # STEP 1: DETECTION
    if st.session_state.step == 1:
        col1, col2 = st.columns(2)
        col1.image(raw_schematic, caption="Schematic")
        col2.image(draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows), caption="Your Circuit (Pale Blue = Detected Rows)")

        if st.button("🔍 Step 1: Detect Components", type="primary"):
            with st.spinner("AI analyzing breadboard..."):
                prompt = """
                Identify components on the breadboard. Specifically locate:
                - power rail (red: +ve and black: -ve)
                - slide-switch, 4-pin Push Button, LDR, LED
                - resistor (check color bands: '5-band 300ohm', '1000 ohm', or '10k ohm')
                Return JSON: 'name', 'center': [y,x], 'legs': [[y,x],...]
                """
                resp = client.models.generate_content(
                    model=MODEL_ID, contents=[raw_student, prompt],
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
                    cy, cx = item.get('center', [500,500])
                    for i, (ly, lx) in enumerate(item.get('legs', [])):
                        records.append({"Component": f"{item.get('name')} (Pin {i+1})", "CX": cx, "CY": cy, "LX": lx, "LY": ly})
                
                st.session_state.components_df = pd.DataFrame(records)
                base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows)
                st.session_state.img2 = draw_pins_on_image(base_grid_img, st.session_state.components_df)
                st.session_state.step = 2
                st.rerun()

    # STEP 2: TUNING
    elif st.session_state.step == 2:
        st.subheader("⚙️ Step 2: Fine-Tune Component Pins (Auto-Snapping)")
        edit_col, img_col = st.columns([1, 2])
        updated_data = []
        with edit_col:
            for i, row in st.session_state.components_df.iterrows():
                with st.expander(f"📍 {row['Component']}"):
                    lx = st.slider(f"X_{i}", 0, 1000, int(row["LX"]), key=f"x{i}")
                    raw_ly = st.slider(f"Y_{i}", 0, 1000, int(row["LY"]), key=f"y{i}")
                    
                    # --- MAGNETIC SNAP LOGIC ---
                    snapped_ly = raw_ly
                    if st.session_state.hough_rows:
                        snapped_ly = min(st.session_state.hough_rows, key=lambda ry: abs(ry - raw_ly))
                    
                    if raw_ly != snapped_ly:
                        st.caption(f"*(Y auto-snapped to nearest row: {snapped_ly})*")
                        
                    updated_data.append({"Component": row["Component"], "CX": row["CX"], "CY": row["CY"], "LX": lx, "LY": snapped_ly})
            edited_df = pd.DataFrame(updated_data)

        with img_col:
            base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows)
            st.session_state.img3 = draw_pins_on_image(base_grid_img, edited_df)
            st.image(st.session_state.img3, caption="Verify Orange Legs & Yellow Pins (Snapped to Blue Rows)")

        if st.button("✅ Confirm & Analyze Circuit", type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.step = 3
            st.rerun()

    # STEP 3: ANALYSIS
    elif st.session_state.step == 3:
        st.subheader("🧠 Step 3: AI Diagnosis")
        if st.session_state.analysis_result is None:
            with st.spinner("Checking electrical logic..."):
                summary = st.session_state.components_df.to_string(index=False)
                prompt = f"""
                Task: {selected_task}. 
                Rules: 
                1. SERIES order flexibility (Switch before or after Resistor is fine).
                2. 4-pin Button: Flows HORIZONTALLY when open.
                3. Polarity: LED/Capacitor must match power rail (+ve to red).
                Data: {summary}. Return JSON: 'feedback', 'error_locations': [[y,x]]
                """
                resp = client.models.generate_content(
                    model=MODEL_ID, contents=[raw_schematic, st.session_state.img3, prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                st.session_state.analysis_result = json.loads(resp.text)
                
                # Create Final Image
                diag_img = st.session_state.img3.copy()
                draw = ImageDraw.Draw(diag_img)
                w, h = diag_img.size
                for ey, ex in st.session_state.analysis_result.get("error_locations", []):
                    px, py = ex * w / 1000, ey * h / 1000
                    draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=10)
                st.session_state.img4 = diag_img

        st.image(st.session_state.img4)
        st.info(st.session_state.analysis_result.get("feedback"))

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("💾 Save to Drive", type="primary", use_container_width=True):
                save_to_drive(user_id, selected_task, st.session_state.analysis_result.get("feedback"), 
                             {"1": st.session_state.img1, "2": st.session_state.img2, 
                              "3": st.session_state.img3, "4": st.session_state.img4})
        with col_b:
            if st.button("🔙 Back", use_container_width=True):
                st.session_state.analysis_result = None
                st.session_state.step = 2
                st.rerun()
        with col_c:
            if st.button("🎉 New Task", use_container_width=True):
                reset_flow()
                st.rerun()
else:
    st.info("Upload a photo to begin.")
