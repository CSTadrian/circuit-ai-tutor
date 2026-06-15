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

# --- SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import random

# --- 1. CONFIGURATION & SETUP ---
DATA_FOLDER = "data"
MODEL_ID = "gemini-3.1-pro-preview"

# Google Drive Config
PARENT_FOLDER_ID = "1_cn9lfvMLaozDTx8pvU6LP62J9AVFrvz"
CSV_FILENAME = "circuit_audit_logs.csv"

# --- LANGUAGE DICTIONARY (Updated for Schematicless Exploration) ---
UI = {
    "en": {
        "title": "🔌 AI Circuit Explorer (Schematic-Free Mode)",
        "setup": "Setup",
        "user_id": "Select User ID",
        "inferred_task": "Inferred Invention Type",
        "input_mode": "Input Method",
        "mode_upload": "Upload Image",
        "mode_camera": "Use Camera",
        "upload": "Upload Student Photo",
        "reset": "Reset Process",
        "your_circuit": "Your Circuit (Pale Blue = Internal Connections)",
        "step1_btn": "🔍 Step 1: Discover Components & Intent",
        "analyzing": "AI reverse-engineering breadboard layout...",
        "step2_title": "⚙️ Step 2: Fine-Tune Component Pins (Auto-Snapping)",
        "step2_confirm": "✅ Confirm & Analyze Circuit Logic",
        "snapped": "*(Y auto-snapped to nearest row: {y})*",
        "verify": "Verify Orange Legs & Yellow Pins (Snapped to Blue Rows)",
        "step3_title": "🧠 Step 3: AI Intent & Diagnosis Verdict",
        "checking": "Analyzing electrical loops and inferring system goals...",
        "ai_diag": "AI Analysis: Red circles indicate potential wiring or safety issues",
        "save": "💾 Save to Drive",
        "back": "🔙 Back",
        "new": "🎉 New Invention",
        "upload_prompt": "Please select an input method to upload or capture a photo.",
        "guide_title": "📖 Quick Guide",
        "camera": "Take a Photo of your Circuit",
        "guide_text": """
        **How to Start:**
        1. Upload a photo of *any* circuit you built.
        2. Let the AI discover what components you used (Step 1).
        3. Verify the pin alignments (Step 2).
        4. See if the AI can guess your invention and check its logic (Step 3)!
        
        **Visual Legend:**
        * 🔴 **Red Circle:** Electrical issue (e.g., open loop, short circuit, missing protection).
        * 🟦 **Blue Box:** Layout anomaly.
        """,
    },
    "hk": {
        "title": "🔌 AI 自由電路探險家",
        "setup": "設定",
        "user_id": "選擇學生 ID",
        "inferred_task": "AI 推斷嘅發明類型",
        "input_mode": "輸入方式",
        "mode_upload": "上傳圖片",
        "mode_camera": "使用相機",
        "upload": "上傳學生電路照片",
        "reset": "重置流程",
        "your_circuit": "你的電路（淺藍色線 = 麵包板內部接線）",
        "step1_btn": "🔍 第一步：探索零件與發明意圖",
        "analyzing": "AI 正在逆向分析麵包板結構...",
        "step2_title": "⚙️ 第二步：微調零件引腳（自動對齊）",
        "step2_confirm": "✅ 確認並分析電路邏輯",
        "snapped": "*(Y 軸已自動對齊至最近的行：{y})*",
        "verify": "請核對橙色引腳與黃色接點（已對齊至淺藍色行）",
        "step3_title": "🧠 第三步：AI 意圖推斷與電路診斷",
        "checking": "正在分析電路迴路並推斷組裝目標...",
        "ai_diag": "AI 診斷：紅圈表示潛在的接線或安全問題",
        "save": "💾 儲存至 Drive",
        "back": "🔙 返回",
        "new": "🎉 新發明挑戰",
        "upload_prompt": "請選擇上傳照片或拍攝新照片以開始。",
        "guide_title": "📖 快速指南",
        "camera": "拍攝電路照片",
        "guide_text": """
        **使用步驟：**
        1. 隨意組裝電路並上傳照片
        2. 讓 AI 自動偵測你使用了什麼零件（第一步）
        3. 微調引腳落點位置（第二步）
        4. 看看 AI 能不能猜出你的發明意圖並檢查線路（第三步）！
        
        **圖示說明：**
        * 🔴 **紅圈：** 電路問題（例如：斷路、短路、缺少限流電阻）。
        * 🟦 **藍框：** 佈局異常。
        """,
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

# --- 3. UI CUSTOMIZATION ---
st.set_page_config(page_title="AI Circuit Explorer", layout="wide")
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"], .stDeployButton {display:none !important;}
    #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 0rem;}
    </style>
    """, unsafe_allow_html=True)

def detect_horizontal_rows(pil_img):
    if pil_img is None: return []
    img_cv = np.array(pil_img)
    if img_cv.dtype != np.uint8:
        img_cv = img_cv.astype(np.uint8)

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

    return [int((y / height) * 1000) for y in peaks]
    
def process_uploaded_image(file_input):
    try:
        if isinstance(file_input, str):
            img = PILImage.open(file_input)
        else:
            data = file_input.read() if hasattr(file_input, 'read') else file_input
            img = PILImage.open(io.BytesIO(data))
            
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        
        MAX_SAFE_DIM = 4500 
        if max(img.size) > MAX_SAFE_DIM:
            img.thumbnail((MAX_SAFE_DIM, MAX_SAFE_DIM), PILImage.Resampling.LANCZOS)
            
        return img
    except Exception as e:
        st.error(f"Image Load Failed: {e}")
        return None

def draw_coordinate_grid(image, snap_rows=None, corners=None):
    draw = ImageDraw.Draw(image)
    w, h = image.size
    pale_blue = (173, 216, 230)
    boundary_color = (0, 0, 255) 

    if not corners or not all(k in corners for k in ["top_left", "top_right", "bottom_right", "bottom_left"]):
        return image

    def get_px(pt):
        if not pt or len(pt) < 2: return (0, 0)
        return (pt[1] * w / 1000, pt[0] * h / 1000)

    tl = get_px(corners.get("top_left"))
    tr = get_px(corners.get("top_right"))
    br = get_px(corners.get("bottom_right"))
    bl = get_px(corners.get("bottom_left"))

    draw.line([tl, tr, br, bl, tl], fill=boundary_color, width=5)

    def lerp_pt(p1, p2, t):
        return (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)

    mid_top = lerp_pt(tl, tr, 0.5)
    mid_bottom = lerp_pt(bl, br, 0.5)
    draw.line([mid_top, mid_bottom], fill=boundary_color, width=4)

    rail_offsets = [0.05, 0.10, 0.90, 0.95]
    for t in rail_offsets:
        top_p = lerp_pt(tl, tr, t)
        bot_p = lerp_pt(bl, br, t)
        draw.line([top_p, bot_p], fill=pale_blue, width=3)
    
    if snap_rows:
        for ry in snap_rows:
            t_vertical = ry / 1000.0
            row_l = lerp_pt(tl, bl, t_vertical)
            row_r = lerp_pt(tr, br, t_vertical)
            
            p_ae_start = lerp_pt(row_l, row_r, 0.18)
            p_ae_end = lerp_pt(row_l, row_r, 0.45)
            draw.line([p_ae_start, p_ae_end], fill=pale_blue, width=3)
            
            p_fj_start = lerp_pt(row_l, row_r, 0.55)
            p_fj_end = lerp_pt(row_l, row_r, 0.82)
            draw.line([p_fj_start, p_fj_end], fill=pale_blue, width=3)
            
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

def create_visual_report(successes, errors, lang):
    img = PILImage.new('RGB', (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    title = "Visual Performance Summary 📊" if lang == "en" else "視覺化成果總結 📊"
    draw.text((30, 20), title, fill=(0, 0, 0))
    
    draw.rectangle([30, 60, 770, 280], outline=(0, 150, 0), width=3, fill=(240, 255, 240))
    draw.text((50, 75), "✅ What you did well! / 做得好嘅地方！", fill=(0, 128, 0))
    
    y_off = 110
    for item in successes[:5]: 
        draw.text((60, y_off), f"🌟 {item}", fill=(30, 30, 30))
        y_off += 30

    draw.rectangle([30, 310, 770, 560], outline=(200, 100, 0), width=3, fill=(255, 250, 240))
    draw.text((50, 325), "🛠️ Things to check / 需要檢查嘅地方", fill=(200, 100, 0))
    
    y_off = 360
    for item in errors[:5]:
        draw.text((60, y_off), f"🔍 {item}", fill=(30, 30, 30))
        y_off += 30
        
    return img

def save_to_drive(user_id, inferred_task_name, ai_feedback, images_dict):
    service = get_drive_service()
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    hk_time_str = datetime.now(hk_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    # Generate clean alphanumeric prefix from inferred name
    clean_task = "".join([c for c in inferred_task_name if c.isalnum() or c=='_'])[:15]
    file_prefix = f"user{user_id}_{clean_task}"

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
            
        st.toast("✅ Automatically saved to Google Drive!")
        
    except Exception as e:
        st.error(f"Drive Save Error: {e}")

# --- 4. SESSION STATE ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "analysis_result" not in st.session_state: st.session_state.analysis_result = None
if "hough_rows" not in st.session_state: st.session_state.hough_rows = []
if "breadboard_corners" not in st.session_state: st.session_state.breadboard_corners = None
if "last_input_id" not in st.session_state: st.session_state.last_input_id = None
if "socratic_q_idx" not in st.session_state: st.session_state.socratic_q_idx = 0
if "socratic_chat" not in st.session_state: st.session_state.socratic_chat = []

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
    st.session_state.socratic_q_idx = 0
    st.session_state.socratic_chat = []

# --- 5. MAIN UI ---
lang_select = st.radio("🌐", ["English", "繁體中文"], horizontal=True, label_visibility="collapsed")
l = "en" if lang_select == "English" else "hk"

st.title(UI[l]["title"])

with st.sidebar:
    st.header(UI[l]["setup"])
    user_id = st.selectbox(UI[l]["user_id"], [f"{i:02d}" for i in range(51)])
    
    st.divider()

    # UPLOAD METHOD TOGGLE
    input_mode = st.radio("Upload Method" if l == "en" else "上傳方式", ["Camera 📸", "File Upload 📁"], index=1, horizontal=True)
    
    if input_mode == "Camera 📸":
        active_input = st.camera_input("Take photo of circuit" if l == "en" else "拍攝電路照片")
    else:
        active_input = st.file_uploader("Upload photo" if l == "en" else "上傳照片", type=["jpg", "png", "jpeg","heic"])
        
    st.divider()
    
    if st.button(UI[l]["reset"]): 
        reset_flow()
        st.session_state.last_input_id = None
        st.rerun()

    st.markdown(f"### {UI[l]['guide_title']}")
    st.markdown(UI[l]['guide_text'])

# --- 6. APPLICATION LOGIC ---
if active_input:
    current_input_id = getattr(active_input, "file_id", str(hash(active_input.getvalue())))
    
    if st.session_state.get("last_input_id") != current_input_id:
        reset_flow()
        st.session_state.last_input_id = current_input_id
        st.session_state.img1 = process_uploaded_image(io.BytesIO(active_input.getvalue()))
    elif st.session_state.img1 is None:
        st.session_state.img1 = process_uploaded_image(io.BytesIO(active_input.getvalue()))
    
    raw_student = st.session_state.img1

    if raw_student is not None:
        if not st.session_state.hough_rows:
            st.session_state.hough_rows = detect_horizontal_rows(raw_student)

        # STEP 1: COMPONENT DETECTION
        if st.session_state.step == 1:
            grid_visualization = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners)
            
            # Expanded layout for detail visualization
            orig_w, orig_h = grid_visualization.size
            large_grid_img = grid_visualization.resize((orig_w * 2, orig_h * 2), PILImage.Resampling.LANCZOS)
            
            st.subheader(UI[l]["your_circuit"])
            st.image(large_grid_img, use_container_width=True)

            if st.button(UI[l]["step1_btn"], type="primary"):
                with st.spinner(UI[l]["analyzing"]):
                    prompt = """
                        1. Identify the BREADBOARD boundaries: Provide the [y, x] coordinates for the four outer corners (top_left, top_right, bottom_right, bottom_left).
                        2. Identify all components and jumper wires physically placed on the breadboard. Follow these strict schema rules:
                        - JUMPER WIRES: Uniquely identify and label every single wire sequentially (e.g., 'Wire 1', 'Wire 2').
                        - OTHER COMPONENTS: Label them uniquely (e.g., 'Resistor 1', 'LED 1', 'Button 1').
                        - PINS/LEGS SCHEMA: Order each component's pin locations sequentially within its 'legs' coordinate array.
                        - POWER SUPPLY: Locate power rails or connections (+ve/Vcc and -ve/GND).
                        - RESISTOR SIGNATURES: Differentiate values based on color band characteristics (10k ohm, 1k ohm, 300 ohm, 150 ohm).
                        Return JSON mapping 'breadboard_corners' and 'components'.
                        """
                    resp = client.models.generate_content(
                        model=MODEL_ID, contents=[raw_student, prompt],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
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
                    
                    st.session_state.breadboard_corners = result.get("breadboard_corners", {})

                    records = []
                    for item in result.get("components", []):
                        center = item.get('center', [500, 500])
                        cy, cx = center if (isinstance(center, list) and len(center) == 2) else (500, 500)
                            
                        legs = item.get('legs', [])
                        if isinstance(legs, list):
                            for i, leg in enumerate(legs):
                                if isinstance(leg, list) and len(leg) >= 2:
                                    records.append({
                                        "Component": f"{item.get('name')} (Pin {i+1})", 
                                        "CX": cx, "CY": cy, "LX": leg[1], "LY": leg[0]
                                    })
                                        
                    st.session_state.components_df = pd.DataFrame(records)
                    base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners)
                    st.session_state.img2 = draw_pins_on_image(base_grid_img, st.session_state.components_df)
                    st.session_state.step = 2
                    st.rerun()

        # STEP 2: TUNING PIN PLACEMENTS
        elif st.session_state.step == 2:
            st.subheader(UI[l]["step2_title"])
            edit_col, img_col = st.columns([1, 2])
                
            updated_data = []
            with edit_col:
                for i, row in st.session_state.components_df.iterrows():
                    with st.expander(f"📍 {row['Component']}"):
                        lx = st.slider(f"Adjust X position", 0, 1000, int(row["LX"]), key=f"x{i}")
                        raw_ly = st.slider(f"Adjust Y position", 0, 1000, int(row["LY"]), key=f"y{i}")
                        
                        snapped_ly = raw_ly
                        if st.session_state.hough_rows:
                            snapped_ly = min(st.session_state.hough_rows, key=lambda ry: abs(ry - raw_ly))
                        
                        if raw_ly != snapped_ly:
                            st.caption(UI[l]["snapped"].format(y=snapped_ly))
                            
                        updated_data.append({"Component": row["Component"], "CX": row["CX"], "CY": row["CY"], "LX": lx, "LY": snapped_ly})
            edited_df = pd.DataFrame(updated_data)

            with img_col:
                base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners)
                st.session_state.img3 = draw_pins_on_image(base_grid_img, edited_df)
                
                tune_w, tune_h = st.session_state.img3.size
                large_img3 = st.session_state.img3.resize((tune_w * 2, tune_h * 2), PILImage.Resampling.LANCZOS)
                st.image(large_img3, caption=UI[l]["verify"], use_container_width=True)

            if st.button(UI[l]["step2_confirm"], type="primary"):
                st.session_state.components_df = edited_df
                st.session_state.analysis_result = None
                st.session_state.img4 = None
                st.session_state.step = 3
                st.rerun()

        # STEP 3: REVERSE ENGINEERING INTENT & VERIFICATION REVIEW
        elif st.session_state.step == 3:
            st.subheader("Step 3: Intent & Connection Verification / 逆向意圖與落點確認")
            
            if l == "en":
                st.warning("🔍 **Review AI Mapping Alignment:** Confirm that the yellow marker locations perfectly capture your physical pins before initiating the reverse-engineering diagnosis.")
            else:
                st.warning("🔍 **確認線路落點：** 請確保黃色標籤位置完全切合你嘅實體引腳，然後點擊下方開始由 AI 逆向診斷你組裝嘅電路。")
            
            w3, h3 = st.session_state.img3.size
            large_img3_review = st.session_state.img3.resize((w3 * 2, h3 * 2), PILImage.Resampling.LANCZOS)
            st.image(large_img3_review, caption="Alignment Precision View", use_container_width=True)
            
            btn_text = "🤖 Run Autonomous AI Analysis" if l == "en" else "🤖 開始 AI 智能分析"
            
            col_btn_run, col_btn_back = st.columns([1, 4])
            with col_btn_run:
                if st.button(btn_text, type="primary"):
                    with st.spinner(UI[l]["checking"]):
                        summary = st.session_state.components_df.to_string(index=False)
                        
                        prompt = f"""
                            You are an autonomous engineering tutor analyzing a physical breadboard setup with NO pre-defined target template.
                            
                            Your tasks are:
                            1. **INFER INTENT**: Look at the component configuration and connectivity string below. Deduce what circuit system the user is trying to build (e.g., 'A button-controlled single LED setup', 'Two LEDs wired in parallel with a protective resistor', 'A basic power-to-LED closed loop'). Give this system a descriptive title in 'inferred_circuit_name'.
                            2. **ELECTRICAL VALIDITY AUDIT**: Check the layout for sound circuit design principles:
                               - Closed Loop: Does power travel seamlessly from the Vcc source, through active components, and safely terminate in the GND rail?
                               - Safety/Overcurrent protection: Do semiconductor components (like LEDs) feature current-limiting resistors?
                               - Shorts & Floating Connections: Are components correctly mapped across terminal strips or accidentally shorted onto the same row?
                            3. **DYNAMIC CHALLENGE GENERATION**: Generate an array of exactly 3 progressive Socratic challenges tailored explicitly for their specific inferred circuit system. 
                               - Level 1: Property modification challenge (e.g., swapping resistor values or flipping LED polarity).
                               - Level 2: Interactive behavior challenge (e.g., integrating a switch or push-button seamlessly).
                               - Level 3: Structural layout challenge (e.g., converting part of the loop from series to parallel).
                            
                            Pedagogical Scaffolding Rule:
                            If errors are found, use open Socratic questioning to let pairs discover *where* the continuity fails. If 100% correct, praise their standalone design and tell them they are ready for the custom challenge mode.
                            
                            Bilingual Format:
                            Provide the 'feedback' string with English first, followed by a newline, and then a formal Cantonese translation.
                            
                            Component Coordinates & Snapped Rows:
                            {summary}
                            """
                        
                        try:
                            resp = client.models.generate_content(
                                model=MODEL_ID, 
                                contents=[st.session_state.img3, prompt],
                                config=types.GenerateContentConfig(
                                    temperature=0.2,
                                    response_mime_type="application/json",
                                    response_schema={
                                        "type": "OBJECT",
                                        "properties": {
                                            "inferred_circuit_name": {"type": "STRING"},
                                            "feedback": {"type": "STRING"},
                                            "success_summary": {"type": "ARRAY", "items": {"type": "STRING"}},
                                            "error_summary": {"type": "ARRAY", "items": {"type": "STRING"}},
                                            "socratic_challenges": {"type": "ARRAY", "items": {"type": "STRING"}},
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
                                        "required": ["inferred_circuit_name", "feedback", "detected_errors", "success_summary", "error_summary", "socratic_challenges"]
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
                                loc = err.get("location", [])
                                if len(loc) == 2:
                                    draw.ellipse([loc[1]*w/1000-25, loc[0]*h/1000-25, loc[1]*w/1000+25, loc[0]*h/1000+25], outline="red", width=8)
                                        
                            st.session_state.img4 = diag_img
                            
                            feedback_text = st.session_state.analysis_result.get("feedback", "")
                            success_list = st.session_state.analysis_result.get("success_summary", [])
                            error_list = st.session_state.analysis_result.get("error_summary", [])
                            inferred_title = st.session_state.analysis_result.get("inferred_circuit_name", "Custom Invention")
                            
                            report_card_img = create_visual_report(success_list, error_list, l)
                            
                            save_to_drive(user_id, inferred_title, feedback_text, 
                                          {"1": st.session_state.img1, "4": st.session_state.img4, "summary": report_card_img})
                            
                            st.session_state.step = 4
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"AI Autonomous Analysis failed: {e}")
                            st.session_state.step = 2
                            st.rerun()
            with col_btn_back:
                if st.button(UI[l]["back"]):
                    st.session_state.step = 2
                    st.rerun()

        # STEP 4: AUTONOMOUS VERDICT DISPLAY
        elif st.session_state.step == 4:
            st.subheader(UI[l]["step3_title"])
            
            inferred_title = st.session_state.analysis_result.get("inferred_circuit_name", "Detected System")
            st.metric(label=UI[l]["inferred_task"], value=inferred_title)
            
            if st.session_state.img4 is not None:
                st.image(st.session_state.img4, caption=UI[l]["ai_diag"], use_container_width=True)
                
                feedback_text = st.session_state.analysis_result.get("feedback", "")
                st.info(feedback_text)
                
                success_list = st.session_state.analysis_result.get("success_summary", [])
                error_list = st.session_state.analysis_result.get("error_summary", [])
                
                report_card_img = create_visual_report(success_list, error_list, l)
                st.image(report_card_img, use_container_width=True)

            if not error_list:
                st.success("🎉 Perfect layout signature! Ready to begin exploration challenges? / 完美嘅電路佈局！準備好接受智能生成嘅挑戰未？")
                if st.button("🚀 Enter Socratic Challenge Mode! / 進入蘇格拉底挑戰模式", type="primary"):
                    st.session_state.step = 5
                    st.rerun()
                    
            st.divider()
            col_b, col_c = st.columns(2)
            with col_b:
                if st.button(UI[l]["back"]):
                    st.session_state.step = 3
                    st.session_state.analysis_result = None 
                    st.session_state.img4 = None
                    st.rerun()
            with col_c:
                if st.button(UI[l]["new"]):
                    reset_flow()
                    st.session_state.last_input_id = None
                    st.rerun()

        # STEP 5: DYNAMIC GENERATED SOCRATIC CHALLENGE MODE
        elif st.session_state.step == 5:
            st.subheader("🚀 Dynamic Socratic Challenges / 智能生成型挑戰模式")
            
            challenges = st.session_state.analysis_result.get("socratic_challenges", [])
            
            for msg in st.session_state.socratic_chat:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                        
            if st.session_state.socratic_q_idx < len(challenges):
                current_q = challenges[st.session_state.socratic_q_idx]
                
                st.info(f"**Generated Challenge ({st.session_state.socratic_q_idx + 1}/{len(challenges)}):**\n\n{current_q}")
                
                st.markdown("### Verify Your Experiment 🔬")
                student_text = st.text_area("What did you change and what happened? / 你改咗咩？觀察到咩？")
                
                socratic_upload_mode = st.radio("Upload modified view:", ["Camera 📸", "File 📁"], horizontal=True, label_visibility="collapsed", key=f"s_upload_{st.session_state.socratic_q_idx}")
                
                if socratic_upload_mode.startswith("Camera"):
                    proof_img = st.camera_input("Take a photo of the new circuit", key=f"s_cam_{st.session_state.socratic_q_idx}")
                else:
                    proof_img = st.file_uploader("Upload a photo", type=["jpg", "png", "jpeg"], key=f"s_file_{st.session_state.socratic_q_idx}")
                    
                if st.button("Verify My Experiment! 🔍", type="primary"):
                    if not student_text or not proof_img:
                        st.warning("Please provide both your explanation and an image! / 請同時提供文字解釋及相片！")
                    else:
                        with st.spinner("AI is verifying your hands-on experiment..."):
                            img_pil = process_uploaded_image(io.BytesIO(proof_img.getvalue()))
                            history_context = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.socratic_chat])
                            
                            prompt = f"""
                                Tasks & Context: {st.session_state.analysis_result.get('inferred_circuit_name')}
                                Previous Chat Logs:
                                {history_context}
                                
                                Validate whether the new circuit image and the following user explanation prove they successfully solved this milestone:
                                Milestone Question: {current_q}
                                User Reflection: "{student_text}"
                                
                                If successful, return output starting EXACTLY with '[VERIFICATION: PASSED]'. If missing components or faulty, output '[VERIFICATION: FAILED]' along with Socratic coaching.
                                """
                            try:
                                resp = client.models.generate_content(
                                    model=MODEL_ID, contents=[img_pil, prompt],
                                    config=types.GenerateContentConfig(temperature=0.4)
                                )
                                feedback = resp.text
                                display_feedback = feedback.replace("[VERIFICATION: PASSED]", "").replace("[VERIFICATION: FAILED]", "").strip()
                                
                                st.session_state.socratic_chat.append({"role": "user", "content": f"📝 **Observation:** {student_text}\n*(New Photo Uploaded)*"})
                                st.session_state.socratic_chat.append({"role": "assistant", "content": display_feedback})
                                
                                if "[VERIFICATION: PASSED]" in feedback:
                                    st.session_state.socratic_q_idx += 1
                                    
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"AI Verification Error: {e}")
            else:
                st.success("🏆 You are a Circuit Master! All challenges completed! / 🏆 你已經成為電路大師！完成晒所有生成挑戰！")
                
            st.divider()
            col_b, col_c = st.columns(2)
            with col_b:
                if st.button("Back to Circuit Check" if l == "en" else "返回電路檢查"):
                    st.session_state.step = 4
                    st.rerun()
            with col_c:
                if st.button(UI[l]["new"]):
                    reset_flow()
                    st.session_state.last_input_id = None
                    st.rerun()
else:
    st.error("Please upload an image or turn on the camera system to begin / 請上傳圖片或開啟相機鏡頭以開始")
