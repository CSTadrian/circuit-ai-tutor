import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta, timezone
from PIL import Image as PILImage
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
SAVE_FILENAME = "ai_debug_streamlit.csv"

if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    # Ensure scopes are explicitly defined for Vertex AI
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    PROJECT_ID = creds_info["project_id"]
    vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

# 🟢 UPDATE: Moving to 3.0-pro
model = GenerativeModel("gemini-3.0-pro-preview")

st.set_page_config(page_title="AI Circuit Tutor v3.0", layout="centered")

# --- 2. SESSION STATE MANAGEMENT ---
if 'socratic_round' not in st.session_state:
    st.session_state.socratic_round = 0
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = ""
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = {}

# --- 3. UI LAYOUT ---
st.title("🔌 AI Circuit Diagnostic Station (3.0 Pro)")

with st.sidebar:
    st.header("Student Setup")
    student_number = st.text_input("Student Number", placeholder="e.g. 42")
    task_number = st.number_input("Task Number", min_value=1, max_value=10, value=1)
    option_choice = st.radio("Debug Mode", ["1: Direct Debug", "2: Socratic Debug"])
    
    if st.button("Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 4. IMAGE CAPTURE ---
img_file = st.camera_input("Capture your breadboard circuit")

# --- 5. CORE LOGIC ---
if img_file and student_number:
    base_folder = "data2"
    ref_image_name = f"circuit-{task_number}.jpg"
    ref_path = os.path.join(base_folder, ref_image_name)

    if not os.path.exists(ref_path):
        st.error(f"Reference image {ref_image_name} not found.")
    else:
        schematic_img_ai = Image.load_from_file(ref_path)
        student_img_bytes = img_file.getvalue()
        student_img_ai = Image.from_bytes(student_img_bytes)

        # --- MODE 1: DIRECT DEBUG ---
        if "1" in option_choice and not st.session_state.analysis_done:
            with st.spinner("Analyzing circuit..."):
                # 🟢 UPDATE: Added strict 50-word limit and completeness instruction
                prompt = f"""
                You are a Senior Electronic Systems Diagnostic Engineer. 
                Compare Student Breadboard (Image 2) to Schematic (Image 1).
                
                RULES:
                - Provide a COMPLETE diagnosis.
                - TOTAL word limit for 'error_analysis' is 50 words.
                - Ensure the last sentence is finished and the idea is whole.

                [OUTPUT FORMAT - JSON ONLY]
                {{
                "match_status": "CORRECT" or "INCORRECT",
                "error_analysis": "[Concise diagnosis, complete sentences, max 50 words]",
                "remediation_hints": "[Actionable fix]",
                "follow_up_QA": "Direct Analysis"
                }}
                """
                response = model.generate_content(
                    [prompt, schematic_img_ai, student_img_ai],
                    generation_config=GenerationConfig(response_mime_type="application/json", temperature=0.0)
                )
                st.session_state.current_analysis = json.loads(response.text)
                st.session_state.analysis_done = True

        # --- MODE 2: SOCRATIC DEBUG ---
        elif "2" in option_choice and not st.session_state.analysis_done:
            if st.session_state.socratic_round < 3:
                st.subheader(f"Socratic Round {st.session_state.socratic_round + 1} of 3")
                q_prompt = "Socratic Mode: Compare images. Ask ONE short guiding question to help student find the error. Do not give the answer."
                q_response = model.generate_content([q_prompt, schematic_img_ai, student_img_ai])
                ai_question = q_response.text
                st.info(f"**AI Question:** {ai_question}")

                with st.form(key=f"round_{st.session_state.socratic_round}"):
                    student_ans = st.text_input("Your Answer:")
                    if st.form_submit_button("Submit Answer") and student_ans:
                        st.session_state.chat_history += f"Q: {ai_question} | A: {student_ans}\n"
                        st.session_state.socratic_round += 1
                        st.rerun()
            else:
                with st.spinner("Finalizing analysis..."):
                    final_prompt = f"""
                    Provide final diagnosis after these Socratic rounds: {st.session_state.chat_history}.
                    Max 50 words for analysis. 
                    [OUTPUT FORMAT - JSON ONLY]
                    {{
                    "match_status": "CORRECT" or "INCORRECT",
                    "error_analysis": "[Final result, max 50 words]",
                    "remediation_hints": "[Remediation]",
                    "follow_up_QA": "{st.session_state.chat_history}"
                    }}
                    """
                    final_res = model.generate_content(
                        [final_prompt, schematic_img_ai, student_img_ai],
                        generation_config=GenerationConfig(response_mime_type="application/json")
                    )
                    st.session_state.current_analysis = json.loads(final_res.text)
                    st.session_state.analysis_done = True

# --- 6. DISPLAY RESULTS & APPENDING TO CSV ---
if st.session_state.analysis_done:
    data = st.session_state.current_analysis
    st.divider()
    status_emoji = "✅" if data['match_status'] == "CORRECT" else "❌"
    st.subheader(f"Result: {data['match_status']} {status_emoji}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Analysis**")
        st.write(data['error_analysis'])
    with col2:
        st.markdown("**Hint**")
        st.info(data['remediation_hints'])

    if st.button("Finalize and Save Entry"):
        now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
        
        new_row = {
            "Student_Number": student_number,
            "Timestamp_HKT": now_hkt.strftime('%Y-%m-%d %H:%M:%S'),
            "Task_ID": task_number,
            "Mode": option_choice,
            "Status": data['match_status'],
            "Analysis": data['error_analysis'],
            "History": data.get("follow_up_QA", "")
        }

        # 🟢 UPDATE: Appending to "ai_debug_streamlit.csv"
        if os.path.exists(SAVE_FILENAME):
            master_df = pd.read_csv(SAVE_FILENAME)
        else:
            master_df = pd.DataFrame()

        master_df = pd.concat([master_df, pd.DataFrame([new_row])], ignore_index=True)
        master_df.to_csv(SAVE_FILENAME, index=False)

        st.success(f"Entry saved to {SAVE_FILENAME}")
        st.balloons()
        st.download_button("Download Latest CSV", master_df.to_csv(index=False), SAVE_FILENAME, "text/csv")

 
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
