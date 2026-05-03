# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
from PIL import Image as PILImage
import io

# --- GOOGLE GENAI SDK SETUP ---
# Note: You will need to provide your API key in Streamlit secrets or as an environment variable
from google import genai
from google.genai import types

st.set_page_config(page_title="AI Circuit Auditor Pro", layout="wide")

# --- 1. COMPONENT GRAPHICS (SVG) ---
ASSETS_RAW = {
    "LED": {
        "OFF": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#822" opacity="0.9"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>',
        "ON": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#f00" filter="drop-shadow(0 0 8px red)"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>'
    },
    "RESISTOR": {
        "1000": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="5" y="9" width="70" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="25" y="4" width="3" height="12" fill="#8b4513"/><rect x="31" y="4" width="3" height="12" fill="#000"/><rect x="37" y="4" width="3" height="12" fill="#000"/><rect x="43" y="4" width="3" height="12" fill="#8b4513"/><rect x="52" y="4" width="3" height="12" fill="#8b4513"/></svg>'
    },
    "BATTERY": '<svg width="40" height="60" viewBox="0 0 40 60"><rect x="2" y="2" width="36" height="46" rx="4" fill="#333" stroke="#555"/><rect x="6" y="6" width="28" height="10" fill="#f1c40f"/><rect x="6" y="18" width="28" height="10" fill="#f1c40f"/><rect x="6" y="30" width="28" height="10" fill="#f1c40f"/><text x="11" y="40" fill="black" font-size="7" font-weight="bold">4.5V</text><rect x="10" y="48" width="2" height="12" fill="#ff4444"/><rect x="30" y="48" width="2" height="12" fill="#4444ff"/></svg>',
    "SWITCH": '<svg width="40" height="20" viewBox="0 0 40 20"><rect x="5" y="2" width="30" height="16" rx="2" fill="#555"/><rect x="10" y="6" width="10" height="8" fill="#eee"/></svg>'
}

# --- 2. THE SIMULATOR (JAVASCRIPT COMPONENT) ---
def simulator_ui(state_json):
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/streamlit-component-lib@1.4.0/dist/streamlit-component-lib.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: #e0e0e0; margin: 0; display: flex; }}
            #sidebar {{ width: 200px; background: #1e1e1e; padding: 20px; border-right: 1px solid #333; height: 100vh; }}
            .tool {{ background: #2d2d2d; border: 1px solid #444; padding: 10px; margin-bottom: 15px; border-radius: 6px; cursor: pointer; text-align: center; transition: 0.2s; }}
            .tool:hover {{ background: #3d3d3d; border-color: #666; }}
            #workspace {{ flex-grow: 1; position: relative; background: radial-gradient(#222 1px, transparent 1px); background-size: 20px 20px; }}
            .breadboard {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 600px; height: 350px; background: #fdfdfd; border-radius: 10px; border: 2px solid #ccc; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            .comp-instance {{ position: absolute; cursor: grab; z-index: 10; }}
            .comp-instance:active {{ cursor: grabbing; }}
            #sync-btn {{ width: 100%; padding: 12px; background: #0078d4; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div id="sidebar">
            <h3 style="margin-top:0">Components</h3>
            <div class="tool" onclick="addComp('BATTERY')">{ASSETS_RAW['BATTERY']}<br>4.5V Battery</div>
            <div class="tool" onclick="addComp('LED')">{ASSETS_RAW['LED']['OFF']}<br>LED</div>
            <div class="tool" onclick="addComp('RESISTOR')">{ASSETS_RAW['RESISTOR']['1000']}<br>1kΩ Resistor</div>
            <hr style="border: 0; border-top: 1px solid #444; margin: 20px 0;">
            <button id="sync-btn" onclick="syncData()">💾 Sync Board Data</button>
        </div>
        <div id="workspace">
            <div class="breadboard" id="bb">
                <!-- Visual breadboard pattern would go here -->
            </div>
            <div id="comp-container"></div>
        </div>

        <script>
            let components = {state_json if state_json else '[]'};
            const assets = {json.dumps(ASSETS_RAW)};

            function addComp(type) {{
                const id = "comp_" + Date.now();
                components.push({{ id, type, x: 250, y: 150, rotation: 0 }});
                render();
                syncData();
            }}

            function render() {{
                const container = document.getElementById('comp-container');
                container.innerHTML = '';
                components.forEach((c, index) => {{
                    const div = document.createElement('div');
                    div.className = 'comp-instance';
                    div.style.left = c.x + 'px';
                    div.style.top = c.y + 'px';
                    div.innerHTML = c.type === 'LED' ? assets.LED.OFF : (c.type === 'RESISTOR' ? assets.RESISTOR['1000'] : assets.BATTERY);
                    
                    div.onmousedown = (e) => {{
                        let shiftX = e.clientX - div.getBoundingClientRect().left;
                        let shiftY = e.clientY - div.getBoundingClientRect().top;
                        
                        function moveAt(pageX, pageY) {{
                            c.x = pageX - shiftX;
                            c.y = pageY - shiftY;
                            div.style.left = c.x + 'px';
                            div.style.top = c.y + 'px';
                        }}

                        function onMouseMove(e) {{ moveAt(e.pageX, e.pageY); }}
                        document.addEventListener('mousemove', onMouseMove);
                        
                        div.onmouseup = () => {{
                            document.removeEventListener('mousemove', onMouseMove);
                            div.onmouseup = null;
                            syncData();
                        }};
                    }};
                    container.appendChild(div);
                }});
            }}

            function syncData() {{
                // This is the CRITICAL bridge that sends data back to Python
                Streamlit.setComponentValue(JSON.stringify(components));
            }}

            window.addEventListener('load', () => {{
                Streamlit.setFrameHeight(700);
                render();
            }});
        </script>
    </body>
    </html>
    """
    return components.html(html_code, height=720)

# --- 3. AI AUDIT LOGIC ---
def run_ai_audit(circuit_json, schematic_image):
    # Initialize your client (ensure you have st.secrets["GEMINI_API_KEY"])
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    except:
        return {"is_correct": False, "feedback": "API Key not found in Streamlit Secrets."}

    # Prepare visual context
    img = PILImage.open(schematic_image)
    
    # Prompt explaining the state of the board
    prompt = f"""
    You are an electronics tutor. Compare the attached schematic image with the student's current breadboard state.
    
    Student's Breadboard Data (JSON):
    {circuit_json}
    
    Requirements:
    1. 4.5V Battery must power the circuit.
    2. 1k Ohm Resistor must be in series with the LED.
    3. The circuit must be closed.
    
    If the JSON shows '[]' or no components, tell the student to place components and click 'Sync Board Data'.
    Otherwise, give specific feedback on wiring.
    """

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "is_correct": {"type": "BOOLEAN"},
                    "feedback": {"type": "STRING"}
                }
            }
        )
    )
    return response.parsed

# --- 4. STREAMLIT APP LAYOUT ---
st.title("⚡ Breadboard AI Tutor")
st.markdown("Place your components and wire them. Then upload your schematic to check for errors.")

if "circuit_state" not in st.session_state:
    st.session_state.circuit_state = "[]"

col_sim, col_audit = st.columns([3, 1])

with col_sim:
    # Capturing the returned value from the HTML component
    new_state = simulator_ui(st.session_state.circuit_state)
    if new_state:
        st.session_state.circuit_state = new_state

with col_audit:
    st.subheader("Audit Panel")
    target_img = st.file_uploader("Upload Schematic", type=["png", "jpg", "jpeg"])
    
    if st.button("Check Circuit", type="primary", use_container_width=True):
        if not target_img:
            st.warning("Please upload a schematic image first.")
        else:
            with st.spinner("AI analyzing your board..."):
                result = run_ai_audit(st.session_state.circuit_state, target_img)
                
                if result.get("is_correct"):
                    st.success("✅ Circuit Correct!")
                else:
                    st.error("❌ Improvements Needed")
                
                st.write(result.get("feedback"))

    with st.expander("Raw Board Data (Debug)"):
        st.code(st.session_state.circuit_state, language="json")
