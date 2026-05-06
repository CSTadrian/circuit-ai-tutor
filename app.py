# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
import io
import pytz
import cv2
import numpy as np
import base64  # Added per your previous correction
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

# --- NEW: LANGUAGE DICTIONARY ---
UI = {
    "en": {
        "title": "🔌 AI Circuit Tutor",
        "setup": "Setup",
        "user_id": "Select User ID",
        "task": "Select Task",
        "target": "Target Schematic",
        "input_mode": "Input Method",
        "mode_upload": "Upload Image",
        "mode_camera": "Use Camera",
        "upload": "Upload Student Photo",
        "reset": "Reset Process",
        "schematic": "Schematic",
        "your_circuit": "Your Circuit (Pale Blue = Internal Connections)",
        "step1_btn": "🔍 Step 1: Detect Components",
        "analyzing": "AI analyzing breadboard...",
        "step2_title": "⚙️ Step 2: Fine-Tune Component Pins (Auto-Snapping)",
        "step2_confirm": "✅ Confirm & Analyze Circuit",
        "snapped": "*(Y auto-snapped to nearest row: {y})*",
        "verify": "Verify Orange Legs & Yellow Pins (Snapped to Blue Rows)",
        "step3_title": "🧠 Step 3: AI Diagnosis",
        "checking": "Checking electrical logic...",
        "ai_diag": "AI Diagnosis: Red circles indicate potential wiring issues",
        "save": "💾 Save to Drive",
        "back": "🔙 Back",
        "new": "🎉 New Task",
        "upload_prompt": "Please select an input method to upload or capture a photo.",
        "prompt_addition": "", 
        "guide_title": "📖 Quick Guide",
        "camera": "Take a Photo of your Circuit",
        "guide_text": """
        **How to Start:**
        1. Select Task & Upload Photo
        2. Detect Components (Step 1)
        3. Adjust Pin Rows (Step 2)
        4. AI Diagnosis (Step 3)
        
        **Visual Legend:**
        * 🔴 **Red Circle:** Open circuit (e.g., wires not connecting, misaligned rows).
        * 🟦 **Blue Box:** Wrong component used.
        * 🟡 **Yellow Circle:** Wrong connection/orientation (e.g., switch placed horizontally).
        """,
    },
    "hk": {
        "title": "🔌 AI 電路導師",
        "setup": "設定",
        "user_id": "選擇學生 ID",
        "task": "選擇任務",
        "target": "目標電路圖",
        "input_mode": "輸入方式",
        "mode_upload": "上傳圖片",
        "mode_camera": "使用相機",
        "upload": "上傳學生電路照片",
        "reset": "重置流程",
        "schematic": "電路圖",
        "your_circuit": "你的電路（淺藍色線 = 麵包板內部接線）",
        "step1_btn": "🔍 第一步：偵測零件",
        "analyzing": "AI 正在分析麵包板...",
        "step2_title": "⚙️ 第二步：微調零件引腳（自動對齊）",
        "step2_confirm": "✅ 確認並分析電路",
        "snapped": "*(Y 軸已自動對齊至最近的行：{y})*",
        "verify": "請核對橙色引腳與黃色接點（已對齊至淺藍色行）",
        "step3_title": "🧠 第三步：AI 診斷",
        "checking": "正在檢查電路邏輯...",
        "ai_diag": "AI 診斷：紅圈表示潛在的接線問題",
        "save": "💾 儲存至 Drive",
        "back": "🔙 返回",
        "new": "🎉 新任務",
        "upload_prompt": "請選擇上傳照片或拍攝新照片以開始。",
        "guide_title": "📖 快速指南",
        "camera": "拍攝電路照片",
        "guide_text": """
        **使用步驟：**
        1. 選擇任務並上傳照片
        2. 偵測零件（第一步）
        3. 微調引腳位置（第二步）
        4. AI 進行診斷（第三步）
        
        **圖示說明：**
        * 🔴 **紅圈：** 斷路（例如：接線未連接 / 錯誤插在相鄰的行數）。
        * 🟦 **藍框：** 使用了錯誤的零件。
        * 🟡 **黃圈：** 接法或方向錯誤（例如：開關打橫插）。
        """,
        "prompt_addition": "Please provide the 'feedback' text entirely in written formal Cantonese (Traditional Chinese). Ensure the tone is encouraging for a primary/secondary school student."
    }
}

# --- 2. AUTHENTICATION & INITIALIZATION ---
@st.cache_resource
def get_drive_creds():
    oauth_info = st.secrets["google_oauth"]
    creds = Credentials(
        token=None,
        refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"],
        client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return creds

def get_drive_service():
    creds = get_drive_creds()
    if not creds.valid:
        creds.refresh(Request())
    return build('drive', 'v3', credentials=creds, static_discovery=False)

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
    /* Hide the GitHub/Streamlit menu components */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"], .stDeployButton {display:none !important;}
    
    /* Ensure no stray elements appear */
    #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 0rem;}
    </style>
    """, unsafe_allow_html=True)

# --- NEW CV FUNCTION: FIND BREADBOARD BOUNDARIES ---
def find_breadboard_x_bounds(pil_img):
    """
    Uses edge density to locate the actual breadboard horizontally within the image.
    """
    img_cv = np.array(pil_img)
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_cv

    # Use Canny to find edges (breadboard holes create very dense edge signatures)
    edges = cv2.Canny(gray, 50, 150)
    
    # Project edge density vertically
    col_sums = np.sum(edges, axis=0)

    # Smooth the distribution to find the main body
    window_size = max(int(img_cv.shape[1] * 0.02), 5)
    kernel = np.ones(window_size) / window_size
    smoothed = np.convolve(col_sums, kernel, mode='same')

    # Threshold for what we consider "inside" the breadboard
    threshold_val = np.max(smoothed) * 0.25
    active_cols = np.where(smoothed > threshold_val)[0]

    if len(active_cols) > 0:
        x_start = int(active_cols[0])
        x_end = int(active_cols[-1])
        
        # Verify it looks like a breadboard (takes up at least 30% of width)
        if (x_end - x_start) > img_cv.shape[1] * 0.3:
            return x_start, x_end

    # Fallback if detection fails
    return 0, img_cv.shape[1]

def detect_horizontal_rows(pil_img):
    """
    Detects breadboard rows AFTER resizing. 
    The higher resolution helps the algorithm find holes more accurately.
    """
    img_cv = np.array(pil_img)
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_cv

    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 31, 10
    )

    height, width = thresh.shape
    row_sums = np.sum(thresh, axis=1)

    window_size = max(int(height * 0.005), 5)
    kernel = np.ones(window_size) / window_size
    smoothed_sums = np.convolve(row_sums, kernel, mode='same')

    min_peak_distance = max(int(height * 0.012), 10)
    threshold_val = np.max(smoothed_sums) * 0.08 

    peaks = []
    for i in range(min_peak_distance, height - min_peak_distance):
        if smoothed_sums[i] > threshold_val:
            local_window = smoothed_sums[i - min_peak_distance : i + min_peak_distance + 1]
            if smoothed_sums[i] == np.max(local_window):
                if not peaks or (i - peaks[-1]) >= min_peak_distance:
                    peaks.append(i)

    # MATH FILL-IN ALGORITHM
    if len(peaks) > 5:
        distances = [peaks[i] - peaks[i-1] for i in range(1, len(peaks))]
        median_dist = np.median(distances)
        
        filled_peaks = []
        for i in range(len(peaks)-1):
            filled_peaks.append(peaks[i])
            gap = peaks[i+1] - peaks[i]
            if 1.5 * median_dist < gap < 5 * median_dist:
                num_missing = int(round(gap / median_dist)) - 1
                step = gap / (num_missing + 1)
                for j in range(1, num_missing + 1):
                    filled_peaks.append(int(peaks[i] + j * step))
        filled_peaks.append(peaks[-1])
        peaks = filled_peaks

    # Normalize back to 0-1000 scale based on the NEW height
    return [int((y / height) * 1000) for y in peaks]
    
def process_uploaded_image(file_input):
    """
    Robust image loader to fix Android/iOS rotation and buffering issues.
    """
    try:
        if isinstance(file_input, str):
            img = PILImage.open(file_input)
        else:
            img = PILImage.open(io.BytesIO(file_input.read() if hasattr(file_input, 'read') else file_input))
            
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        
        w, h = img.size
        new_size = (w * 2, h * 4)
        
        img = img.resize(new_size, PILImage.Resampling.LANCZOS)
        
        MAX_DIM = 4000 
        if max(img.size) > MAX_DIM:
            img.thumbnail((MAX_DIM, MAX_DIM), PILImage.Resampling.LANCZOS)
            
        return img
    except Exception as e:
        st.error(f"Image Load Failed: {e}")
        return None

def draw_coordinate_grid(image, snap_rows=None):
    """
    Draws realistic internal breadboard connections dynamically based on the detected board bounds.
    """
    draw = ImageDraw.Draw(image)
    w_img, h_img = image.size
    pale_blue = (173, 216, 230)
    
    # 1. Dynamically locate the breadboard body
    x_start, x_end = find_breadboard_x_bounds(image)
    bb_w = x_end - x_start

    # 2. Calculate standard breadboard proportional offsets relative to the bounding box
    rail_1 = x_start + int(bb_w * 0.05)
    rail_2 = x_start + int(bb_w * 0.12)
    rail_3 = x_start + int(bb_w * 0.88)
    rail_4 = x_start + int(bb_w * 0.95)

    ae_start = x_start + int(bb_w * 0.20)
    ae_end = x_start + int(bb_w * 0.45)
    fj_start = x_start + int(bb_w * 0.55)
    fj_end = x_start + int(bb_w * 0.80)

    # 3. Draw Vertical Power Rails
    for rx in [rail_1, rail_2, rail_3, rail_4]:
        draw.line([(rx, 0), (rx, h_img)], fill=pale_blue, width=3)
    
    # 4. Draw Split Horizontal Rows
    if snap_rows:
        for ry in snap_rows:
            y_px = ry * h_img / 1000
            # Left block (A-E)
            draw.line([(ae_start, y_px), (ae_end, y_px)], fill=pale_blue, width=3)
            # Right block (F-J)
            draw.line([(fj_start, y_px), (fj_end, y_px)], fill=pale_blue, width=3)
            
    # Draw red reference markers on edges
    for i in range(0, 1001, 100):
        x_px, y_px = i * w_img / 1000, i * h_img / 1000
        draw.line([(x_px, 0), (x_px, 30)], fill=(255, 0, 0), width=4)
        draw.line([(0, y_px), (30, y_px)], fill=(255, 0, 0), width=4)
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

def save_to_drive(user_id, task_name, tutor_note, images_dict):
    service = get_drive_service()
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    hk_time_str = datetime.now(hk_tz).strftime('%Y-%m-%d %H:%M:%S')
    task_num = task_name.split(":")[0].replace("Task", "").strip()
    file_prefix = f"user{user_id}_task{task_num}"

    try:
        for img_key, img_obj in images_dict.items():
            if img_obj:
                buf = io.BytesIO()
                img_obj.save(buf, format='PNG')
                buf.seek(0) 
                
                img_metadata = {'name': f"{file_prefix}_{img_key}.png", 'parents': [PARENT_FOLDER_ID]}
                media = MediaIoBaseUpload(buf, mimetype='image/png', resumable=True)
                service.files().create(body=img_metadata, media_body=media).execute()

        # CSV LOGIC UPDATED TO ONLY SAVE TUTOR NOTE
        new_row = pd.DataFrame([{
            "User ID": user_id, "Time": hk_time_str, 
            "Raw": f"{file_prefix}_1.png", "Final": f"{file_prefix}_4.png", 
            "Tutor Note": tutor_note
        }])

        query = f"name='{CSV_FILENAME}' and '{PARENT_FOLDER_ID}' in parents and trashed=false"
        items = service.files().list(q=query, fields="files(id)").execute().get('files', [])

        if not items:
            csv_bytes = new_row.to_csv(index=False).encode('utf-8')
            meta = {'name': CSV_FILENAME, 'parents': [PARENT_FOLDER_ID]}
            media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype='text/csv')
            service.files().create(body=meta, media_body=media).execute()
        else:
            file_id = items[0]['id']
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            df_existing = pd.read_csv(fh)
            df_combined = pd.concat([df_existing, new_row], ignore_index=True)
            
            updated_csv_bytes = df_combined.to_csv(index=False).encode('utf-8')
            media = MediaIoBaseUpload(io.BytesIO(updated_csv_bytes), mimetype='text/csv')
            service.files().update(fileId=file_id, media_body=media).execute()
            
        st.success("Successfully logged to Drive!")
        
    except Exception as e:
        st.error(f"Drive Save Error: {e}")
        
# --- 5. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "analysis_result" not in st.session_state: st.session_state.analysis_result = None
if "hough_rows" not in st.session_state: st.session_state.hough_rows = []
for i in range(1, 5): 
    if f"img{i}" not in st.session_state: st.session_state[f"img{i}"] = None
if "lang" not in st.session_state: st.session_state.lang = "en"

def reset_flow():
    for key in ["step", "components_df", "analysis_result", "img1", "img2", "img3", "img4"]:
        if "df" in key: st.session_state[key] = pd.DataFrame()
        elif "step" in key: st.session_state[key] = 1
        else: st.session_state[key] = None
    st.session_state.hough_rows = []

# --- 6. MAIN UI ---

# LANGUAGE TOGGLE
lang_select = st.radio("🌐", ["English", "繁體中文"], horizontal=True, label_visibility="collapsed")
l = "en" if lang_select == "English" else "hk"

st.title(UI[l]["title"])

with st.sidebar:
    st.header(UI[l]["setup"])
    user_id = st.selectbox(UI[l]["user_id"], [f"{i:02d}" for i in range(51)])
    selected_task = st.selectbox(UI[l]["task"], list(TASKS.keys()))
    
    path = os.path.join(DATA_FOLDER, TASKS[selected_task])
    if os.path.exists(path):
        raw_schematic = process_uploaded_image(path)
        st.image(raw_schematic, caption=UI[l]["target"])
    else:
        st.error(f"Missing {TASKS[selected_task]}")
        st.stop()
    
    st.divider()
    
    # Input Method Toggle (Defaults to Upload)
    input_mode = st.radio(UI[l]["input_mode"], [UI[l]["mode_upload"], UI[l]["mode_camera"]], horizontal=True)
    if input_mode == UI[l]["mode_upload"]:
        active_input = st.file_uploader(UI[l]["upload"], type=["jpg", "png", "jpeg", "webp","heic"])
    else:
        active_input = st.camera_input(UI[l]["camera"])
    
    if st.button(UI[l]["reset"]): 
        reset_flow()
        st.rerun()

    st.divider()
    st.markdown(f"### {UI[l]['guide_title']}")
    st.markdown(UI[l]['guide_text'])

# --- 7. APPLICATION LOGIC ---

if active_input:
    if st.session_state.img1 is None:
        # 1. Resize/Scale first
        st.session_state.img1 = process_uploaded_image(io.BytesIO(active_input.getvalue()))
    
    raw_student = st.session_state.img1

    # 2. Detect rows based on the ALREADY scaled image
    if not st.session_state.hough_rows:
        st.session_state.hough_rows = detect_horizontal_rows(raw_student)

    # STEP 1: DETECTION
    if st.session_state.step == 1:
        col1, col2 = st.columns(2)
        col1.image(raw_schematic, caption=UI[l]["schematic"])
        col2.image(draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows), caption=UI[l]["your_circuit"])

        if st.button(UI[l]["step1_btn"], type="primary"):
            with st.spinner(UI[l]["analyzing"]):
                prompt = """
                    Identify components on the breadboard. Specifically:
                    - POWER SUPPLY: You MUST identify the power input module. It has exactly 2 pins: the red wire/pin (+ve/Vcc) and the black wire/pin (-ve/GND).
                    - SLIDE-SWITCH: You MUST identify exactly 3 pins (legs) positioned continuously in a single straight row. 
                    - 4-pin Push Button, LDR, LED
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
        st.subheader(UI[l]["step2_title"])
        edit_col, img_col = st.columns([1, 2])
        updated_data = []
        with edit_col:
            for i, row in st.session_state.components_df.iterrows():
                with st.expander(f"📍 {row['Component']}"):
                    lx = st.slider(f"X_{i}", 0, 1000, int(row["LX"]), key=f"x{i}")
                    raw_ly = st.slider(f"Y_{i}", 0, 1000, int(row["LY"]), key=f"y{i}")
                    
                    snapped_ly = raw_ly
                    if st.session_state.hough_rows:
                        snapped_ly = min(st.session_state.hough_rows, key=lambda ry: abs(ry - raw_ly))
                    
                    if raw_ly != snapped_ly:
                        st.caption(UI[l]["snapped"].format(y=snapped_ly))
                        
                    updated_data.append({"Component": row["Component"], "CX": row["CX"], "CY": row["CY"], "LX": lx, "LY": snapped_ly})
            edited_df = pd.DataFrame(updated_data)

        with img_col:
            base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows)
            st.session_state.img3 = draw_pins_on_image(base_grid_img, edited_df)
            st.image(st.session_state.img3, caption=UI[l]["verify"])

        if st.button(UI[l]["step2_confirm"], type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.step = 3
            st.rerun()

    # STEP 3: ANALYSIS
    elif st.session_state.step == 3:
        st.subheader(UI[l]["step3_title"])
        
        if st.session_state.analysis_result is None or st.session_state.img4 is None:
            with st.spinner(UI[l]["checking"]):
                summary = st.session_state.components_df.to_string(index=False)
                
                # UPDATED PROMPT: Requesting tutor_note to support correction request
                prompt = f"""
                    Task: {selected_task}. 
                    
                    Structural Connectivity Rules:
                    1. TERMINAL STRIPS (Center): Pins in the same ROW (horizontal) are electrically connected.
                    2. POWER RAILS (Edges): The two leftmost and two rightmost columns are Power Rails. Pins in the same COLUMN (vertical) are electrically connected. 
                    3. PALE BLUE OVERLAYS: Any component pin placed on a vertical pale blue line is automatically connected to the Power Supply (Vcc or GND) corresponding to that rail.
                
                    Electrical Analysis Rules: 
                    1. POWER SUPPLY: The Power Supply component provides Vcc (+ve) and GND (-ve). All circuits MUST form a valid, closed loop originating from the Power Supply Vcc pin and terminating at the Power Supply GND pin.
                    2. SLIDE-SWITCH: 3 pins in one row. Pin 2 is Common.
                    3. SERIES & PATHS: Components must share a single node (horizontal row for center, vertical column for rails) to connect. The exact sequential order does NOT matter. Evaluate the semantic flow from +ve to GND.
                    4. RESISTOR VALUES: Ignore specific resistor values. Treat all resistors as functionally equivalent.
                
                    Component Data (Available Pins):
                    {summary}
                
                    Instructions & Evaluation:
                    - Identify errors based on the 'Component Data' provided. Trace the circuit from the Power Supply +ve pin to the GND pin.
                    - If a student connects a component horizontally across a Power Rail (expecting horizontal connection where it is vertical), flag as "wrong_orientation".
                    - If a circuit is broken because the student expects horizontal connectivity on the edges, flag as "open_circuit" and explain the vertical rail logic in the feedback.
                    - For 'location', you MUST use the [LY, LX] coordinates of the specific pin causing the error.
                
                    Compare to Target Schematic. Return JSON with 'feedback', 'tutor_note' (private grading data), and 'detected_errors'.
                    {UI[l]["prompt_addition"]}
                    """
                
                try:
                    resp = client.models.generate_content(
                        model=MODEL_ID, 
                        contents=[raw_schematic, st.session_state.img3, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema={
                                "type": "OBJECT",
                                "properties": {
                                    "feedback": {"type": "STRING"},
                                    "tutor_note": {"type": "STRING", "description": "Specific, factual note about student errors suitable for saving to grading CSV logs."},
                                    "detected_errors": {
                                        "type": "ARRAY", 
                                        "items": {
                                            "type": "OBJECT",
                                            "properties": {
                                                "error_type": {"type": "STRING"},
                                                "location": {"type": "ARRAY", "items": {"type": "INTEGER"}}
                                            }
                                        }
                                    }
                                },
                                "required": ["feedback", "tutor_note", "detected_errors"]
                            }
                        )
                    )
                    
                    result = resp.parsed
                    if isinstance(result, list) and len(result) > 0:
                        result = result[0]
                    
                    st.session_state.analysis_result = result
                    
                    diag_img = st.session_state.img3.copy()
                    draw = ImageDraw.Draw(diag_img)
                    w, h = diag_img.size
                    
                    errors = st.session_state.analysis_result.get("detected_errors", [])
                    for err in errors:
                        err_type = err.get("error_type", "open_circuit")
                        loc = err.get("location", [])
                        
                        if len(loc) == 2:
                            ey, ex = loc
                            
                            if not st.session_state.components_df.empty:
                                df = st.session_state.components_df
                                distances = np.sqrt((df['LX'] - ex)**2 + (df['LY'] - ey)**2)
                                nearest_idx = distances.idxmin()
                                ex = df.loc[nearest_idx, 'LX']
                                ey = df.loc[nearest_idx, 'LY']

                            px, py = ex * w / 1000, ey * h / 1000
                            
                            if err_type == "wrong_component":
                                draw.rectangle([px-35, py-35, px+35, py+35], outline="blue", width=8)
                            elif err_type == "wrong_orientation":
                                draw.ellipse([px-30, py-30, px+30, py+30], outline="yellow", width=8)
                            else:
                                draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=8)
                                
                    st.session_state.img4 = diag_img
                    
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")
                    st.session_state.step = 2

        if st.session_state.img4:
            st.image(st.session_state.img4, caption=UI[l]["ai_diag"])
        
        if st.session_state.analysis_result:
            feedback_text = st.session_state.analysis_result.get("feedback", "No feedback provided.")
            tutor_note = st.session_state.analysis_result.get("tutor_note", "No tutor note generated.")
            
            st.info(feedback_text)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button(UI[l]["save"], type="primary", use_container_width=True):
                    # Passing only the tutor_note into save_to_drive per requested logic
                    save_to_drive(user_id, selected_task, tutor_note, 
                                 {"1": st.session_state.img1, "2": st.session_state.img2, 
                                  "3": st.session_state.img3, "4": st.session_state.img4})
            with col_b:
                if st.button(UI[l]["back"], use_container_width=True):
                    st.session_state.analysis_result = None
                    st.session_state.step = 2
                    st.rerun()
            with col_c:
                if st.button(UI[l]["new"], use_container_width=True):
                    reset_flow()
                    st.rerun()
                    
else:
    st.info(UI[l]["upload_prompt"])
