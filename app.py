import streamlit as st
import pandas as pd
import json
import os
import io
import hashlib
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

# AI & Google Auth
import vertexai
from vertexai.generative_models import GenerativeModel, Image as VertexImage, GenerationConfig
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="AI 專業電路導航", layout="wide", page_icon="🔌")

DRIVE_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"
LOG_FILE_NAME = "circuit_ai_0321.csv"

# --- 2. INITIALIZE SERVICES ---
@st.cache_resource
def init_services():
    creds_info = st.secrets["gcp_service_account"]
    vertex_creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=vertex_creds)
    model = GenerativeModel("gemini-1.5-pro") # 使用穩定的 Pro 版本

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

# --- 3. SESSION STATE (狀態管理) ---
if 'current_data' not in st.session_state:
    # 預設零件數據 (P4-S3 常見：LDR, LED)
    st.session_state.current_data = [
        {"component": "LDR (光敏電阻)", "center": [500, 500], "legs": [[480, 480], [520, 520]]},
        {"component": "LED (發光二極管)", "center": [300, 300], "legs": [[280, 280], [320, 320]]}
    ]
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None

# --- 4. 繪圖核心函數 ---
def draw_overlay(base_img):
    w, h = base_img.size
    overlay = Image.new('RGBA', base_img.size, (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    
    # 畫麵包板內部導軌 (視覺輔助)
    for row_y in range(100, 950, 40):
        d.line([(80*w/1000, row_y*h/1000), (440*w/1000, row_y*h/1000)], fill=(0, 255, 0, 40), width=3)
        d.line([(560*w/1000, row_y*h/1000), (920*w/1000, row_y*h/1000)], fill=(0, 255, 0, 40), width=3)
        
    for it in st.session_state.current_data:
        cy, cx = it['center']
        cp = (cx * w / 1000, cy * h / 1000)
        # 中心十字 (紅色)
        d.line([cp[0]-15, cp[1], cp[0]+15, cp[1]], fill="red", width=3)
        d.line([cp[0], cp[1]-15, cp[0], cp[1]+15], fill="red", width=3)
        
        for j, leg in enumerate(it['legs']):
            ly, lx = leg
            start_p = cp
            end_p = (lx * w / 1000, ly * h / 1000)
            # 橘色引線
            d.line([start_p, end_p], fill=(255, 130, 0, 200), width=10)
            # 青色孔位
            d.ellipse([end_p[0]-12, end_p[1]-12, end_p[0]+12, end_p[1]+12], fill=(0, 255, 255, 255))
            
    return Image.alpha_composite(base_img.convert('RGBA'), overlay).convert('RGB')

# --- 5. UI LAYOUT (LEFT-RIGHT) ---
st.title("🛠️ AI 電路零件精密調教站")

# Sidebar
with st.sidebar:
    st.header("👤 學生資訊")
    student_id = st.text_input("學生編號", placeholder="例如: 42")
    task_id = st.number_input("任務編號", 1, 10, 1)
    if st.button("🔄 重設所有位置"):
        del st.session_state.current_data
        st.rerun()

# 拍照/上傳
uploaded_file = st.camera_input("第一步：影低你個麵包板")

if uploaded_file and student_id:
    # 讀取圖片
    raw_img = Image.open(uploaded_file)
    
    # 建立左右兩欄 (35% 控制, 65% 預覽)
    col1, col2 = st.columns([35, 65])
    
    with col1:
        st.subheader("📍 零件座標微調")
        for i, item in enumerate(st.session_state.current_data):
            with st.expander(f"零件 {i+1}: {item['component']}", expanded=True):
                # 中心點調整
                st.markdown(f"**中心位置 (X:{item['center'][1]}, Y:{item['center'][0]})**")
                c_x = st.slider(f"零件{i+1} 中心 X", 0, 1000, item['center'][1], key=f"cx_{i}")
                c_y = st.slider(f"零件{i+1} 中心 Y", 0, 1000, item['center'][0], key=f"cy_{i}")
                st.session_state.current_data[i]['center'] = [c_y, c_x]
                
                # 引腳調整
                for j, leg in enumerate(item['legs']):
                    st.markdown(f"**腳 {j+1} 座標: (X:{leg[1]}, Y:{leg[0]})**")
                    l_x = st.slider(f"零件{i+1}-腳{j+1} X", 0, 1000, leg[1], key=f"lx_{i}_{j}")
                    l_y = st.slider(f"零件{i+1}-腳{j+1} Y", 0, 1000, leg[0], key=f"ly_{i}_{j}")
                    st.session_state.current_data[i]['legs'][j] = [l_y, l_x]
        
        analyze_btn = st.button("🚀 遞交 AI 老師分析", use_container_width=True, type="primary")

    with col2:
        st.subheader("👁️ 即時佈線預覽")
        # 繪製並顯示
        final_view = draw_overlay(raw_img)
        st.image(final_view, use_container_width=True)
        
        # 顯示 AI 分析結果
        if analyze_btn:
            with st.spinner("AI 老師睇緊你嘅接線..."):
                # 這裡放入你原本的 model.generate_content 邏輯
                # 傳送座標數據 + 圖片
                st.session_state.analysis_result = "✅ 接線看起來非常專業！請繼續完成剩餘部份。" # 模擬回覆
                st.success(st.session_state.analysis_result)

elif not student_id:
    st.info("👈 請先在側邊欄輸入學生編號。")
