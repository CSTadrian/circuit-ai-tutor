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
    "Task 2: LED in Series": "task2_series_led.png",
    "Task 3: Parallel LED Setup": "task3_parallel_led.png",
}

# --- NEW: MULTIMODAL ASSETS ---
# You can replace these strings with local file paths (e.g., "videos/task1.mp4") 
# or URLs to test the video output.
TUTORIAL_ASSETS = {
    "Task 1: Basic LED Circuit": {
        "video": "https://www.youtube.com/watch?v=your_video_id", # Replace with actual video file or URL
        "guide_image": "task1_step_by_step.png", 
        "steps": [
            "1. Connect the Ground wire to the Blue Rail.",
            "2. Place the LED (Long leg in Row 15).",
            "3. Add the Resistor to Row 15 and Row 18.",
            "4. Connect Power (Red Rail) to Row 18."
        ]
    }
}

DATA_FOLDER = "data"
MODEL_ID = "gemini-3.1-pro-preview"
PARENT_FOLDER_ID = "1_cn9lfvMLaozDTx8pvU6LP62J9AVFrvz"
CSV_FILENAME = "circuit_audit_logs.csv"

# --- NEW: UPDATED LANGUAGE DICTIONARY ---
UI = {
    "en": {
        "title": "🔌 AI Circuit Tutor",
        "tutorial_tab": "📖 Tutorial",
        "diagnostic_tab": "🔍 Circuit Audit",
        "video_title": "Video Guide: How to Construct",
        "image_guide": "Construction Steps",
        "show_solution": "📺 Watch Video Solution",
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
        "your_circuit": "Your Circuit (Pale Blue = Internal)",
        "step1_btn": "🔍 Step 1: Detect Components",
        "analyzing": "AI analyzing breadboard...",
        "step2_title": "⚙️ Step 2: Fine-Tune Component Pins",
        "step2_confirm": "✅ Confirm & Analyze Circuit",
        "snapped": "*(Y snapped to row: {y})*",
        "verify": "Verify Pin Alignment",
        "step3_title": "🧠 Step 3: AI Diagnosis",
        "checking": "Checking electrical logic...",
        "ai_diag": "AI Diagnosis: Multimodal Feedback",
        "save": "💾 Save to Drive",
        "back": "🔙 Back",
        "new": "🎉 New Task",
        "upload_prompt": "Select an input method to begin.",
        "prompt_addition": "", 
        "guide_title": "📖 Quick Guide",
        "camera": "Take a Photo",
        "guide_text": """
        **Visual Legend:**
        * 🔴 **Red Circle:** Open circuit.
        * 🟦 **Blue Box:** Wrong component.
        * 🟡 **Yellow Circle:** Orientation error.
        """,
    },
    "hk": {
        "title": "🔌 AI 電路導師",
        "tutorial_tab": "📖 教學指南",
        "diagnostic_tab": "🔍 電路審核",
        "video_title": "影片指南：如何接駁",
        "image_guide": "組裝步驟",
        "show_solution": "📺 查看影片示範",
        "setup": "設定",
        "user_id": "選擇學生 ID",
        "task": "選擇任務",
        "target": "目標電路圖",
        "input_mode": "輸入方式",
        "mode_upload": "上傳圖片",
        "mode_camera": "使用相機",
        "upload": "上傳照片",
        "reset": "重置",
        "schematic": "電路圖",
        "your_circuit": "你的電路",
        "step1_btn": "🔍 第一步：偵測零件",
        "analyzing": "AI 正在分析...",
        "step2_title": "⚙️ 第二步：微調引腳",
        "step2_confirm": "✅ 確認並分析",
        "snapped": "*(對齊至行：{y})*",
        "verify": "請核對引腳位置",
        "step3_title": "🧠 第三步：AI 診斷",
        "checking": "正在檢查...",
        "ai_diag": "AI 診斷：多模態回饋",
        "save": "💾 儲存",
        "back": "🔙 返回",
        "new": "🎉 新任務",
        "upload_prompt": "請選擇上傳方式以開始。",
        "guide_title": "📖 快速指南",
        "camera": "拍攝照片",
        "guide_text": "**圖示：** 🔴 斷路 | 🟦 零件錯誤 | 🟡 方向錯誤",
        "prompt_addition": "Please provide the 'feedback' text entirely in written formal Cantonese (Traditional Chinese)."
    }
}

# --- 2. AUTHENTICATION (RETAINED FROM ORIGINAL) ---
@st.cache_resource
def get_drive_creds():
    oauth_info = st.secrets["google_oauth"]
    return Credentials(
        token=None, refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"], client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )

def get_drive_service():
    creds = get_drive_creds()
    if not creds.valid: creds.refresh(Request())
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

# --- 3. HELPER FUNCTIONS ---
def detect_horizontal_rows(pil_img):
    img_cv = np.array(pil_img)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY) if len(img_cv.shape) == 3 else img_cv
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10)
    row_sums = np.sum(thresh, axis=1)
    window_size = max(int(thresh.shape[0] * 0.005), 5)
    smoothed_sums = np.convolve(row_sums, np.ones(window_size)/window_size, mode='same')
    peaks = []
    min_dist = max(int(thresh.shape[0] * 0.012), 10)
    for i in range(min_dist, thresh.shape[0] - min_dist):
        if smoothed_sums[i] > np.max(smoothed_sums) * 0.08:
            if smoothed_sums[i] == np.max(smoothed_sums[i-min_dist:i+min_dist+1]):
                if not peaks or (i - peaks[-1]) >= min_dist: peaks.append(i)
    return [int((y / thresh.shape[0]) * 1000) for y in peaks]

def process_uploaded_image(file_input):
    try:
        img = PILImage.open(io.BytesIO(file_input.read()) if hasattr(file_input, 'read') else file_input)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = img.resize((img.size[0]*2, img.size[1]*4), PILImage.Resampling.LANCZOS)
        if max(img.size) > 4000: img.thumbnail((4000, 4000), PILImage.Resampling.LANCZOS)
        return img
    except Exception as e:
        st.error(f"Load Failed: {e}"); return None

def draw_coordinate_grid(image, snap_rows=None):
    draw = ImageDraw.Draw(image)
    w, h = image.size
    pale_blue = (173, 216, 230)
    for off in [0.05, 0.10, 0.90, 0.95]: draw.line([(int(w*off),0),(int(w*off),h)], fill=pale_blue, width=3)
    if snap_rows:
        for ry in snap_rows:
            y_px = ry * h / 1000
            draw.line([(w*0.18, y_px), (w*0.45, y_px)], fill=pale_blue, width=3)
            draw.line([(w*0.55, y_px), (w*0.82, y_px)], fill=pale_blue, width=3)
    return image

def draw_pins_on_image(image, df):
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    w, h = img_copy.size
    for _, r in df.iterrows():
        start, end = (r["CX"]*w/1000, r["CY"]*h/1000), (r["LX"]*w/1000, r["LY"]*h/1000)
        draw.line([start, end], fill=(255,165,0), width=5)
        draw.ellipse([end[0]-6, end[1]-6, end[0]+6, end[1]+6], fill=(255,255,0), outline=(0,0,0))
    return img_copy

# --- 4. SESSION STATE ---
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

# --- 5. MAIN UI ---
st.set_page_config(page_title="AI Circuit Tutor", layout="wide")
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
    else: st.stop()
    st.divider()
    input_mode = st.radio(UI[l]["input_mode"], [UI[l]["mode_upload"], UI[l]["mode_camera"]], horizontal=True)
    active_input = st.file_uploader(UI[l]["upload"], type=["jpg", "png", "jpeg", "webp","heic"]) if input_mode == UI[l]["mode_upload"] else st.camera_input(UI[l]["camera"])
    if st.button(UI[l]["reset"]): reset_flow(); st.rerun()

# --- NEW: MULTIMODAL TABS ---
tab_audit, tab_tutorial = st.tabs([UI[l]["diagnostic_tab"], UI[l]["tutorial_tab"]])

with tab_tutorial:
    if selected_task in TUTORIAL_ASSETS:
        asset = TUTORIAL_ASSETS[selected_task]
        st.subheader(UI[l]["video_title"])
        # MULTIMODAL OUTPUT: Video
        st.video(asset["video"])
        
        st.divider()
        st.subheader(UI[l]["image_guide"])
        col_steps, col_guide = st.columns([1, 1])
        with col_steps:
            for i, step in enumerate(asset["steps"]):
                st.write(f"**Step {i+1}:** {step}")
        with col_guide:
            # MULTIMODAL OUTPUT: Instructional Image
            if os.path.exists(os.path.join(DATA_FOLDER, asset["guide_image"])):
                st.image(os.path.join(DATA_FOLDER, asset["guide_image"]), caption="Step-by-Step Storyboard")
    else:
        st.info("Tutorial content for this task is coming soon!")

with tab_audit:
    if active_input:
        if st.session_state.img1 is None:
            st.session_state.img1 = process_uploaded_image(io.BytesIO(active_input.getvalue()))
        raw_student = st.session_state.img1
        if not st.session_state.hough_rows:
            st.session_state.hough_rows = detect_horizontal_rows(raw_student)

        # STEP 1: DETECTION
        if st.session_state.step == 1:
            col1, col2 = st.columns(2)
            col1.image(raw_schematic, caption=UI[l]["schematic"])
            col2.image(draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows), caption=UI[l]["your_circuit"])
            if st.button(UI[l]["step1_btn"], type="primary"):
                with st.spinner(UI[l]["analyzing"]):
                    prompt = "Identify components (Power, Switch, Button, LDR, LED, Resistor). Return JSON: 'name', 'center': [y,x], 'legs': [[y,x],...]"
                    resp = client.models.generate_content(model=MODEL_ID, contents=[raw_student, prompt], config=types.GenerateContentConfig(response_mime_type="application/json", response_schema={"type":"ARRAY", "items":{"type":"OBJECT", "properties":{"name":{"type":"STRING"},"center":{"type":"ARRAY", "items":{"type":"INTEGER"}},"legs":{"type":"ARRAY", "items":{"type":"ARRAY", "items":{"type":"INTEGER"}}}}}}))
                    records = []
                    for item in resp.parsed:
                        cy, cx = item.get('center', [500,500])
                        for i, (ly, lx) in enumerate(item.get('legs', [])):
                            records.append({"Component": f"{item.get('name')} (Pin {i+1})", "CX": cx, "CY": cy, "LX": lx, "LY": ly})
                    st.session_state.components_df = pd.DataFrame(records)
                    st.session_state.img2 = draw_pins_on_image(draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows), st.session_state.components_df)
                    st.session_state.step = 2; st.rerun()

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
                        snapped_ly = min(st.session_state.hough_rows, key=lambda ry: abs(ry - raw_ly)) if st.session_state.hough_rows else raw_ly
                        if raw_ly != snapped_ly: st.caption(UI[l]["snapped"].format(y=snapped_ly))
                        updated_data.append({"Component": row["Component"], "CX": row["CX"], "CY": row["CY"], "LX": lx, "LY": snapped_ly})
            edited_df = pd.DataFrame(updated_data)
            with img_col:
                st.session_state.img3 = draw_pins_on_image(draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows), edited_df)
                st.image(st.session_state.img3, caption=UI[l]["verify"])
            if st.button(UI[l]["step2_confirm"], type="primary"):
                st.session_state.components_df = edited_df; st.session_state.step = 3; st.rerun()

        # STEP 3: ANALYSIS & MULTIMODAL FEEDBACK
        elif st.session_state.step == 3:
            st.subheader(UI[l]["step3_title"])
            if st.session_state.analysis_result is None or st.session_state.img4 is None:
                with st.spinner(UI[l]["checking"]):
                    summary = st.session_state.components_df.to_string(index=False)
                    prompt = f"Task: {selected_task}. Trace circuit from Power Supply +ve to GND. Rule 1: Rows connect. Rule 2: Vertical rails connect. Return JSON with 'feedback', 'detected_errors' (error_type, location [y,x]), and 'show_video_tutorial' (boolean). {UI[l]['prompt_addition']}"
                    resp = client.models.generate_content(model=MODEL_ID, contents=[raw_schematic, st.session_state.img3, prompt], config=types.GenerateContentConfig(response_mime_type="application/json", response_schema={"type": "OBJECT", "properties": {"feedback": {"type": "STRING"}, "detected_errors": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"error_type": {"type": "STRING"}, "location": {"type": "ARRAY", "items": {"type": "INTEGER"}}}}}}, "show_video_tutorial": {"type": "BOOLEAN"}}, "required": ["feedback", "detected_errors", "show_video_tutorial"]}))
                    st.session_state.analysis_result = resp.parsed
                    diag_img = st.session_state.img3.copy()
                    draw = ImageDraw.Draw(diag_img)
                    for err in st.session_state.analysis_result.get("detected_errors", []):
                        ly, lx = err.get("location", [0,0])
                        px, py = lx * diag_img.size[0] / 1000, ly * diag_img.size[1] / 1000
                        draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=8)
                    st.session_state.img4 = diag_img

            if st.session_state.img4: st.image(st.session_state.img4, caption=UI[l]["ai_diag"])
            if st.session_state.analysis_result:
                st.info(st.session_state.analysis_result.get("feedback", ""))
                
                # MULTIMODAL ACTION: Proactive Video Suggestion
                if st.session_state.analysis_result.get("show_video_tutorial", False):
                    st.warning("Struggling with the connections? Check the video tutorial in the 'Tutorial' tab above!")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a: 
                    if st.button(UI[l]["save"], type="primary", use_container_width=True): save_to_drive(user_id, selected_task, st.session_state.analysis_result.get("feedback"), {"1":st.session_state.img1, "4":st.session_state.img4})
                with col_b: 
                    if st.button(UI[l]["back"], use_container_width=True): st.session_state.analysis_result = None; st.session_state.step = 2; st.rerun()
                with col_c:
                    if st.button(UI[l]["new"], use_container_width=True): reset_flow(); st.rerun()
    else: st.info(UI[l]["upload_prompt"])
