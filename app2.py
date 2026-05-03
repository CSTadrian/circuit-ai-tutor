# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json

st.set_page_config(page_title="Pro-STEM Precision Lab", layout="wide")

# --- 1. VECTOR ASSETS ---
ASSETS = {
    "LED_OFF": '<svg width="40" height="40" viewBox="0 0 40 40"><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/><path d="M10 25 Q 10 5 20 5 Q 30 5 30 25 Z" fill="#882222" opacity="0.9"/></svg>',
    "LED_ON": '<svg width="40" height="40" viewBox="0 0 40 40"><defs><radialGradient id="glow"><stop offset="0%" stop-color="#ffaaaa"/><stop offset="100%" stop-color="#ff0000"/></radialGradient></defs><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/><path d="M10 25 Q 10 5 20 5 Q 30 5 30 25 Z" fill="url(#glow)" filter="drop-shadow(0px 0px 8px red)"/></svg>',
    "LED_BROKEN": '<svg width="40" height="40" viewBox="0 0 40 40"><rect x="9" y="20" width="2" height="20" fill="#aaa"/><rect x="29" y="25" width="2" height="15" fill="#aaa"/><path d="M10 25 Q 10 5 20 5 Q 30 5 30 25 Z" fill="#333" opacity="0.9"/><path d="M15 10 L25 20 M25 10 L15 20" stroke="white" stroke-width="2"/></svg>',
    "RES_300": '<svg width="80" height="20" viewBox="0 0 80 20"><rect x="10" y="9" width="60" height="2" fill="#aaa"/><rect x="20" y="4" width="40" height="12" rx="4" fill="#69a8e6"/><rect x="28" y="4" width="6" height="12" fill="#ff8c00"/><rect x="40" y="4" width="6" height="12" fill="#000"/><rect x="52" y="4" width="6" height="12" fill="#8b4513"/></svg>',
    "SWITCH": '<svg width="60" height="20" viewBox="0 0 60 20"><rect x="10" y="9" width="2" height="11" fill="#aaa"/><rect x="30" y="9" width="2" height="11" fill="#aaa"/><rect x="50" y="9" width="2" height="11" fill="#aaa"/><rect x="5" y="0" width="50" height="14" rx="2" fill="#333"/><rect x="15" y="2" width="12" height="10" fill="#555"/></svg>',
    "BATTERY": '<svg width="40" height="60" viewBox="0 0 40 60"><rect x="2" y="2" width="36" height="44" rx="2" fill="#222" stroke="#eee" stroke-width="1"/><rect x="2" y="2" width="18" height="44" rx="2" fill="#ff4444"/><text x="6" y="28" fill="white" font-weight="bold" font-size="14">+</text><text x="24" y="28" fill="white" font-weight="bold" font-size="14">-</text><rect x="9" y="46" width="2" height="14" fill="#aaa"/><rect x="29" y="46" width="2" height="14" fill="#aaa"/></svg>',
}

assets_json = json.dumps(ASSETS)

# --- 2. HTML/JS SIMULATOR ---
simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: sans-serif; background: #1a1a1a; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 200px; background: #222; padding: 15px; border-right: 1px solid #444; z-index: 100; }}
        #canvas {{ flex-grow: 1; position: relative; overflow: auto; background: #111; }}
        
        .tool-btn {{ background: #444; color: white; border: none; padding: 8px; margin: 2px; border-radius: 4px; cursor: pointer; }}
        .tool-btn:hover {{ background: #007bff; }}

        /* Unified Breadboard Structure */
        .bb-outer {{ 
            position: absolute; top: 120px; left: 60px; background: #fff; 
            padding: 20px; border-radius: 10px; display: flex; gap: 0; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }}
        .bb-section {{ display: grid; grid-template-rows: repeat(30, var(--grid)); }}
        .rail {{ grid-template-columns: repeat(2, var(--grid)); border-left: 2px solid #ff4444; border-right: 2px solid #4444ff; }}
        .main {{ grid-template-columns: repeat(5, var(--grid)); }}
        .trench {{ width: var(--grid); background: #f0f0f0; border-left: 1px solid #ddd; border-right: 1px solid #ddd; }}
        .spacer {{ width: var(--grid); }}

        /* Headers aligned strictly above columns */
        .header-row {{ display: flex; height: 20px; margin-bottom: 5px; }}
        .header-cell {{ width: var(--grid); text-align: center; font-size: 10px; color: #666; font-weight: bold; }}

        .hole {{ 
            width: 12px; height: 12px; background: #ccc; border-radius: 50%; 
            margin: 4px; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.3);
            cursor: pointer; position: relative; z-index: 10;
        }}
        .hole:hover {{ background: #007bff; }}
        .hole.active {{ background: #00ff00; box-shadow: 0 0 8px #00ff00; }}
        .hole.connected {{ background: #add8e6; }}

        .active-comp {{ position: absolute; z-index: 50; cursor: grab; transform-origin: top left; }}
        .active-comp.selected {{ filter: drop-shadow(0 0 5px #007bff); }}
        .pin-collider {{ position: absolute; width: 4px; height: 4px; background: red; opacity: 0; pointer-events: none; }}

        svg.overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }}
        .wire {{ stroke: #2ecc71; stroke-width: 4; stroke-linecap: round; pointer-events: auto; cursor: help; }}
        .flow-line {{ stroke: #ffff00; stroke-width: 4; stroke-dasharray: 8 8; animation: flow 0.5s linear infinite; }}
        @keyframes flow {{ from {{ stroke-dashoffset: 16; }} to {{ stroke-dashoffset: 0; }} }}
        
        .comp-item {{ background: #333; padding: 10px; margin-bottom: 10px; border-radius: 5px; cursor: pointer; text-align: center; border: 1px solid #444; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h4 style="margin:0 0 10px 0;">Library</h4>
            <div class="comp-item" onclick="spawn('BATTERY')">{ASSETS['BATTERY']}<br>9V Battery</div>
            <div class="comp-item" onclick="spawn('LED')">{ASSETS['LED_OFF']}<br>LED</div>
            <div class="comp-item" onclick="spawn('RES_300')">{ASSETS['RES_300']}<br>300Ω Resistor</div>
            <div class="comp-item" onclick="spawn('SWITCH')">{ASSETS['SWITCH']}<br>Slide Switch</div>
        </div>
        <div id="canvas">
            <div style="padding:10px; background:#222; border-bottom:1px solid #444;">
                <button class="tool-btn" onclick="undo()">↶ Undo</button>
                <button class="tool-btn" onclick="rotate()">↻ Rotate</button>
                <button class="tool-btn" onclick="remove()" style="background:#822;">✖ Delete</button>
                <button class="tool-btn" onclick="simulate()" id="sim-btn" style="background:#d4a017; color:black;">⚡ Start</button>
            </div>

            <svg class="overlay" id="wire-layer"></svg>
            <svg class="overlay" id="flow-layer"></svg>

            <div class="bb-outer" id="bb">
                <!-- LHS RAILS -->
                <div class="bb-section rail" id="rail-L"></div>
                
                <!-- MAIN LEFT -->
                <div style="display:flex; flex-direction:column;">
                    <div class="header-row">
                        <div class="header-cell">a</div><div class="header-cell">b</div><div class="header-cell">c</div><div class="header-cell">d</div><div class="header-cell">e</div>
                    </div>
                    <div class="bb-section main" id="main-L"></div>
                </div>

                <!-- NUMBERS -->
                <div class="bb-section" style="width:20px; margin-top:20px;" id="nums"></div>

                <!-- TRENCH -->
                <div class="trench" style="margin-top:20px;"></div>

                <!-- MAIN RIGHT -->
                <div style="display:flex; flex-direction:column;">
                    <div class="header-row">
                        <div class="header-cell">f</div><div class="header-cell">g</div><div class="header-cell">h</div><div class="header-cell">i</div><div class="header-cell">j</div>
                    </div>
                    <div class="bb-section main" id="main-R"></div>
                </div>

                <!-- RHS RAILS -->
                <div class="bb-section rail" id="rail-R"></div>
            </div>

            <div id="comp-layer"></div>
        </div>
    </div>

    <script>
        const ASSETS = {assets_json};
        const GRID = 20;
        let comps = [];
        let wires = [];
        let history = [];
        let selection = null;
        let drag = null;
        let dragOff = {{x:0, y:0}};
        let wiringHole = null;
        let simMode = false;

        function createHoles(id, cols, tag) {{
            const div = document.getElementById(id);
            for(let r=0; r<30; r++) {{
                for(let c=0; c<cols; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    h.id = `h_${{tag}}_${{r}}_${{c}}`;
                    h.onmousedown = (e) => onHoleClick(e, h.id);
                    div.appendChild(h);
                }}
            }}
        }}
        createHoles('rail-L', 2, 'RL');
        createHoles('main-L', 5, 'ML');
        createHoles('main-R', 5, 'MR');
        createHoles('rail-R', 2, 'RR');

        const numBox = document.getElementById('nums');
        for(let i=1; i<=30; i++) {{
            const n = document.createElement('div');
            n.style = "height:20px; font-size:9px; text-align:center; color:#999; line-height:20px;";
            n.innerText = i; numBox.appendChild(n);
        }}

        function onHoleClick(e, id) {{
            e.stopPropagation();
            if(!wiringHole) {{
                wiringHole = id;
                document.getElementById(id).classList.add('active');
            }} else {{
                if(wiringHole !== id) {{
                    wires.push({{start: wiringHole, end: id}});
                    save(); renderWires();
                }}
                document.getElementById(wiringHole).classList.remove('active');
                wiringHole = null;
            }}
        }}

        function spawn(type) {{
            const id = 'c' + Date.now();
            let pins = [{{x:10, y:30}}, {{x:30, y:30}}];
            if(type.includes('RES')) pins = [{{x:10, y:10}}, {{x:70, y:10}}];
            if(type === 'SWITCH') pins = [{{x:10, y:10}}, {{x:30, y:10}}, {{x:50, y:10}}];
            if(type === 'BATTERY') pins = [{{x:10, y:50}}, {{x:30, y:50}}];
            
            comps.push({{id, type, x:100, y:100, rot:0, pins, lit:false, broken:false, conns:[]}});
            selection = id;
            save(); renderComps();
        }}

        function renderComps() {{
            const layer = document.getElementById('comp-layer');
            comps.forEach(c => {{
                let el = document.getElementById(c.id);
                if(!el) {{
                    el = document.createElement('div');
                    el.id = c.id; el.className = 'active-comp';
                    el.onmousedown = (e) => {{ e.stopPropagation(); drag = c; selection = c.id; dragOff = {{x:e.clientX - c.x, y:e.clientY - c.y}}; renderComps(); }};
                    layer.appendChild(el);
                }}
                el.classList.toggle('selected', selection === c.id);
                if(c.type === 'LED') {{
                    el.innerHTML = c.broken ? ASSETS.LED_BROKEN : (c.lit ? ASSETS.LED_ON : ASSETS.LED_OFF);
                }} else el.innerHTML = ASSETS[c.type];
                
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
            checkConns();
        }}

        function checkConns() {{
            const holes = Array.from(document.querySelectorAll('.hole'));
            holes.forEach(h => h.classList.remove('connected'));
            const rect = document.getElementById('canvas').getBoundingClientRect();

            comps.forEach(c => {{
                c.conns = [];
                const el = document.getElementById(c.id);
                el.querySelectorAll('.pin-collider').forEach(pc => {{
                    const pRect = pc.getBoundingClientRect();
                    const px = pRect.left - rect.left + 2;
                    const py = pRect.top - rect.top + 2;
                    
                    let best = null;
                    holes.forEach(h => {{
                        const hRect = h.getBoundingClientRect();
                        const hx = hRect.left - rect.left + 6;
                        const hy = hRect.top - rect.top + 6;
                        if(Math.abs(px-hx) < 8 && Math.abs(py-hy) < 8) best = h.id;
                    }});
                    if(best) {{
                        c.conns.push(best);
                        document.getElementById(best).classList.add('connected');
                    }} else c.conns.push(null);
                }});
            }});
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
                drag.x = Math.round(drag.x / GRID) * GRID;
                drag.y = Math.round(drag.y / GRID) * GRID;
                drag = null; save(); renderComps();
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
                l.className = 'wire';
                l.ondblclick = () => {{ wires.splice(i,1); save(); renderWires(); }};
                layer.appendChild(l);
            }});
        }}

        function simulate() {{
            simMode = !simMode;
            const btn = document.getElementById('sim-btn');
            document.getElementById('flow-layer').innerHTML = '';
            
            if(simMode) {{
                btn.innerText = "⏹ Stop"; btn.style.background = "#822"; btn.style.color = "white";
                runLogic();
            }} else {{
                btn.innerText = "⚡ Start"; btn.style.background = "#d4a017"; btn.style.color = "black";
                comps.forEach(c => {{ c.lit = false; c.broken = false; }});
                renderComps();
            }}
        }}

        function runLogic() {{
            let graph = {{}};
            const link = (u, v, w) => {{
                if(!u || !v) return;
                if(!graph[u]) graph[u] = []; if(!graph[v]) graph[v] = [];
                graph[u].push({{to:v, w}}); graph[v].push({{to:u, w}});
            }};

            // Breadboard Internal Paths
            for(let r=0; r<30; r++) {{
                for(let c=0; c<4; c++) {{
                    link(`h_ML_${{r}}_${{c}}`, `h_ML_${{r}}_${{c+1}}`, 0);
                    link(`h_MR_${{r}}_${{c}}`, `h_MR_${{r}}_${{c+1}}`, 0);
                }}
                if(r<29) {{
                    link(`h_RL_${{r}}_0`, `h_RL_${{r+1}}_0`, 0); link(`h_RL_${{r}}_1`, `h_RL_${{r+1}}_1`, 0);
                    link(`h_RR_${{r}}_0`, `h_RR_${{r+1}}_0`, 0); link(`h_RR_${{r}}_1`, `h_RR_${{r+1}}_1`, 0);
                }}
            }}
            wires.forEach(w => link(w.start, w.end, 0));

            let bat = comps.find(c => c.type === 'BATTERY');
            if(!bat || bat.conns.includes(null)) return;

            comps.forEach(c => {{
                if(c.type.includes('RES')) link(c.conns[0], c.conns[1], 100);
                if(c.type === 'LED') link(c.conns[0], c.conns[1], 10);
                if(c.type === 'SWITCH') {{ link(c.conns[0], c.conns[1], 0); link(c.conns[1], c.conns[2], 0); }}
            }});

            // BFS for path
            let q = [{{id: bat.conns[0], path: [bat.conns[0]], res: 0}}];
            let seen = new Set();
            let result = null;

            while(q.length > 0) {{
                let cur = q.shift();
                if(cur.id === bat.conns[1]) {{ result = cur; break; }}
                if(seen.has(cur.id)) continue;
                seen.add(cur.id);
                (graph[cur.id] || []).forEach(e => {{
                    q.push({{id: e.to, path: [...cur.path, e.to], res: cur.res + e.w}});
                }});
            }}

            if(result) {{
                const shorted = result.res < 50;
                comps.forEach(c => {{
                    if(c.type === 'LED' && result.path.includes(c.conns[0])) {{
                        c.lit = !shorted; c.broken = shorted;
                    }}
                }});
                drawFlow(result.path);
                renderComps();
            }}
        }}

        function drawFlow(nodes) {{
            const layer = document.getElementById('flow-layer');
            const rect = document.getElementById('canvas').getBoundingClientRect();
            let d = "";
            nodes.forEach((n, i) => {{
                const r = document.getElementById(n).getBoundingClientRect();
                const x = r.left - rect.left + 6, y = r.top - rect.top + 6;
                d += (i===0 ? "M " : "L ") + x + " " + y;
            }});
            const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            p.setAttribute('d', d); p.setAttribute('fill', 'none');
            p.className = 'flow-line'; layer.appendChild(p);
        }}

        function rotate() {{
            if(!selection) return;
            const c = comps.find(x => x.id === selection);
            c.rot = (c.rot + 90) % 360; save(); renderComps();
        }}

        function remove() {{
            comps = comps.filter(x => x.id !== selection);
            selection = null; save(); renderComps();
        }}

        function save() {{
            history.push(JSON.stringify({{comps, wires}}));
            if(history.length > 20) history.shift();
        }}

        function undo() {{
            if(history.length > 1) {{
                history.pop();
                const last = JSON.parse(history[history.length-1]);
                comps = last.comps; wires = last.wires;
                renderComps(); renderWires();
            }}
        }}

        save();
    </script>
</body>
</html>
"""

components.html(simulator_html, height=850)
