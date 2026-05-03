# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
from PIL import Image as PILImage

# --- VERTEX AI SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

st.set_page_config(page_title="Pro-STEM Precision Lab", layout="wide")

# --- 1. ASSETS & SIMULATOR HTML ---
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

simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {{ --grid: 20px; --pale-blue: #add8e6; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: white; margin: 0; overflow: hidden; }}
        #workspace {{ display: flex; height: 100vh; }}
        #palette {{ width: 220px; background: #222; padding: 15px; border-right: 1px solid #444; overflow-y: auto; }}
        .comp-item {{ background: #333; padding: 10px; margin-bottom: 10px; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid #444; }}
        .comp-item:hover {{ background: #444; border-color: #3498db; }}
        #canvas {{ flex-grow: 1; position: relative; background: #111; overflow: auto; }}
        #toolbar {{ padding: 10px; background: #222; border-bottom: 1px solid #444; display: flex; gap: 10px; }}
        .tool-btn {{ background: #444; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
        .tool-btn:hover {{ background: #3498db; }}
        .bb-outer {{ position: absolute; top: 60px; left: 40px; background: #eee; padding: 25px; border-radius: 12px; display: flex; align-items: flex-start; box-shadow: 0 10px 40px rgba(0,0,0,0.5); gap: 8px; }}
        .hole {{ width: 12px; height: 12px; background: #bbb; border-radius: 50%; margin: 4px; cursor: pointer; position: relative; z-index: 10; }}
        .hole.occupied {{ background: var(--pale-blue) !important; }}
        .active-comp {{ position: absolute; z-index: 100; cursor: grab; transform-origin: 0 0; }}
        .pin-collider {{ position: absolute; width: 4px; height: 4px; opacity: 0; pointer-events: none; }}
        svg.overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 50; }}
        .wire {{ stroke: #2ecc71; stroke-width: 4; stroke-linecap: round; pointer-events: auto; }}
        .sync-box {{ background: #27ae60; color: white; padding: 10px; border-radius: 4px; text-align: center; cursor: pointer; font-weight: bold; margin-top: 20px; }}
    </style>
</head>
<body>
    <div id="workspace">
        <div id="palette">
            <h4 style="margin:0 0 10px 0;">Components</h4>
            <div class="comp-item" onclick="spawn('BATTERY')">{ASSETS_RAW['BATTERY']}<br>Battery</div>
            <div class="comp-item" onclick="spawn('LED')">{ASSETS_RAW['LED']['OFF']}<br>LED</div>
            <div class="comp-item" onclick="spawn('RESISTOR')">{ASSETS_RAW['RESISTOR']['1000']}<br>1k Resistor</div>
            
            <div class="sync-box" onclick="copyState()">📋 Copy Circuit Data</div>
            <p style="font-size: 10px; color: #888; margin-top: 10px;">Click this button then paste into the "Circuit Link" box below.</p>
        </div>

        <div id="canvas">
            <div id="toolbar">
                <button class="tool-btn" onclick="rotateComp()">↻ Rotate</button>
                <button class="tool-btn" onclick="deleteComp()" style="background:#c0392b;">✖ Delete</button>
                <button class="tool-btn" id="sim-btn" onclick="toggleSim()" style="background:#f39c12; color:black; margin-left:auto; font-weight:bold;">⚡ Stimulate</button>
            </div>
            <svg class="overlay" id="wire-layer"></svg>
            <div class="bb-outer" id="board">
                <div class="main-grid" id="main-grid" style="display:grid; grid-template-columns:repeat(5, var(--grid)); grid-template-rows:repeat(30, var(--grid));"></div>
            </div>
            <div id="comp-layer"></div>
        </div>
    </div>

    <script>
        const ASSETS = {json.dumps(ASSETS_RAW)};
        let comps = [];
        let selection = null;
        let drag = null;
        let dragOff = {{x:0, y:0}};
        let isSimulating = false;

        // Generate breadboard holes
        const grid = document.getElementById('main-grid');
        for(let r=0; r<30; r++) {{
            for(let c=0; c<5; c++) {{
                const h = document.createElement('div');
                h.className = 'hole'; h.id = `h_ML_${{r}}_${{c}}`;
                grid.appendChild(h);
            }}
        }}

        function getTrack(holeId) {{ return holeId ? holeId.split('_').slice(1,3).join('_') : null; }}

        function spawn(type) {{
            const id = 'c' + Date.now();
            let pins = [{{x:10, y:48}}, {{x:30, y:48}}];
            if(type === 'RESISTOR') pins = [{{x:5, y:10}}, {{x:75, y:10}}];
            
            comps.push({{id, type, x:250, y:150, rot:0, pins, state:'OFF', value: (type==='RESISTOR'?'1000':null), connectedTracks: []}});
            selection = id;
            renderComps();
        }}

        function renderComps() {{
            const layer = document.getElementById('comp-layer');
            comps.forEach(c => {{
                let el = document.getElementById(c.id);
                if(!el) {{
                    el = document.createElement('div'); el.id = c.id; el.className = 'active-comp';
                    el.onmousedown = (e) => {{ drag = c; selection = c.id; dragOff = {{x:e.clientX - c.x, y:e.clientY - c.y}}; renderComps(); }};
                    layer.appendChild(el);
                }}
                el.style.left = c.x + 'px'; el.style.top = c.y + 'px';
                el.style.transform = `rotate(${{c.rot}}deg)`;
                el.innerHTML = c.type === 'LED' ? ASSETS.LED[c.state] : (c.type === 'RESISTOR' ? ASSETS.RESISTOR['1000'] : ASSETS.BATTERY);
                
                el.querySelectorAll('.pin-collider').forEach(p => p.remove());
                c.pins.forEach(p => {{
                    const dot = document.createElement('div'); dot.className = 'pin-collider';
                    dot.style.left = p.x + 'px'; dot.style.top = p.y + 'px'; el.appendChild(dot);
                }});
            }});
            Array.from(layer.children).forEach(child => {{ if(!comps.find(x => x.id === child.id)) child.remove(); }});
            updateHoles();
        }}

        function updateHoles() {{
            const holes = Array.from(document.querySelectorAll('.hole'));
            holes.forEach(h => h.classList.remove('occupied'));
            const rect = document.getElementById('canvas').getBoundingClientRect();
            
            comps.forEach(c => {{
                c.connectedTracks = [];
                const el = document.getElementById(c.id);
                el.querySelectorAll('.pin-collider').forEach((pc, idx) => {{
                    const pRect = pc.getBoundingClientRect();
                    const px = pRect.left - rect.left; const py = pRect.top - rect.top;
                    let best = null; let minDist = 15;
                    holes.forEach(h => {{
                        const hRect = h.getBoundingClientRect();
                        const hx = hRect.left - rect.left; const hy = hRect.top - rect.top;
                        const dist = Math.hypot(px-hx, py-hy);
                        if(dist < minDist) {{ minDist = dist; best = h; }}
                    }});
                    if(best) {{ best.classList.add('occupied'); c.connectedTracks[idx] = best.id; }}
                }});
            }});
        }}

        function copyState() {{
            const data = JSON.stringify(comps);
            navigator.clipboard.writeText(data);
            alert("Circuit data copied! Now paste it into the box below the board.");
        }}

        document.onmousemove = (e) => {{ if(drag) {{ drag.x = e.clientX - dragOff.x; drag.y = e.clientY - dragOff.y; renderComps(); }} }};
        document.onmouseup = () => {{ drag = null; renderComps(); }};
        function rotateComp() {{ if(selection) {{ const c = comps.find(x => x.id === selection); c.rot = (c.rot + 90) % 360; renderComps(); }} }}
        function deleteComp() {{ comps = comps.filter(x => x.id !== selection); selection = null; renderComps(); }}
        function toggleSim() {{ isSimulating = !isSimulating; }}
    </script>
</body>
</html>
"""

# --- 2. STREAMLIT APP LOGIC ---
st.title("⚡ AI Circuit Auditor & Tutor")

# Vertex AI Initialization
@st.cache_resource
def get_vertex_client():
    if "gcp_service_account" in st.secrets:
        creds_info = st.secrets["gcp_service_account"]
        credentials = service_account.Credentials.from_service_account_info(creds_info)
        return genai.Client(vertexai=True, project=creds_info["project_id"], location="global", credentials=credentials)
    return None

client = get_vertex_client()
MODEL_ID = "gemini-3.1-pro-preview"

# --- LAYOUT ---
# 1. Simulator Platform
components.html(simulator_html, height=600)

st.divider()

# 2. Audit Control Panel (Directly under the platform)
c1, c2 = st.columns([1, 1])

with c1:
    st.subheader("🛠️ Step 1: Sync Your Data")
    # This is the bridge. Students paste the copied JSON here.
    circuit_json = st.text_area("Circuit Link (Paste copied data here)", height=100, placeholder='[{"id":"c123...", "type":"LED"...}]')
    schematic_file = st.file_uploader("Step 2: Upload Target Schematic", type=["jpg", "png", "jpeg"])

with c2:
    st.subheader("🔍 Step 3: Run Audit")
    
    if st.button("🚀 Check My Circuit", type="primary", use_container_width=True):
        if not circuit_json or circuit_json == "[]":
            st.error("AI Observation: I can't see your circuit yet. Please click 'Copy Circuit Data' above and paste it in the box.")
        elif not schematic_file:
            st.warning("Please upload a schematic for comparison.")
        else:
            try:
                # Process the data
                data = json.loads(circuit_json)
                obs_list = []
                for comp in data:
                    tracks = [t for t in comp.get('connectedTracks', []) if t]
                    track_str = " & ".join(tracks) if tracks else "Unconnected"
                    obs_list.append(f"- **{comp['type']}**: {track_str}")
                
                st.info("👁️ **AI Observation**\n" + "\n".join(obs_list))
                
                # Run AI Feedback
                if client:
                    raw_img = PILImage.open(schematic_file).convert("RGB")
                    prompt = f"Student Circuit Data: {json.dumps(data)}. Compare this to the schematic. Provide pedagogical feedback on connections and polarity."
                    
                    resp = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[raw_img, prompt],
                        config=types.GenerateContentConfig(temperature=0.2)
                    )
                    st.success("🤖 **Tutor Feedback**")
                    st.markdown(resp.text)
                else:
                    st.warning("Vertex AI Client not configured. Showing basic connection check only.")
            except Exception as e:
                st.error(f"Failed to read circuit data: {e}")

# Sidebar for Teacher Instructions
with st.sidebar:
    st.header("Lab Instructions")
    st.write("1. Build your circuit on the breadboard.")
    st.write("2. Use the **Copy Circuit Data** button to capture your build.")
    st.write("3. Paste the data into the **Circuit Link** box.")
    st.write("4. Upload your target diagram and click **Check My Circuit**.")
