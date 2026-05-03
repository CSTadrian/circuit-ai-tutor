# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json

st.set_page_config(page_title="Pro-STEM Accurate Lab", layout="wide")

# --- 1. VECTOR ASSETS (Scaled for 1-hole pitch) ---
ASSETS = {
    # LED: Long leg (+), Short leg (-)
    "LED_OFF": '''<svg width="40" height="60" viewBox="0 0 40 60" xmlns="http://www.w3.org/2000/svg">
        <line x1="10" y1="30" x2="10" y2="60" stroke="#aaa" stroke-width="2.5"/>
        <line x1="30" y1="30" x2="30" y2="50" stroke="#aaa" stroke-width="2.5"/>
        <path d="M5 30 Q 5 5 20 5 Q 35 5 35 30 Z" fill="#882222" opacity="0.9"/>
    </svg>''',
    
    "LED_ON": '''<svg width="40" height="60" viewBox="0 0 40 60" xmlns="http://www.w3.org/2000/svg">
        <line x1="10" y1="30" x2="10" y2="60" stroke="#aaa" stroke-width="2.5"/>
        <line x1="30" y1="30" x2="30" y2="50" stroke="#aaa" stroke-width="2.5"/>
        <path d="M5 30 Q 5 5 20 5 Q 35 5 35 30 Z" fill="#ff0000" filter="drop-shadow(0px 0px 10px red)"/>
    </svg>''',
    
    # Battery: 4.5V (3-cell) with pins at 20px (1 hole) spacing
    "BATTERY": '''<svg width="50" height="60" viewBox="0 0 50 60" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="40" height="35" rx="3" fill="#333"/>
        <rect x="5" y="10" width="15" height="25" fill="#ff4444"/>
        <text x="10" y="30" fill="white" font-size="10" font-family="Arial">+</text>
        <line x1="15" y1="40" x2="15" y2="60" stroke="#ff4444" stroke-width="3"/>
        <line x1="35" y1="40" x2="35" y2="60" stroke="#4444ff" stroke-width="3"/>
    </svg>''',
    
    "RESISTOR": '''<svg width="60" height="20" viewBox="0 0 60 20" xmlns="http://www.w3.org/2000/svg">
        <line x1="10" y1="10" x2="50" y2="10" stroke="#aaa" stroke-width="2"/>
        <rect x="15" y="4" width="30" height="12" rx="3" fill="#69a8e6"/>
        <rect x="22" y="4" width="3" height="12" fill="#ff8c00"/>
        <rect x="35" y="4" width="3" height="12" fill="#8b4513"/>
    </svg>''',

    "SWITCH_L": '''<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="50" height="25" rx="2" fill="#222"/>
        <rect x="10" y="8" width="15" height="19" fill="#eee"/>
        <line x1="15" y1="30" x2="15" y2="45" stroke="#aaa" stroke-width="2"/>
        <line x1="35" y1="30" x2="35" y2="45" stroke="#aaa" stroke-width="2"/>
    </svg>''',

    "SWITCH_R": '''<svg width="60" height="40" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg">
        <rect x="5" y="5" width="50" height="25" rx="2" fill="#222"/>
        <rect x="35" y="8" width="15" height="19" fill="#eee"/>
        <line x1="15" y1="30" x2="15" y2="45" stroke="#aaa" stroke-width="2"/>
        <line x1="35" y1="30" x2="35" y2="45" stroke="#aaa" stroke-width="2"/>
    </svg>''',
}

# --- 2. SIMULATOR HTML ---
assets_json = json.dumps(ASSETS)
simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: sans-serif; background: #1a1a1a; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 200px; background: #2d2d2d; padding: 15px; border-right: 2px solid #444; }}
        #canvas {{ flex-grow: 1; position: relative; background: #222; overflow: auto; }}
        
        /* Breadboard Styling */
        .bb-main {{ 
            position: absolute; top: 100px; left: 250px; background: #f0f0f0; 
            padding: 25px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex; gap: 40px; border: 2px solid #ccc;
        }}
        .bb-group {{ display: flex; flex-direction: column; }}
        .label-row {{ display: flex; justify-content: space-around; color: #666; font-size: 12px; font-weight: bold; margin-bottom: 5px; }}
        .bb-grid {{ display: grid; grid-template-rows: repeat(30, var(--grid)); grid-template-columns: repeat(5, var(--grid)); gap: 2px; }}
        
        .hole {{ width: 14px; height: 14px; background: #bbb; border-radius: 50%; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.4); margin: 3px; }}
        .hole.occupied {{ background: #add8e6 !important; box-shadow: 0 0 8px #add8e6; }}
        
        /* Component Styling */
        .active-comp {{ position: absolute; cursor: grab; z-index: 100; transform-origin: 10px 10px; }}
        .active-comp.selected {{ filter: drop-shadow(0 0 5px #007bff); }}
        
        #toolbar {{ position: absolute; top: 20px; left: 220px; display: flex; gap: 10px; z-index: 1000; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }}
        .btn-run {{ background: #28a745; color: white; }}
        .btn-stop {{ background: #dc3545; color: white; }}
        .comp-card {{ background: #3d3d3d; padding: 10px; margin-bottom: 10px; border-radius: 5px; text-align: center; cursor: pointer; font-size: 13px; }}
        .comp-card:hover {{ background: #4d4d4d; border: 1px solid #007bff; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h3 style="margin-top:0">Components</h3>
            <div class="comp-card" onclick="addComp('BATTERY')">4.5V Battery</div>
            <div class="comp-card" onclick="addComp('LED')">LED (Polarized)</div>
            <div class="comp-card" onclick="addComp('RESISTOR')">Resistor</div>
            <div class="comp-card" onclick="addComp('SWITCH')">Slide Switch</div>
        </div>
        
        <div id="canvas">
            <div id="toolbar">
                <button id="simBtn" class="btn btn-run" onclick="toggleSim()">Start Stimulation</button>
                <button class="btn" onclick="rotateSelected()" style="background:#555; color:white;">Rotate 90°</button>
                <button class="btn" onclick="deleteSelected()" style="background:#771111; color:white;">Delete</button>
            </div>

            <div class="bb-main" id="bb-target">
                <!-- Left Section a-e -->
                <div class="bb-group">
                    <div class="label-row"><span>a</span><span>b</span><span>c</span><span>d</span><span>e</span></div>
                    <div class="bb-grid" id="grid-left"></div>
                </div>
                <!-- Right Section f-j -->
                <div class="bb-group">
                    <div class="label-row"><span>f</span><span>g</span><span>h</span><span>i</span><span>j</span></div>
                    <div class="bb-grid" id="grid-right"></div>
                </div>
            </div>
            <div id="comp-layer"></div>
        </div>
    </div>

    <script>
        const ASSETS = {assets_json};
        let comps = [];
        let selectedId = null;
        let isSimulating = false;

        function initBoard() {{
            const left = document.getElementById('grid-left');
            const right = document.getElementById('grid-right');
            for(let i=0; i<150; i++) {{
                const h = document.createElement('div');
                h.className = 'hole';
                h.id = 'h_L_' + i;
                left.appendChild(h);
            }}
            for(let i=0; i<150; i++) {{
                const h = document.createElement('div');
                h.className = 'hole';
                h.id = 'h_R_' + i;
                right.appendChild(h);
            }}
        }}
        initBoard();

        function addComp(type) {{
            const id = "c_" + Date.now();
            comps.push({{ id, type, x: 50, y: 150, rot: 0, state: 'L', lit: false }});
            selectedId = id;
            render();
        }}

        function toggleSim() {{
            isSimulating = !isSimulating;
            const btn = document.getElementById('simBtn');
            btn.className = isSimulating ? 'btn btn-stop' : 'btn btn-run';
            btn.innerText = isSimulating ? 'Stop Stimulation' : 'Start Stimulation';
            updateLogic();
        }}

        function render() {{
            const layer = document.getElementById('comp-layer');
            layer.innerHTML = "";
            
            // Clear hole highlights
            document.querySelectorAll('.hole').forEach(h => h.classList.remove('occupied'));

            comps.forEach(c => {{
                const div = document.createElement('div');
                div.className = "active-comp" + (selectedId === c.id ? " selected" : "");
                div.style.left = c.x + "px";
                div.style.top = c.y + "px";
                div.style.transform = `rotate(${{c.rot}}deg)`;
                
                let svgKey = c.type;
                if (c.type === 'LED') svgKey = (c.lit && isSimulating) ? 'LED_ON' : 'LED_OFF';
                if (c.type === 'SWITCH') svgKey = c.state === 'L' ? 'SWITCH_L' : 'SWITCH_R';
                
                div.innerHTML = ASSETS[svgKey];
                
                div.onmousedown = (e) => {{
                    e.stopPropagation();
                    selectedId = c.id;
                    startDrag(e, c);
                }};

                if(c.type === 'SWITCH') {{
                    div.onclick = () => {{ 
                        c.state = c.state === 'L' ? 'R' : 'L'; 
                        render();
                        updateLogic();
                    }};
                }}
                layer.appendChild(div);
                highlightHoles(c);
            }});
        }}

        function highlightHoles(c) {{
            const holes = document.querySelectorAll('.hole');
            holes.forEach(h => {{
                const r = h.getBoundingClientRect();
                const cx = r.left + r.width/2;
                const cy = r.top + r.height/2;
                
                // Logic: Pins are roughly at local (15, 50) and (35, 50) for these components
                // We check if a hole is very close to those points
                const distAnode = Math.sqrt((cx - (c.x + 15))**2 + (cy - (c.y + 55))**2);
                const distCathode = Math.sqrt((cx - (c.x + 35))**2 + (cy - (c.y + 55))**2);
                
                if(distAnode < 10 || distCathode < 10) {{
                    h.classList.add('occupied');
                }}
            }});
        }}

        function updateLogic() {{
            if(!isSimulating) {{
                comps.forEach(c => c.lit = false);
                render();
                return;
            }}
            // STEM Logic: Battery exists AND LED rotation is 0 (Long leg is on Left/+ side)
            const hasPower = comps.some(c => c.type === 'BATTERY');
            comps.forEach(c => {{
                if(c.type === 'LED') {{
                    c.lit = hasPower && (c.rot === 0);
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
            }}
            function stop() {{
                window.removeEventListener('mousemove', move);
                window.removeEventListener('mouseup', stop);
            }}
            window.addEventListener('mousemove', move);
            window.addEventListener('mouseup', stop);
        }}

        function rotateSelected() {{
            if(!selectedId) return;
            const c = comps.find(i => i.id === selectedId);
            c.rot = (c.rot + 90) % 360;
            render();
            updateLogic();
        }}

        function deleteSelected() {{
            comps = comps.filter(i => i.id !== selectedId);
            selectedId = null;
            render();
        }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=850)
