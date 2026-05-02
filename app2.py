# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.parse
from google import genai
from google.oauth2 import service_account

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Prototyping Sandbox", layout="wide")

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

# --- 2. STATE MANAGEMENT ---
if "tokens" not in st.session_state: st.session_state.tokens = 15
if "feedback" not in st.session_state: st.session_state.feedback = ""

# Check for data returned from the JavaScript Simulator
query_params = st.query_params
if "circuit_data" in query_params:
    raw_data = query_params["circuit_data"]
    st.query_params.clear() # Clear URL to prevent refresh loops
    
    try:
        decoded_data = json.loads(urllib.parse.unquote(raw_data))
        st.session_state.tokens -= 1
        
        # Socratic AI Prompt
        prompt = f"""
        You are an expert engineering tutor. A student (P4-S3 level) built this circuit:
        Components Placed: {decoded_data['components']}
        Wiring Connections: {decoded_data['connections']}
        
        The goal is a functional circuit using an LED, a protective Resistor, and a control (Switch/LDR).
        
        Analyze for:
        1. Resistor Value: Did they use 300, 1k, or 10k? (300 is best for 9V LED protection).
        2. Component Logic: Is the Slide-Switch or Potentiometer wired correctly?
        3. Polarity: Check LED Anode/Cathode.
        
        Provide a Socratic hint. Do not give the answer. 
        Focus on 'Energy Flow' and 'Resistance'.
        """
        
        if client:
            response = client.models.generate_content(model="gemini-3.1-pro-preview", contents=prompt)
            st.session_state.feedback = response.text
    except:
        st.error("Error analyzing circuit data.")

# --- 3. UI LAYOUT ---
with st.sidebar:
    st.title("🛠️ Component Lab")
    st.metric("Tokens", st.session_state.tokens)
    st.markdown("""
    **Mission:** Build a dimmable LED circuit using the Variable Resistor or a Light-controlled circuit using the LDR.
    """)
    if st.button("Reset Lab"):
        st.session_state.tokens = 15
        st.session_state.feedback = ""
        st.rerun()

if st.session_state.feedback:
    st.info(f"🤖 **Tutor:** {st.session_state.feedback}")

# --- 4. THE JAVASCRIPT SIMULATOR ---
# This simulates breadboard internal connections: vertical columns are connected.
simulator_html = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; }
        #workspace { display: flex; height: 100vh; }
        #palette { width: 200px; background: #333; padding: 15px; border-right: 2px solid #444; }
        #canvas { flex-grow: 1; position: relative; background: #1a1a1a; overflow: auto; }
        
        .breadboard { 
            background: #e0e0e0; width: 800px; height: 400px; border-radius: 10px; 
            margin: 50px; position: relative; display: grid; 
            grid-template-columns: repeat(30, 1fr); padding: 20px; gap: 8px;
        }
        .hole { width: 14px; height: 14px; background: #bbb; border-radius: 50%; cursor: crosshair; }
        .hole:hover { background: #555; }
        
        .comp-item { 
            background: #444; padding: 10px; margin-bottom: 10px; border-radius: 5px; 
            cursor: grab; text-align: center; border: 1px solid #555; font-size: 13px;
        }
        .comp-item:hover { background: #555; }
        
        .active-comp { 
            position: absolute; padding: 5px; background: rgba(255,255,255,0.9); 
            color: black; border-radius: 4px; font-weight: bold; font-size: 11px;
            cursor: move; z-index: 100; border: 2px solid #007bff;
        }
        
        svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
        #analyze-btn { 
            position: fixed; bottom: 20px; right: 20px; padding: 15px 30px; 
            background: #28a745; color: white; border: none; border-radius: 50px; 
            font-weight: bold; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <div class="comp-item" onclick="addComp('LED', 2)">🔴 LED</div>
            <div class="comp-item" onclick="addComp('Resistor-300', 2)">📏 Resistor (300Ω)</div>
            <div class="comp-item" onclick="addComp('Resistor-1k', 2)">📏 Resistor (1kΩ)</div>
            <div class="comp-item" onclick="addComp('Resistor-10k', 2)">📏 Resistor (10kΩ)</div>
            <div class="comp-item" onclick="addComp('LDR', 2)">👁️ LDR</div>
            <div class="comp-item" onclick="addComp('Slide-Switch', 3)">⏻ Slide Switch</div>
            <div class="comp-item" onclick="addComp('Potentiometer', 3)">🎡 Variable Resistor</div>
            <hr>
            <small>1. Click component to add.<br>2. Drag to move.<br>3. Click 2 holes to wire.</small>
        </div>
        <div id="canvas">
            <svg id="wire-layer"></svg>
            <div class="breadboard" id="bb">
                <!-- Holes generated by JS -->
            </div>
        </div>
    </div>
    <button id="analyze-btn" onclick="submit()">Analyze Circuit</button>

    <script>
        const bb = document.getElementById('bb');
        const wireLayer = document.getElementById('wire-layer');
        let holes = [];
        let placedComponents = [];
        let connections = [];
        let wireStartHole = null;

        // 1. Generate Breadboard (30 columns x 10 rows)
        for (let i = 0; i < 300; i++) {
            const h = document.createElement('div');
            h.className = 'hole';
            h.id = 'h-' + i;
            h.onclick = () => handleWire(i);
            bb.appendChild(h);
            holes.push(h);
        }

        // 2. Component Logic
        function addComp(type, pins) {
            const id = 'comp-' + Date.now();
            const el = document.createElement('div');
            el.className = 'active-comp';
            el.innerText = type;
            el.id = id;
            el.style.left = '100px';
            el.style.top = '100px';
            
            // Dragging Logic
            let isDragging = false;
            el.onmousedown = () => { isDragging = true; };
            document.onmousemove = (e) => {
                if (isDragging) {
                    el.style.left = (e.clientX - 250) + 'px';
                    el.style.top = (e.clientY - 50) + 'px';
                }
            };
            document.onmouseup = () => { isDragging = false; };
            
            document.getElementById('canvas').appendChild(el);
            placedComponents.push({ id, type, pins });
        }

        // 3. Wiring Logic (Hole to Hole)
        function handleWire(holeIdx) {
            if (wireStartHole === null) {
                wireStartHole = holeIdx;
                holes[holeIdx].style.background = '#007bff';
            } else {
                const start = holes[wireStartHole].getBoundingClientRect();
                const end = holes[holeIdx].getBoundingClientRect();
                const canvas = document.getElementById('canvas').getBoundingClientRect();

                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', start.left - canvas.left + 7);
                line.setAttribute('y1', start.top - canvas.top + 7);
                line.setAttribute('x2', end.left - canvas.left + 7);
                line.setAttribute('y2', end.top - canvas.top + 7);
                line.setAttribute('stroke', '#00ff00');
                line.setAttribute('stroke-width', '3');
                wireLayer.appendChild(line);

                connections.push({ from: wireStartHole, to: holeIdx });
                holes[wireStartHole].style.background = '#bbb';
                wireStartHole = null;
            }
        }

        // 4. Submit to Streamlit
        function submit() {
            const data = {
                components: placedComponents,
                connections: connections
            };
            const json = JSON.stringify(data);
            const url = window.parent.location.origin + window.parent.location.pathname + '?circuit_data=' + encodeURIComponent(json);
            window.parent.location.assign(url);
        }
    </script>
</body>
</html>
"""

components.html(simulator_html, height=600)
