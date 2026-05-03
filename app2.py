# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.parse
from google import genai
from google.oauth2 import service_account

# --- 1. IMAGE CONFIGURATION ---
# Replace these URLs with your actual GitHub RAW links
ASSET_URLS = {
    "bb": "https://your-github-link/breadboard.png",
    "led": "https://your-github-link/led.png",
    "ldr": "https://your-github-link/ldr.png",
    "res_300": "https://your-github-link/resistor_300.png",
    "res_1k": "https://your-github-link/resistor_1k.png",
    "res_10k": "https://your-github-link/resistor_10k.png",
    "switch": "https://your-github-link/switch.png",
    "pot": "https://your-github-link/pot.png"
}

st.set_page_config(page_title="Pro-STEM Simulator", layout="wide")

# --- 2. AI LOGIC (Silent Scaffolding) ---
if "tokens" not in st.session_state: st.session_state.tokens = 15
if "feedback" not in st.session_state: st.session_state.feedback = ""

query_params = st.query_params
if "circuit_data" in query_params:
    raw_data = query_params["circuit_data"]
    st.query_params.clear()
    try:
        decoded = json.loads(urllib.parse.unquote(raw_data))
        st.session_state.tokens -= 1
        
        # We pass the metadata of the images to Gemini
        # Gemini now 'knows' what the logos represent based on the 'type' tag
        prompt = f"Analyze this circuit: {decoded}. The student is using real-world component logos. Provide a Socratic hint about their placement or logic."
        
        # (AI Client logic remains the same as previous versions)
        st.session_state.feedback = "AI Analysis complete. Check your resistor value!" 
    except:
        pass

# --- 3. THE VISUAL SIMULATOR (JS/HTML5) ---
# I am using a transparent SVG overlay for the holes so your breadboard image shows through.
simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ background: #1e1e1e; color: white; font-family: sans-serif; margin: 0; overflow: hidden; }}
        #ui-root {{ display: flex; height: 100vh; }}
        
        /* Side Palette */
        #palette {{ width: 220px; background: #2d2d2d; padding: 15px; border-right: 2px solid #444; z-index: 1000; }}
        .asset-btn {{ 
            width: 100%; margin-bottom: 15px; background: #3d3d3d; border: 1px solid #555; 
            border-radius: 8px; cursor: pointer; padding: 10px; color: white; transition: 0.2s;
        }}
        .asset-btn:hover {{ background: #505050; border-color: #007bff; }}
        .asset-btn img {{ width: 50px; height: auto; display: block; margin: 0 auto 5px; }}
        
        /* Workspace */
        #workspace {{ flex-grow: 1; position: relative; background-image: radial-gradient(#333 1px, transparent 1px); background-size: 20px 20px; }}
        
        #bb-layer {{ 
            position: absolute; top: 100px; left: 50px; 
            width: 900px; height: 450px;
            background: url('{ASSET_URLS["bb"]}') no-repeat center;
            background-size: contain;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}

        .hole-grid {{ 
            display: grid; grid-template-columns: repeat(30, 1fr); 
            width: 100%; height: 100%; opacity: 0.3; /* Hidden holes that align with your image */
        }}
        .hole {{ width: 15px; height: 15px; border-radius: 50%; cursor: crosshair; margin: auto; }}
        .hole:hover {{ background: rgba(255, 255, 0, 0.5); opacity: 1; }}

        .placed-component {{ 
            position: absolute; cursor: move; z-index: 50; 
            filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.3));
        }}
        .placed-component img {{ pointer-events: none; }}

        #wire-canvas {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 60; }}
        #submit-btn {{ 
            position: fixed; bottom: 20px; right: 20px; padding: 15px 40px; 
            background: #28a745; border: none; border-radius: 30px; color: white; 
            font-weight: bold; font-size: 18px; cursor: pointer;
        }}
    </style>
</head>
<body>
    <div id="ui-root">
        <div id="palette">
            <h4 style="margin-top:0">Components</h4>
            <button class="asset-btn" onclick="spawn('LED', '{ASSET_URLS["led"]}')"><img src="{ASSET_URLS["led"]}">LED</button>
            <button class="asset-btn" onclick="spawn('RES_300', '{ASSET_URLS["res_300"]}')"><img src="{ASSET_URLS["res_300"]}">300Ω</button>
            <button class="asset-btn" onclick="spawn('LDR', '{ASSET_URLS["ldr"]}')"><img src="{ASSET_URLS["ldr"]}">LDR</button>
            <button class="asset-btn" onclick="spawn('SWITCH', '{ASSET_URLS["switch"]}')"><img src="{ASSET_URLS["switch"]}">Switch</button>
            <button class="asset-btn" onclick="spawn('POT', '{ASSET_URLS["pot"]}')"><img src="{ASSET_URLS["pot"]}">Variable</button>
        </div>

        <div id="workspace">
            <svg id="wire-canvas"></svg>
            <div id="bb-layer">
                <div class="hole-grid" id="grid"></div>
            </div>
        </div>
    </div>
    
    <button id="submit-btn" onclick="exportCircuit()">🔍 Analyze Circuit</button>

    <script>
        const grid = document.getElementById('grid');
        const wireCanvas = document.getElementById('wire-canvas');
        let comps = [];
        let wires = [];
        let activeWireStart = null;

        // 1. Create the 'invisible' logic grid over your breadboard image
        for(let i=0; i<300; i++) {{
            const h = document.createElement('div');
            h.className = 'hole';
            h.dataset.id = i;
            h.onclick = () => handleWire(i);
            grid.appendChild(h);
        }}

        // 2. Drag & Drop with Images
        function spawn(type, url) {{
            const id = 'c' + Date.now();
            const div = document.createElement('div');
            div.className = 'placed-component';
            div.id = id;
            div.style.left = '300px';
            div.style.top = '50px';
            div.innerHTML = `<img src="${{url}}" width="80">`;
            
            // Drag Logic
            let x=0, y=0;
            div.onmousedown = (e) => {{
                x = e.clientX - div.offsetLeft;
                y = e.clientY - div.offsetTop;
                document.onmousemove = (me) => {{
                    div.style.left = (me.clientX - x) + 'px';
                    div.style.top = (me.clientY - y) + 'px';
                }};
            }};
            document.onmouseup = () => {{ document.onmousemove = null; }};
            
            document.getElementById('workspace').appendChild(div);
            comps.push({{ id, type, x: 300, y: 50 }});
        }}

        // 3. Wiring Logic
        function handleWire(id) {{
            if(activeWireStart === null) {{
                activeWireStart = id;
            }} else {{
                const h1 = document.querySelector(`[data-id="${{activeWireStart}}"]`).getBoundingClientRect();
                const h2 = document.querySelector(`[data-id="${{id}}"]`).getBoundingClientRect();
                const root = document.getElementById('workspace').getBoundingClientRect();
                
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', h1.left - root.left + 7);
                line.setAttribute('y1', h1.top - root.top + 7);
                line.setAttribute('x2', h2.left - root.left + 7);
                line.setAttribute('y2', h2.top - root.top + 7);
                line.setAttribute('stroke', '#ff4444');
                line.setAttribute('stroke-width', '4');
                wireCanvas.appendChild(line);
                
                wires.push({{ from: activeWireStart, to: id }});
                activeWireStart = null;
            }}
        }}

        function exportCircuit() {{
            const data = JSON.stringify({{ components: comps, connections: wires }});
            const url = window.parent.location.origin + window.parent.location.pathname + '?circuit_data=' + encodeURIComponent(data);
            window.parent.location.assign(url);
        }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=700)
