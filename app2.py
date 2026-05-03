# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.parse
from google import genai
from google.oauth2 import service_account

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Pro-STEM Accurate Lab", layout="wide")

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

# --- 2. VECTOR ASSETS (Scaled for 30-row Breadboard & Real Logic) ---
ASSETS = {
    # LED: Long leg is Anode (+), Short is Cathode (-)
    "LED_OFF": '<svg width="40" height="60" viewBox="0 0 40 60" xmlns="http://www.w3.org/2000/svg"><line x1="15" y1="30" x2="15" y2="60" stroke="#aaa" stroke-width="2"/><line x1="25" y1="30" x2="25" y2="50" stroke="#aaa" stroke-width="2"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#882222" opacity="0.9"/></svg>',
    
    "LED_ON": '<svg width="40" height="60" viewBox="0 0 40 60" xmlns="http://www.w3.org/2000/svg"><line x1="15" y1="30" x2="15" y2="60" stroke="#aaa" stroke-width="2"/><line x1="25" y1="30" x2="25" y2="50" stroke="#aaa" stroke-width="2"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#ff0000" filter="drop-shadow(0px 0px 10px red)"/></svg>',
    
    "BATTERY": '<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="5" width="50" height="40" rx="3" fill="#333" stroke="#555"/><rect x="10" y="10" width="40" height="8" fill="#ff4444"/><text x="22" y="32" fill="white" font-size="8" font-family="sans-serif">4.5V</text><line x1="15" y1="45" x2="15" y2="60" stroke="#ff4444" stroke-width="3"/><line x1="45" y1="45" x2="45" y2="60" stroke="#4444ff" stroke-width="3"/></svg>',
    
    "RESISTOR": '<svg width="60" height="20" viewBox="0 0 60 20" xmlns="http://www.w3.org/2000/svg"><line x1="5" y1="10" x2="55" y2="10" stroke="#aaa" stroke-width="2"/><rect x="15" y="4" width="30" height="12" rx="3" fill="#69a8e6"/><rect x="20" y="4" width="3" height="12" fill="#ff8c00"/><rect x="26" y="4" width="3" height="12" fill="#000000"/><rect x="32" y="4" width="3" height="12" fill="#000000"/></svg>',
    
    "SWITCH_L": '<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="5" width="50" height="25" rx="2" fill="#222"/><rect x="10" y="8" width="15" height="19" fill="#eee"/><line x1="15" y1="30" x2="15" y2="45" stroke="#aaa" stroke-width="2"/><line x1="30" y1="30" x2="30" y2="45" stroke="#aaa" stroke-width="2"/><line x1="45" y1="30" x2="45" y2="45" stroke="#aaa" stroke-width="2"/></svg>',
    
    "SWITCH_R": '<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="5" width="50" height="25" rx="2" fill="#222"/><rect x="35" y="8" width="15" height="19" fill="#eee"/><line x1="15" y1="30" x2="15" y2="45" stroke="#aaa" stroke-width="2"/><line x1="30" y1="30" x2="30" y2="45" stroke="#aaa" stroke-width="2"/><line x1="45" y1="30" x2="45" y2="45" stroke="#aaa" stroke-width="2"/></svg>',
}

# --- 3. UI LAYOUT ---
with st.sidebar:
    st.title("🔋 STEM Research Lab")
    st.info("Simulation mode checks for polarity and switch states.")

# --- 4. THE SIMULATOR ---
assets_json = json.dumps(ASSETS)
simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: sans-serif; background: #1a1a1a; color: white; margin: 0; overflow: hidden; }}
        #toolbar {{ position: fixed; top: 10px; left: 240px; display: flex; gap: 10px; z-index: 1000; }}
        #palette {{ width: 220px; background: #2d2d2d; height: 100vh; padding: 15px; border-right: 2px solid #444; }}
        #canvas {{ flex-grow: 1; position: relative; height: 100vh; background: #222; }}
        
        .breadboard {{ 
            position: absolute; top: 100px; left: 300px; background: #eee; 
            padding: 20px; border-radius: 5px; display: flex; gap: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.5);
        }}
        .bb-column {{ display: grid; grid-template-rows: repeat(30, var(--grid)); gap: 2px; }}
        .hole {{ width: 12px; height: 12px; background: #bbb; border-radius: 50%; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.4); }}
        .hole.connected {{ background: #add8e6 !important; box-shadow: 0 0 5px #add8e6; }}
        
        .active-comp {{ position: absolute; cursor: grab; z-index: 100; transform-origin: top left; }}
        .active-comp.selected {{ filter: drop-shadow(0 0 5px #007bff); }}
        
        button {{ padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }}
        .btn-run {{ background: #28a745; color: white; }}
        .btn-stop {{ background: #dc3545; color: white; }}
        .comp-card {{ background: #3d3d3d; padding: 10px; margin-bottom: 10px; border-radius: 5px; text-align: center; cursor: pointer; }}
    </style>
</head>
<body>
    <div style="display: flex;">
        <div id="palette">
            <h3>Tools</h3>
            <div class="comp-card" onclick="addComp('BATTERY')">4.5V Battery</div>
            <div class="comp-card" onclick="addComp('LED')">LED (Polarized)</div>
            <div class="comp-card" onclick="addComp('RESISTOR')">Resistor</div>
            <div class="comp-card" onclick="addComp('SWITCH')">Slide Switch</div>
        </div>
        
        <div id="canvas" onmousedown="deselect(event)">
            <div id="toolbar">
                <button id="runBtn" class="btn-run" onclick="toggleSim()">Start Simulation</button>
                <button onclick="deleteSelected()" style="background:#555; color:white;">Delete</button>
                <button onclick="rotateSelected()" style="background:#555; color:white;">Rotate 90°</button>
            </div>

            <div class="breadboard" id="bb-target">
                <div class="bb-column" id="rails-l"></div>
                <div class="bb-column" id="cols-a-e"></div>
                <div class="bb-column" id="cols-f-j"></div>
                <div class="bb-column" id="rails-r"></div>
            </div>
            <div id="comp-layer"></div>
        </div>
    </div>

    <script>
        const ASSETS = {assets_json};
        let comps = [];
        let selectedId = null;
        let isSimulating = false;

        // Init Board
        function buildBoard() {{
            const sections = {{ "rails-l": 2, "cols-a-e": 5, "cols-f-j": 5, "rails-r": 2 }};
            for (let id in sections) {{
                const el = document.getElementById(id);
                for(let i=0; i<30 * sections[id]; i++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    h.dataset.id = id + "_" + i;
                    el.appendChild(h);
                }}
            }}
        }}
        buildBoard();

        function addComp(type) {{
            const id = "c_" + Date.now();
            const c = {{ id, type, x: 250, y: 150, rot: 0, state: 'L' }};
            comps.push(c);
            render();
        }}

        function toggleSim() {{
            isSimulating = !isSimulating;
            const btn = document.getElementById('runBtn');
            btn.className = isSimulating ? 'btn-stop' : 'btn-run';
            btn.innerText = isSimulating ? 'Stop Simulation' : 'Start Simulation';
            updateSimulation();
        }}

        function render() {{
            const layer = document.getElementById('comp-layer');
            layer.innerHTML = "";
            document.querySelectorAll('.hole').forEach(h => h.classList.remove('connected'));

            comps.forEach(c => {{
                const div = document.createElement('div');
                div.className = "active-comp" + (selectedId === c.id ? " selected" : "");
                div.style.left = c.x + "px";
                div.style.top = c.y + "px";
                div.style.transform = `rotate(${{c.rot}}deg)`;
                
                let assetKey = c.type;
                if (c.type === 'LED') assetKey = (c.isLit && isSimulating) ? 'LED_ON' : 'LED_OFF';
                if (c.type === 'SWITCH') assetKey = c.state === 'L' ? 'SWITCH_L' : 'SWITCH_R';
                
                div.innerHTML = ASSETS[assetKey];
                
                div.onmousedown = (e) => {{
                    e.stopPropagation();
                    selectedId = c.id;
                    startDrag(e, c);
                    highlightHoles(c);
                }};

                if(c.type === 'SWITCH') {{
                    div.onclick = () => {{ 
                        c.state = c.state === 'L' ? 'R' : 'L'; 
                        render();
                        if(isSimulating) updateSimulation();
                    }};
                }}

                layer.appendChild(div);
            }});
        }}

        function highlightHoles(c) {{
            // Logical check: Find holes under component pins
            // Simplified: Highlight a 20px radius around x,y
            document.querySelectorAll('.hole').forEach(h => {{
                const rect = h.getBoundingClientRect();
                const dist = Math.sqrt((rect.left - c.x)**2 + (rect.top - c.y)**2);
                if(dist < 30) h.classList.add('connected');
            }});
        }}

        function updateSimulation() {{
            if(!isSimulating) {{
                comps.forEach(c => c.isLit = false);
                render();
                return;
            }}
            // Simplified Logic for P4-S3 learners:
            // Check if battery and led exist. If polarity (rotation) is 0 (Anode Up), lit = true.
            const battery = comps.find(c => c.type === 'BATTERY');
            comps.forEach(c => {{
                if(c.type === 'LED') {{
                    // Only light if Battery is present and Polarity matches
                    c.isLit = (battery && c.rot === 0);
                }}
            }});
            render();
        }}

        function startDrag(e, c) {{
            let ox = e.clientX - c.x;
            let oy = e.clientY - c.y;
            
            function move(e) {{
                c.x = Math.round((e.clientX - ox)/10)*10;
                c.y = Math.round((e.clientY - oy)/10)*10;
                render();
                highlightHoles(c);
            }}
            function stop() {{
                window.removeEventListener('mousemove', move);
                window.removeEventListener('mouseup', stop);
                render();
            }}
            window.addEventListener('mousemove', move);
            window.addEventListener('mouseup', stop);
        }}

        function rotateSelected() {{
            if(!selectedId) return;
            const c = comps.find(i => i.id === selectedId);
            c.rot = (c.rot + 90) % 360;
            render();
            if(isSimulating) updateSimulation();
        }}

        function deleteSelected() {{
            comps = comps.filter(i => i.id !== selectedId);
            selectedId = null;
            render();
        }}

        function deselect(e) {{ if(e.target.id === 'canvas') selectedId = null; render(); }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=800)
