# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
from PIL import Image as PILImage, ImageDraw
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & AI CONFIG ---
st.set_page_config(page_title="AI Circuit Tutor & Simulator", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Initialize Vertex AI Client
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    client = genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found!")
    st.stop()

# --- 2. TASK & DATA SETUP ---
TASK_OPTIONS = [
    "1) turn on LED", "2) use a button", "3a) button -- series", 
    "3b) button -- parallel", "3c) button -- NOT", "4a) bright-activated LDR", 
    "4b) dark-activated LDR", "5) light up parallel LED", "6a) capacitor and VR - v1", 
    "6b) capacitor and VR - v2", "7) using one slide-switch", "8) using Two slide-switch", 
    "9) diode", "10) NPN transistor - v1", "11) NPN transistor - v2", 
    "12) IR emitter & detector", "13) 555 IC", "14) 74LS90 IC", "15) IR with 74LS90"
]

def draw_coordinate_grid(image):
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for i in range(0, 1001, 100):
        x_px, y_px = i * w / 1000, i * h / 1000
        draw.line([(x_px, 0), (x_px, 15)], fill=(255, 0, 0), width=2)
        draw.line([(0, y_px), (15, y_px)], fill=(255, 0, 0), width=2)
        draw.text((x_px + 2, 0), str(i), fill=(255, 255, 255))
        draw.text((2, y_px), str(i), fill=(255, 255, 255))
    return image

# --- 3. UI LAYOUT ---
col_side, col_main = st.columns([1, 3])

with col_side:
    st.header("📋 Task")
    selected_task = st.selectbox("Select Project:", TASK_OPTIONS)
    task_id = selected_task.split(")")[0].strip()
    
    # Load Semantic Image from local data2 folder
    img_path = f"data2/circuit-{task_id}.jpg"
    if os.path.exists(img_path):
        ref_img = PILImage.open(img_path)
        st.image(draw_coordinate_grid(ref_img.copy()), caption="Goal Semantic Netlist")
    else:
        st.warning(f"Reference data2/circuit-{task_id}.jpg missing.")
        ref_img = None

    # AI BUTTON
    if st.button("🤖 AI Tutor: Check Circuit", type="primary", use_container_width=True):
        if "last_netlist" in st.session_state and ref_img:
            with st.spinner("Analyzing connections..."):
                prompt = f"""
                You are a STEM tutor. Compare the student's digital breadboard netlist to the semantic image provided.
                Task: {selected_task}
                Student's Netlist: {json.dumps(st.session_state.last_netlist)}
                
                Identify errors in polarity, missing wires, or incorrect pin placement. 
                Be encouraging and guide them to the solution without just giving the answer.
                """
                response = client.models.generate_content(
                    model=MODEL_ID, contents=[ref_img, prompt],
                    config=types.GenerateContentConfig(temperature=0.2)
                )
                st.info(response.text)
        else:
            st.error("Build something on the board first!")

with col_main:
    # --- JAVASCRIPT SIMULATOR WITH DATA EXPORT ---
    # We add a function to "Post" the netlist to Streamlit's parent window
    import streamlit.components.v1 as components
    
    # [SVG Assets logic from previous code here...]
    
    sim_html = f"""
    <div id="canvas"> ... [Previous Simulator HTML] ... </div>
    <script>
        // NEW: Function to send data back to Python
        function exportToAI() {{
            const data = {{
                components: comps.map(c => ({{type: c.type, pins: c.connectedTracks, rot: c.rot}})),
                wires: wires.map(w => ({{from: getTrack(w.start), to: getTrack(w.end)}}))
            }};
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: data
            }}, '*');
        }}

        // Call exportToAI whenever the circuit changes
        // (Inside toggleSim, renderWires, and updateHoles)
    </script>
    """
    # Use a custom component or a simple message listener wrapper
    st.subheader("Interactive Workspace")
    # Note: To fully receive the 'postMessage' in Streamlit, 
    # it's best to use the 'streamlit-javascript' or a custom component wrapper.
    # For now, we simulate the logic:
    st.components.v1.html(sim_html, height=800)
