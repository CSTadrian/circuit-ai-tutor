# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
from google import genai
from google.oauth2 import service_account

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="Socratic Breadboard", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Initialize Session State for game mechanics
if "tokens" not in st.session_state: st.session_state.tokens = 10
if "ai_feedback" not in st.session_state: st.session_state.ai_feedback = ""

# Authentication for Gemini
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

# --- 2. THE DATA BRIDGE (Query Parameter Logic) ---
# We check if the URL contains "circuit_data". If it does, the student just clicked "Analyze".
query_params = st.query_params
incoming_data = query_params.get("circuit_data")

if incoming_data:
    # Clear the URL immediately to prevent infinite loops
    st.query_params.clear()
    
    # Process the data
    st.session_state.tokens -= 1
    try:
        circuit_topology = json.loads(incoming_data)
        
        # --- SOCRATIC AI LOGIC ---
        # We send the raw hole connections to Gemini to detect "struggle"
        prompt = f"""
        You are a Socratic tutor for P4-S3 engineering students.
        Student's Breadboard Connections (Hole IDs): {circuit_topology}
        
        GOAL: The student needs a closed loop (Battery -> Resistor -> LED -> Battery).
        
        TASKS:
        1. Analyze if the circuit is 'Open' (broken path) or 'Short' (bypassing LED).
        2. If they are struggling, do NOT give the answer.
        3. Ask a Socratic question about the 'physical flow' of electricity.
        4. Reference specific Hole IDs if they have tried many times.
        """
        
        if client:
            response = client.models.generate_content(model=MODEL_ID, contents=prompt)
            st.session_state.ai_feedback = response.text
        else:
            st.session_state.ai_feedback = "AI Error: Check GCP Secrets."
            
    except Exception as e:
        st.error(f"Data Decode Error: {e}")

# --- 3. UI LAYOUT ---
with st.sidebar:
    st.title("🔋 Mission Control")
    st.metric("Tokens Remaining", st.session_state.tokens)
    if st.button("Reset Game"):
        st.query_params.clear()
        st.session_state.tokens = 10
        st.session_state.ai_feedback = ""
        st.rerun()

# Display AI feedback if it exists
if st.session_state.ai_feedback:
    st.info(f"🤖 **AI Tutor:** {st.session_state.ai_feedback}")

# --- 4. THE INTERACTIVE BREADBOARD (HTML/JS) ---
# This JS now includes 'URL Redirection' to send data back to Python
simulator_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; background: #f0f2f6; display: flex; flex-direction: column; align-items: center; }}
        #canvas {{ width: 800px; height: 400px; background: white; border: 2px solid #333; position: relative; border-radius: 8px; }}
        .hole {{ width: 10px; height: 10px; background: #ddd; border-radius: 50%; position: absolute; cursor: pointer; }}
        .hole:hover {{ background: #ffaa00; }}
        .btn {{ margin-top: 20px; padding: 10px 25px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }}
        .label {{ position: absolute; font-size: 12px; font-weight: bold; color: #555; }}
    </style>
</head>
<body>
    <h3>🏗️ Breadboard Sandbox</h3>
    <div id="canvas">
        <!-- Labels for Rows/Cols -->
        <div class="label" style="top: 10px; left: 10px;">9V Battery (+)</div>
        <div class="label" style="top: 370px; left: 10px;">Ground (-)</div>
        
        <svg id="wire-svg" style="position:absolute; width:100%; height:100%; pointer-events:none;"></svg>
    </div>
    <button class="btn" onclick="sendToStreamlit()">🔍 Analyze My Circuit (-1 Token)</button>

    <script>
        const canvas = document.getElementById('canvas');
        const svg = document.getElementById('wire-svg');
        const connections = [];
        let firstHole = null;

        // Create a basic breadboard grid (10 rows x 30 columns)
        for (let r = 0; r < 10; r++) {{
            for (let c = 0; c < 30; c++) {{
                const hole = document.createElement('div');
                hole.className = 'hole';
                const x = 50 + (c * 24);
                const y = 50 + (r * 30);
                hole.style.left = x + 'px';
                hole.style.top = y + 'px';
                hole.dataset.id = `R${{r}}C${{c}}`;
                
                hole.onclick = (e) => {{
                    if (!firstHole) {{
                        firstHole = hole;
                        hole.style.background = 'blue';
                    }} else {{
                        const h1 = firstHole.getBoundingClientRect();
                        const h2 = hole.getBoundingClientRect();
                        const cRect = canvas.getBoundingClientRect();
                        
                        // Record connection
                        connections.push({{ from: firstHole.dataset.id, to: hole.dataset.id }});
                        
                        // Draw Wire
                        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                        line.setAttribute('x1', h1.left - cRect.left + 5);
                        line.setAttribute('y1', h1.top - cRect.top + 5);
                        line.setAttribute('x2', h2.left - cRect.left + 5);
                        line.setAttribute('y2', h2.top - cRect.top + 5);
                        line.setAttribute('stroke', '#333');
                        line.setAttribute('stroke-width', '3');
                        svg.appendChild(line);
                        
                        firstHole.style.background = '#ddd';
                        firstHole = null;
                    }}
                }};
                canvas.appendChild(hole);
            }}
        }}

        function sendToStreamlit() {{
            if (connections.length === 0) {{
                alert("Connect some wires first!");
                return;
            }}
            // THE BRIDGE: Push data to the URL so Streamlit can read it
            const dataString = JSON.stringify(connections);
            const newUrl = window.parent.location.origin + window.parent.location.pathname + '?circuit_data=' + encodeURIComponent(dataString);
            window.parent.location.assign(newUrl);
        }}
    </script>
</body>
</html>
"""

components.html(simulator_html, height=550)
