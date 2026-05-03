# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json

st.set_page_config(page_title="Pro-STEM Precision Lab", layout="wide")

# --- SVG ASSET TEMPLATES ---
# 1) LED Updated: Long Anode leg starts higher (y=22 vs y=30) and has clear +/- labels.
# 2) Switch Updated: White logo/toggle visibly shifts left and right.
ASSETS_RAW = {
    "LED": {
        "OFF": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#822" opacity="0.9"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>',
        "ON": '<svg width="40" height="50" viewBox="0 0 40 50"><rect x="9" y="22" width="2" height="28" fill="#aaa"/><rect x="29" y="30" width="2" height="20" fill="#aaa"/><path d="M10 30 Q 10 5 20 5 Q 30 5 30 30 Z" fill="#f00" filter="drop-shadow(0 0 8px red)"/><text x="1" y="48" fill="#aaa" font-size="9">+</text><text x="32" y="48" fill="#aaa" font-size="9">-</text></svg>'
    },
    "RES_5BAND": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="5" y="9" width="70" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="25" y="4" width="3" height="12" fill="#8b4513"/><rect x="31" y="4" width="3" height="12" fill="#000"/><rect x="37" y="4" width="3" height="12" fill="#000"/><rect x="43" y="4" width="3" height="12" fill="#ff8c00"/><rect x="52" y="4" width="3" height="12" fill="#800080"/></svg>',
    "SWITCH": {
        "LEFT": '<svg width="60" height="24" viewBox="0 0 60 24"><rect x="10" y="12" width="2" height="12" fill="#aaa"/><rect x="30" y="12" width="2" height="12" fill="#aaa"/><rect x="50" y="12" width="2" height="12" fill="#aaa"/><rect x="5" y="0" width="50" height="16" rx="2" fill="#333"/><rect x="8" y="3" width="18" height="10" rx="2" fill="#ffffff" stroke="#aaa" stroke-width="1"/></svg>',
        "RIGHT": '<svg width="60" height="24" viewBox="0 0 60 24"><rect x="10" y="12" width="2" height="12" fill="#aaa"/><rect x="30" y="12" width="2" height="12" fill="#aaa"/><rect x="50" y="12" width="2" height="12" fill="#aaa"/><rect x="5" y="0" width="50" height="16" rx="2" fill="#333"/><rect x="34" y="3" width="18" height="10" rx="2" fill="#ffffff" stroke="#aaa" stroke-width="1"/></svg>'
    },
    "BATTERY": '<svg width="40" height="60" viewBox="0 0 40 60"><rect x="2" y="2" width="36" height="46" rx="4" fill="#333" stroke="#555"/><rect x="6" y="6" width="28" height="10" fill="#f1c40f"/><rect x="6" y="18" width="28" height="10" fill="#f1c40f"/><rect x="6" y="30" width="28" height="10" fill="#f1c40f"/><text x="11" y="40" fill="black" font-size="7" font-weight="bold">4.5V DC</text><rect x="10" y="48" width="2" height="12" fill="#ff4444"/><rect x="30" y="48" width="2" height="12" fill="#4444ff"/><text x="6" y="59" fill="white" font-size="9">+</text><text x="31" y="59" fill="white" font-size="9">-</text></svg>'
}

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; --pale-blue: #add8e6; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        
        #palette {{ width: 260px; background: #222; padding: 20px; border-right: 1px solid #444; }}
        .comp-item {{ background: #333; padding: 12px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #444; }}
        .comp-item:hover {{ background: #444; border-color: #3498db; }}

        #canvas {{ flex-grow: 1; position: relative; background: #111; overflow: auto; }}
        #toolbar {{ padding: 10px; background: #222; border-bottom: 1px solid #444; display: flex; gap: 10px; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }}
        .tool-btn:hover {{ background: #3498db; }}

        .bb-outer {{ 
            position: absolute; top: 60px; left: 40px; background: #eee; 
            padding: 25px; border-radius: 12px; display: flex; align-items: flex-start;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5); gap: 8px;
        }}
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); }}
        .rail {{ grid-template-columns: repeat(2, var(--grid)); border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; margin-top: 25px; }}
        .main-col {{ display: flex; flex-direction: column; }}
        .main-grid {{ display: grid; grid-template-rows: repeat(30, var(--grid)); grid-template-columns: repeat(5, var(--grid)); }}
        .trench {{ width: var(--grid); background: #ddd; height: 600px; margin-top: 25px; box-shadow: inset 0 0 5px rgba(0,0,0,0.1); }}
        .num-col {{ width: 20px; margin-top: 25px; text-align: center; font-size: 10px; color: #888; line-height: 20px; }}

        .header-row {{ display: flex; height: 20px; margin-bottom: 5px; }}
        .header-cell {{ width: var(--grid); text-align: center; font-size: 11px; color: #444; font-weight: bold; }}

        .hole {{ 
            width: 12px; height: 12px; background: #bbb; border-radius: 50%; 
            margin: 4px; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.2);
            cursor: pointer; position: relative; z-index: 10;
        }}
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
            <div class="comp-item" onclick="spawn('RESISTOR')">{ASSETS_RAW['RES_5BAND']}<br>5-Band Resistor</div>
            <div class="comp-item" onclick="spawn('SWITCH')">{ASSETS_RAW['SWITCH']['LEFT']}<br>Slide Switch</div>
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

        function createHoles(id, cols, tag) {{
            const container = document.getElementById(id);
            for(let r=0; r<30; r++) {{
                for(let c=0; c<cols; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    h.id = `h_${{tag}}_${{r}}_${{c}}`;
                    h.onmousedown = (e) => {{ e.stopPropagation(); handleWire(h.id); }};
                    container.appendChild(h);
                }}
            }}
        }}

        createHoles('rail-L', 2, 'RL');
        createHoles('main-L', 5, 'ML');
        createHoles('main-R', 5, 'MR');
        createHoles('rail-R', 2, 'RR');

        const numBox = document.getElementById('nums');
        for(let i=1; i<=30; i++) {{
            const d = document.createElement('div'); d.innerText = i; numBox.appendChild(d);
        }}

        function getTrack(holeId) {{
            if(!holeId) return null;
            const p = holeId.split('_'); 
            if(p[1] === 'RL' || p[1] === 'RR') return p[1] + '_' + p[3]; // Vertical Rails are entirely connected per column
            return p[1] + '_' + p[2]; // Horizontal rows are connected 5-wide
        }}

        function handleWire(id) {{
            if (!wiringStart) {{
                wiringStart = id;
                document.getElementById(id).classList.add('wiring');
            }} else {{
                if (wiringStart !== id) {{
                    wires.push({{start: wiringStart, end: id}});
                    renderWires();
                    if(isSimulating) simulateCircuit();
                }}
                document.getElementById(wiringStart).classList.remove('wiring');
                wiringStart = null;
            }}
        }}

        function spawn(type) {{
            const id = 'c' + Date.now();
            let pins = [{{x:10, y:50}}, {{x:30, y:50}}]; // Default LED
            if(type === 'RESISTOR') pins = [{{x:5, y:10}}, {{x:75, y:10}}];
            if(type === 'SWITCH') pins = [{{x:10, y:12}}, {{x:30, y:12}}, {{x:50, y:12}}];
            if(type === 'BATTERY') pins = [{{x:10, y:48}}, {{x:30, y:48}}];
            
            comps.push({{id, type, x:300, y:100, rot:0, pins, state: 'OFF', switchPos: 'LEFT', connectedTracks: []}});
            selection = id;
            renderComps();
        }}

        function renderComps() {{
            const layer = document.getElementById('comp-layer');
            comps.forEach(c => {{
                let el = document.getElementById(c.id);
                if(!el) {{
                    el = document.createElement('div');
                    el.id = c.id; el.className = 'active-comp';
                    el.onmousedown = (e) => {{
                        e.stopPropagation(); drag = c; selection = c.id;
                        dragOff = {{x:e.clientX - c.x, y:e.clientY - c.y}};
                        renderComps();
                    }};
                    el.onclick = (e) => {{
                        if(c.type === 'SWITCH') {{
                            c.switchPos = c.switchPos === 'LEFT' ? 'RIGHT' : 'LEFT';
                            renderComps(); // Triggers simulation update below
                        }}
                    }};
                    layer.appendChild(el);
                }}
                
                el.classList.toggle('selected', selection === c.id);
                
                if(c.type === 'LED') el.innerHTML = ASSETS.LED[c.state];
                else if(c.type === 'SWITCH') el.innerHTML = ASSETS.SWITCH[c.switchPos];
                else if(c.type === 'RESISTOR') el.innerHTML = ASSETS.RES_5BAND;
                else if(c.type === 'BATTERY') el.innerHTML = ASSETS.BATTERY;

                el.style.left = c.x + 'px'; el.style.top = c.y + 'px';
                el.style.transform = `rotate(${{c.rot}}deg)`;
                
                el.querySelectorAll('.pin-collider').forEach(p => p.remove());
                c.pins.forEach(p => {{
                    const dot = document.createElement('div');
                    dot.className = 'pin-collider';
                    dot.style.left = p.x + 'px'; dot.style.top = p.y + 'px';
                    el.appendChild(dot);
                }});
            }});
            
            Array.from(layer.children).forEach(child => {{ if(!comps.find(x => x.id === child.id)) child.remove(); }});
            
            // Allow DOM to update bounding boxes before recalculating physical insertions
            setTimeout(updateHoles, 0);
        }}

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
                    const px = pRect.left - rect.left + 2;
                    const py = pRect.top - rect.top + 2;
                    
                    let bestHole = null;
                    let minDist = 12; 
                    
                    holes.forEach(h => {{
                        const hRect = h.getBoundingClientRect();
                        const hx = hRect.left - rect.left + 6;
                        const hy = hRect.top - rect.top + 6;
                        const dist = Math.hypot(px-hx, py-hy);
                        if(dist < minDist) {{
                            minDist = dist;
                            bestHole = h;
                        }}
                    }});
                    
                    if(bestHole) {{
                        bestHole.classList.add('occupied');
                        c.connectedTracks[idx] = getTrack(bestHole.id);
                    }}
                }});
            }});
            if(isSimulating) simulateCircuit();
        }}

        document.onmousemove = (e) => {{
            if(drag) {{
                drag.x = e.clientX - dragOff.x;
                drag.y = e.clientY - dragOff.y;
                renderComps();
            }}
        }};

        document.onmouseup = () => {{
            if(drag) {{
                drag.x = Math.round(drag.x / 10) * 10; 
                drag.y = Math.round(drag.y / 10) * 10;
                drag = null; renderComps();
            }}
        }};

        function renderWires() {{
            const layer = document.getElementById('wire-layer');
            layer.innerHTML = '';
            const rect = document.getElementById('canvas').getBoundingClientRect();
            wires.forEach((w, i) => {{
                const s = document.getElementById(w.start).getBoundingClientRect();
                const e = document.getElementById(w.end).getBoundingClientRect();
                const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                l.setAttribute('x1', s.left - rect.left + 6); l.setAttribute('y1', s.top - rect.top + 6);
                l.setAttribute('x2', e.left - rect.left + 6); l.setAttribute('y2', e.top - rect.top + 6);
                l.setAttribute('class', 'wire');
                l.ondblclick = () => {{ wires.splice(i, 1); renderWires(); if(isSimulating) simulateCircuit(); }};
                layer.appendChild(l);
            }});
        }}

        function toggleSim() {{
            isSimulating = !isSimulating;
            const btn = document.getElementById('sim-btn');
            if(isSimulating) {{
                btn.innerText = "⏹ Stop Stim";
                btn.style.background = "#c0392b"; btn.style.color = "white";
            }} else {{
                btn.innerText = "⚡ Stimulate";
                btn.style.background = "#f39c12"; btn.style.color = "black";
            }}
            simulateCircuit();
        }}

        // --- GRAPH LOGIC ENGINE ---
        function simulateCircuit() {{
            if (!isSimulating) {{
                comps.forEach(c => {{
                    if(c.type === 'LED' && c.state !== 'OFF') {{
                        c.state = 'OFF';
                        document.getElementById(c.id).innerHTML = ASSETS.LED.OFF;
                    }}
                }});
                return;
            }}

            const fwd = {{}};
            const rev = {{}};
            function addDirected(u, v) {{
                if(!u || !v) return;
                if(!fwd[u]) fwd[u] = []; fwd[u].push(v);
                if(!rev[v]) rev[v] = []; rev[v].push(u);
            }}
            function addUndirected(u, v) {{
                addDirected(u, v);
                addDirected(v, u);
            }}

            // Wires = Undirected Edges
            wires.forEach(w => addUndirected(getTrack(w.start), getTrack(w.end)));

            let vccTracks = [];
            let gndTracks = [];

            comps.forEach(c => {{
                const tr = c.connectedTracks || [];
                if(c.type === 'BATTERY') {{
                    if(tr[0]) vccTracks.push(tr[0]); // Pin 0 is Positive
                    if(tr[1]) gndTracks.push(tr[1]); // Pin 1 is Negative
                }} else if(c.type === 'RESISTOR') {{
                    if(tr[0] && tr[1]) addUndirected(tr[0], tr[1]); // Bidirectional
                }} else if(c.type === 'SWITCH') {{
                    if(c.switchPos === 'LEFT' && tr[0] && tr[1]) addUndirected(tr[0], tr[1]);
                    if(c.switchPos === 'RIGHT' && tr[1] && tr[2]) addUndirected(tr[1], tr[2]);
                }} else if(c.type === 'LED') {{
                    // STRICT POLARITY: Only allows current flow from Anode (Pin 0) to Cathode (Pin 1)
                    if(tr[0] && tr[1]) addDirected(tr[0], tr[1]); 
                }}
            }});

            // BFS to find all tracks with Positive Current
            const reachableFromVCC = new Set();
            let q = [...vccTracks];
            q.forEach(t => reachableFromVCC.add(t));
            while(q.length > 0) {{
                const curr = q.shift();
                (fwd[curr] || []).forEach(n => {{
                    if(!reachableFromVCC.has(n)) {{
                        reachableFromVCC.add(n); q.push(n);
                    }}
                }});
            }}

            // BFS to find all tracks connecting to Negative/Ground
            const canReachGND = new Set();
            q = [...gndTracks];
            q.forEach(t => canReachGND.add(t));
            while(q.length > 0) {{
                const curr = q.shift();
                (rev[curr] || []).forEach(n => {{
                    if(!canReachGND.has(n)) {{
                        canReachGND.add(n); q.push(n);
                    }}
                }});
            }}

            // Evaluate LED States Based on Flow
            comps.forEach(c => {{
                if(c.type === 'LED') {{
                    const tr = c.connectedTracks || [];
                    const newState = (tr[0] && tr[1] && reachableFromVCC.has(tr[0]) && canReachGND.has(tr[1])) ? 'ON' : 'OFF';
                    if(c.state !== newState) {{
                        c.state = newState;
                        document.getElementById(c.id).innerHTML = ASSETS.LED[c.state];
                    }}
                }}
            }});
        }}

        function rotateComp() {{
            if(!selection) return;
            const c = comps.find(x => x.id === selection);
            c.rot = (c.rot + 90) % 360; renderComps();
        }}

        function deleteComp() {{
            comps = comps.filter(x => x.id !== selection);
            selection = null; renderComps();
        }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=850)
