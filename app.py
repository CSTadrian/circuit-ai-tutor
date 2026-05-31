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
    "Task 4: Switch Control": "task4_switch.png",
    "Task 5: Button Control": "task5_button.png",
    "Task 6: Capacitor": "task6_capacitor.png",
    "Exam 1": "exam1.png",
    "Exam 2": "exam2.png",
    "Exam 3": "exam3.png"
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

def detect_breadboard_grid_from_holes(pil_img):
    """
    Detects individual breadboard holes and clusters them to find 
    the exact physical rows and columns, ignoring shadows and edges.
    Returns: (row_y_coords, col_x_coords) scaled to 0-1000.
    """
    # 1. Convert PIL to OpenCV format
    img_cv = np.array(pil_img)
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_cv

    h, w = gray.shape

    # 2. Preprocessing: Enhance contrast and Threshold
    # Breadboard holes are typically the darkest spots
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Adaptive threshold to handle uneven lighting
    thresh = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 21, 10
    )

    # 3. Find Contours (The Holes)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    hole_centers = []
    
    # Estimate reasonable hole sizes based on image resolution
    # A breadboard has roughly 30-60 rows depending on size
    expected_hole_w = w * 0.015
    expected_hole_h = h * 0.01
    
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        aspect_ratio = float(cw) / max(ch, 1)
        area = cv2.contourArea(cnt)
        
        # Filter: Is it roughly square/circular and the right size?
        if 0.5 < aspect_ratio < 2.0 and (expected_hole_w * 0.3) < cw < (expected_hole_w * 3):
            # Calculate center of the hole
            cx = x + cw // 2
            cy = y + ch // 2
            hole_centers.append((cx, cy))

    if not hole_centers:
        return [], []

    # 4. Clustering: Group coordinates into Rows (Y) and Columns (X)
    # Convert to numpy array for easier slicing
    holes = np.array(hole_centers)
    
    def cluster_coordinates(coords, tolerance):
        """Groups close coordinates and returns their average."""
        sorted_coords = np.sort(coords)
        clusters = []
        current_cluster = [sorted_coords[0]]
        
        for val in sorted_coords[1:]:
            if val - current_cluster[-1] <= tolerance:
                current_cluster.append(val)
            else:
                clusters.append(int(np.mean(current_cluster)))
                current_cluster = [val]
        clusters.append(int(np.mean(current_cluster)))
        return clusters

    # Tolerance for clustering (e.g., holes within 1% of height are in the same row)
    y_tolerance = h * 0.008 
    x_tolerance = w * 0.015

    row_y_pixels = cluster_coordinates(holes[:, 1], y_tolerance)
    col_x_pixels = cluster_coordinates(holes[:, 0], x_tolerance)

    # 5. Normalize back to the 0-1000 scale
    normalized_rows = [int((y / h) * 1000) for y in row_y_pixels]
    normalized_cols = [int((x / w) * 1000) for x in col_x_pixels]

    return normalized_rows, normalized_cols

    
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

def draw_coordinate_grid(image, snap_rows=None, snap_cols=None):
    """
    Draws realistic internal breadboard connections (A-E, F-J, Power Rails) 
    anchored perfectly to the exact coordinates detected from physical holes.
    """
    draw = ImageDraw.Draw(image)
    w, h = image.size
    pale_blue = (173, 216, 230)
    boundary_color = (0, 0, 255) # Color for the middle gap trench

    # 1. Determine horizontal bounds based on ACTUAL physical holes
    if snap_cols and len(snap_cols) >= 2:
        # Minimum X is the far-left column of holes, Maximum X is the far-right.
        # This completely ignores shadows and plastic edges.
        x_min_prop = min(snap_cols) / 1000.0
        x_max_prop = max(snap_cols) / 1000.0
    else:
        # Fallback if column detection fails
        x_min_prop = 0.05
        x_max_prop = 0.95

    # Convert proportions to exact pixel coordinates
    x_min_px = x_min_prop * w
    x_max_px = x_max_prop * w
    board_w_px = x_max_px - x_min_px # The true width of the hole matrix

    # 2. DRAW MIDDLE GAP (Vertical trench running through the center)
    # Exactly halfway between the leftmost and rightmost detected holes
    mid_x = x_min_px + (board_w_px * 0.5)
    draw.line([(mid_x, 0), (mid_x, h)], fill=boundary_color, width=4)

    # 3. DRAW POWER RAILS (Vertical lines)
    # We position these proportionally relative to the true hole boundaries
    rail_x_positions = [
        x_min_px,                           # Left outer rail (-)
        x_min_px + (board_w_px * 0.07),     # Left inner rail (+)
        x_max_px - (board_w_px * 0.07),     # Right inner rail (+)
        x_max_px                            # Right outer rail (-)
    ]
    
    for rx in rail_x_positions:
        draw.line([(rx, 0), (rx, h)], fill=pale_blue, width=3)

    # 4. DRAW SPLIT HORIZONTAL ROWS (Columns A-E and F-J)
    if snap_rows:
        # Calculate the exact start and end X-coordinates for the left block (A-E)
        ae_start = x_min_px + (board_w_px * 0.18)
        ae_end   = x_min_px + (board_w_px * 0.45)
        
        # Calculate the exact start and end X-coordinates for the right block (F-J)
        fj_start = x_min_px + (board_w_px * 0.55)
        fj_end   = x_min_px + (board_w_px * 0.82)
        
        for ry in snap_rows:
            y_px = ry * h / 1000.0
            
            # Draw Left block (A-E)
            draw.line([(ae_start, y_px), (ae_end, y_px)], fill=pale_blue, width=3)
            
            # Draw Right block (F-J)
            draw.line([(fj_start, y_px), (fj_end, y_px)], fill=pale_blue, width=3)

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


# --- NEW: VISUAL SUMMARY GENERATOR (Vertical Up/Down Layout) ---
def create_visual_report(successes, errors, lang):
    """Generates a vertical summary image card of the student's performance."""
    # Create a blank white canvas (Taller to handle vertical lists)
    img = PILImage.new('RGB', (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Title
    title = "Visual Performance Summary 📊" if lang == "en" else "視覺化成果總結 📊"
    draw.text((30, 20), title, fill=(0, 0, 0))
    
    # --- TOP BOX: Successes (Good) ---
    draw.rectangle([30, 60, 770, 280], outline=(0, 150, 0), width=3, fill=(240, 255, 240))
    draw.text((50, 75), "✅ What you did well! / 做得好嘅地方！", fill=(0, 128, 0))
    
    y_off = 110
    # Limit to 5 items to prevent vertical overflow in the top box
    for item in successes[:5]: 
        draw.text((60, y_off), f"🌟 {item}", fill=(30, 30, 30))
        y_off += 30

    # --- BOTTOM BOX: Errors (Needs Improvement) ---
    draw.rectangle([30, 310, 770, 560], outline=(200, 100, 0), width=3, fill=(255, 250, 240))
    draw.text((50, 325), "🛠️ Things to check / 需要檢查嘅地方", fill=(200, 100, 0))
    
    y_off = 360
    # Limit to 5 items to prevent vertical overflow in the bottom box
    for item in errors[:5]:
        draw.text((60, y_off), f"🔍 {item}", fill=(30, 30, 30))
        y_off += 30
        
    return img
    
def save_to_drive(user_id, task_name, ai_feedback, images_dict):
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

        new_row = pd.DataFrame([{
            "User ID": user_id, "Time": hk_time_str, 
            "Raw": f"{file_prefix}_1.png", "Final": f"{file_prefix}_4.png", 
            "Feedback": ai_feedback
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
if "hough_cols" not in st.session_state: st.session_state.hough_cols = []
if "breadboard_corners" not in st.session_state: st.session_state.breadboard_corners = None
for i in range(1, 5): 
    if f"img{i}" not in st.session_state: st.session_state[f"img{i}"] = None
if "lang" not in st.session_state: st.session_state.lang = "en"

def reset_flow():
    for key in ["step", "components_df", "analysis_result", "img1", "img2", "img3", "img4"]:
        if "df" in key: st.session_state[key] = pd.DataFrame()
        elif "step" in key: st.session_state[key] = 1
        else: st.session_state[key] = None
    st.session_state.hough_rows = []
    st.session_state.breadboard_corners = None

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

    # 2. Detect Rows AND Columns via Direct Hole Detection
    if not st.session_state.hough_rows:
        st.session_state.hough_rows, st.session_state.hough_cols = detect_breadboard_grid_from_holes(raw_student)

    # STEP 1: DETECTION
    if st.session_state.step == 1:
        col1, col2 = st.columns(2)
        col1.image(raw_schematic, caption=UI[l]["schematic"])
        col2.image(draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners), caption=UI[l]["your_circuit"])

        if st.button(UI[l]["step1_btn"], type="primary"):
            with st.spinner(UI[l]["analyzing"]):
                prompt = """
                    1. Identify the BREADBOARD boundaries: Provide the [y, x] coordinates for the four outer corners (top_left, top_right, bottom_right, bottom_left).
                    2. Identify components on the breadboard. Specifically:
                    - POWER SUPPLY: You MUST identify the power input module. It has exactly 2 pins: the red wire/pin (+ve/Vcc) and the black wire/pin (-ve/GND).
                    - SLIDE-SWITCH: You MUST identify exactly 3 pins (legs) positioned continuously in a single straight row. 
                    - 4-pin Push Button, LDR, LED
                    - resistor (check color bands: '5-band 300ohm', '1000 ohm', or '10k ohm')
                    Return JSON mapping 'breadboard_corners' and 'components'.
                    """
                resp = client.models.generate_content(
                    model=MODEL_ID, contents=[raw_student, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema={
                            "type": "OBJECT",
                            "properties": {
                                "breadboard_corners": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "top_left": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                                        "top_right": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                                        "bottom_right": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                                        "bottom_left": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                                    }
                                },
                                "components": {
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
                            }
                        }
                    )
                )
                
                result = resp.parsed
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                
                # Extract and store corners
                st.session_state.breadboard_corners = result.get("breadboard_corners", {})

                # Process components
                records = []
                for item in result.get("components", []):
                    center = item.get('center', [500, 500])
                    if isinstance(center, list) and len(center) == 2:
                        cy, cx = center
                    else:
                        cy, cx = 500, 500
                        
                    legs = item.get('legs', [])
                    if isinstance(legs, list):
                        for i, leg in enumerate(legs):
                            if isinstance(leg, list) and len(leg) >= 2:
                                ly, lx = leg[0], leg[1]
                                records.append({
                                    "Component": f"{item.get('name')} (Pin {i+1})", 
                                    "CX": cx, 
                                    "CY": cy, 
                                    "LX": lx, 
                                    "LY": ly
                                })
                            else:
                                continue
                                    
                st.session_state.components_df = pd.DataFrame(records)
                base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.hough_cols)
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
            base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.hough_cols)
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
                
                prompt = f"""
                    Task: {selected_task}. 
                    Structural Connectivity Rules:
                    1. TERMINAL STRIPS (Center): Pins in the same ROW (horizontal) are electrically connected.
                    2. POWER RAILS (Edges): The two leftmost and two rightmost columns are Power Rails. 
                    3. PALE BLUE OVERLAYS: Connected to Power Supply.
                
                    Electrical Analysis Rules: 
                    1. POWER SUPPLY: Must form a closed loop.
                    2. SERIES REVERSIBILITY: An LED in series with a resistor is considered correct regardless of order (LED -> Resistor IS THE SAME AS Resistor -> LED).
                    3. RESISTOR VALUES IGNORED: Do NOT check exact resistance values or color bands. Only verify that a generic resistor component is present and connected properly.
                
                    Pedagogical Scaffolding Rules (CRITICAL):
                    1. IF THERE ARE ERRORS: DO NOT give direct answers or tell the student which exact rows to change. Instead, use SOCRATIC SCAFFOLDING. Ask a guiding question related to the underlying theory of their specific mistake (e.g., if the circuit is open, ask how electricity needs a continuous path to return home). 
                    2. IF 100% CORRECT: Praise them enthusiastically, and then provide a "What-If" CHALLENGE to encourage deeper exploration. Tailor the challenge to the components used (e.g., "What happens if you swap the resistor for a smaller one?", "Can you add a button?", "If you have a capacitor, how can you make the LED fade out slowly?").

                    Bilingual Output Requirement:
                    For the 'feedback' string, provide the English text first, followed by a newline, and then a formal Cantonese (Traditional Chinese) translation. Use emojis and an engaging tone suitable for P4-S3 students.
                    
                    Example Format (Error - Socratic):
                    "It looks like your LED isn't lighting up! 🧐 Follow the path of electricity from the positive red wire. Does it have a continuous bridge to reach the negative wire? Where does the path break?\n\n睇落你粒 LED 唔著喎！🧐 試吓跟住電流由紅線 (+) 出發嘅路徑。佢有冇一條完整嘅路徑可以返去黑線 (-)？條路喺邊度斷咗呀？"
                    
                    Example Format (Correct - Challenge):
                    "Perfect circuit! 🎉 Since it's working beautifully, here is a challenge: What do you think will happen to the LED brightness if you replace the current resistor with a much stronger one? Try it out! ⚡\n\n完美嘅電路！🎉 既然已經成功咗，考吓你：如果你換一粒電阻值更大嘅電阻，你估吓 LED 嘅亮度會有咩變化？試吓啦！⚡"

                    Component Data (Available Pins):
                    {summary}
                
                    Compare to Target Schematic. Return JSON with 'feedback' (containing the Socratic/Challenge text), 'detected_errors', 'success_summary' (array of strings), and 'error_summary' (array of strings).
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
                                    "success_summary": {"type": "ARRAY", "items": {"type": "STRING"}},
                                    "error_summary": {"type": "ARRAY", "items": {"type": "STRING"}},
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
                                "required": ["feedback", "detected_errors", "success_summary", "error_summary"]
                            }
                        )
                    )
                    
                    result = resp.parsed
                    if isinstance(result, list) and len(result) > 0:
                        result = result[0]
                    
                    st.session_state.analysis_result = result
                    
                    # Drawing logic
                    diag_img = st.session_state.img3.copy()
                    draw = ImageDraw.Draw(diag_img)
                    w, h = diag_img.size
                    
                    errors = st.session_state.analysis_result.get("detected_errors", [])
                    for err in errors:
                        loc = err.get("location", [])
                        if len(loc) == 2:
                            ey, ex = loc
                            px, py = ex * w / 1000, ey * h / 1000
                            draw.ellipse([px-25, py-25, px+25, py+25], outline="red", width=8)
                                
                    st.session_state.img4 = diag_img
                    
                except Exception as e:
                    st.error(f"AI Analysis failed: {e}")
                    st.session_state.step = 2

        # Display Logic
        if st.session_state.img4:
            st.image(st.session_state.img4, caption=UI[l]["ai_diag"])
        
        if st.session_state.analysis_result:
            feedback_text = st.session_state.analysis_result.get("feedback", "")
            st.info(feedback_text)
            
            success_list = st.session_state.analysis_result.get("success_summary", [])
            error_list = st.session_state.analysis_result.get("error_summary", [])
            
            report_card_img = create_visual_report(success_list, error_list, l)
            st.image(report_card_img, use_container_width=True)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button(UI[l]["save"], type="primary"):
                    save_to_drive(user_id, selected_task, feedback_text, 
                                 {"1": st.session_state.img1, "4": st.session_state.img4, "summary": report_card_img})
            with col_b:
                if st.button(UI[l]["back"]):
                    st.session_state.step = 2
                    st.rerun()
            with col_c:
                if st.button(UI[l]["new"]):
                    reset_flow()
                    st.rerun()
                    
else:
    st.info(UI[l]["upload_prompt"])
