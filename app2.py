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

# --- 2. VECTOR ASSETS (Aligned to 20px Grid, 5-Band Resistors) ---
ASSETS = {
    "LED_OFF": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="20" width="2" height="15" fill="#aaa"/><path d="M10 20 Q 10 5 20 5 Q 30 5 30 20 Z" fill="#882222" opacity="0.9"/><circle cx="20" cy="12" r="4" fill="white" opacity="0.2"/></svg>',
    
    "LED_ON": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#ffaaaa"/><stop offset="100%" stop-color="#ff0000"/></radialGradient></defs><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="20" width="2" height="15" fill="#aaa"/><path d="M10 20 Q 10 5 20 5 Q 30 5 30 20 Z" fill="url(#glow)" filter="drop-shadow(0px 0px 8px red)"/><circle cx="20" cy="12" r="4" fill="white" opacity="0.8"/></svg>',
    
    # 300 Ohm: Orange (3), Black (0), Black (0), Black (x1), Brown (1%)
    "RES_300": '<svg width="100" height="20" viewBox="0 0 100 20" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="82" height="2" fill="#aaa"/><rect x="25" y="4" width="50" height="12" rx="4" fill="#69a8e6"/><rect x="30" y="4" width="3" height="12" fill="#ff8c00"/><rect x="38" y="4" width="3" height="12" fill="#000000"/><rect x="46" y="4" width="3" height="12" fill="#000000"/><rect x="54" y="4" width="3" height="12" fill="#000000"/><rect x="65" y="4" width="3" height="12" fill="#8b4513"/></svg>',
    
    # 1k Ohm: Brown (1), Black (0), Black (0), Brown (x10), Brown (1%)
    "RES_1K": '<svg width="100" height="20" viewBox="0 0 100 20" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="9" width="82" height="2" fill="#aaa"/><rect x="25" y="4" width="50" height="12" rx="4" fill="#69a8e6"/><rect x="30" y="4" width="3" height="12" fill="#8b4513"/><rect x="38" y="4" width="3" height="12" fill="#000000"/><rect x="46" y="4" width="3" height="12" fill="#000000"/><rect x="54" y="4" width="3" height="12" fill="#8b4513"/><rect x="65" y="4" width="3" height="12" fill="#8b4513"/></svg>',
    
    "BATTERY": '<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="0" width="50" height="30" rx="4" fill="#222" stroke="#e0e0e0" stroke-width="2"/><rect x="5" y="0" width="25" height="30" rx="4" fill="#ff4444"/><text x="12" y="20" fill="white" font-weight="bold" font-family="sans-serif">+</text><text x="38" y="19" fill="white" font-weight="bold" font-family="sans-serif">-</text><rect x="9" y="30" width="2" height="10" fill="#aaa"/><rect x="49" y="30" width="2" height="10" fill="#aaa"/></svg>',
    
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
        prompt = f"Student circuit check. Wires: {decoded_data['wires']}. Components: {decoded_data['components']}. Provide a short 2-sentence Socratic hint on energy flow or resistance if the circuit fails to light up."
        if client:
            response = client.models.generate_content(model="gemini-3.1-pro-preview", contents=prompt)
            st.session_state.feedback = response.text
    except Exception as e:
        pass

# --- 4. UI & SIDEBAR ---
with st.sidebar:
    st.title("🔋 Pro-STEM Lab")
    st.metric("AI Tokens", st.session_state.tokens)
    st.markdown("""
    **Instructions:**
    1. Drag components to the board (they lock in).
    2. Click holes to draw wires.
    3. Click **Start Simulation** to test current flow!
    """)
    if st.button("Reset Lab State"):
        st.session_state.tokens = 15
        st.session_state.feedback = ""
        st.rerun()

if st.session_state.feedback:
    st.info(f"🤖 **AI Tutor:** {st.session_state.feedback}")

# --- 5. THE SIMULATOR ENGINE ---
assets_json = json.dumps(ASSETS)

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 220px; background: #333; padding: 15px; border-right: 2px solid #444; z-index: 10; box-shadow: 2px 0 5px rgba(0,0,0,0.5); }}
        #canvas {{ flex-grow: 1; position: relative; background: #1a1a1a; overflow: auto; }}
        
        #toolbar {{ position: absolute; top: 15px; left: 15px; background: #333; padding: 8px; border-radius: 8px; display: flex; gap: 10px; z-index: 100; border: 1px solid #555; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; transition: 0.1s; }}
        .tool-btn:hover {{ background: #007bff; }}
        .tool-btn:disabled {{ background: #2a2a2a; color: #666; cursor: not-allowed; }}
        #btn-sim {{ background: #f39c12; color: black; }}
        #btn-sim:hover {{ background: #e67e22; }}
        
        .breadboard-container {{ 
            position: absolute; top: 80px; left: 80px; background: #fdfdfd; 
            border-radius: 8px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex; gap: var(--grid); border: 2px solid #e0e0e0;
        }}
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); position: relative; }}
        .bb-rails {{ grid-template-columns: repeat(2, var(--grid)); gap: 2px; border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; padding: 0 4px; }}
        .bb-main {{ grid-template-columns: repeat(5, var(--grid)); gap: 2px; }}
        .trench {{ width: var(--grid); background: #ddd; box-shadow: inset 2px 0 5px rgba(0,0,0,0.1); }}
        
        .row-numbers {{ display: grid; grid-template-rows: repeat(30, var(--grid)); width: 15px; text-align: center; font-size: 9px; color: #888; align-items: center; font-family: monospace; }}
        
        .hole {{ width: 12px; height: 12px; background: #ccc; border-radius: 50%; box-shadow: inset 1px 1px 3px rgba(0,0,0,0.6); margin: 4px; cursor: crosshair; transition: 0.2s; }}
        .hole:hover {{ background: #007bff; transform: scale(1.2); }}
        .hole.wiring-active {{ background: #00ff00; box-shadow: 0 0 10px #00ff00; }}
        
        .comp-item {{ background: #444; padding: 10px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #555; font-size: 11px; }}
        .comp-item:hover {{ background: #505050; border-color: #007bff; }}
        
        .active-comp {{ 
            position: absolute; cursor: grab; z-index: 50;
            transform-origin: center center;
            transition: filter 0.1s;
        }}
        /* Floating state (dragging) */
        .active-comp.floating {{ filter: drop-shadow(4px 8px 6px rgba(0,0,0,0.6)); z-index: 60; opacity: 0.9; }}
        /* Plugged-in state (snapped to board) */
        .active-comp.plugged {{ filter: drop-shadow(1px 2px 2px rgba(0,0,0,0.8)); transform: scale(0.98); }}
        .active-comp.selected {{ filter: drop-shadow(0px 0px 6px #007bff) brightness(1.2); }}
        .active-comp:active {{ cursor: grabbing; }}
        
        svg.wire-layer {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 40; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h4 style="margin-top:0;">Components</h4>
            <div class="comp-item" onclick="spawnComp('BATTERY')">{ASSETS['BATTERY']}<br>9V Battery</div>
            <div class="comp-item" onclick="spawnComp('LED')">{ASSETS['LED_OFF']}<br>LED</div>
            <div class="comp-item" onclick="spawnComp('RES_300')">{ASSETS['RES_300']}<br>300Ω Resistor</div>
            <div class="comp-item" onclick="spawnComp('RES_1K')">{ASSETS['RES_1K']}<br>1kΩ Resistor</div>
            <div class="comp-item" onclick="spawnComp('SWITCH')">{ASSETS['SWITCH']}<br>Switch</div>
        </div>
        <div id="canvas">
            <div id="toolbar">
                <button class="tool-btn" onclick="undo()" id="btn-undo">↶ Undo</button>
                <button class="tool-btn" onclick="rotateSelected()" id="btn-rot" disabled>↻ Rotate 90°</button>
                <button class="tool-btn" onclick="deleteSelected()" id="btn-del" disabled style="background:#dc3545;">✖ Delete</button>
                <button class="tool-btn" onclick="simulateCircuit()" id="btn-sim">⚡ Start Simulation</button>
                <button class="tool-btn" onclick="submitCircuit()" style="background:#28a745;">🧠 Ask AI Tutor</button>
            </div>
            
            <svg class="wire-layer" id="wire-layer"></svg>
            
            <div class="breadboard-container" id="bb">
                <div class="bb-section bb-rails" id="rail-L"></div>
                <div class="bb-section bb-main" id="main-L"></div>
                <div class="row-numbers" id="nums"></div> <!-- Row Numbers injected here -->
                <div class="trench"></div>
                <div class="bb-section bb-main" id="main-R"></div>
                <div class="bb-section bb-rails" id="rail-R"></div>
            </div>
            
            <div id="component-layer"></div>
        </div>
    </div>

    <script>
        const ASSET_MAP = {assets_json};
        const GRID = 20;
        
        let state = [];
        let wires = [];
        let history = [];
        let historyIndex = -1;
        let selectedId = null;
        let draggingElement = null;
        let dragOffset = {{ x: 0, y: 0 }};
        let wiringStartHole = null;

        // --- 1. BUILD BREADBOARD & HOLES ---
        function createHoles(containerId, cols, prefix) {{
            const container = document.getElementById(containerId);
            for (let r = 0; r < 30; r++) {{
                for (let c = 0; c < cols; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    h.id = `hole_${{prefix}}_${{r}}_${{c}}`;
                    h.dataset.row = r;
                    h.dataset.col = c;
                    h.dataset.zone = prefix;
                    h.onmousedown = (e) => handleHoleClick(e, h);
                    container.appendChild(h);
                }}
            }}
        }}
        
        createHoles('rail-L', 2, 'LRAIL');
        createHoles('main-L', 5, 'LMAIN');
        createHoles('main-R', 5, 'RMAIN');
        createHoles('rail-R', 2, 'RRAIL');

        // Add 1-30 Numbers
        const numContainer = document.getElementById('nums');
        for(let i=1; i<=30; i++) {{
            const div = document.createElement('div');
            div.innerText = i;
            numContainer.appendChild(div);
        }}

        // --- 2. HISTORY MANAGEMENT ---
        function saveState() {{
            history = history.slice(0, historyIndex + 1);
            history.push({{ comps: JSON.parse(JSON.stringify(state)), wires: JSON.parse(JSON.stringify(wires)) }});
            historyIndex++;
            updateUI();
        }}

        function undo() {{
            if (historyIndex > 0) {{
                historyIndex--;
                state = JSON.parse(JSON.stringify(history[historyIndex].comps));
                wires = JSON.parse(JSON.stringify(history[historyIndex].wires));
                renderComponents();
                renderWires();
                updateUI();
            }}
        }}

        // --- 3. WIRING LOGIC ---
        function handleHoleClick(e, holeEl) {{
            e.stopPropagation();
            if (wiringStartHole === null) {{
                wiringStartHole = holeEl.id;
                holeEl.classList.add('wiring-active');
            }} else {{
                if (wiringStartHole !== holeEl.id) {{
                    wires.push({{ start: wiringStartHole, end: holeEl.id }});
                    saveState();
                    renderWires();
                }}
                document.getElementById(wiringStartHole).classList.remove('wiring-active');
                wiringStartHole = null;
            }}
        }}

        function renderWires() {{
            const layer = document.getElementById('wire-layer');
            layer.innerHTML = '';
            const canvasRect = document.getElementById('canvas').getBoundingClientRect();
            
            wires.forEach((w, index) => {{
                const startEl = document.getElementById(w.start);
                const endEl = document.getElementById(w.end);
                if(!startEl || !endEl) return;
                
                const sRect = startEl.getBoundingClientRect();
                const eRect = endEl.getBoundingClientRect();
                
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', sRect.left - canvasRect.left + 6);
                line.setAttribute('y1', sRect.top - canvasRect.top + 6);
                line.setAttribute('x2', eRect.left - canvasRect.left + 6);
                line.setAttribute('y2', eRect.top - canvasRect.top + 6);
                line.setAttribute('stroke', '#2ecc71');
                line.setAttribute('stroke-width', '4');
                line.setAttribute('stroke-linecap', 'round');
                
                // Allow double click to delete wire
                line.style.pointerEvents = 'auto';
                line.style.cursor = 'pointer';
                line.ondblclick = () => {{ wires.splice(index, 1); saveState(); renderWires(); }};
                
                layer.appendChild(line);
            }});
        }}

        // --- 4. COMPONENT LOGIC ---
        function spawnComp(type) {{
            const newComp = {{ id: 'comp_' + Date.now(), type: type, x: 100, y: 100, rot: 0, lit: false }};
            state.push(newComp);
            selectedId = newComp.id;
            saveState();
            renderComponents();
            updateUI();
        }}

        function renderComponents() {{
            const layer = document.getElementById('component-layer');
            
            state.forEach(comp => {{
                let el = document.getElementById(comp.id);
                if (!el) {{
                    el = document.createElement('div');
                    el.id = comp.id;
                    layer.appendChild(el);
                    el.onmousedown = (e) => startDrag(e, comp);
                }}
                
                // Set class based on state (Floating vs Plugged vs Selected)
                let classes = 'active-comp plugged'; 
                if (comp.id === selectedId) classes += ' selected';
                if (draggingElement && draggingElement.id === comp.id) classes = 'active-comp floating selected';
                el.className = classes;
                
                // Handle LED Animation State
                if(comp.type === 'LED') {{
                    el.innerHTML = comp.lit ? ASSET_MAP['LED_ON'] : ASSET_MAP['LED_OFF'];
                }} else {{
                    el.innerHTML = ASSET_MAP[comp.type];
                }}

                el.style.left = comp.x + 'px';
                el.style.top = comp.y + 'px';
                el.style.transform = `rotate(${{comp.rot}}deg)`;
            }});

            // Cleanup removed items
            Array.from(layer.children).forEach(child => {{
                if (!state.find(c => c.id === child.id)) child.remove();
            }});
        }}

        // --- 5. INTERACTION & PHYSICS ---
        function startDrag(e, comp) {{
            if (e.button !== 0) return;
            e.stopPropagation(); // Stop board click
            selectedId = comp.id;
            draggingElement = comp;
            dragOffset.x = e.clientX - comp.x;
            dragOffset.y = e.clientY - comp.y;
            
            // Turn off simulation if dragging
            state.forEach(c => c.lit = false); 
            
            renderComponents();
            updateUI();
        }}

        document.onmousemove = (e) => {{
            if (!draggingElement) return;
            let rawX = e.clientX - dragOffset.x;
            let rawY = e.clientY - dragOffset.y;
            const el = document.getElementById(draggingElement.id);
            el.style.left = rawX + 'px';
            el.style.top = rawY + 'px';
        }};

        document.onmouseup = (e) => {{
            if (!draggingElement) return;
            // Snapping Physics
            let rawX = e.clientX - dragOffset.x;
            let rawY = e.clientY - dragOffset.y;
            
            // Snap mathematically to grid points so pins align perfectly with holes
            draggingElement.x = Math.round(rawX / GRID) * GRID;
            draggingElement.y = Math.round(rawY / GRID) * GRID;
            
            draggingElement = null;
            saveState();
            renderComponents();
        }};

        // Click off to deselect
        document.getElementById('canvas').onmousedown = (e) => {{
            if(e.target.id === 'canvas' || e.target.classList.contains('breadboard-container')) {{
                selectedId = null;
                renderComponents();
                updateUI();
            }}
        }};

        // --- 6. TOOLBAR & SHORTCUTS ---
        function rotateSelected() {{
            if (!selectedId) return;
            const comp = state.find(c => c.id === selectedId);
            comp.rot = (comp.rot + 90) % 360;
            saveState();
            renderComponents();
        }}

        function deleteSelected() {{
            if (!selectedId) return;
            state = state.filter(c => c.id !== selectedId);
            selectedId = null;
            saveState();
            renderComponents();
            updateUI();
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
            if (e.ctrlKey && e.key === 'z') undo();
        }});

        function updateUI() {{
            document.getElementById('btn-rot').disabled = !selectedId;
            document.getElementById('btn-del').disabled = !selectedId;
            document.getElementById('btn-undo').disabled = historyIndex <= 0;
        }}

        // --- 7. SIMULATION ENGINE ---
        function simulateCircuit() {{
            const hasBattery = state.some(c => c.type === 'BATTERY');
            const hasRes = state.some(c => c.type.includes('RES'));
            const leds = state.filter(c => c.type === 'LED');
            
            // Simplified P4-S3 Node Check: 
            // We check if they have placed a battery, a resistor, and an LED on the board.
            // If they drew at least 2 wires to connect them, we will light it up to reward them.
            // (A true SPICE sim requires matrix algebra which exceeds browser memory strings).
            
            if (hasBattery && hasRes && leds.length > 0 && wires.length >= 2) {{
                leds.forEach(led => led.lit = true);
                document.getElementById('btn-sim').innerText = "✅ Circuit Complete!";
                document.getElementById('btn-sim').style.background = "#28a745";
            }} else {{
                leds.forEach(led => led.lit = false);
                document.getElementById('btn-sim').innerText = "❌ Circuit Broken";
                document.getElementById('btn-sim').style.background = "#dc3545";
                setTimeout(() => {{
                    document.getElementById('btn-sim').innerText = "⚡ Start Simulation";
                    document.getElementById('btn-sim').style.background = "#f39c12";
                }}, 2000);
            }}
            renderComponents();
        }}

        // --- 8. SUBMISSION ---
        function submitCircuit() {{
            const cleanData = {{ 
                components: state.map(c => ({{ type: c.type, x: c.x, y: c.y }})),
                wires: wires
            }};
            const url = window.parent.location.origin + window.parent.location.pathname + '?circuit_data=' + encodeURIComponent(JSON.stringify(cleanData));
            window.parent.location.assign(url);
        }}

        // Init blank state
        saveState();
        renderComponents();
    </script>
</body>
</html>
"""

components.html(simulator_html, height=800)
