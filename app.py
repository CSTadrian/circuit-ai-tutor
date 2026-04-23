import streamlit as st
import pandas as pd
import PIL.Image
import os
import time
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. CONFIG & AUTH ---
st.set_page_config(page_title="Circuit AI Debugger", layout="wide")
st.title("🚀 3.1-PRO Circuit Analysis")

# Load credentials from Streamlit Secrets
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    PROJECT_ID = st.secrets["project_id"]
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global", credentials=credentials)
else:
    st.error("Please configure Google Cloud Secrets in Streamlit!")
    st.stop()

# Paths
BASE_PATH = "data" 
CSV_LOG_PATH = os.path.join(BASE_PATH, "circuit_log_0321.csv")
CSV_PRO_PATH = "ai_debug_results.csv"

# --- 2. DATA LOADING ---
if os.path.exists(CSV_LOG_PATH):
    working_df = pd.read_csv(CSV_LOG_PATH)
    st.write(f"Loaded {len(working_df)} photos from log.")
else:
    st.error(f"Could not find {CSV_LOG_PATH}")
    st.stop()

# --- 3. PROCESSING LOOP ---
if st.button("Start Analysis"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # LOAD EXISTING CSV (to allow appending/updating)
    if os.path.exists(CSV_PRO_PATH):
        master_df = pd.read_csv(CSV_PRO_PATH)
        st.info(f"Existing results found. Appending/Updating {CSV_PRO_PATH}...")
    else:
        master_df = pd.DataFrame()

    for idx, row in working_df.iterrows():
        img_name = row['Filename']
        task_id = img_name.split('_')[0].replace('Task', '').strip()
        img_path = os.path.join(BASE_PATH, "0321", img_name)
        ref_path = os.path.join(BASE_PATH, "data2", f"circuit-{task_id}.jpg")

        status_text.text(f"Processing {img_name} ({idx+1}/{len(working_df)})...")

        try:
            student_img = PIL.Image.open(img_path)
            ref_img = PIL.Image.open(ref_path)
        except Exception as e:
            st.warning(f"Skip {img_name}: {e}")
            continue

        prompt = f"""
            Compare Student Breadboard (Image 2) to Schematic (Image 1) for Task {task_id}.
            RULES:
            - Red rail = Positive (+), Blue rail = Negative (-).
            - Component order in series is CORRECT.
            OUTPUT FORMAT (Strict):
            1) STATUS: [Correct ✅ or Wrong ❌]
            2) WHY: [Concise reason, max 50 words. Complete the sentence.]
            3) SOCRATIC HINTS: [L1, L2, L3]
        """

        ai_text, duration = "ERROR", 0
        try:
            start_time = time.time()
            response = client.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=[ref_img, student_img, prompt],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(include_thoughts=True),
                    temperature=0.0,
                    max_output_tokens=1000
                )
            )
            duration = time.time() - start_time
            ai_text = response.text.strip()
        except Exception as e:
            ai_text = f"AI Error: {str(e)}"

        # --- UI DISPLAY ---
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(student_img, caption=f"Student: {img_name}", use_container_width=True)
        
        with col2:
            is_correct = "✅" in ai_text or "CORRECT" in ai_text.upper()
            if is_correct:
                st.success(ai_text)
            else:
                st.error(ai_text)
            st.caption(f"⏱️ Latency: {duration:.2f}s")

        # --- SAVE DATA (APPEND/UPDATE LOGIC) ---
        new_row_data = row.to_dict()
        new_row_data.update({
            "ai_output": ai_text, 
            "latency": f"{duration:.2f}s", 
            "model": "3.1-pro"
        })
        
        # If the file already exists in our master dataframe, update it. Otherwise, concat.
        if not master_df.empty and img_name in master_df['Filename'].values:
            # Locate the index of the existing filename and update that specific row
            idx_to_update = master_df.index[master_df['Filename'] == img_name].tolist()[0]
            for key, value in new_row_data.items():
                master_df.at[idx_to_update, key] = value
        else:
            # Append new record
            master_df = pd.concat([master_df, pd.DataFrame([new_row_data])], ignore_index=True)
        
        # Save to CSV after every image to prevent data loss
        master_df.to_csv(CSV_PRO_PATH, index=False)
        progress_bar.progress((idx + 1) / len(working_df))

    st.balloons()
    st.success(f"Processing complete. Data saved to {CSV_PRO_PATH}")
    
    # Allow user to download the final state
    st.download_button(
        label="Download Results CSV",
        data=master_df.to_csv(index=False),
        file_name=CSV_PRO_PATH,
        mime='text/csv'
    )
    
# import streamlit as st
# import pandas as pd
# import json
# import os
# import io
# from PIL import Image, ImageDraw

# # AI & Google Auth Imports
# import vertexai
# from vertexai.generative_models import GenerativeModel, Image as VertexImage
# from google.oauth2 import service_account

# # --- 1. CONFIG ---
# st.set_page_config(page_title="AI Circuit Socratic Tutor", layout="wide", page_icon="🔌")

# @st.cache_resource
# def init_ai():
#     creds_info = st.secrets["gcp_service_account"]
#     creds = service_account.Credentials.from_service_account_info(creds_info)
#     vertexai.init(project=creds_info["project_id"], location="us-central1", credentials=creds)
#     return GenerativeModel("gemini-1.5-pro")

# model = init_ai()

# # --- 2. SESSION STATE ---
# if 'current_data' not in st.session_state:
#     st.session_state.current_data = [
#         {"id": 0, "component": "LDR (光敏電阻)", "center": [500, 400], "legs": [[550, 420], [550, 380]]},
#         {"id": 1, "component": "LED (發光二極管)", "center": [300, 300], "legs": [[350, 320], [350, 280]]}
#     ]
# if 'selected_index' not in st.session_state:
#     st.session_state.selected_index = None  # 初始不選擇任何零件

# # --- 3. 核心標註與邏輯函數 ---
# def process_and_draw(base_img, data):
#     img = base_img.convert("RGBA")
#     w, h = img.size
#     overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
#     draw = ImageDraw.Draw(overlay)
    
#     inventory_text = ""
#     for i, item in enumerate(data):
#         cy, cx = item['center']
#         comp = item.get('component', f'Part_{i}')
        
#         # 標註：選中的零件顏色加深或加框
#         is_selected = (st.session_state.selected_index == i)
#         line_color = (255, 165, 0, 255) if is_selected else (255, 165, 0, 100)
#         dot_color = (0, 255, 255, 255) if is_selected else (0, 255, 255, 100)

#         inventory_text += f"- {comp}: "
#         for j, leg in enumerate(item['legs']):
#             ly, lx = leg
#             # 畫橘色引線 (由零件中心出發)
#             draw.line([(cx*w/1000, cy*h/1000), (lx*w/1000, ly*h/1000)], fill=line_color, width=15 if is_selected else 8)
#             # 畫青色孔位 (Cyan Ground Truth)
#             draw.ellipse([(lx*w/1000-15, ly*h/1000-15), (lx*w/1000+15, ly*h/1000+15)], fill=dot_color, outline="white")
            
#             side = "LEFT" if lx < 500 else "RIGHT"
#             inventory_text += f"Pin{j+1}[{side}, y:{ly}, x:{lx}]; "
#         inventory_text += "\n"

#     # 中央隔離線
#     mid_x = w // 2
#     draw.line([(mid_x, 0), (mid_x, h)], fill=(0, 0, 255, 150), width=20)
    
#     combined = Image.alpha_composite(img, overlay).convert("RGB")
#     return combined, inventory_text

# # --- 4. UI 介面佈局 ---
# st.title("🔌 AI 電路精密診斷站")

# with st.sidebar:
#     st.header("📋 學生資訊")
#     student_id = st.text_input("學生編號", placeholder="例如: 2026001")
#     task_type = st.selectbox("電路任務", ["Task 4b: LDR 控制電路", "Task 1: LED 基本迴路"])
#     if st.button("🔄 重置所有座標"):
#         st.session_state.current_data = [
#             {"id": 0, "component": "LDR (光敏電阻)", "center": [500, 400], "legs": [[550, 420], [550, 380]]},
#             {"id": 1, "component": "LED (發光二極管)", "center": [300, 300], "legs": [[350, 320], [350, 280]]}
#         ]
#         st.session_state.selected_index = None
#         st.rerun()

# # --- 5. 多功能上傳區 ---
# st.subheader("第一步：獲取圖片")
# tab_camera, tab_upload = st.tabs(["📷 即時影相", "📁 上傳檔案"])
# raw_image = None
# with tab_camera:
#     cam_file = st.camera_input("拍照")
#     if cam_file: raw_image = Image.open(cam_file)
# with tab_upload:
#     up_file = st.file_uploader("選擇檔案", type=['jpg', 'jpeg', 'png'])
#     if up_file: raw_image = Image.open(up_file)

# # --- 6. 調校與分析區 (核心 UI 改變) ---
# if raw_image and student_id:
#     col_ctrl, col_view = st.columns([0.4, 0.6])
    
#     with col_ctrl:
#         st.subheader("🛠️ 零件選擇與調校")
        
#         # --- A. 零件選擇區 ---
#         st.write("1. 點擊按鈕選擇你要調整的零件：")
#         btn_cols = st.columns(len(st.session_state.current_data))
#         for idx, item in enumerate(st.session_state.current_data):
#             if btn_cols[idx].button(item['component'], use_container_width=True, 
#                                     type="primary" if st.session_state.selected_index == idx else "secondary"):
#                 st.session_state.selected_index = idx
#                 st.rerun()
        
#         st.divider()

#         # --- B. 動態 Slider 顯示區 ---
#         if st.session_state.selected_index is not None:
#             idx = st.session_state.selected_index
#             target = st.session_state.current_data[idx]
            
#             st.markdown(f"### ⚙️ 正在調校：`{target['component']}`")
            
#             # 調整中心位置 (紅十字/零件主體)
#             with st.container(border=True):
#                 st.write("**📍 零件中心位置**")
#                 target['center'][1] = st.slider(f"中心 X (左右) ##cx{idx}", 0, 1000, target['center'][1])
#                 target['center'][0] = st.slider(f"中心 Y (上下) ##cy{idx}", 0, 1000, target['center'][0])

#             # 調整引腳孔位
#             for j, leg in enumerate(target['legs']):
#                 with st.container(border=True):
#                     st.write(f"**🔵 引腳 {j+1} 插孔位置**")
#                     leg[1] = st.slider(f"引腳{j+1} X ##lx{idx}{j}", 0, 1000, leg[1])
#                     leg[0] = st.slider(f"引腳{j+1} Y ##ly{idx}{j}", 0, 1000, leg[0])
            
#             if st.button("✅ 完成此零件調校", use_container_width=True):
#                 st.session_state.selected_index = None
#                 st.rerun()
#         else:
#             st.info("💡 請點擊上方按鈕選擇一個零件進行調校。")

#         # --- C. 分析提交 ---
#         st.divider()
#         if st.button("🚀 提交 AI 全局分析", type="primary", use_container_width=True):
#             final_img, inv_text = process_and_draw(raw_image, st.session_state.current_data)
#             buf = io.BytesIO()
#             final_img.save(buf, format="JPEG")
#             with st.spinner("AI 老師分析中..."):
#                 prompt = f"Analyze circuit topology based on verification: {inv_text} Task: {task_type}"
#                 response = model.generate_content([VertexImage.from_bytes(buf.getvalue()), prompt])
#                 st.session_state.analysis_report = response.text

#     with col_view:
#         st.subheader("🖼️ 即時標註預覽")
#         preview_img, _ = process_and_draw(raw_image, st.session_state.current_data)
#         st.image(preview_img, use_container_width=True, caption="橘色實線表示當前選中的零件")
        
#         if st.session_state.get('analysis_report'):
#             st.success("AI 診斷報告已生成")
#             st.markdown(st.session_state.analysis_report)

# st.divider()
# st.caption("ECCC AI Research 2026 | Selective UI v4.0")
