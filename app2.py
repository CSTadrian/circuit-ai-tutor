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
import random

# --- 1. CONFIGURATION & TASK SETUP ---
TASKS = {
    "Task 1: Basic LED Circuit": "task1_led_10k.png",
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

def detect_horizontal_rows(pil_img):
    """
    Detects breadboard rows. Uses 8-bit depth safety check.
    """
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

    return [int((y / height) * 1000) for y in peaks]
    
def process_uploaded_image(file_input):
    """
    Robust image loader with Memory Safety Cap.
    """
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
            
        st.toast("✅ Automatically saved to Google Drive!")
        
    except Exception as e:
        st.error(f"Drive Save Error: {e}")

    
# --- 5. SESSION STATE ---
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


def get_socratic_challenges(task_name):
    """
    Returns 3 specific, progressive challenges tailored for absolute beginners.
    For Task 1, options are randomized to dynamically test different concepts.
    """
    
    # Default fallback challenges for other tasks
    if "Task 1" not in task_name:
        return [
            "Level 1 🟢 (The Polarity Trick): Let's test the LED! Flip it around... \n\n第一關 🟢 (極性小把戲): 測試吓粒 LED！...",
            "Level 2 🟡 (The Resistance Test): Swap it for the 10k ohm one... \n\n第二關 🟡 (電阻大測試): 換成 10k ohm...",
            "Level 3 🔴 (The Series Swap): Swap the places of the LED and Resistor... \n\n第三關 🔴 (串聯對調): 將 LED 同電阻對調位置..."
        ]
        
    # --- TASK 1 REGION (RANDOMIZED SOCRATIC CHALLENGES) ---
    challenges = []

    # 1. Level 1: Randomize between Polarity Swap OR Component Order Swap
    level1_options = [
        # Option A: Polarity
        "Level 1 🟢 (The Polarity Trick): Let's test the LED! Pull the LED out of your board, flip it around so the long and short legs are swapped, and plug it back in. Take a photo. Does it still light up? Tell me what you see!\n\n"
        "第一關 🟢 (極性小把戲): 測試吓粒 LED！將 LED 抆出嚟，掉轉長短腳再插返入去。影張相，佢仲會唔會發光？話我知你見到咩！",
        
        # Option B: Series Order
        "Level 1 🟢 (The Series Swap): Let's test the electrical order! Keep the same wires, but just swap the positions of the LED and the Resistor. (For example, if the path was Power -> Resistor -> LED, change it to Power -> LED -> Resistor). Make sure LED legs connect correctly! Take a photo. Does swapping the order change the brightness?\n\n"
        "第一關 🟢 (串聯對調): 測試吓接線嘅「次序」！用返同樣嘅線，將 LED 同電阻對調位置插返好 (例如：原本係「電源 -> 電阻 -> LED」，改為「電源 -> LED -> 電阻」)。記得 LED 兩隻腳要插啱位呀！影張相，對調咗位置之後燈嘅亮度有冇變化？"
    ]
    challenges.append(random.choice(level1_options))

    # 2. Level 2: Randomize target resistor swap value (150, 300, or 10k)
    resistor_choices = [
        {"val": "150", "color_en": "GREEN", "color_hk": "綠"},
        {"val": "300", "color_en": "ORANGE", "color_hk": "橙"},
        {"val": "10k", "color_en": "RED", "color_hk": "紅"}
    ]
    chosen_resistor = random.choice(resistor_choices)
    
    level2_text = (
        f"Level 2 🟡 (The Resistance Test): Great job with your first experiment! Now let's change the resistance. Take out your current resistor and swap it for the {chosen_resistor['val']} ohm one (the one with the {chosen_resistor['color_en']} band). Take a photo. How does the brightness compare to your original circuit?\n\n"
        f"第二關 🟡 (電阻大測試): 上一關做得好！依家我哋改變吓電阻值。將你依家粒電阻換成 {chosen_resistor['val']} ohm (有{chosen_resistor['color_hk']}色彩環嗰粒)。影張相，同原本個電路比，燈嘅亮度有咩變化？"
    )
    challenges.append(level2_text)

    # 3. Level 3: Circuit Topology Comparison (Base vs Series Addition vs Parallel Addition)
    level3_text = (
        "Level 3 🔴 (The Topology Puzzle): Let's explore circuit layouts! Look at your original circuit. Now, try two experiments:\n"
        "1. **Series Experiment**: Add ONE MORE resistor of the exact same value in series (end-to-end) with your current resistor.\n"
        "2. **Parallel Experiment**: Instead of series, try adding that second resistor in parallel (side-by-side) across your first resistor.\n"
        "Take photos of both setups! Compare the brightness: Original circuit vs. Two Resistors in Series vs. Two Resistors in Parallel. What do you notice?\n\n"
        "第三關 🔴 (電路結構大挑戰): 我哋一齊探索電路結構！睇吓你原本個電路。依家嘗試做兩個實驗：\n"
        "1. **串聯實驗**：加多一粒相同數值嘅電阻，同依家粒電阻「串聯」（頭尾相接）。\n"
        "2. **並聯實驗**：唔用串聯，改為將第二粒電阻同第一粒「並聯」（並排相接）。\n"
        "兩次實驗都影張相。對比返三種情況：原本個電路 vs 串聯兩粒 vs 並聯兩粒，你觀察到燈嘅光度有咩分別？"
    )
    challenges.append(level3_text)

    return challenges

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

    # 📸 UPLOAD METHOD TOGGLE
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

# --- 7. APPLICATION LOGIC ---

if active_input:
    # --- AUTO RESET ON NEW IMAGE ---
    current_input_id = getattr(active_input, "file_id", str(hash(active_input.getvalue())))
    
    if st.session_state.get("last_input_id") != current_input_id:
        reset_flow()
        st.session_state.last_input_id = current_input_id
        st.session_state.img1 = process_uploaded_image(io.BytesIO(active_input.getvalue()))
    elif st.session_state.img1 is None:
        st.session_state.img1 = process_uploaded_image(io.BytesIO(active_input.getvalue()))
    
    raw_student = st.session_state.img1

    # Detect rows based on the safe scaled image
    if raw_student is not None:
        if not st.session_state.hough_rows:
            st.session_state.hough_rows = detect_horizontal_rows(raw_student)

        # Flag for determining layout structure magnification
        is_camera_mode = (input_mode == "Camera 📸")

        # STEP 1: DETECTION
        if st.session_state.step == 1:
            grid_visualization = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners)
            
            if is_camera_mode:
                # Direct massive display layout (Enlarged 3x in width and height)
                orig_w, orig_h = grid_visualization.size
                large_grid_img = grid_visualization.resize((orig_w * 3, orig_h * 3), PILImage.Resampling.LANCZOS)
                
                st.subheader(UI[l]["your_circuit"])
                st.image(large_grid_img, caption=UI[l]["your_circuit"])
                with st.expander(UI[l]["schematic"], expanded=False):
                    st.image(raw_schematic, caption=UI[l]["schematic"])
            else:
                # Standard side-by-side split layout for uploaded files
                col1, col2 = st.columns(2)
                col1.image(raw_schematic, caption=UI[l]["schematic"])
                col2.image(grid_visualization, caption=UI[l]["your_circuit"])

            if st.button(UI[l]["step1_btn"], type="primary"):
                with st.spinner(UI[l]["analyzing"]):
                    prompt = """
                        1. Identify the BREADBOARD boundaries: Provide the [y, x] coordinates for the four outer corners (top_left, top_right, bottom_right, bottom_left).
                        2. Identify components and jumper wires on the breadboard. Follow these strict unique component/pin naming constraints:
                        - JUMPER WIRES: Uniquely identify and label every single wire sequentially (e.g., 'Wire 1', 'Wire 2', 'Wire 3') so users can instantly tell them apart. Do not group them generically.
                        - OTHER COMPONENTS: Label them uniquely (e.g., 'Resistor 1', 'LED 1', 'Button 1').
                        - PINS/LEGS SCHEMA: Order each component's pin locations sequentially within its 'legs' coordinate array so they transparently map to 'Pin 1', 'Pin 2', 'Pin 3' respectively.
                        - POWER SUPPLY: Must identify the power input module. It has exactly 2 pins: the red wire/pin (+ve/Vcc) and the black wire/pin (-ve/GND).
                        - SLIDE-SWITCH: You MUST identify exactly 3 pins (legs) positioned continuously in a single straight row. 
                        - 4-pin Push Button, LDR, LED
                        - RESISTOR: Identify 5-band resistors and strictly categorize their detected values using these explicit color signatures:
                          * '10k ohm' resistor: characterized by containing a red band/line.
                          * '300 ohm' resistor: characterized by containing an orange band/line.
                          * '150 ohm' resistor: characterized by containing a green band/line.
                          * '1k ohm' resistor: characterized by containing mostly black and brown bands/lines.
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
                    base_grid_img = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners)
                    st.session_state.img2 = draw_pins_on_image(base_grid_img, st.session_state.components_df)
                    st.session_state.step = 2
                    st.rerun()

        # STEP 2: TUNING
        elif st.session_state.step == 2:
            st.subheader(UI[l]["step2_title"])
            
            # Balance configuration layout columns
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
                
                # Double width and height (2x) as requested for tuning precision visibility
                tune_w, tune_h = st.session_state.img3.size
                large_img3 = st.session_state.img3.resize((tune_w * 2, tune_h * 2), PILImage.Resampling.LANCZOS)
                st.image(large_img3, caption=UI[l]["verify"], use_container_width=True)

            if st.button(UI[l]["step2_confirm"], type="primary"):
                st.session_state.components_df = edited_df
                st.session_state.analysis_result = None
                st.session_state.img4 = None
                st.session_state.step = 3
                st.rerun()

        # STEP 3: PRE-ANALYSIS ALIGNMENT TRANSPARENCY DISPLAY
        elif st.session_state.step == 3:
            st.subheader("Step 3: Intent vs. Detection Review / 檢查對齊與落點")
            
            # Transparency Guidance Callout Box
            if l == "en":
                st.warning("🔍 **Double check your connections before marking!** Review the large mapping below to look for any misalignments between what you intended to connect vs. an AI vision mapping mistake.")
            else:
                st.warning("🔍 **開始評分前請仔細檢查！** 請對照下方放大圖，睇吓你原本想連接嘅位置，同系統『睇』到嘅黃色落點有冇任何偏離或移位。")
            
            # Display image prominently at 2x width and 2x height, isolated across the FULL WIDTH layout
            w3, h3 = st.session_state.img3.size
            large_img3_review = st.session_state.img3.resize((w3 * 2, h3 * 2), PILImage.Resampling.LANCZOS)
            st.image(large_img3_review, caption="Large Alignment Check View (Before AI Logic Assessment)", use_container_width=True)
            
            st.info("Everything looks perfectly aligned! Click below to begin the Socratic Assessment." if l == "en" else "如果落點對齊完全無誤，請點擊下方按鈕開始蘇格拉底式評估。")

            btn_text = UI[l].get("ai_analysis_btn", "🤖 Run AI Analysis" if l == "en" else "🤖 開始 AI 分析")
            
            col_btn_run, col_btn_back = st.columns([1, 4])
            with col_btn_run:
                if st.button(btn_text, type="primary"):
                    with st.spinner(UI[l]["checking"]):
                        summary = st.session_state.components_df.to_string(index=False)
                        
                        prompt = f"""
                            Task: {selected_task}. 
                            Structural Connectivity Rules:
                            1. TERMINAL STRIPS (Center): Pins in the same ROW (horizontal) are electrically connected.
                            2. POWER RAILS (Edges): The two leftmost and two rightmost columns are Power Rails. 
                            3. PALE BLUE OVERLAYS: Connected to Power Supply.
                        
                            Electrical Analysis & Strict Semantic Resistor Rules: 
                            1. POWER SUPPLY: Must form a closed loop.
                            2. SERIES REVERSIBILITY: An LED in series with a resistor is considered correct regardless of order (LED -> Resistor IS THE SAME AS Resistor -> LED).
                            3. RESISTOR STRUCTURAL & SEMANTIC VALIDATION: You must identify whether the correct resistor is used by checking its visual 5-band color signatures against the target requirement:
                               - Target requires '150 ohm': Physical resistor must visually contain exactly ONE green band.
                               - Target requires '10k ohm': Physical resistor must visually contain exactly ONE red band.
                               - Target requires '300 ohm': Physical resistor must visually contain exactly ONE orange band.
                               - Target requires '1k ohm': Physical resistor must visually consist mostly of black and brown bands.
                               CRITICAL SEMANTIC OUTPUT: Explicitly state whether the resistor is correct or not in your evaluation. If the physical color bands fail to match the required target rule, add 'Incorrect Resistor Used' to 'error_summary' and 'detected_errors'. If it matches, add 'Correct Resistor Used' to 'success_summary'.
                        
                            Pedagogical Scaffolding Rules (CRITICAL):
                            1. IF THERE ARE ERRORS: DO NOT give direct answers or tell the student which exact rows to change. Instead, use SOCRATIC SCAFFOLDING. Ask a guiding question related to the underlying theory of their specific mistake (e.g., if the circuit is open, ask how electricity needs a continuous path to return home; if the wrong resistor is used, guide them to inspect the color bands). 
                            2. IF 100% CORRECT: Praise them enthusiastically, and then provide a "What-If" CHALLENGE to encourage deeper exploration. Tailor the challenge to the components used (e.g., "What happens if you swap the resistor for a smaller one?", "Can you add a button?", "If you have a capacitor, how can you make the LED fade out slowly?").

                            Bilingual Output Requirement:
                            For the 'feedback' string, provide the English text first, followed by a newline, and then a formal Cantonese (Traditional Chinese) translation. Use emojis and an engaging tone suitable for P4-S3 students.
                            
                            Example Format (Error - Socratic):
                            "It looks like your LED isn't lighting up! 🧐 Follow the path of electricity from the positive red wire. Does it have a continuous bridge to reach the negative wire? Where does the path break?\\n\\n睇落你粒 LED 唔著喎！🧐 試吓跟住電流由紅線 (+) 出發嘅路徑。佢有冇一條完整嘅路徑可以返去黑線 (-)？條路喺邊度斷咗呀？"
                            
                            Component Data (Available Pins):
                            {summary}
                        
                            Compare to Target Schematic. Return JSON with 'feedback' (containing the Socratic/Challenge text), 'detected_errors', 'success_summary' (array of strings), and 'error_summary' (array of strings).
                            """
                        
                        try:
                            resp = client.models.generate_content(
                                model=MODEL_ID, 
                                contents=[raw_schematic, st.session_state.img3, prompt],
                                config=types.GenerateContentConfig(
                                    temperature=0.0,
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
                            
                            # Drawing marker error layers
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
                            
                            # --- AUTO-SAVE SEQUENCE ---
                            feedback_text = st.session_state.analysis_result.get("feedback", "")
                            success_list = st.session_state.analysis_result.get("success_summary", [])
                            error_list = st.session_state.analysis_result.get("error_summary", [])
                            report_card_img = create_visual_report(success_list, error_list, l)
                            
                            save_to_drive(user_id, selected_task, feedback_text, 
                                          {"1": st.session_state.img1, "4": st.session_state.img4, "summary": report_card_img})
                            
                            st.session_state.step = 4
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"AI Analysis failed: {e}")
                            st.session_state.step = 2
                            st.rerun()
            with col_btn_back:
                if st.button(UI[l]["back"]):
                    st.session_state.step = 2
                    st.rerun()

        # STEP 4: AI AUTOMATED CIRCUIT ANALYSIS RESULTS
        elif st.session_state.step == 4:
            st.subheader(UI[l]["step3_title"])
            
            if st.session_state.img4 is not None:
                st.image(st.session_state.img4, caption=UI[l]["ai_diag"], use_container_width=True)
                
                feedback_text = st.session_state.analysis_result.get("feedback", "")
                st.info(feedback_text)
                
                success_list = st.session_state.analysis_result.get("success_summary", [])
                error_list = st.session_state.analysis_result.get("error_summary", [])
                
                report_card_img = create_visual_report(success_list, error_list, l)
                st.image(report_card_img, width="stretch")

            # If Base Circuit is 100% correct, unlock Personalized Socratic Scaffold!
            if not error_list:
                st.success("🎉 Perfect base circuit! Ready to level up? / 完美嘅基礎電路！準備好升級挑戰未？")
                if st.button("🚀 Enter Socratic Challenge Mode! / 進入蘇格拉底挑戰模式", type="primary"):
                    st.session_state.step = 5
                    st.rerun()
                    
            st.divider()
            # Flow Actions Footer Columns
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

        # STEP 5: PERSONALIZED SOCRATIC CHALLENGE MODE
        elif st.session_state.step == 5:
            st.subheader("🚀 Socratic Challenge Mode / 蘇格拉底挑戰模式")
            
            challenges = get_socratic_challenges(selected_task)
            
            # Display past experiments to enforce the "progressive/spiral" feeling
            for msg in st.session_state.socratic_chat:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    
            if st.session_state.socratic_q_idx < len(challenges):
                current_q = challenges[st.session_state.socratic_q_idx]
                
                st.info(f"**Current Challenge ({st.session_state.socratic_q_idx + 1}/{len(challenges)}):**\n\n{current_q}")
                
                st.markdown("### Verify Your Experiment 🔬")
                student_text = st.text_area("What did you change and what happened? / 你改咗咩？觀察到咩？")
                
                # Dedicated iPad/Mobile Upload for the Socratic Challenge
                socratic_upload_mode = st.radio("Upload your modified circuit:", ["Camera 📸", "File 📁"], horizontal=True, label_visibility="collapsed", key=f"s_upload_{st.session_state.socratic_q_idx}")
                
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
                            
                            # Construct chat history string to pass context so AI can personalize the feedback
                            history_context = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.socratic_chat])
                            
                            prompt = f"""
                            Task Context: {selected_task}
                            Previous Conversation History (Use this to personalize your response and reference past levels):
                            {history_context}
                            
                            Current Socratic Challenge: {current_q}
                            Student's Explanation: "{student_text}"
                            
                            Task: Evaluate if the physical circuit image AND their text explanation prove they successfully completed the CURRENT challenge.
                            If correct, respond EXACTLY with "[VERIFICATION: PASSED]" followed by encouraging feedback that references their success in both this level and past levels.
                            If incorrect, respond EXACTLY with "[VERIFICATION: FAILED]" followed by a helpful Socratic hint pointing to their image (do not give the direct answer).
                            Tone: Fun, encouraging, suited for P4-S3 students. Provide bilingual text (English, then Traditional Chinese).
                            """
                            try:
                                resp = client.models.generate_content(
                                    model=MODEL_ID, 
                                    contents=[img_pil, prompt],
                                    config=types.GenerateContentConfig(temperature=0.4)
                                )
                                feedback = resp.text
                                
                                display_feedback = feedback.replace("[VERIFICATION: PASSED]", "").replace("[VERIFICATION: FAILED]", "").strip()
                                
                                st.session_state.socratic_chat.append({"role": "user", "content": f"📝 **My Observation:** {student_text}\n*(Circuit Image Uploaded)*"})
                                st.session_state.socratic_chat.append({"role": "assistant", "content": display_feedback})
                                
                                if "[VERIFICATION: PASSED]" in feedback:
                                    st.session_state.socratic_q_idx += 1
                                    
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"AI Verification Error: {e}")
                                
            else:
                st.success("🏆 You are a Circuit Master! All challenges completed! / 🏆 你已經成為電路大師！完成晒所有挑戰！")
                
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
