# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json

# --- 1. CONFIG ---
st.set_page_config(page_title="Pro-STEM Lab - Precision Alignment", layout="wide")

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

assets_json = json.dumps(ASSETS)

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 220px; background: #333; padding: 15px; border-right: 2px solid #444; z-index: 10; }}
        #canvas {{ flex-grow: 1; position: relative; background: #1a1a1a; overflow: auto; }}
        
        #toolbar {{ position: absolute; top: 15px; left: 15px; background: #333; padding: 8px; border-radius: 8px; display: flex; gap: 10px; z-index: 100; border: 1px solid #555; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }}
        .tool-btn:hover {{ background: #007bff; }}
        
        /* BREADBOARD ALIGNMENT - CRITICAL FIX */
        .breadboard-container {{ 
            position: absolute; top: 100px; left: 50px; background: #fdfdfd; 
            border-radius: 8px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex; gap: 0; border: 2px solid #e0e0e0;
        }}
        
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); position: relative; }}
        .bb-rails {{ grid-template-columns: repeat(2, var(--grid)); border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; }}
        .bb-main {{ grid-template-columns: repeat(5, var(--grid)); }}
        .trench {{ width: var(--grid); background: #eee; box-shadow: inset 0 0 5px rgba(0,0,0,0.1); margin-top: 18px; }}
        
        .bb-wrapper {{ display: flex; flex-direction: column; }}
        .col-headers {{ 
            display: grid; grid-template-columns: repeat(5, var(--grid)); 
            font-size: 11px; color: #555; text-align: center; font-weight: bold; height: 18px;
        }}
        
        /* THE HOLE: 12px + 4px margin on each side = 20px total box */
        .hole {{ 
            width: 12px; height: 12px; background: #ccc; border-radius: 50%; 
            box-shadow: inset 1px 1px 2px rgba(0,0,0,0.4); margin: 4px; 
            cursor: crosshair; transition: 0.2s; 
        }}
        .hole:hover {{ background: #007bff; transform: scale(1.2); }}
        .hole.wiring-active {{ background: #00ff00 !important; box-shadow: 0 0 10px #00ff00; }}
        .hole.connected {{ background: #add8e6 !important; }}

        .row-numbers {{ display: grid; grid-template-rows: repeat(30, var(--grid)); width: 20px; text-align: center; font-size: 9px; color: #888; align-items: center; margin-top: 18px; }}
        
        .active-comp {{ position: absolute; cursor: grab; z-index: 50; transform-origin: top left; }}
        .active-comp.selected {{ filter: drop-shadow(0px 0px 6px #007bff) brightness(1.2); }}
        .pin-collider {{ position: absolute; width: 4px; height: 4px; opacity: 0; pointer-events: none; }}
        
        svg.overlay-layer {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }}
        #flow-layer {{ z-index: 45; }}
        .flow-line {{ stroke-dasharray: 10 10; animation: flowAnim 0.5s linear infinite; }}
        @keyframes flowAnim {{ from {{ stroke-dashoffset: 20; }} to {{ stroke-dashoffset: 0; }} }}
        
        .comp-item {{ background: #444; padding: 10px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #555; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h4 style="margin:0 0 15px 0;">Components</h4>
            <div class="comp-item" onclick="spawnComp('BATTERY')">{ASSETS['BATTERY']}<br>9V Battery</div>
            <div class="comp-item" onclick="spawnComp('LED')">{ASSETS['LED_OFF']}<br>LED</div>
            <div class="comp-item" onclick="spawnComp('RES_300')">{ASSETS['RES_300']}<br>300Ω Resistor</div>
            <div class="comp-item" onclick="spawnComp('SWITCH')">{ASSETS['SWITCH']}<br>Switch</div>
        </div>
        <div id="canvas">
            <div id="toolbar">
                <button class="tool-btn" onclick="undo()">↶ Undo</button>
                <button class="tool-btn" onclick="rotateSelected()">↻ Rotate</button>
                <button class="tool-btn" onclick="deleteSelected()" style="background:#dc3545;">✖ Delete</button>
                <button class="tool-btn" onclick="toggleSimulation()" id="btn-sim" style="background:#f39c12; color:black;">⚡ Start Simulation</button>
            </div>
            
            <svg class="overlay-layer" id="wire-layer"></svg>
            <svg class="overlay-layer" id="flow-layer"></svg>
            
            <div class="breadboard-container">
                <!-- LHS RAILS -->
                <div class="bb-section bb-rails" style="margin-top:18px;" id="rail-L"></div>
                <!-- MAIN LEFT -->
                <div class="bb-wrapper">
                    <div class="col-headers"><div>a</div><div>b</div><div>c</div><div>d</div><div>e</div></div>
                    <div class="bb-section bb-main" id="main-L"></div>
                </div>
                <!-- NUMBERS -->
                <div class="row-numbers" id="nums"></div>
                <!-- TRENCH -->
                <div class="trench"></div>
                <!-- MAIN RIGHT -->
                <div class="bb-wrapper">
                    <div class="col-headers"><div>f</div><div>g</div><div>h</div><div>i</div><div>j</div></div>
                    <div class="bb-section bb-main" id="main-R"></div>
                </div>
                <!-- RHS RAILS -->
                <div class="bb-section bb-rails" style="margin-top:18px;" id="rail-R"></div>
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

        function getPins(type) {{
            if (type.includes('RES')) return [{{x: 10, y: 10}}, {{x: 70, y: 10}}];
            if (type === 'SWITCH') return [{{x: 10, y: 10}}, {{x: 30, y: 10}}, {{x: 50, y: 10}}];
            if (type === 'BATTERY') return [{{x: 10, y: 50}}, {{x: 30, y: 50}}];
            return [{{x: 10, y: 30}}, {{x: 30, y: 30}}]; // LED
        }}

        function spawnComp(type) {{
            state.push({{ id: 'comp_' + Date.now(), type: type, x: 100, y: 100, rot: 0, lit: false, broken: false, pins: getPins(type), connectedHoles: [] }});
            selectedId = state[state.length-1].id;
            saveState(); renderComponents();
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

        function startDrag(e, comp) {{
            e.stopPropagation(); selectedId = comp.id; draggingElement = comp;
            dragOffset.x = e.clientX - comp.x; dragOffset.y = e.clientY - comp.y;
            renderComponents();
        }}

        document.onmousemove = (e) => {{
            if (!draggingElement) return;
            draggingElement.x = e.clientX - dragOffset.x;
            draggingElement.y = e.clientY - dragOffset.y;
            renderComponents();
        }};

        document.onmouseup = () => {{
            if (!draggingElement) return;
            // Precise snapping to the grid
            draggingElement.x = Math.round(draggingElement.x / GRID) * GRID;
            draggingElement.y = Math.round(draggingElement.y / GRID) * GRID;
            draggingElement = null; 
            saveState(); renderComponents();
        }};

        function updateConnections() {{
            const holes = Array.from(document.querySelectorAll('.hole'));
            holes.forEach(h => h.classList.remove('connected'));
            const canvasRect = document.getElementById('canvas').getBoundingClientRect();

            state.forEach(comp => {{
                comp.connectedHoles = [];
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

            // Internal Rails & Main Bus
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
            while(queue.length > 0) {{
                let curr = queue.shift();
                if(curr.id === endHole) return {{ success: true, pathNodes: curr.path, weight: curr.weight }};
                if(visited.has(curr.id)) continue;
                visited.add(curr.id);
                (graph[curr.id] || []).forEach(edge => {{
                    if(!visited.has(edge.to)) queue.push({{ id: edge.to, path: [...curr.path, edge.to], weight: curr.weight + edge.weight }});
                }});
            }}
            return {{ success: false }};
        }}

        function toggleSimulation() {{
            isSimulating = !isSimulating;
            if (isSimulating) {{
                let res = simulateCircuit();
                if (res.success) {{
                    const isBurnedOut = res.weight < 50;
                    state.forEach(c => {{ if(c.type === 'LED') {{ c.lit = !isBurnedOut; c.broken = isBurnedOut; }} }});
                    drawFlow(res.pathNodes);
                }}
            }} else {{
                state.forEach(c => {{ c.lit = false; c.broken = false; }});
                document.getElementById('flow-layer').innerHTML = '';
            }}
            renderComponents();
        }}

        function drawFlow(pathNodes) {{
            const layer = document.getElementById('flow-layer'); layer.innerHTML = '';
            const canvasRect = document.getElementById('canvas').getBoundingClientRect();
            let d = "";
            pathNodes.forEach((node, i) => {{
                const r = document.getElementById(node).getBoundingClientRect();
                const x = r.left - canvasRect.left + 6, y = r.top - canvasRect.top + 6;
                d += (i === 0 ? "M " : "L ") + x + " " + y;
            }});
            const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            p.setAttribute('d', d); p.setAttribute('fill', 'none'); p.setAttribute('stroke', '#ff0');
            p.setAttribute('stroke-width', '4'); p.classList.add('flow-line');
            layer.appendChild(p);
        }}

        function renderWires() {{
            const layer = document.getElementById('wire-layer'); layer.innerHTML = '';
            const canvasRect = document.getElementById('canvas').getBoundingClientRect();
            wires.forEach(w => {{
                const s = document.getElementById(w.start).getBoundingClientRect();
                const e = document.getElementById(w.end).getBoundingClientRect();
                const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                l.setAttribute('x1', s.left - canvasRect.left + 6); l.setAttribute('y1', s.top - canvasRect.top + 6);
                l.setAttribute('x2', e.left - canvasRect.left + 6); l.setAttribute('y2', e.top - canvasRect.top + 6);
                l.setAttribute('stroke', '#2ecc71'); l.setAttribute('stroke-width', '4');
                layer.appendChild(l);
            }});
        }}

        function rotateSelected() {{
            if (!selectedId) return;
            const c = state.find(x => x.id === selectedId);
            c.rot = (c.rot + 90) % 360; saveState(); renderComponents();
        }}

        function deleteSelected() {{
            state = state.filter(x => x.id !== selectedId);
            selectedId = null; saveState(); renderComponents();
        }}

        function saveState() {{
            historyIndex++;
            history = history.slice(0, historyIndex);
            history.push({{ comps: JSON.deepcopy(state), wires: JSON.deepcopy(wires) }});
        }}
        function undo() {{ if(historyIndex > 0) {{ historyIndex--; state = history[historyIndex].comps; wires = history[historyIndex].wires; renderComponents(); renderWires(); }} }}
        const JSON = {{ deepcopy: (o) => window.JSON.parse(window.JSON.stringify(o)) }};

        saveState(); renderComponents();
    </script>
</body>
</html>
"""

components.html(simulator_html, height=850)
