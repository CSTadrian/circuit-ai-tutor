# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.parse
from google import genai
from google.oauth2 import service_account

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Pro-STEM Direct Lab", layout="wide")

@st.cache_resource
def get_ai_client():
    if "gcp_service_account" in st.secrets:
        creds_info = st.secrets["gcp_service_account"]
        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
    return None

client = get_ai_client()

# --- 2. VECTOR ASSETS (Embedded directly in code) ---
# These are SVG strings that represent realistic electronic components
ASSETS = {
    "LED": '<svg width="50" height="80" viewBox="0 0 50 80" xmlns="http://www.w3.org/2000/svg"><rect x="22" y="40" width="2" height="40" fill="#aaa"/><rect x="26" y="40" width="2" height="35" fill="#aaa"/><path d="M15 40 Q 15 15 25 15 Q 35 15 35 40 Z" fill="#ff4444" opacity="0.9"/><circle cx="25" cy="25" r="5" fill="white" opacity="0.3"/></svg>',
    
    "RES_300": '<svg width="80" height="30" viewBox="0 0 80 30" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="14" width="80" height="2" fill="#aaa"/><rect x="20" y="5" width="40" height="20" rx="5" fill="#d2b48c"/><rect x="25" y="5" width="4" height="20" fill="orange"/><rect x="33" y="5" width="4" height="20" fill="orange"/><rect x="41" y="5" width="4" height="20" fill="brown"/></svg>',
    
    "RES_1K": '<svg width="80" height="30" viewBox="0 0 80 30" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="14" width="80" height="2" fill="#aaa"/><rect x="20" y="5" width="40" height="20" rx="5" fill="#d2b48c"/><rect x="25" y="5" width="4" height="20" fill="brown"/><rect x="33" y="5" width="4" height="20" fill="black"/><rect x="41" y="5" width="4" height="20" fill="red"/></svg>',
    
    "RES_10K": '<svg width="80" height="30" viewBox="0 0 80 30" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="14" width="80" height="2" fill="#aaa"/><rect x="20" y="5" width="40" height="20" rx="5" fill="#d2b48c"/><rect x="25" y="5" width="4" height="20" fill="brown"/><rect x="33" y="5" width="4" height="20" fill="black"/><rect x="41" y="5" width="4" height="20" fill="orange"/></svg>',
    
    "LDR": '<svg width="50" height="50" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg"><circle cx="25" cy="25" r="20" fill="#cc0000"/><path d="M15 25 L20 20 L25 30 L30 20 L35 30 L40 25" fill="none" stroke="yellow" stroke-width="2"/><rect x="22" y="45" width="2" height="20" fill="#aaa"/><rect x="26" y="45" width="2" height="20" fill="#aaa"/></svg>',
    
    "SWITCH": '<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="5" width="50" height="30" rx="2" fill="#333"/><rect x="20" y="10" width="20" height="20" fill="#555"/><rect x="25" y="12" width="10" height="16" fill="white" opacity="0.8"/></svg>',
    
    "POT": '<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg"><circle cx="30" cy="30" r="25" fill="#555" stroke="#333" stroke-width="2"/><circle cx="30" cy="30" r="5" fill="#999"/><line x1="30" y1="30" x2="30" y2="10" stroke="white" stroke-width="3"/></svg>'
}

# --- 3. STATE MANAGEMENT ---
if "tokens" not in st.session_state: st.session_state.tokens = 15
if "feedback" not in st.session_state: st.session_state.feedback = ""

query_params = st.query_params
if "circuit_data" in query_params:
    raw_data = query_params["circuit_data"]
    st.query_params.clear()
    try:
        decoded_data = json.loads(urllib.parse.unquote(raw_data))
        st.session_state.tokens -= 1
        prompt = f"Student built: {decoded_data}. Provide a Socratic hint for a P4-S3 student."
        if client:
            response = client.models.generate_content(model="gemini-3.1-pro-preview", contents=prompt)
            st.session_state.feedback = response.text
    except:
        pass

# --- 4. UI & SIDEBAR ---
with st.sidebar:
    st.title("🔋 Component Lab")
    st.metric("Tokens", st.session_state.tokens)
    if st.button("Reset Lab"):
        st.session_state.tokens = 15
        st.session_state.feedback = ""
        st.rerun()

if st.session_state.feedback:
    st.info(f"🤖 **Tutor:** {st.session_state.feedback}")

# --- 5. THE SIMULATOR ---
# We pass the SVGs as a JSON string to the JavaScript
assets_json = json.dumps(ASSETS)

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 220px; background: #333; padding: 15px; border-right: 2px solid #444; overflow-y: auto; }}
        #canvas {{ flex-grow: 1; position: relative; background: #1a1a1a; }}
        
        .breadboard {{ 
            background: #e0e0e0; width: 850px; height: 420px; border-radius: 10px; 
            margin: 50px auto; position: relative; display: grid; 
            grid-template-columns: repeat(30, 1fr); padding: 30px 20px; gap: 8px;
            border: 5px solid #ccc;
        }}
        .hole {{ width: 14px; height: 14px; background: #bbb; border-radius: 50%; cursor: crosshair; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.2); }}
        .hole:hover {{ background: #555; }}
        
        .comp-item {{ 
            background: #444; padding: 10px; margin-bottom: 12px; border-radius: 8px; 
            cursor: pointer; text-align: center; border: 1px solid #555; font-size: 11px;
            display: flex; flex-direction: column; align-items: center;
        }}
        .comp-item:hover {{ border-color: #007bff; background: #505050; }}
        .comp-item svg {{ margin-bottom: 5px; max-width: 60px; height: auto; }}
        
        .active-comp {{ 
            position: absolute; cursor: move; z-index: 100;
            filter: drop-shadow(3px 5px 5px rgba(0,0,0,0.4));
        }}
        
        svg.wire-layer {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 90; }}
        #analyze-btn {{ 
            position: fixed; bottom: 20px; right: 20px; padding: 15px 30px; 
            background: #28a745; color: white; border: none; border-radius: 50px; 
            font-weight: bold; cursor: pointer;
        }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <div class="comp-item" onclick="addComp('LED')">{ASSETS['LED']}LED</div>
            <div class="comp-item" onclick="addComp('Resistor-300')">{ASSETS['RES_300']}300Ω Resistor</div>
            <div class="comp-item" onclick="addComp('Resistor-1k')">{ASSETS['RES_1K']}1kΩ Resistor</div>
            <div class="comp-item" onclick="addComp('Resistor-10k')">{ASSETS['RES_10K']}10kΩ Resistor</div>
            <div class="comp-item" onclick="addComp('LDR')">{ASSETS['LDR']}LDR</div>
            <div class="comp-item" onclick="addComp('Slide-Switch')">{ASSETS['SWITCH']}Switch</div>
            <div class="comp-item" onclick="addComp('Potentiometer')">{ASSETS['POT']}Variable</div>
        </div>
        <div id="canvas">
            <svg class="wire-layer" id="wire-layer"></svg>
            <div class="breadboard" id="bb"></div>
        </div>
    </div>
    <button id="analyze-btn" onclick="submit()">Analyze My Circuit</button>

    <script>
        const bb = document.getElementById('bb');
        const wireLayer = document.getElementById('wire-layer');
        const ASSET_MAP = {assets_json};
        let placedComponents = [];
        let connections = [];
        let wireStartHole = null;

        for (let i = 0; i < 300; i++) {{
            const h = document.createElement('div');
            h.className = 'hole';
            h.id = 'h-' + i;
            h.onclick = () => handleWire(i);
            bb.appendChild(h);
        }}

        function addComp(type) {{
            const id = 'comp-' + Date.now();
            const div = document.createElement('div');
            div.className = 'active-comp';
            div.id = id;
            div.innerHTML = ASSET_MAP[type.toUpperCase().replace('-', '_')];
            div.style.left = '300px';
            div.style.top = '100px';
            
            let isDragging = false;
            div.onmousedown = () => {{ isDragging = true; }};
            document.onmousemove = (e) => {{
                if (isDragging) {{
                    div.style.left = (e.clientX - 250) + 'px';
                    div.style.top = (e.clientY - 50) + 'px';
                }}
            }};
            document.onmouseup = () => {{ isDragging = false; }};
            
            document.getElementById('canvas').appendChild(div);
            placedComponents.push({{ id, type }});
        }}

        function handleWire(holeIdx) {{
            if (wireStartHole === null) {{
                wireStartHole = holeIdx;
                document.getElementById('h-' + holeIdx).style.background = '#007bff';
            } else {{
                const start = document.getElementById('h-' + wireStartHole).getBoundingClientRect();
                const end = document.getElementById('h-' + holeIdx).getBoundingClientRect();
                const canvas = document.getElementById('canvas').getBoundingClientRect();

                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', start.left - canvas.left + 7);
                line.setAttribute('y1', start.top - canvas.top + 7);
                line.setAttribute('x2', end.left - canvas.left + 7);
                line.setAttribute('y2', end.top - canvas.top + 7);
                line.setAttribute('stroke', '#00ff00');
                line.setAttribute('stroke-width', '3');
                wireLayer.appendChild(line);

                connections.push({{ from: wireStartHole, to: holeIdx }});
                document.getElementById('h-' + wireStartHole).style.background = '#bbb';
                wireStartHole = null;
            }}
        }}

        function submit() {{
            const data = JSON.stringify({{ components: placedComponents, connections: connections }});
            const url = window.parent.location.origin + window.parent.location.pathname + '?circuit_data=' + encodeURIComponent(data);
            window.parent.location.assign(url);
        }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=700)
