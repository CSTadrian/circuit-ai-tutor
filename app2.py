# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import json
import pandas as pd
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="Interactive Circuit Builder", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Setup Session State for the Token Economy
if "tokens" not in st.session_state: st.session_state.tokens = 5
if "team_name" not in st.session_state: st.session_state.team_name = "Engineering Alpha"
if "circuit_data" not in st.session_state: st.session_state.circuit_data = None

# Authentication Setup
@st.cache_resource
def get_ai_client():
    if "gcp_service_account" in st.secrets:
        creds_info = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        return genai.Client(
            vertexai=True, 
            project=creds_info["project_id"], 
            location="global", 
            credentials=credentials
        )
    return None

client = get_ai_client()

# --- 2. SIDEBAR: GAME MANAGEMENT ---
with st.sidebar:
    st.header(f"Team: {st.session_state.team_name}")
    st.metric("Tokens Remaining", st.session_state.tokens)
    st.divider()
    
    st.markdown("### Mission")
    st.markdown("Connect the Battery, Resistor, and LED in a continuous series loop.")
    
    if st.button("🆘 Buy Socratic Hint (-2 Tokens)"):
        if st.session_state.tokens >= 2:
            st.session_state.tokens -= 2
            st.info("Hint: Electricity must flow from the Battery (+), through the Resistor, into the LED (Anode), and back to the Battery (-).")
            st.rerun()
        else:
            st.error("Not enough tokens!")

# --- 3. THE FRONTEND: JAVASCRIPT CIRCUIT BUILDER ---
# This HTML block creates a sandbox where students can drag components and draw wires.
html_code = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; padding: 0; font-family: sans-serif; background-color: #f0f2f6; }
        #canvas-container { position: relative; width: 100%; height: 500px; background: white; border: 2px solid #ccc; overflow: hidden; }
        .component { position: absolute; width: 80px; height: 80px; background: #eee; border: 2px solid #333; border-radius: 8px; cursor: grab; user-select: none; display: flex; align-items: center; justify-content: center; font-weight: bold; text-align: center; font-size: 12px; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); }
        .component:active { cursor: grabbing; }
        .terminal { position: absolute; width: 14px; height: 14px; background: gold; border: 2px solid black; border-radius: 50%; cursor: crosshair; }
        .terminal:hover { background: red; transform: scale(1.2); }
        svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
        
        /* Specific Terminals */
        .term-top { top: -8px; left: 33px; }
        .term-bottom { bottom: -8px; left: 33px; }
        .term-left { left: -8px; top: 33px; }
        .term-right { right: -8px; top: 33px; }
        
        #instruction { padding: 10px; background: #e8f0fe; color: #1a73e8; border-bottom: 1px solid #ccc;}
    </style>
</head>
<body>
    <div id="instruction">Drag blocks to move. Click and drag between gold terminals to draw wires.</div>
    <div id="canvas-container">
        <svg id="wire-layer"></svg>
        
        <!-- Battery -->
        <div class="component" id="Battery" style="left: 50px; top: 50px; background: #ffcccc;">
            Battery
            <div class="terminal term-top" data-parent="Battery" data-node="Positive" title="Positive (+)"></div>
            <div class="terminal term-bottom" data-parent="Battery" data-node="Negative" title="Negative (-)"></div>
        </div>

        <!-- LED -->
        <div class="component" id="LED" style="left: 300px; top: 50px; background: #ccffcc;">
            LED
            <div class="terminal term-left" data-parent="LED" data-node="Anode" title="Anode (+)"></div>
            <div class="terminal term-right" data-parent="LED" data-node="Cathode" title="Cathode (-)"></div>
        </div>

        <!-- Resistor -->
        <div class="component" id="Resistor" style="left: 175px; top: 250px; background: #ccccff;">
            Resistor
            <div class="terminal term-left" data-parent="Resistor" data-node="P1" title="Pin 1"></div>
            <div class="terminal term-right" data-parent="Resistor" data-node="P2" title="Pin 2"></div>
        </div>
    </div>

    <script>
        // --- Drag and Drop Logic ---
        let draggedElement = null;
        let offsetX = 0, offsetY = 0;

        document.querySelectorAll('.component').forEach(el => {
            el.addEventListener('mousedown', (e) => {
                if(e.target.classList.contains('terminal')) return; // Don't drag if clicking terminal
                draggedElement = el;
                offsetX = e.clientX - el.getBoundingClientRect().left;
                offsetY = e.clientY - el.getBoundingClientRect().top;
                el.style.zIndex = 1000;
            });
        });

        document.addEventListener('mousemove', (e) => {
            if (draggedElement) {
                const container = document.getElementById('canvas-container').getBoundingClientRect();
                let newX = e.clientX - container.left - offsetX;
                let newY = e.clientY - container.top - offsetY;
                draggedElement.style.left = newX + 'px';
                draggedElement.style.top = newY + 'px';
                updateWires();
            }
        });

        document.addEventListener('mouseup', () => {
            if (draggedElement) {
                draggedElement.style.zIndex = 1;
                draggedElement = null;
            }
        });

        // --- Wiring Logic ---
        let isDrawing = false;
        let startTerminal = null;
        let activeLine = null;
        const svgLayer = document.getElementById('wire-layer');
        let connections = []; // Stores { from: {comp, node}, to: {comp, node} }

        document.querySelectorAll('.terminal').forEach(term => {
            term.addEventListener('mousedown', (e) => {
                isDrawing = true;
                startTerminal = e.target;
                
                activeLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                activeLine.setAttribute('stroke', 'black');
                activeLine.setAttribute('stroke-width', '4');
                svgLayer.appendChild(activeLine);
                e.stopPropagation();
            });

            term.addEventListener('mouseup', (e) => {
                if (isDrawing && startTerminal !== e.target) {
                    // Valid connection made
                    connections.push({
                        from: { parent: startTerminal.dataset.parent, node: startTerminal.dataset.node },
                        to: { parent: e.target.dataset.parent, node: e.target.dataset.node }
                    });
                    
                    // Create permanent visual wire
                    const permLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    permLine.setAttribute('stroke', 'green');
                    permLine.setAttribute('stroke-width', '4');
                    permLine.dataset.fromNode = startTerminal.dataset.parent + '-' + startTerminal.dataset.node;
                    permLine.dataset.toNode = e.target.dataset.parent + '-' + e.target.dataset.node;
                    svgLayer.appendChild(permLine);
                }
            });
        });

        document.addEventListener('mousemove', (e) => {
            if (isDrawing && activeLine) {
                const container = document.getElementById('canvas-container').getBoundingClientRect();
                const startRect = startTerminal.getBoundingClientRect();
                const startX = startRect.left + startRect.width/2 - container.left;
                const startY = startRect.top + startRect.height/2 - container.top;
                
                activeLine.setAttribute('x1', startX);
                activeLine.setAttribute('y1', startY);
                activeLine.setAttribute('x2', e.clientX - container.left);
                activeLine.setAttribute('y2', e.clientY - container.top);
            }
        });

        document.addEventListener('mouseup', () => {
            if (isDrawing) {
                isDrawing = false;
                if (activeLine) activeLine.remove();
                startTerminal = null;
                updateWires();
                
                // Expose the topology to the window object so Streamlit could potentially read it
                window.parent.postMessage({
                    type: "circuit_update",
                    topology: connections
                }, "*");
            }
        });

        function updateWires() {
            const container = document.getElementById('canvas-container').getBoundingClientRect();
            document.querySelectorAll('line').forEach(line => {
                if (!line.dataset.fromNode) return;
                
                // Re-calculate positions based on current component locations
                const fromParts = line.dataset.fromNode.split('-');
                const toParts = line.dataset.toNode.split('-');
                
                const term1 = document.querySelector(`.component#${fromParts[0]} .terminal[data-node="${fromParts[1]}"]`);
                const term2 = document.querySelector(`.component#${toParts[0]} .terminal[data-node="${toParts[1]}"]`);
                
                if(term1 && term2) {
                    const rect1 = term1.getBoundingClientRect();
                    const rect2 = term2.getBoundingClientRect();
                    
                    line.setAttribute('x1', rect1.left + rect1.width/2 - container.left);
                    line.setAttribute('y1', rect1.top + rect1.height/2 - container.top);
                    line.setAttribute('x2', rect2.left + rect2.width/2 - container.left);
                    line.setAttribute('y2', rect2.top + rect2.height/2 - container.top);
                }
            });
        }
    </script>
</body>
</html>
"""

st.subheader("🛠️ Hardware Sandbox")
# Render the interactive HTML canvas
components.html(html_code, height=550)

# --- 4. DATA BRIDGE & AI EVALUATION ---
st.markdown("### Step 2: Request AI Scan")

# Because passing data directly out of an iframe in standard Streamlit is restricted,
# we use a text input for the student to "log" their completed loop to the AI.
# In a full React component, this would be invisible and automatic.
topology_input = st.text_area(
    "Circuit Log", 
    placeholder="Example: Battery(+) to Resistor(P1), Resistor(P2) to LED(Anode)...",
    help="Describe your connections here to spend a token and ask the AI."
)

if st.button("🔍 Analyze Circuit (-1 Token)", type="primary"):
    if st.session_state.tokens <= 0:
        st.error("No tokens left! You must debug visually.")
    elif not topology_input:
        st.warning("Please describe your connections in the log first.")
    else:
        st.session_state.tokens -= 1
        
        with st.spinner("AI is analyzing your circuit logic..."):
            
            # The new AI Prompt: Focuses on topological logic rather than pixel coordinates.
            system_prompt = f"""
            You are a Socratic tutor helping a younger student build a circuit.
            The student is trying to connect a Battery, a Resistor, and an LED in series.
            
            The student has described their wiring as: "{topology_input}"
            
            Analyze this logic. 
            - Are all components in a single closed loop?
            - Is the polarity correct (Battery + flows towards LED Anode)?
            - Remember Series Flexibility: Swapping the order of the Resistor and LED is perfectly fine.
            
            DO NOT give the direct answer. Provide a Socratic hint explaining the physical reasoning of where the electricity gets "stuck".
            """
            
            if client:
                try:
                    resp = client.models.generate_content(
                        model=MODEL_ID,
                        contents=system_prompt,
                    )
                    st.success("Analysis Complete")
                    st.info(f"🤖 Socratic AI says: {resp.text}")
                except Exception as e:
                    st.error(f"AI Connection Error: {e}")
            else:
                st.error("No valid GCP credentials configured.")
