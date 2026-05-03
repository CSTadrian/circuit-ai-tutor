# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
import os
from PIL import Image as PILImage, ImageDraw, ImageFont

# --- SDK IMPORTS ---
from google import genai
from google.genai import types
from google.oauth2 import service_account

# --- 1. INITIALIZATION & CONFIG ---
st.set_page_config(page_title="AI Circuit Tutor", layout="wide")
MODEL_ID = "gemini-3.1-pro-preview"

# Authentication
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    PROJECT_ID = creds_info["project_id"]

    client = genai.Client(
        vertexai=True, 
        project=PROJECT_ID, 
        location="global", 
        credentials=credentials
    )
else:
    st.error("GCP Service Account secrets not found! Check your Streamlit Cloud settings.")
    st.stop()

# --- 2. HELPER FUNCTIONS ---
def draw_coordinate_grid(image):
    """Draws a 0-1000 scale on the top and left edges of the image."""
    draw = ImageDraw.Draw(image)
    w, h = image.size
    
    line_color = (255, 0, 0, 150)
    text_bg = (0, 0, 0)
    text_color = (255, 255, 255)
    
    for i in range(0, 1001, 50):
        x_px = i * w / 1000
        y_px = i * h / 1000

        # X-AXIS
        draw.line([(x_px, 0), (x_px, 15)], fill=line_color, width=2)
        if i % 100 == 0:
            label = str(i)
            draw.rectangle([x_px, 0, x_px + 25, 15], fill=text_bg)
            draw.text((x_px + 2, 0), label, fill=text_color)

        # Y-AXIS
        draw.line([(0, y_px), (15, y_px)], fill=line_color, width=2)
        if i % 100 == 0:
            label = str(i)
            draw.rectangle([0, y_px, 25, y_px + 12], fill=text_bg)
            draw.text((2, y_px), label, fill=text_color)
            
    return image

# --- 3. UI AND TASK SELECTION ---
TASK_OPTIONS = [
    "1) turn on LED", "2) use a button", "3a) button -- series", 
    "3b) button -- parallel", "3c) button -- NOT", "4a) bright-activated LDR", 
    "4b) dark-activated LDR", "5) light up parallel LED", "6a) capacitor and VR - v1", 
    "6b) capacitor and VR - v2", "7) using one slide-switch", "8) using Two slide-switch", 
    "9) diode", "10) NPN transistor - v1", "11) NPN transistor - v2", 
    "12) IR emitter & detector", "13) 555 IC", "14) 74LS90 IC", "15) IR with 74LS90"
]

st.title("⚡ Precision Lab: AI Circuit Checker")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Task Selection")
    selected_task = st.selectbox("Choose your circuit task:", TASK_OPTIONS)
    
    # Extract the task identifier (e.g., "3a") to build the filename
    task_id = selected_task.split(")")[0]
    image_path = f"data2/circuit-{task_id}.jpg"
    
    # Load and display the semantic reference image
    if os.path.exists(image_path):
        ref_image = PILImage.open(image_path)
        ref_image_gridded = draw_coordinate_grid(ref_image.copy())
        st.image(ref_image_gridded, caption=f"Semantic Target: {selected_task}", use_container_width=True)
    else:
        st.warning(f"Reference image not found at: {image_path}")
        ref_image = None

with col2:
    st.subheader("Workspace")
    # [!] Insert your components.html() simulator code here
    st.info("Interactive Breadboard Simulator goes here.")
    
    # Placeholder for the data extracted from the simulator (or an uploaded photo)
    # In a real app, you'd use a custom component to sync JS state to this variable
    student_netlist_json = '{"components": [{"type": "LED", "pins": ["a1", "a2"]}], "wires": [{"start": "VCC", "end": "a1"}]}'

    if st.button("🤖 Check My Circuit", type="primary", use_container_width=True):
        if not ref_image:
            st.error("Cannot evaluate without a reference semantic image.")
        else:
            with st.spinner("AI is analyzing the netlist against the semantic image..."):
                
                # We format the prompt to act as an encouraging, age-appropriate tutor
                # ensuring feedback is constructive and breaks down the logic clearly.
                prompt_text = f"""
                You are an expert, encouraging STEM tutor helping a student verify their breadboard circuit.
                The student is working on the task: "{selected_task}".
                
                Attached is the correct 'semantic image' of the target circuit. 
                Below is the JSON netlist representing the student's current connections on their digital breadboard:
                
                <student_netlist>
                {student_netlist_json}
                </student_netlist>
                
                Task:
                1. Compare the student's JSON netlist against the required connections shown in the semantic image.
                2. Identify any missing wires, incorrect polarities (especially for LEDs/diodes), or shorts.
                3. Provide clear, encouraging feedback. If there is an error, do not just give the answer; gently guide them to check a specific area (e.g., "Check where the positive leg of your LED is connected").
                """

                try:
                    # Make the multimodal call to Gemini via Vertex AI
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=[ref_image, prompt_text],
                        config=types.GenerateContentConfig(
                            temperature=0.2, # Low temperature for accurate, deterministic grading
                        )
                    )
                    
                    st.success("Analysis Complete!")
                    st.markdown(f"### Tutor Feedback\n{response.text}")
                    
                except Exception as e:
                    st.error(f"Failed to reach Vertex AI: {e}")
