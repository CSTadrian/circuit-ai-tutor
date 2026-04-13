import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
import io
import math
from streamlit_image_coordinates import streamlit_image_coordinates

# AI & Google Auth Imports (與你原本代碼一致)
import vertexai
from vertexai.generative_models import GenerativeModel, Image as VertexImage

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="智能電路導航 Alpha", layout="wide", page_icon="💡")

@st.cache_resource
def init_ai():
    # 請在 Secrets 中設定 GCP Service Account JSON
    try:
        creds_info = st.secrets["gcp_service_account"]
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(creds_info)
        vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=creds)
        return GenerativeModel("gemini-1.5-pro")
    except Exception as e:
        st.error(f"AI 初始化失敗 (請檢查 Secrets): {e}")
        return None

model = init_ai()

# --- 2. 核心數據邏輯 ---
if 'component_data' not in st.session_state:
    # Normalized (0-1000) 座標系統，學生可調校
    st.session_state.component_data = [
        {"id": 1, "component": "LDR (光敏電阻)", "center": [420, 180], "legs": [[450, 200], [450, 160]]},
        {"id": 2, "component": "LED (發光二極管)", "center": [700, 260], "legs": [[750, 280], [750, 240]]}
    ]
if 'selected_comp_id' not in st.session_state: st.session_state.selected_comp_id = None
if 'analysis_report' not in st.session_state: st.session_state.analysis_report = None

def snap_to_grid(value, interval=20):
    """將座標吸附到最接近的麵包板孔位 ( Normalized 座標 )"""
    return round(value / interval) * interval

# --- 3. 繪圖核心函數 (解決引線與組件對齊問題) ---
def draw_smart_overlay(base_img, data, show_flow=False):
    # 建立一個與原圖一樣大小的透明圖層
    img = base_img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    
    # 教學層：麵包板內部導軌預覽 (教學 P4-S3 孔位連接)
    for row_y in range(100, 950, 40):
        # 左側 a-e，Normalized Y 座標
        d.line([(80*w/1000, row_y*h/1000), (440*w/1000, row_y*h/1000)], fill=(0, 255, 0, 30), width=5)
        # 右側 f-j，Normalized Y 座標
        d.line([(560*w/1000, row_y*h/1000), (920*w/1000, row_y*h/1000)], fill=(0, 255, 0, 30), width=5)

    for item in data:
        # 組件中心點 (Cy, Cx) - 學生可調校
        cy, cx = item['center']
        comp_center_p = (cx * w / 1000, cy * h / 1000)
        
        # 視覺輔助：在組件中心畫一個紅色十字架，幫助學生對準相片零件
        d.line([comp_center_p[0]-15, comp_center_p[1], comp_center_p[0]+15, comp_center_p[1]], fill="red", width=3)
        d.line([comp_center_p[0], comp_center_p[1]-15, comp_center_p[0], comp_center_p[1]+15], fill="red", width=3)

        for j, leg in enumerate(item['legs']):
            # 引腳位置 (Ly, Lx) - 滑桿調整，加上 Snap 效果
            ly, lx = snap_to_grid(leg[0]), snap_to_grid(leg[1])
            comp_pin_p = (lx * w / 1000, ly * h / 1000)
            
            # --- 核心優化：橘色引線由紅十字中心 (start_p) 緊隨畫到青色孔位 (end_p) ---
            start_p = comp_center_p # 紅十字中心
            end_p = comp_pin_p     # 青色孔位
            
            # 1. 畫出橘色引線
            d.line([start_p, end_p], fill=(255, 130, 0, 200), width=12)
            
            # 2. 畫出青色孔位指示 (學生調整後的 Ground Truth)
            d.ellipse([end_p[0]-15, end_p[1]-15, end_p[0]+15, end_p[1]+15], fill=(0, 255, 255, 255))
            
            # 3. 視覺輔助：加上腳位編號 (P1, P2) 幫助 P4 學生
            d.text((end_p[0]+18, end_p[1]-10), f"P{j+1}", fill="white", stroke_fill="black", stroke_width=2)
            
            # 如果 AI 分析成功，繪製「電流流動」綠色能量點
            if show_flow:
                # 綠色能量脈衝
                d.ellipse([end_p[0]-8, end_p[1]-8, end_p[0]+8, end_p[1]+8], fill=(0, 255, 0, 255))
    
    return Image.alpha_composite(img, overlay).convert("RGB")

# --- 4. Streamlit UI 佈局 (廣東話對應 P4-S3) ---
st.title("💡 Circuit Explorer 智慧電路小導航 Alpha")

# 側邊欄：原理圖參考與資訊
with st.sidebar:
    st.header("👤 學生資訊")
    student_id = st.text_input("學生編號", placeholder="例如: 2026_01")
    
    st.header("📖 Task 1：原理圖參考")
    try:
        ref_img = Image.open("Task1_ref.jpg")
        st.image(ref_img, use_container_width=True, caption="LDR 控制 LED 迴路")
    except:
        st.caption("(請將 Task1_ref.jpg 放到程式碼目錄下)")
        
    st.divider()
    if st.button("🔄 重設組件位置"):
        del st.session_state.component_data
        st.session_state.selected_comp_id = None
        st.rerun()

# 主區域
# --- Step 1: 獲取學生作品圖片 ---
tab_camera, tab_upload = st.tabs(["📷 即時影相 (Camera)", "📁 上傳檔案 (Upload)"])

uploaded_image_raw = None
with tab_camera:
    cam_file = st.camera_input("拍照並上傳")
    if cam_file: uploaded_image_raw = Image.open(cam_file)

with tab_upload:
    up_file = st.file_uploader("選擇手機中的圖片...", type=['jpg', 'jpeg', 'png'])
    if up_file: uploaded_image_raw = Image.open(up_file)

# --- Step 2: 互動調校區域 (核心 UI 改進) ---
if uploaded_image_raw and student_id:
    
    st.subheader("🛠️ 零件精確調教 (點擊圖中組件選擇)")
    col_ctrl, col_view = st.columns([0.4, 0.6])
    
    # 預覽圖區域
    with col_view:
        # 先繪製標註後的圖片
        marked_img = draw_smart_overlay(uploaded_image_raw, st.session_state.component_data)
        
        # 顯示互動圖片：允許學生點擊組件
        # streamlit-image-coordinates 會回傳 Normalized 座標 (0-1000 系統)
        st.caption("💡 點擊上圖中組件嘅 **紅十字中心** 來進行選擇：")
        clicked_coords = streamlit_image_coordinates(marked_img, key="image_interactive")
        
        # 點擊檢測邏輯
        if clicked_coords:
            cx, cy = clicked_coords['x'], clicked_coords['y']
            # 計算點擊點與哪個組件中心最近
            min_dist = float('inf')
            found_comp = None
            for item in st.session_state.component_data:
                # 零件中心數據 (Cy, Cx)
                dist = math.sqrt((cx - item['center'][1])**2 + (cy - item['center'][0])**2)
                if dist < 60 and dist < min_dist: # 增加一個點擊容差半徑
                    min_dist = dist
                    found_comp = item
            
            # 如果點擊到零件，儲存其 ID 到 Session State
            if found_comp:
                st.session_state.selected_comp_id = found_comp['id']
                # 強制重新執行，以更新左側 Slider 顯示
                st.rerun()
                
    # 控制面板區域 (只顯示選定組件的 Slider)
    with col_ctrl:
        st.markdown(f"**👤 學生：** `{student_id}` | **Task:** `1 (LDR)`")
        
        selected_id = st.session_state.selected_comp_id
        selected_index = next((i for i, item in enumerate(st.session_state.component_data) if item['id'] == selected_id), None)
        
        if selected_index is not None:
            comp_data = st.session_state.component_data[selected_index]
            icon = "🔌" if "LDR" in comp_data['component'] else "💡"
            st.markdown(f"### <div style='background:#fcf3cf; padding:10px; border_radius:5px;'>⚙️ 正在編輯: {icon} {comp_data['component']}</div>", unsafe_allow_y=True)
            
            # --- 核心功能 1：橘色引線跟隨組件 ---
            # 當 Slider 郁動，數據更新 -> 重新繪圖 -> 橘色線重新連線 -> 引線追隨組件中心
            st.markdown("#### ✅ 引腳孔位調校 (青色點)")
            for j, leg in enumerate(comp_data['legs']):
                st.write(f"**引腳 {j+1} (Normalized 座標)**")
                l_x = st.slider(f"腳 {j+1} 左右 ↔️", 0, 1000, leg[1], key=f"lx_{comp_data['id']}_{j}")
                l_y = st.slider(f"腳 {j+1} 上下 ↕️", 0, 1000, leg[0], key=f"ly_{comp_data['id']}_{j}")
                
                # 更新數據到 Session State
                st.session_state.component_data[selected_index]['legs'][j] = [l_y, l_x]
        else:
            st.info("💡 請在右側圖片中，**點擊組件嘅「紅十字」中心**，開始調教引腳。")

        st.divider()
        analyze_btn = st.button("🚀 CHECK MY CIRCUIT", button_style='success', layout={'width': '100%', 'height': '50px'})

elif uploaded_image_raw and not student_id:
    st.warning("Please enter your Student ID in the sidebar first!")

st.divider()
st.caption("ECCC AI Circuit Tutor | Socratic Scaffolding | HK v2.5")
