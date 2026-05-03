# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import os
from PIL import Image as PILImage, ImageDraw
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & AI CONFIG ---
st.set_page_config(page_title="Pro-STEM Precision Lab", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Initialize Vertex AI Client from Secrets
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    client = genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
else:
    st.error("GCP Service Account secrets not found! Please check your Streamlit secrets.")
    st.stop()

# --- 2. HELPER FUNCTIONS ---
def draw_coordinate_grid(image):
    """Draws the 0-1000 scale required for Gemini's spatial reasoning."""
    # FIX: Explicitly convert to RGB to avoid the TypeError on draw.line
    if image.mode != "RGB":
        image = image.convert("RGB")
        
    draw = ImageDraw.Draw(image)
    w, h = image.size
    
    line_color = (255, 0, 0) # Red
    for i in range(0, 1001, 100):
        x_px, y_px = i * w / 1000, i * h / 1000
        # Draw Ticks
        draw.line([(x_px, 0), (x_px, 15)], fill=line_color, width=2)
        draw.line([(0, y_px), (15, y_px)], fill=line_color, width=2)
        # Labels
        draw.text((x_px + 2, 2), str(i), fill=(255, 255, 255))
        draw.text((2, y_px + 2), str(i), fill=(255, 255, 255))
    return image

# --- 3. UI LAYOUT ---
TASK_OPTIONS = [
    "1) turn on LED", "2) use a button", "3a) button -- series", 
    "3b) button -- parallel", "3c) button -- NOT", "4a) bright-activated LDR", 
    "4b) dark-activated LDR", "5) light up parallel LED", "6a) capacitor and VR - v1", 
    "6b) capacitor and VR - v2", "7) using one slide-switch", "8) using Two slide-switch", 
    "9) diode", "10) NPN transistor - v1", "11) NPN transistor - v2", 
    "12) IR emitter & detector", "13) 555 IC", "14) 74LS90 IC", "15) IR with 74LS90"
]

col_side, col_main = st.columns([1, 3])

with col_side:
    st.header("📋 Task Goal")
    selected_task = st.selectbox("Current Project:", TASK_OPTIONS)
    
    # Load Semantic Image from local data2 folder
    task_id = selected_task.split(")")[0].strip()
    img_path = f"data2/circuit-{task_id}.jpg"
    
    if os.path.exists(img_path):
        ref_img = PILImage.open(img_path)
        ref_img_gridded = draw_coordinate_grid(ref_img.copy())
        st.image(ref_img_gridded, caption="Target Semantic Netlist", use_container_width=True)
    else:
        st.warning(f"Semantic image circuit-{task_id}.jpg not found in 'data2/'.")
        ref_img = None

    st.markdown("---")
    st.subheader("🤖 AI Tutor Analysis")
    
    # Bridge for simulator data
    netlist_input = st.text_area("Paste Netlist for Analysis", placeholder="Click 'Export Netlist' in the simulator, then paste here...", height=150)
    
    if st.button("Check My Circuit", type="primary", use_container_width=True):
        if not ref_img:
            st.error("No target image available for comparison.")
        elif not netlist_input:
            st.warning("Please export your work from the simulator first.")
        else:
            with st.spinner("Analyzing your connections..."):
                prompt = f"""
                You are an encouraging STEM research assistant tutor. 
                Compare the provided 'Semantic Goal' image to the student's digital netlist.
                
                TASK: {selected_task}
                STUDENT NETLIST: {netlist_input}
                
                Check for:
                1. Component Presence: Are all required parts on the board?
                2. Connection Accuracy: Do the track/row numbers match the semantic image?
                3. Polarity: Are polarized parts (LED, Battery) oriented correctly?
                
                Feedback Style: Constructive, scaffolding-based, and friendly.
                """
                
                try:
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[ref_img, prompt],
                        config=types.GenerateContentConfig(temperature=0.2)
                    )
                    st.info(response.text)
                except Exception as e:
                    st.error(f"AI Error: {e}")

with col_main:
    # --- SVG ASSETS & SIMULATOR ---
    # (Including your updated assets and simulation logic)
    ASSETS_JSON = json.dumps({
        "LED": {
            "OFF": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#822" opacity="0.9"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>',
            "ON": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#f00" filter="drop-shadow(0 0 8px red)"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>'
        },
        "RES_5BAND": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="5" y="9" width="70" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="25" y="4" width="3" height="12" fill="#8b4513"/><rect x="31" y="4" width="3" height="12" fill="#000"/><rect x="37" y="4" width="3" height="12" fill="#000"/><rect x="43" y="4" width="3" height="12" fill="#ff8c00"/><rect x="52" y="4" width="3" height="12" fill="#800080"/></svg>',
        "SWITCH": {
            "LEFT": '<svg width="60" height="24" viewBox="0 0 60 24"><rect x="10" y="12" width="2" height="12" fill="#aaa"/><rect x="30" y="12" width="2" height="12" fill="#aaa"/><rect x="50" y="12" width="2" height="12" fill="#aaa"/><rect x="5" y="0" width="50" height="16" rx="2" fill="#333"/><rect x="8" y="3" width="18" height="10" rx="2" fill="#ffffff" stroke="#aaa" stroke-width="1"/></svg>',
            "RIGHT": '<svg width="60" height="24" viewBox="0 0 60 24"><rect x="10" y="12" width="2" height="12" fill="#aaa"/><rect x="30" y="12" width="2" height="12" fill="#aaa"/><rect x="50" y="12" width="2" height="12" fill="#aaa"/><rect x="5" y="0" width="50" height="16" rx="2" fill="#333"/><rect x="34" y="3" width="18" height="10" rx="2" fill="#ffffff" stroke="#aaa" stroke-width="1"/></svg>'
        },
        "BATTERY": '<svg width="40" height="60" viewBox="0 0 40 60"><rect x="2" y="2" width="36" height="46" rx="4" fill="#333" stroke="#555"/><rect x="6" y="6" width="28" height="10" fill="#f1c40f"/><rect x="6" y="18" width="28" height="10" fill="#f1c40f"/><rect x="6" y="30" width="28" height="10" fill="#f1c40f"/><text x="11" y="40" fill="black" font-size="7" font-weight="bold">4.5V DC</text><rect x="10" y="48" width="2" height="12" fill="#ff4444"/><rect x="30" y="48" width="2" height="12" fill="#4444ff"/><text x="6" y="59" fill="white" font-size="9">+</text><text x="31" y="59" fill="white" font-size="9">-</text></svg>'
    })

    # Combined Simulator Script with Netlist Export Fix
    # (Full simulator HTML content is injected here)
    st.components.v1.html(f"""
        <!-- ... [Insert your Simulator HTML from the previous turn here] ... -->
        <script>
            // Added function to serialize actual connections for the AI
            function exportNetlist() {{
                const data = {{
                    components: comps.map(c => ({{
                        type: c.type, 
                        rotation: c.rot, 
                        connectedRows: c.connectedTracks // This is the 'semantic' part!
                    }})),
                    wires: wires.map(w => ({{
                        from: getTrack(w.start), 
                        to: getTrack(w.end)
                    }}))
                }};
                navigator.clipboard.writeText(JSON.stringify(data, null, 2));
                alert("Circuit netlist copied to clipboard! Paste it into the 'AI Tutor' box on the left.");
            }}
        </script>
    """, height=850)
