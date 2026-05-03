# -*- coding: utf-8 -*-
import os
import streamlit as st
import streamlit.components.v1 as components
import json
from PIL import Image as PILImage

# --- VERTEX AI SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pro-STEM Precision Lab", layout="wide")

# --- 1. SVG ASSET TEMPLATES ---
ASSETS_RAW = {
    "LED": {
        "OFF": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#822" opacity="0.9"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>',
        "ON": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#f00" filter="drop-shadow(0 0 8px red)"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>'
    },
    "RESISTOR": {
        "300": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="5" y="9" width="70" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="25" y="4" width="3" height="12" fill="#ff8c00"/><rect x="31" y="4" width="3" height="12" fill="#000"/><rect x="37" y="4" width="3" height="12" fill="#000"/><rect x="43" y="4" width="3" height="12" fill="#000"/><rect x="52" y="4" width="3" height="12" fill="#8b4513"/></svg>',
        "1000": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="5" y="9" width="70" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="25" y="4" width="3" height="12" fill="#8b4513"/><rect x="31" y="4" width="3" height="12" fill="#000"/><rect x="37" y="4" width="3" height="12" fill="#000"/><rect x="43" y="4" width="3" height="12" fill="#8b4513"/><rect x="52" y="4" width="3" height="12" fill="#8b4513"/></svg>',
        "10k": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="5" y="9" width="70" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="25" y="4" width="3" height="12" fill="#8b4513"/><rect x="31" y="4" width="3" height="12" fill="#000"/><rect x="37" y="4" width="3" height="12" fill="#000"/><rect x="43" y="4" width="3" height="12" fill="#f00"/><rect x="52" y="4" width="3" height="12" fill="#8b4513"/></svg>'
    },
    "SWITCH": {
        "LEFT": '<svg width="60" height="24" viewBox="0 0 60 24"><rect x="10" y="12" width="2" height="12" fill="#aaa"/><rect x="30" y="12" width="2" height="12" fill="#aaa"/><rect x="50" y="12" width="2" height="12" fill="#aaa"/><rect x="5" y="0" width="50" height="16" rx="2" fill="#333"/><rect x="8" y="3" width="18" height="10" rx="2" fill="#ffffff" stroke="#aaa" stroke-width="1"/></svg>',
        "RIGHT": '<svg width="60" height="24" viewBox="0 0 60 24"><rect x="10" y="12" width="2" height="12" fill="#aaa"/><rect x="30" y="12" width="2" height="12" fill="#aaa"/><rect x="50" y="12" width="2" height="12" fill="#aaa"/><rect x="5" y="0" width="50" height="16" rx="2" fill="#333"/><rect x="34" y="3" width="18" height="10" rx="2" fill="#ffffff" stroke="#aaa" stroke-width="1"/></svg>'
    },
    "BATTERY": '<svg width="40" height="60" viewBox="0 0 40 60"><rect x="2" y="2" width="36" height="46" rx="4" fill="#333" stroke="#555"/><rect x="6" y="6" width="28" height="10" fill="#f1c40f"/><rect x="6" y="18" width="28" height="10" fill="#f1c40f"/><rect x="6" y="30" width="28" height="10" fill="#f1c40f"/><text x="11" y="40" fill="black" font-size="7" font-weight="bold">4.5V DC</text><rect x="10" y="48" width="2" height="12" fill="#ff4444"/><rect x="30" y="48" width="2" height="12" fill="#4444ff"/><text x="6" y="59" fill="white" font-size="9">+</text><text x="31" y="59" fill="white" font-size="9">-</text></svg>'
}

# --- 2. VIRTUAL SIMULATOR (HTML/JS) ---
# Notice the addition of the Streamlit protocol handshake in JS
simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; --pale-blue: #add8e6; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 260px; background: #222; padding: 20px; border-right: 1px solid #444; }}
        .comp-item {{ background: #333; padding: 12px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #444; position: relative; }}
        .comp-item:hover {{ background: #444; border-color: #3498db; }}
        .resistor-select {{ background: #222; color: white; border: 1px solid #555; padding: 4px; border-radius: 4px; margin-bottom: 8px; font-size: 12px; width: 80%; cursor: pointer; }}
        #canvas {{ flex-grow: 1; position: relative; background: #111; overflow: auto; }}
        #toolbar {{ padding: 10px; background: #222; border-bottom: 1px solid #444; display: flex; gap: 10px; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }}
        .tool-btn:hover {{ background: #3498db; }}
        .bb-outer {{ position: absolute; top: 60px; left: 40px; background: #eee; padding: 25px; border-radius: 12px; display: flex; align-items: flex-start; box-shadow: 0 10px 40px rgba(0,0,0,0.5); gap: 8px; }}
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); }}
        .rail {{ grid-template-columns: repeat(2, var(--grid)); border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; margin-top: 25px; }}
        .main-col {{ display: flex; flex-direction: column; }}
        .main-grid {{ display: grid; grid-template-rows: repeat(30, var(--grid)); grid-template-columns: repeat(5, var(--grid)); }}
        .trench {{ width: var(--grid); background: #ddd; height: 600px; margin-top: 25px; box-shadow: inset 0 0 5px rgba(0,0,0,0.1); }}
        .num-col {{ width: 20px; margin-top: 25px; text-align: center; font-size: 10px; color: #888; line-height: 20px; }}
        .header-row {{ display: flex; height: 20px; margin-bottom: 5px; }}
        .header-cell {{ width: var(--grid); text-align: center; font-size: 11px; color: #444; font-weight: bold; }}
        .hole {{ width: 12px; height: 12px; background: #bbb; border-radius: 50%; margin: 4px; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.2); cursor: pointer; position: relative; z-index: 10; }}
        .hole.occupied {{ background: var(--pale-blue) !important; box-shadow: 0 0 5px var(--pale-blue); }}
        .hole.wiring {{ background: #2ecc71 !important; }}
        .active-comp {{ position: absolute; z-index: 100; cursor: grab; transform-origin: 0 0; }}
        .active-comp.selected {{ filter: drop-shadow(0 0 5px #3498db); }}
        .pin-collider {{ position: absolute; width: 4px; height: 4px; opacity: 0; pointer-events: none; }}
        svg.overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 50; }}
        .wire {{ stroke: #2ecc71; stroke-width: 4; stroke-linecap: round; pointer-events: auto; cursor: crosshair; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h4 style="margin-top:0;">Precision Lab</h4>
            <div class="comp-item" onclick="spawn('BATTERY')">{ASSETS_RAW['BATTERY']}<br>4.5V Battery</div>
            <div class="comp-item" onclick="spawn('LED')">{ASSETS_RAW['LED']['OFF']}<br>LED (Polarized)</div>
            <div class="comp-item">
                <select id="res-val" class="resistor-select" onchange="updateResistorPreview()" onclick="event.stopPropagation()">
                    <option value="300">300 Ω (Orange/Blk/Blk)</option>
                    <option value="1000" selected>1 kΩ (Brn/Blk/Blk/Brn)</option>
                    <option value="10k">10 kΩ (Brn/Blk/Blk/Red)</option>
                </select>
                <div id="res-preview" onclick="spawn('RESISTOR')" style="margin-top: 5px;">
                    {ASSETS_RAW['RESISTOR']['1000']}<br>Add Resistor
                </div>
            </div>
            <div class="comp-item" onclick="spawn('SWITCH')">{ASSETS_RAW['SWITCH']['LEFT']}<br>Slide Switch</div>
            <div class="comp-item" onclick="clearBoard()" style="background:#822; margin-top: 20px;">🗑 Reset Board</div>
        </div>

        <div id="canvas">
            <div id="toolbar">
                <button class="tool-btn" onclick="rotateComp()">↻ Rotate</button>
                <button class="tool-btn" onclick="deleteComp()" style="background:#c0392b;">✖ Delete</button>
                <button class="tool-btn" id="sim-btn" onclick="toggleSim()" style="background:#f39c12; color:black; margin-left:auto;">⚡ Stimulate</button>
            </div>
            <svg class="overlay" id="wire-layer"></svg>
            <div class="bb-outer" id="board">
                <div class="bb-section rail" id="rail-L"></div>
                <div class="main-col">
                    <div class="header-row">
                        <div class="header-cell">a</div><div class="header-cell">b</div><div class="header-cell">c</div><div class="header-cell">d</div><div class="header-cell">e</div>
                    </div>
                    <div class="main-grid" id="main-L"></div>
                </div>
                <div class="num-col" id="nums"></div>
                <div class="trench"></div>
                <div class="main-col">
                    <div class="header-row">
                        <div class="header-cell">f</div><div class="header-cell">g</div><div class="header-cell">h</div><div class="header-cell">i</div><div class="header-cell">j</div>
                    </div>
                    <div class="main-grid" id="main-R"></div>
                </div>
                <div class="bb-section rail" id="rail-R"></div>
            </div>
            <div id="comp-layer"></div>
        </div>
    </div>

    <script>
        const ASSETS = {json.dumps(ASSETS_RAW)};
        let comps = [];
        let wires = [];
        let selection = null;
        let drag = null;
        let dragOff = {{x:0, y:0}};
        let wiringStart = null;
        let isSimulating = false;

        function notifyPython() {{
            
            const circuitData = {{ comps: comps, wires: wires }};
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: "streamlit:setComponentValue",
                value: JSON.stringify(circuitData)
            }}, '*');
        }}
        
        // --- PERSISTENCE LAYER ---
        function saveState() {{
            const state = {{ comps, wires }};
            localStorage.setItem('precision_lab_circuit', JSON.stringify(state));
            notifyPython(); // PUSH STATE TO PYTHON EVERY TIME IT CHANGES!
        }}

        function loadState() {{
            const saved = localStorage.getItem('precision_lab_circuit');
            if(saved) {{
                try {{
                    const state = JSON.parse(saved);
                    
                    // AUTOMATIC MIGRATION: 
                    // Check if wires use the old "h_" format
                    const isOldFormat = state.wires && state.wires.some(w => w.start.includes('h_'));
                    
                    if (isOldFormat) {{
                        console.log("Old data format detected. Migrating...");
                        localStorage.removeItem('precision_lab_circuit');
                        location.reload(); // Automatically refreshes the page to start clean
                        return;
                    }}
        
                    comps = state.comps || [];
                    wires = state.wires || [];
                    renderComps();
                    renderWires();
                }} catch (e) {{
                    console.error("Data corrupt, resetting.");
                    localStorage.removeItem('precision_lab_circuit');
                }}
            }}
        }}

        function clearBoard() {{
            if(confirm("Clear the entire board?")) {{
                comps = []; wires = [];
                localStorage.removeItem('precision_lab_circuit');
                saveState();
                location.reload();
            }}
        }}

        function updateResistorPreview() {{
            const val = document.getElementById('res-val').value;
            document.getElementById('res-preview').innerHTML = ASSETS.RESISTOR[val] + "<br>Add Resistor";
        }}

        function createHoles(id, cols, tag) {{
            const container = document.getElementById(id);
            for(let r=0; r<30; r++) {{
                for(let c=0; c<cols; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole'; h.id = `h_${{tag}}_${{r}}_${{c}}`;
                    h.onmousedown = (e) => {{ e.stopPropagation(); handleWire(h.id); }};
                    container.appendChild(h);
                }}
            }}
        }}

        createHoles('rail-L', 2, 'RL'); createHoles('main-L', 5, 'ML');
        createHoles('main-R', 5, 'MR'); createHoles('rail-R', 2, 'RR');
        const numBox = document.getElementById('nums');
        for(let i=1; i<=30; i++) {{ const d = document.createElement('div'); d.innerText = i; numBox.appendChild(d); }}

        function getTrack(holeId) {{
            if(!holeId) return null;
            // Split the ID (e.g., "h_ML_4_1" -> ["h", "ML", "4", "1"])
            const p = holeId.split('_'); 
            const type = p[1]; 
            const row = parseInt(p[2]) + 1; // Convert 0-29 index to 1-30
            const col = parseInt(p[3]);
        
            // LHS Rails (RL)
            if (type === 'RL') return `${{row}}_${{col === 0 ? 'red_l' : 'blue_l'}}`;
            
            // RHS Rails (RR)
            if (type === 'RR') return `${{row}}_${{col === 0 ? 'red_r' : 'blue_r'}}`;
            
            // Main Left (ML) -> Columns a, b, c, d, e (ASCII 97, 98, 99, 100, 101)
            if (type === 'ML') return `${{row}}${{String.fromCharCode(97 + col)}}`;
            
            // Main Right (MR) -> Columns f, g, h, i, j (ASCII 102, 103, 104, 105, 106)
            if (type === 'MR') return `${{row}}${{String.fromCharCode(102 + col)}}`;
            
            return holeId;
        }}

        function handleWire(id) {{
            if (!wiringStart) {{
                wiringStart = id; 
                document.getElementById(id).classList.add('wiring');
            }} else {{
                if (wiringStart !== id) {{
                    // Check for duplicates
                    const exists = wires.some(w => 
                        (w.start === wiringStart && w.end === id) || 
                        (w.start === id && w.end === wiringStart)
                    );
                    
                    if (!exists) {{
                        wires.push({{start: wiringStart, end: id}}); 
                        renderWires(); 
                        saveState();
                    }}
                }}
                document.getElementById(wiringStart).classList.remove('wiring');
                wiringStart = null;
            }}
        }}

        function spawn(type) {{
            const id = 'c' + Date.now();
            let pins = [{{x:10, y:50}}, {{x:30, y:50}}];
            let compValue = null;
            if(type === 'RESISTOR') {{
                pins = [{{x:5, y:10}}, {{x:75, y:10}}];
                compValue = document.getElementById('res-val').value;
            }}
            else if(type === 'SWITCH') pins = [{{x:10, y:12}}, {{x:30, y:12}}, {{x:50, y:12}}];
            else if(type === 'BATTERY') pins = [{{x:10, y:48}}, {{x:30, y:48}}];
            
            comps.push({{id, type, x:300, y:100, rot:0, pins, state: 'OFF', switchPos: 'LEFT', value: compValue, connectedTracks: []}});
            selection = id;
            renderComps();
            saveState();
        }}

        function renderComps() {
            const layer = document.getElementById('comp-layer');
            comps.forEach(c => {
                let el = document.getElementById(c.id);
                if(!el) {
                    el = document.createElement('div'); el.id = c.id; el.className = 'active-comp';
                    el.onmousedown = (e) => {
                        e.stopPropagation(); drag = c; selection = c.id;
                        dragOff = {x:e.clientX - c.x, y:e.clientY - c.y}; 
                        renderComps();
                    };
                    el.onclick = (e) => {
                        if(c.type === 'SWITCH') { 
                            c.switchPos = c.switchPos === 'LEFT' ? 'RIGHT' : 'LEFT'; 
                            renderComps(); 
                            saveState();
                            if(isSimulating) simulateCircuit(); // Trigger sim on click
                        }
                    };
                    layer.appendChild(el);
                }
                
                // Apply state/visuals
                if(c.type === 'LED') el.innerHTML = ASSETS.LED[c.state];
                else if(c.type === 'SWITCH') el.innerHTML = ASSETS.SWITCH[c.switchPos];
                else if(c.type === 'BATTERY') el.innerHTML = ASSETS.BATTERY;
                else if(c.type === 'RESISTOR') el.innerHTML = ASSETS.RESISTOR[c.value];
        
                el.style.left = c.x + 'px'; el.style.top = c.y + 'px';
                el.style.transform = `rotate(${c.rot}deg)`;
                
                // Remove and recreate colliders
                el.querySelectorAll('.pin-collider').forEach(p => p.remove());
                c.pins.forEach(p => {
                    const dot = document.createElement('div'); dot.className = 'pin-collider';
                    // Important: Pin positions need to be relative to rotation if your pins move
                    dot.style.left = p.x + 'px'; dot.style.top = p.y + 'px'; 
                    el.appendChild(dot);
                });
            });
            // Ensure holes are mapped after render
            setTimeout(updateHoles, 0);
        }

        function updateHoles() {{
            const holes = Array.from(document.querySelectorAll('.hole'));
            holes.forEach(h => h.classList.remove('occupied'));
            const rect = document.getElementById('canvas').getBoundingClientRect();
            comps.forEach(c => {{
                c.connectedTracks = [];
                const el = document.getElementById(c.id);
                if(!el) return;
                const pinNodes = el.querySelectorAll('.pin-collider');
                pinNodes.forEach((pc, idx) => {{
                    const pRect = pc.getBoundingClientRect();
                    const px = pRect.left - rect.left + 2; const py = pRect.top - rect.top + 2;
                    let bestHole = null; let minDist = 12; 
                    holes.forEach(h => {{
                        const hRect = h.getBoundingClientRect();
                        const hx = hRect.left - rect.left + 6; const hy = hRect.top - rect.top + 6;
                        const dist = Math.hypot(px-hx, py-hy);
                        if(dist < minDist) {{ minDist = dist; bestHole = h; }}
                    }});
                    if(bestHole) {{ bestHole.classList.add('occupied'); c.connectedTracks[idx] = getTrack(bestHole.id); }}
                }});
            }});
            if(isSimulating) simulateCircuit();
        }}

        document.onmousemove = (e) => {{ if(drag) {{ drag.x = e.clientX - dragOff.x; drag.y = e.clientY - dragOff.y; renderComps(); }} }};
        document.onmouseup = () => {{ if(drag) {{ 
            drag.x = Math.round(drag.x / 10) * 10; drag.y = Math.round(drag.y / 10) * 10; 
            drag = null; renderComps(); saveState();
        }} }};

        function renderWires() {{
            const layer = document.getElementById('wire-layer'); 
            layer.innerHTML = '';
            const rect = document.getElementById('canvas').getBoundingClientRect();
            
            wires.forEach((w, i) => {{
                // Calculate the track name on the fly using your new getTrack logic
                const startTrack = getTrack(w.start);
                const endTrack = getTrack(w.end);
                
                const s = document.getElementById(w.start).getBoundingClientRect();
                const e = document.getElementById(w.end).getBoundingClientRect();
                
                const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                l.setAttribute('x1', s.left - rect.left + 6); 
                l.setAttribute('y1', s.top - rect.top + 6);
                l.setAttribute('x2', e.left - rect.left + 6); 
                l.setAttribute('y2', e.top - rect.top + 6);
                l.setAttribute('class', 'wire');
                
                // This keeps the wires interactive
                l.ondblclick = () => {{ wires.splice(i, 1); renderWires(); saveState(); }};
                layer.appendChild(l);
            }});
        }}

        function toggleSim() {{
            isSimulating = !isSimulating;
            const btn = document.getElementById('sim-btn');
            
            if(isSimulating) {{ 
                btn.innerText = "⏹ Stop Stim"; btn.style.background = "#c0392b"; btn.style.color = "white"; 
            }} else {{ 
                btn.innerText = "⚡ Stimulate"; btn.style.background = "#f39c12"; btn.style.color = "black"; 
            }}
            simulateCircuit();
        }}

        function simulateCircuit() {
            // 1. Reset logic
            if (!isSimulating) {
                comps.forEach(c => { 
                    if(c.type === 'LED' && c.state !== 'OFF') { 
                        c.state = 'OFF'; 
                        document.getElementById(c.id).innerHTML = ASSETS.LED.OFF; 
                    } 
                });
                return;
            }
        
            // 2. Map the graph
            const fwd = {}; const rev = {};
            function addDirected(u, v) { if(!u || !v) return; if(!fwd[u]) fwd[u] = []; fwd[u].push(v); if(!rev[v]) rev[v] = []; rev[v].push(u); }
            function addUndirected(u, v) { addDirected(u, v); addDirected(v, u); }
            
            // Add Wires
            wires.forEach(w => addUndirected(getTrack(w.start), getTrack(w.end)));
            
            let vccTracks = []; let gndTracks = [];
            
            // 3. Process Components
            comps.forEach(c => {
                const tr = c.connectedTracks || [];
                if(c.type === 'BATTERY') { if(tr[0]) vccTracks.push(tr[0]); if(tr[1]) gndTracks.push(tr[1]); } 
                else if(c.type === 'RESISTOR') { if(tr[0] && tr[1]) addUndirected(tr[0], tr[1]); } 
                else if(c.type === 'SWITCH') {
                    if(c.switchPos === 'LEFT' && tr[0] && tr[1]) addUndirected(tr[0], tr[1]);
                    else if(c.switchPos === 'RIGHT' && tr[1] && tr[2]) addUndirected(tr[1], tr[2]);
                } 
                else if(c.type === 'LED') { if(tr[0] && tr[1]) addDirected(tr[0], tr[1]); }
            });
        
            // 4. Traversal
            const reachableFromVCC = new Set(vccTracks);
            let q = [...vccTracks];
            while(q.length > 0) {
                const curr = q.shift();
                (fwd[curr] || []).forEach(n => { if(!reachableFromVCC.has(n)) { reachableFromVCC.add(n); q.push(n); } });
            }
            
            const canReachGND = new Set(gndTracks);
            q = [...gndTracks];
            while(q.length > 0) {
                const curr = q.shift();
                (rev[curr] || []).forEach(n => { if(!canReachGND.has(n)) { canReachGND.add(n); q.push(n); } });
            }
            
            // 5. Update UI
            comps.forEach(c => {
                if(c.type === 'LED') {
                    const tr = c.connectedTracks || [];
                    // A simple path exists if Anode (tr[0]) is VCC and Cathode (tr[1]) is GND
                    const newState = (tr[0] && tr[1] && reachableFromVCC.has(tr[0]) && canReachGND.has(tr[1])) ? 'ON' : 'OFF';
                    if(c.state !== newState) { 
                        c.state = newState; 
                        document.getElementById(c.id).innerHTML = ASSETS.LED[c.state]; 
                    }
                }
            });
        }

        function rotateComp() {{ if(!selection) return; const c = comps.find(x => x.id === selection); c.rot = (c.rot + 90) % 360; renderComps(); saveState(); }}
        function deleteComp() {{ comps = comps.filter(x => x.id !== selection); selection = null; renderComps(); saveState(); }}

        // BOOTSTRAP: Load saved circuit and handshake with Streamlit
        window.onload = function() {{
            loadState();
            
            // Tell Streamlit the component is ready
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: "streamlit:componentReady",
                apiVersion: 1
            }}, "*");
            
            // Set the iframe height so it doesn't collapse
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: "streamlit:setFrameHeight",
                height: 850
            }}, "*");
            
            // Send initial state on boot
            notifyPython();
        }};
    </script>
</body>
</html>
"""

# --- 3. VERTEX AI INITIALIZATION ---
@st.cache_resource
def get_vertex_client():
    if "gcp_service_account" in st.secrets:
        creds_info = st.secrets["gcp_service_account"]
        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return genai.Client(
            vertexai=True, 
            project=creds_info["project_id"], 
            location="global", 
            credentials=credentials
        )
    return None

client = get_vertex_client()
MODEL_ID = "gemini-3.1-pro-preview"

# --- 4. LEARNING ANALYTICS HELPER ---
def get_ai_observation(student_data):
    try:
        data = json.loads(student_data) if isinstance(student_data, str) else student_data
        comps = data.get('comps', [])
        wires = data.get('wires', [])
        
        if not comps and not wires:
            return "The breadboard is empty."

        # Helper to translate the internal IDs to your new format
        def translate_id(holeId):
            if not holeId or 'h_' not in holeId: return holeId
            p = holeId.split('_')
            # p[1] is type (RL, ML, etc), p[2] is row (0-29), p[3] is col
            row = int(p[2]) + 1
            col = int(p[3])
            
            if p[1] == 'RL': return f"{row}_{'red_l' if col == 0 else 'blue_l'}"
            if p[1] == 'RR': return f"{row}_{'red_r' if col == 0 else 'blue_r'}"
            if p[1] == 'ML': return f"{row}{chr(97 + col)}" # a, b, c, d, e
            if p[1] == 'MR': return f"{row}{chr(102 + col)}" # f, g, h, i, j
            return holeId

        observations = ["### Current Breadboard State", "\n**Components:**"]
        for comp in comps:
            ctype = comp.get('type', 'Unknown')
            val = comp.get('value', 'N/A')
            # Translate tracks for components
            tracks = [translate_id(str(t)) for t in comp.get('connectedTracks', []) if t]
            track_str = f" on tracks: {', '.join(tracks)}" if tracks else " (not connected)"
            observations.append(f"- {ctype} ({val}){track_str}")

        observations.append("\n**Physical Wire Connections:**")
        if not wires:
            observations.append("- No wires used.")
        else:
            for i, w in enumerate(wires):
                # Translate start and end for wires
                s = translate_id(w['start'])
                e = translate_id(w['end'])
                observations.append(f"- Wire {i+1}: Connects track '{s}' to track '{e}'")
        
        return "\n".join(observations)
    except Exception as e:
        return f"Circuit data parsing error: {e}"
        

# --- 5. MAIN UI LAYOUT ---
st.title("⚡ AI Circuit Auditor")

with st.sidebar:
    st.header("Teacher's Goal")
    schematic_file = st.file_uploader("Upload Target Schematic", type=["jpg", "png", "jpeg"])

# --- NEW: REGISTER HTML AS A CUSTOM COMPONENT ---
# This forces Streamlit to actually read the postMessages
if not os.path.exists("sim_frontend"):
    os.makedirs("sim_frontend")
with open("sim_frontend/index.html", "w", encoding="utf-8") as f:
    f.write(simulator_html)

# Declare component with a default object structure
sim_component = components.declare_component("sim_component", path="sim_frontend")
current_sim_data = sim_component(default='{"comps": [], "wires": []}')


# --- 6. AI AUDIT EXECUTION ---
if st.button("🔍 Check My Circuit", type="primary"):
    if not schematic_file:
        st.warning("Please upload a schematic.")
    else:
        # Notice we are now directly passing current_sim_data instead of pulling from session state
        user_circuit_description = get_ai_observation(current_sim_data)
        
        st.subheader("👁️ AI Observation")
        st.info("The AI analyzed your board and sees:")
        st.markdown(user_circuit_description)

        raw_schematic = PILImage.open(schematic_file).convert("RGB")
        
        analysis_prompt = f"""
        Compare this schematic to the student's breadboard description.
        
        STUDENT DATA:
        {user_circuit_description}
        
        Check for:
        1. Complete path from Power (VCC) to Ground (GND).
        2. LED presence and correct polarity.
        3. Protection resistor presence.
        """

        try:
            resp = client.models.generate_content(
                model=MODEL_ID,
                contents=[raw_schematic, analysis_prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "is_correct": {"type": "BOOLEAN"},
                            "ai_observation": {"type": "STRING"},
                            "feedback": {"type": "STRING"}
                        },
                        "required": ["is_correct", "ai_observation", "feedback"]
                    }
                )
            )
            
            result = resp.parsed
            st.divider()
            if result.get("is_correct"):
                st.success("✅ **Circuit matches! Well done.**")
            else:
                st.error("❌ **Audit failed. See suggestions below.**")
            
            st.write(f"**Interpretation:** {result.get('ai_observation')}")
            st.info(f"**Tutor Note:** {result.get('feedback')}")

        except Exception as e:
            st.error(f"Audit failed: {e}")
