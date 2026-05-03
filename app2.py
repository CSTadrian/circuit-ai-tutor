# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import urllib.parse

# --- 1. CONFIG ---
st.set_page_config(page_title="Pro-STEM Interactive Lab", layout="wide")

# --- 2. VECTOR ASSETS (Refined for Breadboard Logic) ---
ASSETS = {
    # LED: Long leg (Anode +), Short leg/Flat side (Cathode -). Spans 1 Grid Unit.
    "LED_OFF": '''<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 35 L12 20 M28 35 L28 25" stroke="#aaa" stroke-width="2"/>
        <path d="M10 20 Q 10 5 20 5 Q 30 5 30 20 L30 22 L10 22 Z" fill="#882222"/>
        <line x1="30" y1="18" x2="30" y2="22" stroke="#441111" stroke-width="2"/> 
    </svg>''',
    
    "LED_ON": '''<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 35 L12 20 M28 35 L28 25" stroke="#aaa" stroke-width="2"/>
        <path d="M10 20 Q 10 5 20 5 Q 30 5 30 20 L30 22 L10 22 Z" fill="#ff4444" filter="drop-shadow(0 0 5px red)"/>
        <circle cx="20" cy="12" r="4" fill="white" opacity="0.5"/>
    </svg>''',
    
    # Resistor: Spans 1 Grid Unit
    "RES_300": '''<svg width="40" height="20" viewBox="0 0 40 20" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="9" width="40" height="2" fill="#aaa"/>
        <rect x="10" y="5" width="20" height="10" rx="2" fill="#69a8e6"/>
        <rect x="14" y="5" width="2" height="10" fill="orange"/>
        <rect x="18" y="5" width="2" height="10" fill="black"/>
        <rect x="22" y="5" width="2" height="10" fill="black"/>
    </svg>''',

    # Battery: Spans 1 Grid Unit
    "BATTERY": '''<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
        <rect x="10" y="5" width="20" height="25" rx="2" fill="#333"/>
        <rect x="10" y="5" width="10" height="25" fill="#ff4444"/>
        <path d="M15 30 L15 40 M25 30 L25 40" stroke="#aaa" stroke-width="2"/>
        <text x="12" y="15" fill="white" font-size="8" font-family="sans-serif">+</text>
    </svg>'''
}

# --- 3. UI ---
with st.sidebar:
    st.title("🔋 Pro-STEM Lab v2")
    st.info("Components now snap to exactly 1 hole distance. Long leg = Positive.")

# --- 4. SIMULATOR ENGINE ---
assets_json = json.dumps(ASSETS)

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #222; color: white; margin: 0; overflow: hidden; user-select: none; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 180px; background: #333; padding: 15px; border-right: 2px solid #444; }}
        #canvas {{ flex-grow: 1; position: relative; background: #1a1a1a; overflow: auto; }}
        
        .toolbar {{ position: absolute; top: 10px; left: 10px; z-index: 100; display: flex; gap: 10px; }}
        .btn {{ padding: 8px 15px; border-radius: 5px; border: none; cursor: pointer; font-weight: bold; }}
        .btn-sim {{ background: #f39c12; }}
        .btn-stop {{ background: #dc3545; color: white; }}

        /* Breadboard Styling */
        .bb-container {{ 
            position: absolute; top: 60px; left: 60px; background: #eee; 
            padding: 20px; border-radius: 5px; display: flex; gap: 20px; color: #666;
        }}
        .bb-grid {{ display: grid; grid-template-rows: repeat(30, var(--grid)); }}
        .bb-column-labels {{ display: flex; font-size: 10px; font-weight: bold; margin-bottom: 5px; justify-content: space-around; }}
        
        .hole {{ 
            width: 12px; height: 12px; background: #bbb; border-radius: 50%; 
            margin: 4px; transition: 0.2s; box-shadow: inset 1px 1px 2px rgba(0,0,0,0.3);
        }}
        .hole.occupied {{ background: #add8e6 !important; box-shadow: 0 0 5px #87ceeb; }}
        
        .comp-item {{ background: #444; padding: 10px; margin-bottom: 10px; cursor: pointer; border-radius: 4px; text-align: center; font-size: 11px; }}
        .active-comp {{ position: absolute; cursor: grab; z-index: 50; pointer-events: auto; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <div class="comp-item" onclick="spawn('BATTERY')">{ASSETS['BATTERY']}<br>9V Battery</div>
            <div class="comp-item" onclick="spawn('LED')">{ASSETS['LED_OFF']}<br>LED (Red)</div>
            <div class="comp-item" onclick="spawn('RES_300')">{ASSETS['RES_300']}<br>300Ω Resistor</div>
        </div>
        <div id="canvas">
            <div class="toolbar">
                <button id="simToggle" class="btn btn-sim" onclick="toggleSim()">⚡ Start Simulation</button>
                <button class="btn" style="background:#555; color:white" onclick="location.reload()">Reset</button>
            </div>

            <div class="bb-container" id="bb">
                <!-- Left Section (a-e) -->
                <div>
                    <div class="bb-column-labels"><span>a</span><span>b</span><span>c</span><span>d</span><span>e</span></div>
                    <div class="bb-grid" id="grid-left"></div>
                </div>
                <div style="width: 20px; background: #ccc; margin: 20px 0 0 0; border-radius: 2px;"></div>
                <!-- Right Section (f-j) -->
                <div>
                    <div class="bb-column-labels"><span>f</span><span>g</span><span>h</span><span>i</span><span>j</span></div>
                    <div class="bb-grid" id="grid-right"></div>
                </div>
            </div>
            <div id="comp-layer"></div>
        </div>
    </div>

    <script>
        const ASSETS = {assets_json};
        let components = [];
        let isSimulating = false;
        let dragging = null;

        // Create 30 rows of 5 holes for each side
        function initGrid(id) {{
            const grid = document.getElementById(id);
            for(let r=0; r<30; r++) {{
                const row = document.createElement('div');
                row.style.display = 'flex';
                for(let c=0; c<5; c++) {{
                    const h = document.createElement('div');
                    h.className = 'hole';
                    h.id = `h-${{id}}-${{r}}-${{c}}`;
                    row.appendChild(h);
                }}
                grid.appendChild(row);
            }}
        }}
        initGrid('grid-left');
        initGrid('grid-right');

        function spawn(type) {{
            const id = 'c' + Date.now();
            components.push({{ id, type, x: 50, y: 50, lit: false }});
            render();
        }}

        function render() {{
            const layer = document.getElementById('comp-layer');
            layer.innerHTML = '';
            
            // Reset hole highlights
            document.querySelectorAll('.hole').forEach(h => h.classList.remove('occupied'));

            components.forEach(c => {{
                const div = document.createElement('div');
                div.className = 'active-comp';
                div.style.left = c.x + 'px';
                div.style.top = c.y + 'px';
                
                let icon = ASSETS[c.type] || ASSETS['LED_OFF'];
                if(c.type === 'LED') icon = c.lit ? ASSETS['LED_ON'] : ASSETS['LED_OFF'];
                div.innerHTML = icon;

                div.onmousedown = (e) => startDrag(e, c);
                layer.appendChild(div);

                // Highlight holes if snapped
                highlightHoles(c);
            }});
        }}

        function highlightHoles(c) {{
            // Find holes closest to component pins (Pins are roughly 20px apart)
            const holes = document.querySelectorAll('.hole');
            holes.forEach(h => {{
                const r = h.getBoundingClientRect();
                const cx = c.x + 15; // Pin 1 offset
                const cy = c.y + 35; // Pin 1 offset
                const dist = Math.hypot(r.left - cx, r.top - cy);
                if(dist < 15) h.classList.add('occupied');
                
                // Pin 2 (20px to the right)
                const cx2 = cx + 20;
                const dist2 = Math.hypot(r.left - cx2, r.top - cy);
                if(dist2 < 15) h.classList.add('occupied');
            }});
        }}

        function startDrag(e, c) {{
            dragging = c;
            const startX = e.clientX - c.x;
            const startY = e.clientY - c.y;

            document.onmousemove = (ev) => {{
                c.x = ev.clientX - startX;
                c.y = ev.clientY - startY;
                render();
            }};

            document.onmouseup = () => {{
                // Snap to Grid (20px)
                c.x = Math.round(c.x / 20) * 20;
                c.y = Math.round(c.y / 20) * 20;
                document.onmousemove = null;
                dragging = null;
                render();
            }};
        }}

        function toggleSim() {{
            isSimulating = !isSimulating;
            const btn = document.getElementById('simToggle');
            
            if(isSimulating) {{
                btn.innerText = "🛑 Stop Simulation";
                btn.className = "btn btn-stop";
                // Simple Logic: if battery + resistor + LED exist, light up
                const hasBat = components.some(c => c.type === 'BATTERY');
                const hasRes = components.some(c => c.type === 'RES_300');
                components.forEach(c => {{
                    if(c.type === 'LED' && hasBat && hasRes) c.lit = true;
                }});
            }} else {{
                btn.innerText = "⚡ Start Simulation";
                btn.className = "btn btn-sim";
                components.forEach(c => c.lit = false);
            }}
            render();
        }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=800)
