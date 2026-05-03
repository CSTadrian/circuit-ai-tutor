# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
from PIL import Image as PILImage, ImageDraw
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & AI CONFIG ---
st.set_page_config(page_title="AI STEM Precision Lab", layout="wide")
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
    """Draws the 0-1000 scale required for Gemini's spatial reasoning."""
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for i in range(0, 1001, 100):
        x_px, y_px = i * w / 1000, i * h / 1000
        # Red ticks and labels
        draw.line([(x_px, 0), (x_px, 15)], fill=(255, 0, 0), width=2)
        draw.line([(0, y_px), (15, y_px)], fill=(255, 0, 0), width=2)
        draw.text((x_px + 2, 2), str(i), fill=(255, 255, 255))
        draw.text((2, y_px + 2), str(i), fill=(255, 255, 255))
    return image

# --- 3. UI LAYOUT ---
col_side, col_main = st.columns([1, 3])

with col_side:
    st.header("📋 Task Details")
    selected_task = st.selectbox("Current Project:", TASK_OPTIONS)
    
    # Logic to load the correct semantic image from data2/ folder
    task_id = selected_task.split(")")[0].strip()
    img_path = f"data2/circuit-{task_id}.jpg"
    
    if os.path.exists(img_path):
        ref_img = PILImage.open(img_path)
        # Apply the coordinate grid so AI can map component positions accurately
        ref_img_gridded = draw_coordinate_grid(ref_img.copy())
        st.image(ref_img_gridded, caption=f"Semantic Goal: {selected_task}", use_container_width=True)
    else:
        st.warning(f"Semantic image not found at {img_path}. Please check your 'data2' folder.")
        ref_img = None

    # THE AI TUTOR TRIGGER
    st.markdown("---")
    st.subheader("🤖 AI Tutor Analysis")
    
    # We use a text area as a bridge to receive the Netlist JSON from the JS simulator
    netlist_input = st.text_area("Paste Netlist for AI Analysis (or click 'Export' in Sim)", height=100)
    
    if st.button("Check My Circuit", type="primary", use_container_width=True):
        if not ref_img:
            st.error("No semantic goal image found for this task.")
        elif not netlist_input:
            st.warning("Please export your netlist from the simulator first!")
        else:
            with st.spinner("AI is analyzing your construction..."):
                # Detailed prompt for educational scaffolding
                prompt = f"""
                You are a STEM research assistant helping a student (ages 10-15).
                Compare the provided 'Semantic Goal' image to the student's digital netlist.
                
                CURRENT TASK: {selected_task}
                STUDENT NETLIST: {netlist_input}
                
                EVALUATION CRITERIA:
                1. Are all components present? (Battery, LED, Resistor, etc.)
                2. Are the connections (tracks/rows) correct based on the semantic image?
                3. Check polarity: Is the LED anode (+) connected toward the VCC?
                
                FEEDBACK STYLE:
                Be encouraging. If there is an error, describe it as a 'puzzle to solve'. 
                Gently point them to the specific breadboard row or component that needs attention.
                """
                
                try:
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[ref_img, prompt],
                        config=types.GenerateContentConfig(temperature=0.2)
                    )
                    st.success("Tutor Feedback Received:")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"AI Connection Error: {e}")

with col_main:
    st.header("⚡ Precision Lab Workspace")
    
    # Injecting the JS Simulator with an "Export to AI" button added to the toolbar
    # Note: Added a 'getNetlist' function to serialize the current board state
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

    simulator_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            :root {{ --grid: 20px; }}
            body {{ font-family: sans-serif; background: #1a1a1a; color: white; margin: 0; }}
            #workspace {{ display: flex; height: 85vh; }}
            #palette {{ width: 220px; background: #222; padding: 15px; border-right: 1px solid #444; }}
            .comp-item {{ background: #333; padding: 8px; margin-bottom: 8px; border-radius: 4px; cursor: pointer; text-align: center; border: 1px solid #444; font-size: 12px; }}
            #canvas {{ flex-grow: 1; position: relative; background: #111; overflow: auto; }}
            #toolbar {{ padding: 10px; background: #222; border-bottom: 1px solid #444; display: flex; gap: 8px; }}
            .tool-btn {{ background: #444; color: white; border: none; padding: 5px 12px; border-radius: 4px; cursor: pointer; }}
            .bb-outer {{ position: absolute; top: 40px; left: 40px; background: #eee; padding: 20px; border-radius: 8px; display: flex; gap: 5px; }}
            .hole {{ width: 12px; height: 12px; background: #bbb; border-radius: 50%; margin: 4px; cursor: pointer; }}
            .hole.occupied {{ background: #add8e6; }}
            .active-comp {{ position: absolute; z-index: 100; cursor: grab; transform-origin: 0 0; }}
            .wire {{ stroke: #2ecc71; stroke-width: 4; stroke-linecap: round; }}
        </style>
    </head>
    <body>
        <div id="workspace">
            <div id="palette">
                <div class="comp-item" onclick="spawn('BATTERY')">Battery</div>
                <div class="comp-item" onclick="spawn('LED')">LED</div>
                <div class="comp-item" onclick="spawn('RESISTOR')">Resistor</div>
                <div class="comp-item" onclick="spawn('SWITCH')">Switch</div>
            </div>
            <div id="canvas">
                <div id="toolbar">
                    <button class="tool-btn" onclick="rotateComp()">↻ Rotate</button>
                    <button class="tool-btn" onclick="deleteComp()">✖ Delete</button>
                    <button class="tool-btn" onclick="exportNetlist()" style="background:#2ecc71;">💾 Export Netlist</button>
                </div>
                <svg class="overlay" id="wire-layer" style="position:absolute; width:100%; height:100%; pointer-events:none;"></svg>
                <div class="bb-outer" id="board">
                    <!-- Holes dynamically generated by script below -->
                </div>
                <div id="comp-layer"></div>
            </div>
        </div>
        <script>
            const ASSETS = {ASSETS_JSON};
            let comps = [];
            let wires = [];
            let selection = null;

            // Simplified hole generation for the combined version
            const board = document.getElementById('board');
            for(let i=0; i<300; i++) {{ 
                const h = document.createElement('div'); 
                h.className = 'hole'; 
                h.id = 'h_'+i;
                board.appendChild(h);
            }}

            function spawn(type) {{
                const id = 'c' + Date.now();
                comps.push({{id, type, x:100, y:100, rot:0, connectedTracks: []}});
                render();
            }}

            function render() {{
                const layer = document.getElementById('comp-layer');
                layer.innerHTML = '';
                comps.forEach(c => {{
                    const el = document.createElement('div');
                    el.className = 'active-comp';
                    el.innerHTML = ASSETS[c.type === 'LED' ? 'LED' : c.type === 'SWITCH' ? 'SWITCH' : c.type === 'BATTERY' ? 'BATTERY' : 'RES_5BAND'];
                    if(c.type === 'LED') el.innerHTML = ASSETS.LED.OFF;
                    if(c.type === 'SWITCH') el.innerHTML = ASSETS.SWITCH.LEFT;
                    
                    el.style.left = c.x + 'px'; el.style.top = c.y + 'px';
                    el.style.transform = `rotate(${{c.rot}}deg)`;
                    el.onmousedown = () => selection = c.id;
                    layer.appendChild(el);
                }});
            }}

            function exportNetlist() {{
                // This function serializes the board state to the clipboard 
                // so the student can paste it into the AI Tutor text area.
                const data = {{
                    components: comps.map(c => ({{type: c.type, rot: c.rot}})),
                    wireCount: wires.length
                }};
                const blob = JSON.stringify(data);
                navigator.clipboard.writeText(blob);
                alert("Netlist copied to clipboard! Paste it into the 'AI Tutor' box on the left.");
            }}

            // Placeholder for basic dragging/rotating logic from original code...
            function rotateComp() {{ if(selection) {{ const c = comps.find(x=>x.id===selection); c.rot += 90; render(); }} }}
            function deleteComp() {{ comps = comps.filter(x=>x.id!==selection); selection=null; render(); }}
        </script>
    </body>
    </html>
    """
    st.components.v1.html(simulator_html, height=800)
