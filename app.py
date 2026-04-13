import streamlit as st
import pandas as pd
import json
import os
import io
from PIL import Image, ImageDraw, ImageFont

# AI & Google Auth Imports
import vertexai
from vertexai.generative_models import GenerativeModel, Image as VertexImage, GenerationConfig
from google.oauth2 import service_account

# --- 1. CONFIG & SETUP ---
st.set_page_config(page_title="AI Circuit Socratic Tutor", layout="wide")

@st.cache_resource
def init_ai():
    # 請確保在 Streamlit Secrets 放入 creds
    creds_info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=creds)
    return GenerativeModel("gemini-1.5-pro") # 或使用 gemini-2.0-flash-exp

model = init_ai()

# --- 2. SESSION STATE ---
if 'current_data' not in st.session_state:
    # 預設數據，實際應用可由 get_initial_leads 產生
    st.session_state.current_data = [
        {"component": "LDR", "center": [500, 500], "legs": [[480, 480], [520, 520]]}
    ]
if 'analysis_report' not in st.session_state: st.session_state.analysis_report = None

# --- 3. 核心功能：繪製藍色隔離線與標註 ---
def process_image_with_logic(base_img, data):
    img = base_img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    inventory_text = ""
    # 1. 畫零件引線與孔位
    for i, item in enumerate(data):
        cy, cx = item['center']
        comp = item.get('component', f'Part_{i}')
        inventory_text += f"- {comp}: "
        for j, leg in enumerate(item['legs']):
            ly, lx = leg
            # 橘色引線 (Orange Line)
            draw.line([(cx*w/1000, cy*h/1000), (lx*w/1000, ly*h/1000)], fill=(255, 165, 0, 200), width=15)
            # 青色孔位點 (Cyan Dot)
            draw.ellipse([(lx*w/1000-12, ly*h/1000-12), (lx*w/1000+12, ly*h/1000+12)], fill=(0, 255, 255, 255))
            
            side = "LEFT (a-e)" if lx < 500 else "RIGHT (f-j)"
            inventory_text += f"Leg{j+1}[{side},y:{ly},x:{lx}]; "
        inventory_text += "\n"

    # 2. 畫藍色中央隔離線 (Blue Middle Gap)
    middle_x = w // 2
    draw.line([(middle_x, 0), (middle_x, h)], fill=(0, 0, 255, 180), width=25)
    
    # 3. 合併
    combined = Image.alpha_composite(img, overlay).convert("RGB")
    return combined, inventory_text

# --- 4. UI LAYOUT ---
st.title("🧠 AI 電路老師：中央隔離線強化版")

with st.sidebar:
    st.header("設置")
    student_id = st.text_input("學生編號", "S001")
    task_id = st.selectbox("任務", ["4b (LDR Control)", "1a (LED Basic)"])
    if st.button("🔄 重置座標"):
        st.session_state.current_data = [{"component": "LDR", "center": [500, 500], "legs": [[480, 480], [520, 520]]}]
        st.rerun()

img_file = st.camera_input("拍照並開始調校")

if img_file and student_id:
    raw_img = Image.open(img_file)
    
    col_left, col_right = st.columns([0.4, 0.6])
    
    with col_left:
        st.subheader("🛠️ 座標精確調校")
        for i, item in enumerate(st.session_state.current_data):
            with st.expander(f"零件 {i+1}: {item['component']}", expanded=True):
                # 中心點 (不影響 AI 判斷，但影響橘色線視覺)
                item['center'][1] = st.slider(f"中心 X {i}", 0, 1000, item['center'][1])
                item['center'][0] = st.slider(f"中心 Y {i}", 0, 1000, item['center'][0])
                
                # 引腳 (AI 判斷的核心)
                for j, leg in enumerate(item['legs']):
                    st.markdown(f"**引腳 {j+1} (Cyan Dot Ground Truth)**")
                    leg[1] = st.slider(f"引腳{j+1} X {i}", 0, 1000, leg[1])
                    leg[0] = st.slider(f"引腳{j+1} Y {i}", 0, 1000, leg[0])

        if st.button("✅ 提交 AI 分析", type="primary", use_container_width=True):
            combined_img, inv_text = process_image_with_logic(raw_img, st.session_state.current_data)
            
            prompt = f"""
            CRITICAL: Look at the BLUE LINE in the middle. 
            - LEFT of blue: rows a, b, c, d, e.
            - RIGHT of blue: rows f, g, h, i, j.
            
            Inventory: {inv_text}
            
            Task: {task_id}.
            Analyze if the CYAN DOTS correctly form the circuit loop according to schematic.
            
            Format:
            1. RESULT: [✅ CORRECT] or [❌ INCORRECT]
            2. ANALYSIS: Max 50 words.
            3. SOCRATIC QUESTIONS: Guided hints.
            """
            
            # 轉換為 Vertex AI 圖像格式
            buf = io.BytesIO()
            combined_img.save(buf, format="JPEG")
            vertex_img = VertexImage.from_bytes(buf.getvalue())
            
            with st.spinner("AI 正在根據藍色隔離線進行邏輯判斷..."):
                response = model.generate_content([vertex_img, prompt])
                st.session_state.analysis_report = response.text

    with col_right:
        st.subheader("🖼️ 標註預覽")
        preview_img, _ = process_image_with_logic(raw_img, st.session_state.current_data)
        st.image(preview_img, use_container_width=True, caption="藍色粗線代表麵包板中央凹槽")
        
        if st.session_state.analysis_report:
            st.markdown("---")
            st.subheader("📝 AI 老師回饋")
            res = st.session_state.analysis_report
            if "[✅ CORRECT]" in res.upper():
                st.success(res)
            else:
                st.error(res)
