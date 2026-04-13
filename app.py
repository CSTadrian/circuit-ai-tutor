import streamlit as st
import pandas as pd
import json
import os
import io
from PIL import Image, ImageDraw

# AI & Google Auth Imports
import vertexai
from vertexai.generative_models import GenerativeModel, Image as VertexImage
from google.oauth2 import service_account

# --- 1. CONFIG ---
st.set_page_config(page_title="AI Circuit Socratic Tutor", layout="wide", page_icon="🔌")

@st.cache_resource
def init_ai():
    # 喺 Streamlit Cloud Settings -> Secrets 放入 GCP Service Account JSON
    creds_info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=creds)
    return GenerativeModel("gemini-1.5-pro")

model = init_ai()

# --- 2. SESSION STATE (狀態持久化) ---
if 'current_data' not in st.session_state:
    # 預設數據 (Normalized 0-1000 座標系統)
    st.session_state.current_data = [
        {"component": "LDR (光敏電阻)", "center": [500, 500], "legs": [[480, 480], [520, 520]]},
        {"component": "LED (發光二極管)", "center": [300, 300], "legs": [[280, 280], [320, 320]]}
    ]
if 'analysis_report' not in st.session_state: st.session_state.analysis_report = None

# --- 3. 核心標註與邏輯函數 ---
def process_and_draw(base_img, data):
    img = base_img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    inventory_text = ""
    for i, item in enumerate(data):
        cy, cx = item['center']
        comp = item.get('component', f'Part_{i}')
        inventory_text += f"- {comp}: "
        for j, leg in enumerate(item['legs']):
            ly, lx = leg
            # 畫橘色引線
            draw.line([(cx*w/1000, cy*h/1000), (lx*w/1000, ly*h/1000)], fill=(255, 165, 0, 200), width=12)
            # 畫青色孔位 (Cyan Ground Truth)
            draw.ellipse([(lx*w/1000-15, ly*h/1000-15), (lx*w/1000+15, ly*h/1000+15)], fill=(0, 255, 255, 255))
            
            side = "LEFT (a-e)" if lx < 500 else "RIGHT (f-j)"
            inventory_text += f"Pin{j+1}[{side}, y:{ly}, x:{lx}]; "
        inventory_text += "\n"

    # 關鍵：畫藍色中央隔離線 (定義 Breadboard Gap)
    mid_x = w // 2
    draw.line([(mid_x, 0), (mid_x, h)], fill=(0, 0, 255, 180), width=25)
    
    combined = Image.alpha_composite(img, overlay).convert("RGB")
    return combined, inventory_text

# --- 4. UI 介面佈局 ---
st.title("🔌 AI 電路精密診斷站")

with st.sidebar:
    st.header("📋 學生資訊")
    student_id = st.text_input("學生編號", placeholder="例如: 2026001")
    task_type = st.selectbox("電路任務", ["Task 4b: LDR 控制電路", "Task 1: LED 基本迴路"])
    
    st.divider()
    if st.button("🔄 重置所有座標"):
        del st.session_state.current_data
        st.rerun()

# --- 5. 多功能上傳區 (核心改動) ---
st.subheader("第一步：獲取電路圖片")
tab_camera, tab_upload = st.tabs(["📷 即時影相 (Camera)", "📁 上傳檔案 (Upload)"])

raw_image = None

with tab_camera:
    cam_file = st.camera_input("請對準麵包板拍攝")
    if cam_file: raw_image = Image.open(cam_file)

with tab_upload:
    up_file = st.file_uploader("選擇手機或電腦中的圖片檔案", type=['jpg', 'jpeg', 'png'])
    if up_file: raw_image = Image.open(up_file)

# --- 6. 調校與分析區 ---
if raw_image and student_id:
    col_ctrl, col_view = st.columns([0.4, 0.6])
    
    with col_ctrl:
        st.subheader("🛠️ 座標與接線調校")
        st.info("💡 貼士：移動 Slider 令青色圈圈完全覆蓋你插喺麵包板上嘅引腳窿。")
        
        for i, item in enumerate(st.session_state.current_data):
            with st.expander(f"📦 {item['component']}", expanded=True):
                # 中心點 (Red)
                st.write("零件中心位置")
                item['center'][1] = st.slider(f"X (左右) ##cx{i}", 0, 1000, item['center'][1])
                item['center'][0] = st.slider(f"Y (上下) ##cy{i}", 0, 1000, item['center'][0])
                
                # 孔位 (Cyan)
                for j, leg in enumerate(item['legs']):
                    st.write(f"引腳 {j+1} 孔位")
                    leg[1] = st.slider(f"X (左右) ##lx{i}{j}", 0, 1000, leg[1])
                    leg[0] = st.slider(f"Y (上下) ##ly{i}{j}", 0, 1000, leg[0])

        if st.button("✅ 提交 AI 進行邏輯分析", type="primary", use_container_width=True):
            final_img, inv_text = process_and_draw(raw_image, st.session_state.current_data)
            
            prompt = f"""
            Identify the circuit topology. 
            A BLUE LINE marks the middle gap.
            Verified Data: {inv_text}
            Check if the circuit correctly follows the rules for {task_type}.
            Output Format:
            - RESULT: [✅ CORRECT] or [❌ INCORRECT]
            - ANALYSIS: Brief technical check.
            - SOCRATIC: 3 guiding questions.
            """
            
            # 轉換為 AI 識別格式
            buf = io.BytesIO()
            final_img.save(buf, format="JPEG")
            
            with st.spinner("AI 老師正透過藍色隔離線分析左右區域..."):
                response = model.generate_content([VertexImage.from_bytes(buf.getvalue()), prompt])
                st.session_state.analysis_report = response.text

    with col_view:
        st.subheader("🖼️ 即時標註預覽")
        # 繪製預覽圖
        preview_img, _ = process_and_draw(raw_image, st.session_state.current_data)
        st.image(preview_img, use_container_width=True, caption="藍色線代表麵包板中央隔離帶")
        
        if st.session_state.analysis_report:
            st.divider()
            st.markdown(st.session_state.analysis_report)

elif not student_id and raw_image:
    st.warning("👈 請先在側邊欄輸入學生編號。")

st.divider()
st.caption("ECCC AI Research 2026 | Streamlit Multi-Input v3.5")
