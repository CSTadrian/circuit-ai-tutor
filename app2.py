# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.parse
from google import genai
from google.oauth2 import service_account

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Pro-STEM Interactive Lab", layout="wide")

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

# --- 2. VECTOR ASSETS (Redesigned for 20px Grid alignment) ---
# Each pin/leg is spaced exactly in multiples of 20px to fit the breadboard.
ASSETS = {
    "LED": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="20" width="2" height="15" fill="#aaa"/><path d="M10 20 Q 10 5 20 5 Q 30 5 30 20 Z" fill="#ff4444" opacity="0.9"/><circle cx="20" cy="12" r="4" fill="white" opacity="0.4"/></svg>',
    
    "RES_300": '<svg width="100" height="20" viewBox="0 0 100 20" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="82" height="2" fill="#aaa"/><rect x="30" y="4" width="40" height="12" rx="4" fill="#d2b48c"/><rect x="35" y="4" width="4" height="12" fill="orange"/><rect x="43" y="4" width="4" height="12" fill="orange"/><rect x="51" y="4" width="4" height="12" fill="brown"/></svg>',
    
    "RES_1K": '<svg width="100" height="20" viewBox="0 0 100 20" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="82" height="2" fill="#aaa"/><rect x="30" y="4" width="40" height="12" rx="4" fill="#d2b48c"/><rect x="35" y="4" width="4" height="12" fill="brown"/><rect x="43" y="4" width="4" height="12" fill="black"/><rect x="51" y="4" width="4" height="12" fill="red"/></svg>',
    
    "LDR": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="15" r="12" fill="#cc0000"/><path d="M12 15 L16 11 L20 19 L24 11 L28 19" fill="none" stroke="yellow" stroke-width="1.5"/><rect x="9" y="25" width="2" height="15" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/></svg>',
    
    "SWITCH": '<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="10" width="50" height="20" rx="2" fill="#333"/><rect x="15" y="12" width="15" height="16" fill="#555"/><rect x="18" y="14" width="9" height="12" fill="white" opacity="0.8"/><rect x="9" y="0" width="2" height="10" fill="#aaa"/><rect x="29" y="0" width="2" height="10" fill="#aaa"/><rect x="49" y="0" width="2" height="10" fill="#aaa"/></svg>',
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
        prompt = f"Student built circuit: {decoded_data}. Provide a short Socratic hint on resistance/flow."
        if client:
            response = client.models.generate_content(model="gemini-3.1-pro-preview", contents=prompt)
            st.session_state.feedback = response.text
    except Exception as e:
        pass

# --- 4. UI & SIDEBAR ---
with st.sidebar:
    st.title("🔋 Component Lab")
    st.metric("AI Tokens", st.session_state.tokens)
    st.markdown("Use the simulator on the right. Components snap to the grid automatically.")
    if st.button("Reset Lab State"):
        st.session_state.tokens = 15
        st.session_state.feedback = ""
        st.rerun()

if st.session_state.feedback:
    st.info(f"🤖 **Tutor:** {st.session_state.feedback}")

# --- 5. THE SIMULATOR ENGINE ---
assets_json = json.dumps(ASSETS)

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 220px; background: #333; padding: 15px; border-right: 2px solid #444; z-index: 10; box-shadow: 2px 0 5px rgba(0,0,0,0.5); }}
        #canvas {{ flex-grow: 1; position: relative; background: #1a1a1a; overflow: auto; }}
        
        /* Interactive Toolbar */
        #toolbar {{ position: absolute; top: 15px; left: 15px; background: #333; padding: 8px; border-radius: 8px; display: flex; gap: 10px; z-index: 100; border: 1px solid #555; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }}
        .tool-btn:hover {{ background: #007bff; }}
        .tool-btn:disabled {{ background: #2a2a2a; color: #666; cursor: not-allowed; }}
        
        /* Standard Breadboard Layout */
        .breadboard-container {{ 
            position: absolute; top: 80px; left: 80px; background: #fdfdfd; 
            border-radius: 8px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex; gap: var(--grid); border: 2px solid #e0e0e0;
        }}
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); }}
        .bb-rails {{ grid-template-columns: repeat(2, var(--grid)); gap: 2px; border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; padding: 0 4px; }}
        .bb-main {{ grid-template-columns: repeat(5, var(--grid)); gap: 2px; }}
        .trench {{ width: var(--grid); background: #ddd; box-shadow: inset 2px 0 5px rgba(0,0,0,0.1); }}
        .hole {{ width: 12px; height: 12px; background: #ccc; border-radius: 50%; box-shadow: inset 1px 1px 3px rgba(0,0,0,0.6); margin: 4px; }}
        
        .comp-item {{ background: #444; padding: 10px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #555; font-size: 11px; }}
        .comp-item:hover {{ background: #505050; border-color: #007bff; }}
        
        .active-comp {{ 
            position: absolute; cursor: grab; z-index: 50;
            filter: drop-shadow(2px 4px 4px rgba(0,0,0,0.5));
            transition: transform 0.2s ease, box-shadow 0.2s;
            transform-origin: center center;
        }}
        .active-comp.selected {{ filter: drop-shadow(0px 0px 8px #007bff); }}
        .active-comp:active {{ cursor: grabbing; }}
        
        #analyze-btn {{ position: fixed; bottom: 20px; right: 20px; padding: 15px 30px; background: #28a745; color: white; border: none; border-radius: 50px; font-weight: bold; cursor: pointer; z-index: 100; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h4 style="margin-top:0;">Components</h4>
            <div class="comp-item" onclick="spawnComp('LED')">{ASSETS['LED']}<br>LED</div>
            <div class="comp-item" onclick="spawnComp('RES_300')">{ASSETS['RES_300']}<br>300Ω Resistor</div>
            <div class="comp-item" onclick="spawnComp('RES_1K')">{ASSETS['RES_1K']}<br>1kΩ Resistor</div>
            <div class="comp-item" onclick="spawnComp('LDR')">{ASSETS['LDR']}<br>LDR</div>
            <div class="comp-item" onclick="spawnComp('SWITCH')">{ASSETS['SWITCH']}<br>Switch</div>
        </div>
        <div id="canvas">
            <div id="toolbar">
                <button class="tool-btn" onclick="undo()" id="btn-undo">↶ Undo (Ctrl+Z)</button>
                <button class="tool-btn" onclick="redo()" id="btn-redo">↷ Redo (Ctrl+Y)</button>
                <button class="tool-btn" onclick="rotateSelected()" id="btn-rot" disabled>↻ Rotate 90°</button>
                <button class="tool-btn" onclick="deleteSelected()" id="btn-del" disabled style="background:#dc3545;">✖ Delete (Del)</button>
            </div>
            
            <div class="breadboard-container" id="bb">
                <!-- Left Rails -->
                <div class="bb-section bb-rails" id="rail-L"></div>
                <!-- Main Board Left (a-e) -->
                <div class="bb-section bb-main" id="main-L"></div>
                <!-- Trench -->
                <div class="trench"></div>
                <!-- Main Board Right (f-j) -->
                <div class="bb-section bb-main" id="main-R"></div>
                <!-- Right Rails -->
                <div class="bb-section bb-rails" id="rail-R"></div>
            </div>
            
            <div id="component-layer"></div>
        </div>
    </div>
    <button id="analyze-btn" onclick="submitCircuit()">Analyze My Circuit</button>

    <script>
        const ASSET_MAP = {assets_json};
        const GRID = 20;
        
        let state = [];
        let history = [];
        let historyIndex = -1;
        let selectedId = null;
        let draggingElement = null;
        let dragOffset = {{ x: 0, y: 0 }};

        // --- 1. BUILD BREADBOARD ---
        function createHoles(containerId, cols) {{
            const container = document.getElementById(containerId);
            for (let r = 0; r < 30; r++) {{
                for (let c = 0; c < cols; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    container.appendChild(h);
                }}
            }}
        }}
        createHoles('rail-L', 2);
        createHoles('main-L', 5);
        createHoles('main-R', 5);
        createHoles('rail-R', 2);

        // --- 2. HISTORY MANAGEMENT ---
        function saveState() {{
            history = history.slice(0, historyIndex + 1);
            history.push(JSON.parse(JSON.stringify(state)));
            historyIndex++;
            updateUI();
        }}

        function loadState() {{
            state = JSON.parse(JSON.stringify(history[historyIndex]));
            renderComponents();
            updateUI();
        }}

        function undo() {{ if (historyIndex > 0) {{ historyIndex--; loadState(); }} }}
        function redo() {{ if (historyIndex < history.length - 1) {{ historyIndex++; loadState(); }} }}

        // --- 3. COMPONENT LOGIC ---
        function spawnComp(type) {{
            const newComp = {{ id: 'comp_' + Date.now(), type: type, x: 100, y: 100, rot: 0 }};
            state.push(newComp);
            selectedId = newComp.id;
            saveState();
        }}

        function renderComponents() {{
            const layer = document.getElementById('component-layer');
            layer.innerHTML = ''; // Clear layer
            
            state.forEach(comp => {{
                const el = document.createElement('div');
                el.className = 'active-comp' + (comp.id === selectedId ? ' selected' : '');
                el.id = comp.id;
                el.innerHTML = ASSET_MAP[comp.type];
                el.style.left = comp.x + 'px';
                el.style.top = comp.y + 'px';
                el.style.transform = `rotate(${{comp.rot}}deg)`;
                
                el.onmousedown = (e) => startDrag(e, comp);
                layer.appendChild(el);
            }});
        }}

        // --- 4. INTERACTION ---
        function startDrag(e, comp) {{
            if (e.button !== 0) return; // Only left click
            selectedId = comp.id;
            draggingElement = comp;
            dragOffset.x = e.clientX - comp.x;
            dragOffset.y = e.clientY - comp.y;
            renderComponents();
            updateUI();
        }}

        document.onmousemove = (e) => {{
            if (!draggingElement) return;
            // Free movement during drag
            let rawX = e.clientX - dragOffset.x;
            let rawY = e.clientY - dragOffset.y;
            document.getElementById(draggingElement.id).style.left = rawX + 'px';
            document.getElementById(draggingElement.id).style.top = rawY + 'px';
        }};

        document.onmouseup = (e) => {{
            if (!draggingElement) return;
            
            // Snap to 20px Grid on drop
            let rawX = e.clientX - dragOffset.x;
            let rawY = e.clientY - dragOffset.y;
            draggingElement.x = Math.round(rawX / GRID) * GRID;
            draggingElement.y = Math.round(rawY / GRID) * GRID;
            
            draggingElement = null;
            saveState(); // Save after dropping
        }};

        // Deselect if clicking canvas background
        document.getElementById('canvas').onmousedown = (e) => {{
            if(e.target.id === 'canvas' || e.target.classList.contains('hole')) {{
                selectedId = null;
                renderComponents();
                updateUI();
            }}
        }};

        // --- 5. TOOLBAR & SHORTCUTS ---
        function rotateSelected() {{
            if (!selectedId) return;
            const comp = state.find(c => c.id === selectedId);
            comp.rot = (comp.rot + 90) % 360;
            saveState();
        }}

        function deleteSelected() {{
            if (!selectedId) return;
            state = state.filter(c => c.id !== selectedId);
            selectedId = null;
            saveState();
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
            if (e.ctrlKey && e.key === 'z') undo();
            if (e.ctrlKey && e.key === 'y') redo();
        }});

        function updateUI() {{
            document.getElementById('btn-rot').disabled = !selectedId;
            document.getElementById('btn-del').disabled = !selectedId;
            document.getElementById('btn-undo').disabled = historyIndex <= 0;
            document.getElementById('btn-redo').disabled = historyIndex >= history.length - 1;
        }}

        // --- 6. SUBMISSION ---
        function submitCircuit() {{
            // Clean state data for python backend
            const cleanData = state.map(c => ({{ type: c.type, x: c.x, y: c.y, rot: c.rot }}));
            const url = window.parent.location.origin + window.parent.location.pathname + '?circuit_data=' + encodeURIComponent(JSON.stringify(cleanData));
            window.parent.location.assign(url);
        }}

        // Init blank state
        saveState();
    </script>
</body>
</html>
"""

components.html(simulator_html, height=750)
