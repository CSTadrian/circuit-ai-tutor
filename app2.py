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

# --- 2. VECTOR ASSETS (Grid Aligned to 20px) ---
ASSETS = {
    "LED_OFF": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/><path d="M10 25 Q 10 5 20 5 Q 30 5 30 25 Z" fill="#882222" opacity="0.9"/><circle cx="20" cy="12" r="4" fill="white" opacity="0.2"/></svg>',
    
    "LED_ON": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#ffaaaa"/><stop offset="100%" stop-color="#ff0000"/></radialGradient></defs><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/><path d="M10 25 Q 10 5 20 5 Q 30 5 30 25 Z" fill="url(#glow)" filter="drop-shadow(0px 0px 8px red)"/><circle cx="20" cy="12" r="4" fill="white" opacity="0.8"/></svg>',
    
    "LED_BROKEN": '<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/><path d="M10 25 Q 10 5 20 5 Q 30 5 30 25 Z" fill="#333333" opacity="0.9"/><path d="M18 5 L23 12 L17 18 L22 25" stroke="#000" stroke-width="2" fill="none"/></svg>',
    
    "RES_300": '<svg width="80" height="20" viewBox="0 0 80 20" xmlns="http://www.w3.org/2000/svg"><rect x="10" y="9" width="60" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="28" y="4" width="6" height="12" fill="#ff8c00"/><rect x="40" y="4" width="6" height="12" fill="#000000"/><rect x="52" y="4" width="6" height="12" fill="#8b4513"/></svg>',
    
    "RES_1K": '<svg width="80" height="20" viewBox="0 0 80 20" xmlns="http://www.w3.org/2000/svg"><rect x="10" y="9" width="60" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="28" y="4" width="6" height="12" fill="#8b4513"/><rect x="40" y="4" width="6" height="12" fill="#000000"/><rect x="52" y="4" width="6" height="12" fill="#ff0000"/></svg>',
    
    "SWITCH": '<svg width="60" height="20" viewBox="0 0 60 20" xmlns="http://www.w3.org/2000/svg"><rect x="10" y="9" width="2" height="11" fill="#aaa"/><rect x="30" y="9" width="2" height="11" fill="#aaa"/><rect x="50" y="9" width="2" height="11" fill="#aaa"/><rect x="5" y="0" width="50" height="14" rx="2" fill="#333"/><rect x="15" y="2" width="12" height="10" fill="#555"/></svg>',

    "BATTERY": '<svg width="40" height="60" viewBox="0 0 40 60" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="36" height="44" rx="2" fill="#222" stroke="#e0e0e0" stroke-width="1"/><rect x="2" y="2" width="18" height="44" rx="2" fill="#ff4444"/><text x="6" y="28" fill="white" font-weight="bold" font-size="14">+</text><text x="24" y="28" fill="white" font-weight="bold" font-size="14">-</text><rect x="9" y="46" width="2" height="14" fill="#aaa"/><rect x="29" y="46" width="2" height="14" fill="#aaa"/></svg>',
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

# --- 4. THE SIMULATOR ENGINE ---
assets_json = json.dumps(ASSETS)

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; --bb-gap: 2px; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 220px; background: #333; padding: 15px; border-right: 2px solid #444; z-index: 10; box-shadow: 2px 0 5px rgba(0,0,0,0.5); }}
        #canvas {{ flex-grow: 1; position: relative; background: #1a1a1a; overflow: auto; }}
        
        #toolbar {{ position: absolute; top: 15px; left: 15px; background: #333; padding: 8px; border-radius: 8px; display: flex; gap: 10px; z-index: 100; border: 1px solid #555; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; transition: 0.1s; }}
        .tool-btn:hover {{ background: #007bff; }}
        
        .breadboard-container {{ 
            position: absolute; top: 80px; left: 80px; background: #fdfdfd; 
            border-radius: 8px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex; gap: var(--bb-gap); border: 2px solid #e0e0e0;
        }}
        
        .bb-wrapper {{ display: flex; flex-direction: column; }}
        .col-headers {{ display: grid; grid-template-columns: repeat(5, var(--grid)); font-size: 11px; color: #555; text-align: center; font-weight: bold; font-family: sans-serif; margin-bottom: 4px; gap: var(--bb-gap); }}
        
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); position: relative; }}
        .bb-rails {{ grid-template-columns: repeat(2, var(--grid)); gap: var(--bb-gap); border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; padding: 0 4px; margin-top: 18px; }}
        .bb-main {{ grid-template-columns: repeat(5, var(--grid)); gap: var(--bb-gap); }}
        .trench {{ width: var(--grid); background: #eee; box-shadow: inset 0 0 5px rgba(0,0,0,0.1); margin-top: 18px; }}
        
        .row-numbers {{ display: grid; grid-template-rows: repeat(30, var(--grid)); width: 15px; text-align: center; font-size: 9px; color: #888; align-items: center; font-family: monospace; margin-top: 18px; }}
        
        .hole {{ width: 12px; height: 12px; background: #ccc; border-radius: 50%; box-shadow: inset 1px 1px 3px rgba(0,0,0,0.6); margin: 4px; cursor: crosshair; transition: 0.2s; }}
        .hole:hover {{ background: #007bff; transform: scale(1.2); }}
        .hole.wiring-active {{ background: #00ff00 !important; box-shadow: 0 0 10px #00ff00; }}
        .hole.connected {{ background: #add8e6 !important; box-shadow: 0 0 6px #add8e6; }}
        
        .comp-item {{ background: #444; padding: 10px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #555; font-size: 11px; display: flex; flex-direction: column; align-items: center; }}
        
        .active-comp {{ position: absolute; cursor: grab; z-index: 50; transform-origin: center center; }}
        .active-comp.selected {{ filter: drop-shadow(0px 0px 6px #007bff) brightness(1.2); }}
        
        .pin-collider {{ position: absolute; width: 4px; height: 4px; opacity: 0; pointer-events: none; }}
        
        svg.overlay-layer {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }}
        #wire-layer {{ z-index: 40; }}
        #flow-layer {{ z-index: 45; }}

        .flow-line {{ stroke-dasharray: 10 10; animation: flowAnim 0.5s linear infinite; }}
        @keyframes flowAnim {{ from {{ stroke-dashoffset: 20; }} to {{ stroke-dashoffset: 0; }} }}
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
                <button class="tool-btn" onclick="toggleSimulation()" id="btn-sim" style="background:#f39c12; color:black;">⚡ Start Simulation</button>
            </div>
            
            <svg class="overlay-layer" id="wire-layer"></svg>
            <svg class="overlay-layer" id="flow-layer"></svg>
            
            <div class="breadboard-container" id="bb">
                <div class="bb-section bb-rails" id="rail-L"></div>
                <div class="bb-wrapper">
                    <div class="col-headers"><div>a</div><div>b</div><div>c</div><div>d</div><div>e</div></div>
                    <div class="bb-section bb-main" id="main-L"></div>
                </div>
                <div class="row-numbers" id="nums"></div>
                <div class="trench"></div>
                <div class="bb-wrapper">
                    <div class="col-headers"><div>f</div><div>g</div><div>h</div><div>i</div><div>j</div></div>
                    <div class="bb-section bb-main" id="main-R"></div>
                </div>
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
        let isSimulating = false;

        function createHoles(containerId, cols, prefix) {{
            const container = document.getElementById(containerId);
            for (let r = 0; r < 30; r++) {{
                for (let c = 0; c < cols; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    h.id = `hole_${{prefix}}_${{r}}_${{c}}`;
                    h.onmousedown = (e) => handleHoleClick(e, h);
                    container.appendChild(h);
                }}
            }}
        }}
        
        createHoles('rail-L', 2, 'LRAIL');
        createHoles('main-L', 5, 'LMAIN');
        createHoles('main-R', 5, 'RMAIN');
        createHoles('rail-R', 2, 'RRAIL');

        const numContainer = document.getElementById('nums');
        for(let i=1; i<=30; i++) {{
            const div = document.createElement('div'); div.innerText = i; numContainer.appendChild(div);
        }}

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
                renderComponents(); renderWires(); updateUI();
            }}
        }}

        function handleHoleClick(e, holeEl) {{
            e.stopPropagation();
            if (wiringStartHole === null) {{
                wiringStartHole = holeEl.id;
                holeEl.classList.add('wiring-active');
            }} else {{
                if (wiringStartHole !== holeEl.id) {{
                    wires.push({{ start: wiringStartHole, end: holeEl.id }});
                    saveState(); renderWires();
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
                const sRect = document.getElementById(w.start).getBoundingClientRect();
                const eRect = document.getElementById(w.end).getBoundingClientRect();
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', sRect.left - canvasRect.left + 6);
                line.setAttribute('y1', sRect.top - canvasRect.top + 6);
                line.setAttribute('x2', eRect.left - canvasRect.left + 6);
                line.setAttribute('y2', eRect.top - canvasRect.top + 6);
                line.setAttribute('stroke', '#2ecc71');
                line.setAttribute('stroke-width', '4');
                line.setAttribute('stroke-linecap', 'round');
                line.style.pointerEvents = 'auto';
                line.style.cursor = 'pointer';
                line.ondblclick = () => {{ wires.splice(index, 1); saveState(); renderWires(); }};
                layer.appendChild(line);
            }});
        }}

        function getPinsForComponent(type) {{
            if (type.includes('RES')) return [{{x: 10, y: 10}}, {{x: 70, y: 10}}];
            if (type === 'SWITCH') return [{{x: 10, y: 10}}, {{x: 30, y: 10}}, {{x: 50, y: 10}}];
            if (type === 'BATTERY') return [{{x: 10, y: 50}}, {{x: 30, y: 50}}];
            return [{{x: 10, y: 30}}, {{x: 30, y: 30}}];
        }}

        function spawnComp(type) {{
            state.push({{ id: 'comp_' + Date.now(), type: type, x: 100, y: 100, rot: 0, lit: false, broken: false, pins: getPinsForComponent(type), connectedHoles: [] }});
            selectedId = state[state.length-1].id;
            saveState(); renderComponents(); updateUI();
        }}

        function renderComponents() {{
            const layer = document.getElementById('component-layer');
            state.forEach(comp => {{
                let el = document.getElementById(comp.id);
                if (!el) {{
                    el = document.createElement('div');
                    el.id = comp.id; layer.appendChild(el);
                    el.onmousedown = (e) => startDrag(e, comp);
                }}
                
                el.className = `active-comp ${{comp.id === selectedId ? 'selected' : ''}}`;
                if (comp.type === 'LED') {{
                    el.innerHTML = comp.broken ? ASSET_MAP['LED_BROKEN'] : (comp.lit ? ASSET_MAP['LED_ON'] : ASSET_MAP['LED_OFF']);
                }} else {{ el.innerHTML = ASSET_MAP[comp.type]; }}

                el.querySelectorAll('.pin-collider').forEach(p => p.remove());
                comp.pins.forEach(p => {{
                    let dot = document.createElement('div');
                    dot.className = 'pin-collider';
                    dot.style.left = p.x + 'px'; dot.style.top = p.y + 'px';
                    el.appendChild(dot);
                }});

                el.style.left = comp.x + 'px'; el.style.top = comp.y + 'px';
                el.style.transform = `rotate(${{comp.rot}}deg)`;
            }});
            
            Array.from(layer.children).forEach(child => {{ if (!state.find(c => c.id === child.id)) child.remove(); }});
            updateConnections();
        }}

        function updateConnections() {{
            const holes = Array.from(document.querySelectorAll('.hole'));
            holes.forEach(h => h.classList.remove('connected'));
            const canvasRect = document.getElementById('canvas').getBoundingClientRect();

            state.forEach(comp => {{
                comp.connectedHoles = [];
                if(draggingElement && draggingElement.id === comp.id) return;

                const colEls = document.getElementById(comp.id).querySelectorAll('.pin-collider');
                colEls.forEach(colEl => {{
                    const cRect = colEl.getBoundingClientRect();
                    const px = cRect.left - canvasRect.left + 2; 
                    const py = cRect.top - canvasRect.top + 2;

                    let foundHole = null;
                    holes.forEach(h => {{
                        const hRect = h.getBoundingClientRect();
                        if (Math.abs(px - (hRect.left - canvasRect.left + 6)) < 8 && Math.abs(py - (hRect.top - canvasRect.top + 6)) < 8) {{
                            h.classList.add('connected');
                            foundHole = h.id;
                        }}
                    }});
                    comp.connectedHoles.push(foundHole);
                }});
            }});
        }}

        function simulateCircuit() {{
            updateConnections();
            let graph = {{}};
            const addEdge = (u, v, weight) => {{
                if(!u || !v) return;
                if(!graph[u]) graph[u] = []; if(!graph[v]) graph[v] = [];
                graph[u].push({{ to: v, weight }}); graph[v].push({{ to: u, weight }});
            }};

            for(let r=0; r<30; r++) {{
                for(let c=0; c<4; c++) {{
                    addEdge(`hole_LMAIN_${{r}}_${{c}}`, `hole_LMAIN_${{r}}_${{c+1}}`, 0);
                    addEdge(`hole_RMAIN_${{r}}_${{c}}`, `hole_RMAIN_${{r}}_${{c+1}}`, 0);
                }}
                if(r<29) {{
                    addEdge(`hole_LRAIL_${{r}}_0`, `hole_LRAIL_${{r+1}}_0`, 0);
                    addEdge(`hole_LRAIL_${{r}}_1`, `hole_LRAIL_${{r+1}}_1`, 0);
                    addEdge(`hole_RRAIL_${{r}}_0`, `hole_RRAIL_${{r+1}}_0`, 0);
                    addEdge(`hole_RRAIL_${{r}}_1`, `hole_RRAIL_${{r+1}}_1`, 0);
                }}
            }}

            wires.forEach(w => addEdge(w.start, w.end, 0));

            let startHole = null, endHole = null;
            state.forEach(c => {{
                if(c.connectedHoles.includes(null) || c.connectedHoles.length === 0) return;
                if(c.type === 'BATTERY') {{ startHole = c.connectedHoles[0]; endHole = c.connectedHoles[1]; }}
                else if(c.type.includes('RES')) addEdge(c.connectedHoles[0], c.connectedHoles[1], 100);
                else if(c.type === 'SWITCH') {{ addEdge(c.connectedHoles[0], c.connectedHoles[1], 0); addEdge(c.connectedHoles[1], c.connectedHoles[2], 0); }}
                else if(c.type === 'LED') addEdge(c.connectedHoles[0], c.connectedHoles[1], 10);
            }});

            if(!startHole || !endHole) return {{ success: false }};

            let queue = [{{ id: startHole, path: [startHole], weight: 0 }}];
            let visited = new Set();
            let validPath = null;

            while(queue.length > 0) {{
                let curr = queue.shift();
                if(curr.id === endHole) {{ validPath = curr; break; }}
                if(visited.has(curr.id)) continue;
                visited.add(curr.id);

                (graph[curr.id] || []).forEach(edge => {{
                    if(!visited.has(edge.to)) queue.push({{ id: edge.to, path: [...curr.path, edge.to], weight: curr.weight + edge.weight }});
                }});
            }}
            return validPath ? {{ success: true, pathNodes: validPath.path, weight: validPath.weight }} : {{ success: false }};
        }}

        function drawFlow(pathNodes) {{
            const layer = document.getElementById('flow-layer'); layer.innerHTML = '';
            const canvasRect = document.getElementById('canvas').getBoundingClientRect();
            let pathData = "";

            for(let i=0; i<pathNodes.length; i++) {{
                const h = document.getElementById(pathNodes[i]);
                if(!h) continue;
                const r = h.getBoundingClientRect();
                const x = r.left - canvasRect.left + 6;
                const y = r.top - canvasRect.top + 6;
                pathData += (i === 0 ? `M ${{x}} ${{y}} ` : `L ${{x}} ${{y}} `);
            }}

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathData); path.setAttribute('fill', 'none');
            path.setAttribute('stroke', '#ffff00'); path.setAttribute('stroke-width', '4');
            path.setAttribute('stroke-linecap', 'round'); path.setAttribute('stroke-linejoin', 'round');
            path.style.filter = 'drop-shadow(0 0 5px #ffff00)';
            path.classList.add('flow-line');
            layer.appendChild(path);
        }}

        function startDrag(e, comp) {{
            if (e.button !== 0) return; e.stopPropagation();
            selectedId = comp.id; draggingElement = comp;
            dragOffset.x = e.clientX - comp.x; dragOffset.y = e.clientY - comp.y;
            if (isSimulating) toggleSimulation(); 
            renderComponents(); updateUI();
        }}

        document.onmousemove = (e) => {{
            if (!draggingElement) return;
            document.getElementById(draggingElement.id).style.left = (e.clientX - dragOffset.x) + 'px';
            document.getElementById(draggingElement.id).style.top = (e.clientY - dragOffset.y) + 'px';
        }};

        document.onmouseup = (e) => {{
            if (!draggingElement) return;
            draggingElement.x = Math.round((e.clientX - dragOffset.x) / GRID) * GRID;
            draggingElement.y = Math.round((e.clientY - dragOffset.y) / GRID) * GRID;
            draggingElement = null; saveState(); renderComponents();
        }};

        function rotateSelected() {{
            if (!selectedId) return;
            const comp = state.find(c => c.id === selectedId);
            comp.rot = (comp.rot + 90) % 360; saveState(); renderComponents();
        }}

        function deleteSelected() {{
            if (!selectedId) return;
            state = state.filter(c => c.id !== selectedId);
            selectedId = null; saveState(); renderComponents(); updateUI();
        }}

        function updateUI() {{
            document.getElementById('btn-rot').disabled = !selectedId;
            document.getElementById('btn-del').disabled = !selectedId;
            document.getElementById('btn-undo').disabled = historyIndex <= 0;
        }}

        function toggleSimulation() {{
            isSimulating = !isSimulating;
            const btn = document.getElementById('btn-sim');
            document.getElementById('flow-layer').innerHTML = '';

            if (isSimulating) {{
                let res = simulateCircuit();
                if (res.success) {{
                    const isBurnedOut = res.weight < 50;
                    state.forEach(c => {{ 
                        if(c.type === 'LED' && res.pathNodes.includes(c.connectedHoles[0])) {{ c.lit = !isBurnedOut; c.broken = isBurnedOut; }}
                    }});
                    btn.innerText = isBurnedOut ? "⏹ Stop (SHORT!)" : "⏹ Stop (Running)";
                    btn.style.background = "#dc3545";
                    drawFlow(res.pathNodes);
                }} else {{
                    btn.innerText = "⏹ Stop (No Loop)";
                }}
            }} else {{
                state.forEach(c => {{ if(c.type === 'LED') {{c.lit = false; c.broken = false;}} }});
                btn.innerText = "⚡ Start Simulation"; btn.style.background = "#f39c12";
            }}
            renderComponents();
        }}

        saveState(); renderComponents();
    </script>
</body>
</html>
"""

components.html(simulator_html, height=800)
