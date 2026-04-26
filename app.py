# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from PIL import Image as PILImage, ImageDraw

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="AI Circuit Tutor (Series Flexibility)", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Authentication
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    PROJECT_ID = creds_info["project_id"]

    client = genai.Client(
        vertexai=True, 
        project=PROJECT_ID, 
        location="global", 
        credentials=credentials
    )
else:
    st.error("GCP Service Account secrets not found! Check your Streamlit Cloud settings.")
    st.stop()

# --- 2. SESSION STATE MANAGEMENT ---
if "step" not in st.session_state: st.session_state.step = 1
if "components_df" not in st.session_state: st.session_state.components_df = pd.DataFrame()
if "raw_student_img" not in st.session_state: st.session_state.raw_student_img = None
if "raw_schematic_img" not in st.session_state: st.session_state.raw_schematic_img = None

def reset_flow():
    st.session_state.step = 1
    st.session_state.components_df = pd.DataFrame()

# --- 3. UI: SIDEBAR SETUP ---
st.title("🔌 AI Circuit Debugger: Series Logic")

with st.sidebar:
    st.header("Setup & Inputs")
    task_id = st.text_input("Task/Experiment Name", "Task 4b")
    feedback_mode = st.radio("Feedback Mode", ["Direct Answer", "Socratic Scaffolding"])
    
    st.divider()
    st.subheader("1. Reference Schematic")
    schematic_file = st.file_uploader("Upload Schematic", type=["jpg", "png", "jpeg"], on_change=reset_flow)
    
    st.subheader("2. Student Breadboard")
    student_file = st.file_uploader("Upload Student Circuit", type=["jpg", "png", "jpeg"], on_change=reset_flow)

    if st.button("Reset Process"):
        reset_flow()
        st.rerun()

# Process uploaded images
if schematic_file and student_file:
    st.session_state.raw_schematic_img = PILImage.open(schematic_file).convert("RGB")
    st.session_state.raw_student_img = PILImage.open(student_file).convert("RGB")

    # --- MAIN FLOW ---
    if st.session_state.step == 1:
        col1, col2 = st.columns(2)
        with col1:
            st.image(st.session_state.raw_schematic_img, caption="Reference Schematic", use_container_width=True)
        with col2:
            st.image(st.session_state.raw_student_img, caption="Student Breadboard", use_container_width=True)

        if st.button("🔍 Step 1: AI Lead Detection", type="primary"):
            with st.spinner("AI is analyzing components and metal legs..."):
                prompt_seg = """
                Identify each electronic component (e.g., LDR, Resistor, Transistor, Button, LED, Switch).
                For each, return:
                - 'center': [y, x] coordinate of the component body (scale 0-1000).
                - 'legs': A list of [y, x] coordinates for every metal leg/wire end (scale 0-1000).
                """
                
                try:
                    resp = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[st.session_state.raw_student_img, prompt_seg],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema={
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
                        )
                    )
                    
                    records = []
                    parsed_data = resp.parsed if hasattr(resp, 'parsed') else json.loads(resp.text)
                    
                    for comp_idx, item in enumerate(parsed_data):
                        name = item.get('name', f"Component_{comp_idx}")
                        cy, cx = item.get('center', [500, 500])
                        for leg_idx, (ly, lx) in enumerate(item.get('legs', [])):
                            records.append({
                                "Component": f"{name} (Leg {leg_idx+1})",
                                "Center_X": cx, "Center_Y": cy,
                                "Leg_X": lx, "Leg_Y": ly
                            })
                    
                    st.session_state.components_df = pd.DataFrame(records)
                    st.session_state.step = 2
                    st.rerun()

                except Exception as e:
                    st.error(f"Detection failed: {e}")

    # --- STEP 2: EDITING WITH SLIDERS ---
    elif st.session_state.step == 2:
        st.subheader("⚙️ Step 2: Fine-Tune Component Leads")
        st.info("Align the orange markers with the breadboard holes. The AI will use these exact coordinates for its logic.")

        edit_col, img_col = st.columns([1, 1.5])
        updated_data = []
        
        with edit_col:
            st.write("### Adjust Coordinates")
            for i, row in st.session_state.components_df.iterrows():
                with st.expander(f"📍 {row['Component']}", expanded=False):
                    new_lx = st.slider(f"Horizontal (X)", 0, 1000, int(row["Leg_X"]), key=f"x_{i}")
                    new_ly = st.slider(f"Vertical (Y)", 0, 1000, int(row["Leg_Y"]), key=f"y_{i}")
                    
                    updated_data.append({
                        "Component": row["Component"],
                        "Center_X": row["Center_X"],
                        "Center_Y": row["Center_Y"],
                        "Leg_X": new_lx,
                        "Leg_Y": new_ly
                    })
            
            edited_df = pd.DataFrame(updated_data)
        
        with img_col:
            display_img = st.session_state.raw_student_img.copy()
            draw = ImageDraw.Draw(display_img)
            w, h = display_img.size
            
            for index, row in edited_df.iterrows():
                try:
                    cx, cy = int(row["Center_X"]), int(row["Center_Y"])
                    lx, ly = int(row["Leg_X"]), int(row["Leg_Y"])
                    start_pt = (cx * w / 1000, cy * h / 1000)
                    end_pt = (lx * w / 1000, ly * h / 1000)
                    draw.line([start_pt, end_pt], fill="orange", width=4)
                    draw.ellipse([end_pt[0]-5, end_pt[1]-5, end_pt[0]+5, end_pt[1]+5], fill="yellow", outline="orange")
                except Exception: pass

            st.image(display_img, caption="Live Updated Breadboard", use_container_width=True)

        if st.button("✅ Confirm Leads & Analyze Circuit", type="primary"):
            st.session_state.components_df = edited_df
            st.session_state.annotated_img = display_img
            st.session_state.step = 3
            st.rerun()

    # --- STEP 3: TOPOLOGICAL PEDAGOGICAL ANALYSIS ---
    elif st.session_state.step == 3:
        st.subheader("🧠 Step 3: Pedagogical Evaluation")
        st.image(st.session_state.annotated_img, width=600, caption="Final Evaluated Image")
        
        coord_summary = st.session_state.components_df[["Component", "Leg_X", "Leg_Y"]].to_string(index=False)

        with st.spinner("Analyzing circuit topology..."):
            # SYSTEM PROMPT: Instructions for series flexibility
            context_header = f"""
            SYSTEM DATA (GROUND TRUTH):
            Use these precise coordinates for logic:
            {coord_summary}
            
            ENGINEERING PRINCIPLES:
            1. SERIES FLEXIBILITY: In a series circuit, the order of components does not matter (e.g., Battery-Resistor-LED is identical to Battery-LED-Resistor). 
               Do NOT mark the circuit as incorrect if the sequence differs from the schematic, provided the total series loop is correct.
            2. BREADBOARD CONNECTION: Rows are horizontal strips. Components in the same row are electrically connected.
            3. NO SPOILERS: If using Socratic mode, do not explain the pins of a slide-switch.
            """

            if feedback_mode == "Direct Answer":
                analysis_prompt = context_header + f"""
                Compare the Schematic (Image 1) with the Breadboard (Image 2).
                This is {task_id}.
                Diagnosis: Check if a continuous series loop exists. Confirm if polarity (LED) is correct. 
                If the order is swapped but the loop is closed and components are correct, mark it as CORRECT.
                """
            else:
                analysis_prompt = context_header + f"""
                Provide SOCRATIC SCAFFOLDING. If the student has swapped component order but the circuit works, 
                congratulate them and ask if they know why the order doesn't matter in series.
                If it's truly broken (short circuit/open loop), ask a guided question.
                """

            try:
                final_response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[
                        st.session_state.raw_schematic_img, 
                        st.session_state.annotated_img, 
                        analysis_prompt
                    ],
                    config=types.GenerateContentConfig(temperature=0.0)
                )
                
                st.success("Analysis Complete")
                st.markdown(f"**{feedback_mode} Feedback:**")
                st.write(final_response.text)
                
            except Exception as e:
                st.error(f"Analysis failed: {e}")



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
