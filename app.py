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

# --- 1. CONFIGURATION & GAMIFIED TASK SETUP ---
TASKS = {
    "Task 1: Brightest LED Challenge": "task1_brightness.png",
    "Task 2: Longest Fade-out Challenge": "task2_fade.png",
    "Task 3: Max LDR Difference Challenge": "task3_ldr.png"
}

DATA_FOLDER = "data"
MODEL_ID = "gemini-3.1-pro-preview"

# Google Drive Config
PARENT_FOLDER_ID = "1_cn9lfvMLaozDTx8pvU6LP62J9AVFrvz"
CSV_FILENAME = "circuit_audit_logs.csv"

# --- UI LANGUAGE DICTIONARY ---
UI = {
    "en": {
        "title": "🔌 AI Circuit Quest: Optimization Arena",
        "setup": "Game Setup",
        "user_id": "Select Team / User ID",
        "task": "Select Quest Arena",
        "inferred_task": "AI Inferred Architecture",
        "target": "Target Strategy Worksheet Guide",
        "input_mode": "Capture Method",
        "mode_upload": "Upload Image",
        "mode_camera": "Use Camera",
        "upload": "Upload Circuit Configuration Photo",
        "reset": "Reset Current Quest",
        "schematic": "Quest Reference Schematic",
        "your_circuit": "Your Layout Scan (Pale Blue = Internal Lanes Connected)",
        "step1_btn": "🔍 Step 1: Scan Component Architecture",
        "analyzing": "AI Engine reverse-engineering hardware topology...",
        "step2_title": "⚙️ Step 2: Fine-Tune Pin Connections (Auto-Snapping Rows)",
        "step2_confirm": "🔒 Lock Setup & Predict Outcome",
        "snapped": "*(Leg auto-aligned to nearest horizontal lane: {y})*",
        "verify": "Verify Orange Paths & Yellow Target Pins (Snapped to Blue Lanes)",
        "step3_title": "📊 Step 3: Performance Telemetry HUD & Diagnosis",
        "checking": "Calculating electrical network transformations...",
        "ai_diag": "AI Scan HUD: Red circles flag system blockages/open nodes",
        "semantic_map_title": "🗺️ Detected Circuit Semantic Layout Map",
        "save": "💾 Save Score to Drive",
        "back": "🔙 Modify Hardware",
        "new": "🎉 Choose Next Quest",
        "upload_prompt": "Select an input method to scan your hardware configuration.",
        "guide_title": "📖 Quest Field Guide",
        "camera": "Scan Your Live Configuration",
        "guide_text": """
        **Quest Loop:**
        1. Select Arena & Submit Hardware Configuration Photo.
        2. Scan Architecture (Step 1) to build digital structural map.
        3. Clear the **Prediction Gate** (Step 2) to unlock live simulation data.
        4. Read Telemetry HUD and execute Socratic experiments (Step 3 & 4) to break room records!
        
        **HUD Telemetry Icons:**
        * 🔴 **Red Ring:** System structural break (Open Circuit / Floating Node).
        * 🟦 **Blue Frame:** Component asset structural mismatch.
        * 🟡 **Yellow Ring:** Axis orientation or directional polarity failure.
        """,
        "prediction_header": "🔮 The Prediction Gate",
        "prediction_prompt": "Before the AI Engine simulates your circuit, your team must lock in a structural hypothesis choice. What will this configuration change do?",
        "predict_err": "Please select a hypothesis choice before confirming your setup!",
        "metrics_header": "🏎️ Live Performance Metrics",
        "metric_brightness": "💡 Brightness Score (Power Output)",
        "metric_resistance": "🚧 Traffic Jam Thickness (Resistance Blockage)",
        "metric_capacitance": "💧 Energy Water Tank Volume",
        "metric_ldr_delta": "🌗 Light-to-Shadow Delta Swing",
    },
    "hk": {
        "title": "🔌 AI 電路大挑戰：極限優化競技場",
        "setup": "遊戲設定",
        "user_id": "選擇隊伍 / 學生 ID",
        "task": "選擇挑戰關卡",
        "inferred_task": "AI 推斷嘅電路拓撲",
        "target": "目標任務工作紙指引",
        "input_mode": "輸入方式",
        "mode_upload": "上傳圖片",
        "mode_camera": "使用相機",
        "upload": "上傳實體結構相片",
        "reset": "重置當前挑戰",
        "schematic": "挑戰參考電路圖",
        "your_circuit": "你嘅線路掃描（淺藍色線 = 麵包板內部已連通車道）",
        "step1_btn": "🔍 第一步：掃描零件結構拓撲",
        "analyzing": "AI 引擎正喺度逆向解構你嘅硬件佈局...",
        "step2_title": "⚙️ 第二步：微調引腳位置（自動對齊橫向車道）",
        "step2_confirm": "🔒 鎖定佈局並進行成果預測",
        "snapped": "*(引腳已自動對齊至最近嘅橫向車道：{y})*",
        "verify": "請核對橙色路徑與黃色接點（已對齊至淺藍色車道）",
        "step3_title": "📊 第三步：實時性能數據面板（HUD）與核心診斷",
        "checking": "正在運算電路網絡之物理數據表現...",
        "ai_diag": "AI 診斷面板：紅圈表示系統內部有斷開或懸空阻礙",
        "semantic_map_title": "🗺️ 偵測到嘅電路結構路徑圖",
        "save": "💾 儲存分數至 Drive",
        "back": "🔙 修改實體硬件",
        "new": "🎉 挑戰下一關",
        "upload_prompt": "請選擇上傳相片或開啟相機鏡頭以開始挑戰。",
        "guide_title": "📖 快速指南",
        "camera": "拍攝電路照片",
        "guide_text": """
        **核心玩法循環：**
        1. 選擇關卡並提交硬件配置相片。
        2. 掃描結構（第一步）以建立數位電路網絡地圖。
        3. 通過 **「預測閘門」**（第二步）鎖定假設，以解鎖實時模擬數據。
        4. 解讀 HUD 數據並執行蘇格拉底探究任務（第三、四步）去衝擊全班紀錄！
        
        **面板圖示說明：**
        * 🔴 **紅圈：** 結構性斷路 / 懸空節點（電力無法返回負極）。
        * 🟦 **藍框：** 元件型號錯誤或阻值不符。
        * 🟡 **黃圈：** 方向性極性接反或軸向打橫放錯。
        """,
        "prediction_header": "🔮 預測閘門 (Prediction Gate)",
        "prediction_prompt": "喺 AI 引擎幫你運行模擬之前，你嘅隊伍必須先鎖定一個結構性假設。你認為今次改動會帶嚟咩結果？",
        "predict_err": "請先選擇一個結果假設，先可以鎖定並確認佈局！",
        "metrics_header": "🏎️ 實時系統性能指標 (HUD)",
        "metric_brightness": "💡 亮度得分 (實際功率輸出)",
        "metric_resistance": "🚧 交通擠塞厚度 (總電阻屏障)",
        "metric_capacitance": "💧 儲能水箱容量 (電容容量)",
        "metric_ldr_delta": "🌗 光影動態擺幅 (LDR 變動差值)",
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

# --- 3. COMPUTER VISION PROCESSORS & REPORT GENERATORS ---
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
    draw.text((50, 75), "✅ Electrical Successes / 順利運作指標", fill=(0, 128, 0))
    
    y_off = 110
    for item in successes[:5]: 
        draw.text((60, y_off), f"🌟 {item}", fill=(30, 30, 30))
        y_off += 30

    draw.rectangle([30, 310, 770, 560], outline=(200, 100, 0), width=3, fill=(255, 250, 240))
    draw.text((50, 325), "🛠️ Engineering Constraints / 硬件設計限制", fill=(200, 100, 0))
    
    y_off = 360
    for item in errors[:5]:
        draw.text((60, y_off), f"🔍 {item}", fill=(30, 30, 30))
        y_off += 30
        
    return img

def save_to_drive(user_id, inferred_task_name, ai_feedback, images_dict, prediction_made, score_achieved):
    service = get_drive_service()
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    hk_time_str = datetime.now(hk_tz).strftime('%Y-%m-%d %H:%M:%S')
    
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
            "User ID": user_id, 
            "Time": hk_time_str, 
            "Task Arena": inferred_task_name,
            "Prediction Made": prediction_made,
            "Optimization Score": score_achieved,
            "Raw": f"{file_prefix}_1.png", 
            "Final": f"{file_prefix}_4.png", 
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
            
        st.toast("✅ Automatically saved to Google Drive leaderboard database!")
        
    except Exception as e:
        st.error(f"Drive Save Error: {e}")

# --- 4. PROGRESSIVE SOCRATIC EXPERIMENT GENERATOR ---
def get_socratic_challenges(task_name, user_id):
    try:
        uid_int = int(user_id)
    except (ValueError, TypeError):
        uid_int = 0
        
    is_odd = (uid_int % 2 != 0)
    challenges = []

    if "Task 1" in task_name:
        if is_odd:
            challenges = [
                "Level 1 🟢 (The Twin Bridge): Connect TWO 10k ohm resistors side-by-side (parallel) across the lane. Look at your new Brightness score. Why did adding more resistance obstacles make the light brighter?\n\n第一關 🟢 (雙子橋樑): 將兩粒 10k ohm 電阻並排（並聯）跨接喺車道上。睇下你嘅亮度得分。點解加多粒阻礙物，粒燈反而會變光咗？",
                "Level 2 🟡 (The Triple Lane): Add a THIRD 10k ohm resistor parallel to the first two. Observe the Traffic Jam score. Did the blockage grow thicker or thinner? Explain how electricity chooses its path!\n\n第二關 🟡 (三線行車): 加上第三粒 10k ohm 電阻進行並聯。觀察「交通擠塞」得分。究竟阻礙物係變厚咗定薄咗？試下解釋電流係點樣揀路行！",
                "Level 3 🔴 (The Short Circuit Boundary): What happens if you remove all resistors and run a single straight wire into the LED? Predict the danger before you scan! How does a floor resistor protect a system?\n\n第三關 🔴 (短路邊界大挑戰): 如果抆走晒所有電阻，直接用一條導線駁入 LED 會發生咩事？喺掃描前先預測危險！限流底層電阻係點樣保護一個系統？"
            ]
        else:
            challenges = [
                "Level 1 🟢 (The Series Trap): Connect two 10k ohm resistors end-to-end (series) in a single line before the LED. Scan it. Why did the Traffic Jam score double, and what happened to the brightness?\n\n第一關 🟢 (串聯陷阱): 將兩粒 10k ohm 電阻排成一條直線（串聯）接喺 LED 前面。掃描佢。點解「交通擠塞」分數翻咗倍，而亮度又發生咗咩事？",
                "Level 2 🟡 (The Reversibility Loop): Keep the series resistors, but swap the physical layout order (LED first, then resistors). Does changing the structural order change the terminal brightness score? Why?\n\n第二關 🟡 (順序對調圈): 保留串聯電阻，但將硬件位置對調（LED 放前，電阻放後）。改變排隊次序會唔會影響最終嘅亮度得分？點解？",
                "Level 3 🔴 (The Mixed Highway): Try to place two resistors in parallel, and then chain a third resistor in series right after them. Analyze your HUD metrics. How does this combined configuration scale your final current output?\n\n第三關 🔴 (混合高速公路): 嘗試將兩粒電阻並聯，然後喺後面串聯駁上第三粒電阻。分析你嘅 HUD 數據。呢種混合排列點樣影響你最終嘅電流輸出？"
            ]
    elif "Task 2" in task_name:
        if is_odd:
            challenges = [
                "Level 1 🟢 (The Tank Valve Test): Move your resistor so it sits directly inside the discharge path between the capacitor bucket and the LED. What changes on the fade-out timeline?\n\n第一關 🟢 (水箱水閥測試): 移動你嘅電阻，等佢直接坐喺電容水箱同 LED 之間嘅放電路徑上。變暗時間線產生咗咩變化？",
                "Level 2 🟡 (The Dual Bucket Stack): Add a second, identical 220uF capacitor side-by-side (parallel) with the first one. Look at your Energy Tank metric. Did you increase water storage volume or pressure?\n\n第二關 🟡 (雙水箱並聯): 將第二粒相同嘅 220uF 電容並排（並聯）接上。睇下你嘅「儲能水箱」指標。你究竟係增加了儲水容量，定係增加了水壓？",
                "Level 3 🔴 (The Latching Gate Logic): Toggle your slide-switch rapidly back and forth. Can you trace how the switch mechanically redirects power from the battery into the storage tank versus locking it into the LED loop?\n\n第三關 🔴 (鎖定閘門邏輯): 快速來回切換你嘅滑動開關掣。你能唔能追蹤到開關掣係點樣透過機械結構，將電力由電池導向儲能水箱，抑或鎖定喺 LED 迴路入面放電？"
            ]
        else:
            challenges = [
                "Level 1 🟢 (The Resistor Pipe Chain): Chain two 10k ohm resistors in series inside the discharge loop. Does a longer single-file pipe line slow down the water flow or speed it up?\n\n第一關 🟢 (串聯水管鏈): 喺放電迴路裏面串聯裝上兩粒 10k ohm 電阻。排成單行、更長嘅水管線，會令水流減慢定加快？",
                "Level 2 🟡 (The Parallel Leak): Arrange your resistors side-by-side in parallel instead of series inside the capacitor loop. Look at the fade clock. Why did the parallel highway empty the water tank instantly?\n\n第二關 🟡 (並聯洩漏): 喺電容迴路中將電阻改為並排（並聯）接駁。觀察變暗時鐘。點解並聯快線會令水箱一瞬間排空？",
                "Level 3 🔴 (The Giant Dynamic Window): Try to maximize your layout using all available capacitors and resistors to construct the ultimate slow-drain setup. Can your team push the timeline past 10 seconds?\n\n第三關 🔴 (極限動態視窗): 嘗試用盡手頭上所有嘅電容同電阻，砌出終極慢速放電佈局。你嘅隊伍能唔能將時間線推高過 10 秒？"
            ]
    else:
        challenges = [
            "Level 1 🟢 (The Total Shadow Void): Shield the LDR using an opaque cup or your thumb until room light drops to zero. Read the HUD delta score. What happens to an LDR's internal bridge blockage when darkness hits?\n\n第一關 🟢 (全黑盲區): 用不透明嘅杯或大拇指完全遮蓋 LDR 阻擋所有光線。讀取 HUD 擺幅得分。當黑暗襲來時，LDR 內部嘅「道路屏障」發生咗咩事？",
            "Level 2 🟡 (The Protective Floor Boundary): Remove your 1k ohm inline series resistor and run only the LDR. Shine a blinding flashlight directly on it. Why does the AI sound an alarm, and how does a safety floor resistor prevent system burnouts?\n\n第二關 🟡 (安全底線邊界): 抆走 1k ohm 限流電阻，只留下 LDR。用強光電筒直接照射。點解 AI 會發出警告？安全底線電阻點樣防止系統元件燒毀？",
            "Level 3 🔴 (The Dynamic Voltage Maximizer): Adjust your baseline fixed resistance layer to match your LDR's ambient room midpoint value. Can your team unlock the highest dynamic contrast swing code on the leaderboard?\n\n第三關 🔴 (動態擺幅極大化): 調整你嘅固定底層電阻，去配對你粒 LDR 喺課室光線下嘅中位數。你能不能解鎖龍虎榜上最高嘅對比度差值？"
        ]
    return challenges

# --- 5. GLOBAL SESSION STATE ENGINE ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "analysis_result" not in st.session_state: st.session_state.analysis_result = None
if "hough_rows" not in st.session_state: st.session_state.hough_rows = []
if "breadboard_corners" not in st.session_state: st.session_state.breadboard_corners = None
if "last_input_id" not in st.session_state: st.session_state.last_input_id = None
if "socratic_q_idx" not in st.session_state: st.session_state.socratic_q_idx = 0
if "socratic_chat" not in st.session_state: st.session_state.socratic_chat = []
if "locked_prediction" not in st.session_state: st.session_state.locked_prediction = "None"

for i in range(1, 5): 
    if f"img{i}" not in st.session_state: st.session_state[f"img{i}"] = None

def reset_flow():
    for key in ["step", "components_df", "analysis_result", "img1", "img2", "img3", "img4"]:
        if "df" in key: st.session_state[key] = pd.DataFrame()
        elif "step" in key: st.session_state[key] = 1
        else: st.session_state[key] = None
    st.session_state.hough_rows = []
    st.session_state.breadboard_corners = None
    st.session_state.socratic_q_idx = 0
    st.session_state.socratic_chat = []
    st.session_state.locked_prediction = "None"

# --- 6. ENVIRONMENT COMPILATION & SIDEBAR CONTROL ---
lang_select = st.radio("🌐", ["English", "繁體中文"], horizontal=True, label_visibility="collapsed")
l = "en" if lang_select == "English" else "hk"

st.title(UI[l]["title"])

with st.sidebar:
    st.header(UI[l]["setup"])
    user_id = st.selectbox(UI[l]["user_id"], [f"{i:02d}" for i in range(1, 61)])
    selected_task = st.selectbox("Select Arena / 選擇挑戰關卡", list(TASKS.keys()))
    
    st.divider()
    input_mode = st.radio(UI[l]["input_mode"], ["Camera 📸", "File Upload 📁"], index=1, horizontal=True)
    
    if input_mode == "Camera 📸":
        active_input = st.camera_input(UI[l]["camera"])
    else:
        active_input = st.file_uploader(UI[l]["upload"], type=["jpg", "png", "jpeg", "heic"])
        
    st.divider()
    if st.button(UI[l]["reset"]): 
        reset_flow()
        st.session_state.last_input_id = None
        st.rerun()

    st.markdown(f"### {UI[l]['guide_title']}")
    st.markdown(UI[l]['guide_text'])

# --- 7. MAIN STATE RUNTIME STATE MACHINE ---
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

        is_camera_mode = (input_mode == "Camera 📸")

        # --- STEP 1: COMPONENT TRACE EXTRACTION ---
        if st.session_state.step == 1:
            grid_visualization = draw_coordinate_grid(raw_student.copy(), st.session_state.hough_rows, st.session_state.breadboard_corners)
            orig_w, orig_h = grid_visualization.size
            large_grid_img = grid_visualization.resize((orig_w * 2, orig_h * 2), PILImage.Resampling.LANCZOS)
            
            st.subheader(UI[l]["your_circuit"])
            st.image(large_grid_img, use_container_width=True)

            if st.button(UI[l]["step1_btn"], type="primary"):
                with st.spinner(UI[l]["analyzing"]):
                    prompt = """
                        1. Identify the BREADBOARD boundaries: Provide [y, x] coordinates for the four outer corners (top_left, top_right, bottom_right, bottom_left).
                        2. Identify all components and jumper wires physically placed on the breadboard. Follow these strict schema rules:
                        - JUMPER WIRES: Uniquely identify and label every single wire sequentially (e.g., 'Wire 1', 'Wire 2').
                        - OTHER STRATEGIC ASSETS: Label them uniquely (e.g., 'Resistor 1', 'LED 1', 'Capacitor 1', 'Slide-Switch 1', 'LDR 1').
                        - PINS/LEGS SCHEMA: Order each component's pin locations sequentially within its 'legs' coordinate array.
                        - POWER SUPPLY RAIL LINKS: Locate positive (+ve/Vcc) and negative (-ve/GND) rail columns.
                        - RESISTOR SIGNATURES: Treat all resistors as 10k ohm baseline values for calculation mapping unless overridden by task scope.
                        Return JSON mapping 'breadboard_corners' and 'components'.
                        """
                    resp = client.models.generate_content(
                        model=MODEL_ID, contents=[raw_student, prompt],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json",
                            response_schema={
                                "type": "object",
                                "properties": {
                                    "breadboard_corners": {
                                        "type": "object",
                                        "properties": {
                                            "top_left": {"type": "array", "items": {"type": "integer"}},
                                            "top_right": {"type": "array", "items": {"type": "integer"}},
                                            "bottom_right": {"type": "array", "items": {"type": "integer"}},
                                            "bottom_left": {"type": "array", "items": {"type": "integer"}},
                                        }
                                    },
                                    "components": {
                                        "type": "array", 
                                        "items": {
                                            "type": "object", 
                                            "properties": {
                                                "name": {"type": "string"},
                                                "center": {"type": "array", "items": {"type": "integer"}},
                                                "legs": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}
                                            }
                                        }
                                    }
                                }
                            }
                        )
                    )
                    
                    result = resp.parsed
                    if isinstance(result, list) and len(result) > 0: result = result[0]
                    st.session_state.breadboard_corners = result.get("breadboard_corners", {})

                    records = []
                    for item in result.get("components", []):
                        center = item.get('center', [500, 500])
                        cy, cx = center[0], center[1] if (isinstance(center, list) and len(center) == 2) else (500, 500)
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

        # --- STEP 2: HYPOTHESIS PREDICTION GATE & CALIBRATION LOCK ---
        elif st.session_state.step == 2:
            st.subheader(UI[l]["step2_title"])
            
            st.markdown("### 🔮 The Prediction Gate / 預測閘門")
            st.info("Lock in your prediction hypothesis before the AI calculates system metrics! / 請先進行科學成果假設預測：")
            
            hypotheses_options = [
                "--- Select Hypothesis / 請選擇假設 ---",
                "📈 Optimize Performance Score (Brighter Light / Longer Fade Window) / 提升表現分數 (更亮 / 更耐)",
                "📉 Lower Performance Score (Dimmer Light / Faster Drainage) / 降低表現分數 (變暗 / 變快放電)",
                "💥 Short Circuit Node Condition / 引發系統短路狀態"
            ]
            selected_hypothesis = st.selectbox("Your Team's Prediction / 你組別嘅預測：", hypotheses_options, key="quest_prediction")
            
            st.divider()
            edit_col, img_col = st.columns([1, 2])
                
            updated_data = []
            with edit_col:
                for i, row in st.session_state.components_df.iterrows():
                    with st.expander(f"📍 {row['Component']}"):
                        lx = st.slider(f"Adjust X position", 0, 1000, int(row["LX"]), key=f"x{i}")
                        raw_ly = st.slider(f"Adjust Y position", 0, 1000, int(row["LY"]), key=f"y{i}")
                        snapped_ly = min(st.session_state.hough_rows, key=lambda ry: abs(ry - raw_ly)) if st.session_state.hough_rows else raw_ly
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
                if selected_hypothesis == hypotheses_options[0]:
                    st.error("Please lock in a valid hypothesis prediction choice first! / 請先選擇一個結果假設！")
                else:
                    st.session_state.components_df = edited_df
                    st.session_state.locked_prediction = selected_hypothesis
                    st.session_state.analysis_result = None
                    st.session_state.img4 = None
                    st.session_state.step = 3
                    st.rerun()

        # --- STEP 3: REVERSE ENGINEERING ALIGNMENT REVIEW ---
        elif st.session_state.step == 3:
            st.subheader("Step 3: Intent & Connection Verification / 逆向意圖與落點確認")
            st.warning("🔍 Double-check pins before mapping / 評分前請細心核對")
            
            w3, h3 = st.session_state.img3.size
            large_img3_review = st.session_state.img3.resize((w3 * 2, h3 * 2), PILImage.Resampling.LANCZOS)
            st.image(large_img3_review, caption="Alignment Precision View", use_container_width=True)
            
            btn_text = "🤖 Run Optimization & Engineering Analysis" if l == "en" else "🤖 開始亮度與綜合網絡指標分析"
            
            col_btn_run, col_btn_back = st.columns([1, 4])
            with col_btn_run:
                if st.button(btn_text, type="primary"):
                    with st.spinner(UI[l]["checking"]):
                        summary = st.session_state.components_df.to_string(index=False)
                        
                        prompt = f"""
                            You are an autonomous engineering tutor reverse-engineering a student breadboard for: {selected_task}.
                            
                            Perform an electrical analysis check and calculate performance metrics:
                            1. TASK 1 (BRIGHTEST LED CHALLENGE):
                               - Goal: Maximize 'brightness_score' by dropping total network resistance. Every valid parallel resistor lane drives current higher.
                               - Compute the loop current (mA) strictly based on Ohm's law: I = 3V / R_total.
                               - SCORING CRITERIA: Scale the current directly into 'brightness_score' using the classroom formula: current_ma * 100. For instance, 0.300 mA = 30 marks.
                            2. TASK 2 (LONGEST FADE-OUT CHALLENGE):
                               - Goal: Maximize 'fade_duration_score' (0-100) using the RC time formula with a 220uF capacitor.
                               - Resistors in a SERIES chain add resistance, stretching the time constant (+25 per series resistor). Parallel layout empties tank instantly.
                               - Set 'water_tank_score' to show energy storage layer status.
                            3. TASK 3 (MAX LDR DIFFERENCE CHALLENGE):
                               - Goal: Maximize 'ldr_delta_score' (0-100) light-to-dark contrast swing.
                               - Check for a 1k ohm inline protective series resistor. If missing, flag hazard and drop score to 0.
                            
                            Pedagogical Scaffolding Rule:
                            - If any structural wiring errors exist, use written formal Cantonese and English SOCRATIC FEEDBACK in 'feedback'. Do not reveal row coordinate fixes. Use traffic/water bucket analogies.
                            
                            ASCII Text Map:
                            Generate a clean vertically aligned text flow block for 'circuit_semantic_map' from positive power rail down to ground.
                            
                            Component Coordinates:
                            {summary}
                            """
                        
                        try:
                            resp = client.models.generate_content(
                                model=MODEL_ID, 
                                contents=[st.session_state.img3, prompt],
                                config=types.GenerateContentConfig(
                                    temperature=0.0,
                                    response_mime_type="application/json",
                                    response_schema={
                                        "type": "object",
                                        "properties": {
                                            "inferred_circuit_name": {"type": "string"},
                                            "feedback": {"type": "string"},
                                            "circuit_semantic_map": {"type": "string"},
                                            "success_summary": {"type": "array", "items": {"type": "string"}},
                                            "error_summary": {"type": "array", "items": {"type": "string"}},
                                            "brightness_score": {"type": "integer"},
                                            "traffic_jam_score": {"type": "integer"},
                                            "water_tank_score": {"type": "integer"},
                                            "ldr_delta_score": {"type": "integer"},
                                            "calculated_current_ma": {"type": "number"},
                                            "detected_errors": {
                                                "type": "array", 
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "error_type": {"type": "string"},
                                                        "location": {"type": "array", "items": {"type": "integer"}}
                                                    }
                                                }
                                            }
                                        },
                                        "required": ["inferred_circuit_name", "feedback", "circuit_semantic_map", "detected_errors", "success_summary", "error_summary", "calculated_current_ma"]
                                    }
                                )
                            )
                            
                            result = resp.parsed
                            if isinstance(result, list) and len(result) > 0: result = result[0]
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
                            
                            if "Task 1" in selected_task:
                                final_score = result.get("brightness_score", 0)
                            elif "Task 2" in selected_task:
                                final_score = result.get("brightness_score", 0)
                            else:
                                final_score = result.get("ldr_delta_score", 0)

                            feedback_text = result.get("feedback", "")
                            success_list = result.get("success_summary", [])
                            error_list = result.get("error_summary", [])
                            report_card_img = create_visual_report(success_list, error_list, l)
                            
                            save_to_drive(
                                user_id, selected_task, feedback_text, 
                                {"1": st.session_state.img1, "4": st.session_state.img4, "summary": report_card_img},
                                st.session_state.locked_prediction, final_score
                            )
                            
                            st.session_state.step = 4
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"AI Numerical Core Execution Failed: {e}")
                            st.session_state.step = 2
                            st.rerun()
            with col_btn_back:
                if st.button(UI[l]["back"]):
                    st.session_state.step = 2
                    st.rerun()

        # --- STEP 4: LIVE METRICS HUD & FEEDBACK ARENA ---
        elif st.session_state.step == 4:
            st.subheader(UI[l]["step3_title"])
            
            res_data = st.session_state.analysis_result
            inferred_title = res_data.get("inferred_circuit_name", "Custom Setup Matrix")
            st.metric(label=UI[l]["inferred_task"], value=inferred_title)
            
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.markdown(f"""<div class='metric-card'><h4>{UI[l]['metric_brightness']}</h4><h2>{res_data.get('brightness_score', 0)} MARKS</h2></div>""", unsafe_allow_html=True)
            with m_col2:
                st.markdown(f"""<div class='metric-card' style='border-left-color: #ef4444;'><h4>{UI[l]['metric_resistance']}</h4><h2>{res_data.get('traffic_jam_score', 0)} %</h2></div>""", unsafe_allow_html=True)
            with m_col3:
                if "Task 2" in selected_task:
                    st.markdown(f"""<div class='metric-card' style='border-left-color: #10b981;'><h4>{UI[l]['metric_capacitance']}</h4><h2>{res_data.get('water_tank_score', 0)} L</h2></div>""", unsafe_allow_html=True)
                elif "Task 3" in selected_task:
                    st.markdown(f"""<div class='metric-card' style='border-left-color: #f59e0b;'><h4>{UI[l]['metric_ldr_delta']}</h4><h2>{res_data.get('ldr_delta_score', 0)} Δ</h2></div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class='metric-card' style='border-left-color: #cccccc;'><h4>Calculated Current</h4><h2>{res_data.get('calculated_current_ma', 0.0):.3f} mA</h2></div>""", unsafe_allow_html=True)

            st.divider()

            if st.session_state.img4 is not None:
                st.image(st.session_state.img4, caption=UI[l]["ai_diag"], use_container_width=True)
                
                st.markdown(f"### {UI[l]['semantic_map_title']}")
                st.code(res_data.get("circuit_semantic_map", "No Map Generated"), language="text")
                
                st.info(res_data.get("feedback", ""))
                
                success_list = res_data.get("success_summary", [])
                error_list = res_data.get("error_summary", [])
                
                report_card_img = create_visual_report(success_list, error_list, l)
                st.image(report_card_img, use_container_width=True)

            if not error_list:
                st.success("🏆 Hardware Core Loop Stable! Optimization Arena unlocked! / 基礎結構安全無誤！優化競技場沙盒已解鎖！")
                if st.button("🚀 Enter Progressive Socratic Sandbox / 進入蘇格拉底深度挑戰", type="primary"):
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

        # --- STEP 5: SPIRAL CHALLENGE MATRIX ---
        elif st.session_state.step == 5:
            st.subheader("🚀 Socratic Challenge Sandbox / 蘇格拉底探究沙盒")
            
            challenges = get_socratic_challenges(selected_task, user_id)
            
            for msg in st.session_state.socratic_chat:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    
            if st.session_state.socratic_q_idx < len(challenges):
                current_q = challenges[st.session_state.socratic_q_idx]
                st.info(f"**Current Arena Challenge ({st.session_state.socratic_q_idx + 1}/{len(challenges)}):**\n\n{current_q}")
                
                st.markdown("### Verify Experiment Modification / 驗證你嘅變項修改 🔬")
                student_text = st.text_area("What variable did you change, and what metric shifted on the board? / 你改動咗邊個變項？數據有咩轉變？")
                
                socratic_upload_mode = st.radio("Scan modification layout:", ["Camera 📸", "File 📁"], horizontal=True, label_visibility="collapsed", key=f"s_upload_{st.session_state.socratic_q_idx}")
                if socratic_upload_mode.startswith("Camera"):
                    proof_img = st.camera_input("Scan modified hardware alignment", key=f"s_cam_{st.session_state.socratic_q_idx}")
                else:
                    proof_img = st.file_uploader("Upload modification proof photo", type=["jpg", "png", "jpeg"], key=f"s_file_{st.session_state.socratic_q_idx}")
                    
                if st.button("Submit Experiment to Leaderboard Engine! 🔍", type="primary"):
                    if not student_text or not proof_img:
                        st.warning("Please submit both text reasoning logs and a photo scan! / 請同時提供文字推論紀錄與配置相片！")
                    else:
                        with st.spinner("AI checking modified structural execution mechanics..."):
                            img_pil = process_uploaded_image(io.BytesIO(proof_img.getvalue()))
                            history_context = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.socratic_chat])
                            
                            prompt = f"""
                                Task Arena Master: {selected_task}
                                Past Experiment Iterations Registry:
                                {history_context}
                                
                                Targeted Socratic Objective: {current_q}
                                Student Team In-Situ Reason Log: "{student_text}"
                                
                                Task Requirement: Check if the new circuit photo asset AND their textual reasoning log successfully prove they completed the TARGETED sandbox level.
                                If successful -> Begin string output exactly with prefix '[VERIFICATION: PASSED]' followed by enthusiastic, bilingual text validating their learning.
                                If failed -> Begin string output exactly with prefix '[VERIFICATION: FAILED]' followed by a strategic hint. Do not provide answers.
                                """
                            
                            try:
                                resp = client.models.generate_content(
                                    model=MODEL_ID, 
                                    contents=[img_pil, prompt],
                                    config=types.GenerateContentConfig(temperature=0.4)
                                )
                                feedback = resp.text
                                display_feedback = feedback.replace("[VERIFICATION: PASSED]", "").replace("[VERIFICATION: FAILED]", "").strip()
                                
                                st.session_state.socratic_chat.append({"role": "user", "content": f"📝 **Team Logic Log:** {student_text}\n*(Hardware Scan Uploaded)*"})
                                st.session_state.socratic_chat.append({"role": "assistant", "content": display_feedback})
                                
                                if "[VERIFICATION: PASSED]" in feedback:
                                    st.session_state.socratic_q_idx += 1
                                    
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Scaffold Evaluation Failed: {e}")
                                
            else:
                st.success("🏆 Elite Circuit Master Status Achieved! Arena Challenges Completed! / 🏆 恭喜你完成全套大挑戰，榮登終極電路大師寶座！")
                
            st.divider()
            col_b, col_c = st.columns(2)
            with col_b:
                if st.button("Return to Simulation HUD" if l == "en" else "返回主數據儀表面板"):
                    st.session_state.step = 4
                    st.rerun()
            with col_c:
                if st.button(UI[l]["new"]):
                    reset_flow()
                    st.session_state.last_input_id = None
                    st.rerun()
else:
    st.error(UI[l]["upload_prompt"])
