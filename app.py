import streamlit as st
import pandas as pd
import json
import os
import io
import hashlib
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw

# AI & Google Auth Imports
import vertexai
from vertexai.generative_models import GenerativeModel, Image as VertexImage, GenerationConfig
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AI Circuit Precision Tutor", layout="wide", page_icon="🔌")

# 假設你已在 Streamlit Secrets 設定好憑證
DRIVE_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"
LOG_FILE_NAME = "circuit_ai_precision_log.csv"

# --- 2. INITIALIZE SERVICES ---
@st.cache_resource
def init_services():
    creds_info = st.secrets["gcp_service_account"]
    vertex_creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=vertex_creds)
    model = GenerativeModel("gemini-1.5-pro")

    oauth_info = st.secrets["google_oauth"]
    from google.oauth2.credentials import Credentials
    drive_creds = Credentials(
        token=None,
        refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"],
        client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    drive_service = build('drive', 'v3', credentials=drive_creds)
    return model, drive_service

model, drive_service = init_services()

# --- 3. SESSION STATE (儲存零件座標) ---
if 'component_data' not in st.session_state:
    st.session_state.component_data = [
        {"component": "LDR (光敏電阻)", "center": [500, 500], "legs": [[480, 480], [520, 520]]},
        {"component": "LED (發光二極管)", "center": [300, 300], "legs": [[280, 280], [320, 320]]}
    ]

# --- 4. 繪圖核心功能 ---
def draw_circuit_overlay(base_img):
    # 轉換為 RGBA 方便畫半透明層
    img = base_img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 1. 繪製麵包板導軌參考 (綠色線)
    for row_y in range(100, 950, 40):
        draw.line([(80*w/1000, row_y*h/1000), (440*w/1000, row_y*h/1000)], fill=(0, 255, 0, 40), width=3)
        draw.line([(560*w/1000, row_y*h/1000), (920*w/1000, row_y*h/1000)], fill=(0, 255, 0, 40), width=3)

    # 2. 繪製零件數據
    for it in st.session_state.component_data:
        cy, cx = it['center']
        cp = (cx * w / 1000, cy * h / 1000)
        
        # 零件中心紅色十字
        draw.line([cp[0]-15, cp[1], cp[0]+15, cp[1]], fill="red", width=3)
        draw.line([cp[0], cp[1]-15, cp[0], cp[1]+15], fill="red", width=3)

        for j, leg in enumerate(it['legs']):
            ly, lx = leg
            start_p = cp
            end_p = (lx * w / 1000, ly * h / 1000)

            # 橘色引線
            draw.line([start_p, end_p], fill=(255, 130, 0, 200), width=10)
            # 青色孔位圈
            draw.ellipse([end_p[0]-12, end_p[1]-12, end_p[0]+12, end_p[1]+12], fill=(0, 255, 255, 255), outline="white")
    
    return Image.alpha_composite(img, overlay).convert("RGB")

# --- 5. UI LAYOUT ---
st.title("🔌 AI 電路接線精確調校站")

# Sidebar
with st.sidebar:
    st.header("Student Setup")
    student_num = st.text_input("Student ID", placeholder="e.g. 42")
    task_num = st.number_input("Task", 1, 10, 1)
    if st.button("Reset All Positions"):
        del st.session_state.component_data
        st.rerun()

# 第一步：獲取圖片
img_input = st.camera_input("Step 1: Capture your breadboard")

if img_input and student_num:
    original_image = Image.open(img_input)
    
    # 建立左右佈局
    col_ctrl, col_view = st.columns([0.4, 0.6])

    with col_ctrl:
        st.subheader("🛠️ 精確座標控制")
        st.info("💡 貼士：先移動紅十字對準零件，再移動青色圈對準插孔。")
        
        # 動態生成 Sliders
        for i, item in enumerate(st.session_state.component_data):
            with st.expander(f"📦 零件 {i+1}: {item['component']}", expanded=True):
                # 中心點控制
                st.write("**零件本體中心 (Red Cross)**")
                cx = st.slider(f"X (左右) ##{i}_c", 0, 1000, item['center'][1], key=f"c_x_{i}")
                cy = st.slider(f"Y (上下) ##{i}_c", 0, 1000, item['center'][0], key=f"c_y_{i}")
                st.session_state.component_data[i]['center'] = [cy, cx]
                
                # 引腳控制
                for j, leg in enumerate(item['legs']):
                    st.write(f"**引腳 {j+1} 位置 (Cyan Hole)**")
                    lx = st.slider(f"X (左右) ##{i}_l{j}", 0, 1000, leg[1], key=f"l_x_{i}_{j}")
                    ly = st.slider(f"Y (上下) ##{i}_l{j}", 0, 1000, leg[0], key=f"l_y_{i}_{j}")
                    st.session_state.component_data[i]['legs'][j] = [ly, lx]

        if st.button("🚀 提交 AI 診斷", use_container_width=True, type="primary"):
            # 這裡執行 AI 分析邏輯
            st.success("AI 老師正在處理座標數據與圖像...")

    with col_view:
        st.subheader("🖼️ 即時標註預覽")
        processed_img = draw_circuit_overlay(original_image)
        st.image(processed_img, use_container_width=True, caption="橘色線必須由零件中心連向麵包板孔位")

elif not student_num and img_input:
    st.warning("Please enter your Student ID in the sidebar first!")

st.divider()
st.caption("ECCC AI Research 2026 | Streamlit Precision UI v3.0")
