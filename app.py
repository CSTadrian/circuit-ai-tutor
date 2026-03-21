import os
import json
import pd
import base64
import shutil
import ipywidgets as widgets
from datetime import datetime, timedelta, timezone
from google.colab import output
from IPython.display import display, Javascript, clear_output
import vertexai
from vertexai.generative_models import GenerativeModel, Image, GenerationConfig

# --- 1. UPDATED INITIALIZATION ---
# Replace "your-project-id" with your actual GCP Project ID
# Note: Gemini 3.1 Pro is significantly better at the "Structural Netlist Analysis" 
# step you defined in your prompt.
vertexai.init(project="your-project-id", location="us-central1")

# Use the 3.1 Pro model for advanced reasoning on breadboard spacing
MODEL_ID = "gemini-3.1-pro-preview-0520" 
model = GenerativeModel(MODEL_ID)

# --- JAVASCRIPT FOR WEBCAM ACCESS (Unchanged) ---
def take_photo(filepath, quality=0.8):
    js = Javascript('''
    async function takePhoto(quality) {
      const div = document.createElement('div');
      const capture = document.createElement('button');
      capture.textContent = 'Capture Photo';
      capture.style.padding = '10px';
      capture.style.margin = '10px';
      capture.style.backgroundColor = '#4CAF50';
      capture.style.color = 'white';
      capture.style.border = 'none';
      capture.style.borderRadius = '5px';
      capture.style.cursor = 'pointer';

      const video = document.createElement('video');
      video.style.display = 'block';
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { exact: "environment" } }
      });
      document.body.appendChild(div);
      div.appendChild(video);
      div.appendChild(capture);
      video.srcObject = stream;
      await video.play();

      google.colab.output.setIframeHeight(document.documentElement.scrollHeight, true);

      await new Promise((resolve) => capture.onclick = resolve);

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      stream.getVideoTracks()[0].stop();
      div.remove();
      return canvas.toDataURL('image/jpeg', quality);
    }
    ''')
    display(js)
    data = output.eval_js('takePhoto({})'.format(quality))
    binary = base64.b64decode(data.split(',')[1])
    with open(filepath, 'wb') as f:
        f.write(binary)
    return filepath

def process_live_circuit(task_number):
    base_folder = "data2"
    saved_folder = os.path.join(base_folder, "saved")
    unsaved_folder = os.path.join(base_folder, "unsaved")
    csv_filename = "circuit_records.csv"

    for folder in [saved_folder, unsaved_folder]:
        os.makedirs(folder, exist_ok=True)

    ref_image_name = f"circuit-{task_number}.jpg"
    ref_path = os.path.join(base_folder, ref_image_name)

    if not os.path.exists(ref_path):
        print(f"Error: Reference image {ref_image_name} not found.")
        return

    now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
    timestamp_str = now_hkt.strftime('%Y_%m_%d__%H_%M_%S')
    temp_filename = f"temp_{timestamp_str}.jpg"

    print(f"--- TASK {task_number} LIVE CAPTURE ---")
    try:
        take_photo(temp_filename)
    except Exception as e:
        print(f"Webcam Error: {e}")
        return

    # --- 2. AI ANALYSIS (Running on Gemini 3.1 Pro) ---
    print(f"Analyzing with {MODEL_ID}... please wait.")
    try:
        schematic_img_ai = Image.load_from_file(ref_path)
        student_img_ai = Image.load_from_file(temp_filename)

        # Your existing detailed prompt
        prompt = """
        You are a Senior Electronic Systems Diagnostic Engineer. Your task is to perform a two-stage validation...
        [Rest of your prompt remains the same]
        """
        
        # 3.1 Pro handles temperature=0 very strictly for consistent JSON output
        response = model.generate_content(
            [prompt, schematic_img_ai, student_img_ai],
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )

        data = json.loads(response.text)

        print(f"\n" + "="*40)
        print(f"DIAGNOSTIC RESULT: {data['match_status']}")
        print(f"ANALYSIS: {data['error_analysis']}")
        print(f"HINT: {data['remediation_hints']}")
        print("="*40 + "\n")

        # --- 3. UI BUTTONS & SAVING (Unchanged) ---
        save_button = widgets.Button(description="Save to CSV", button_style='success', icon='check')
        no_save_button = widgets.Button(description="Discard (Don't Save)", button_style='danger', icon='times')
        output_widget = widgets.Output()
        display(widgets.HBox([save_button, no_save_button]), output_widget)

        def on_save_clicked(b):
            with output_widget:
                clear_output()
                final_name = f"{timestamp_str}.jpg"
                final_path = os.path.join(saved_folder, final_name)
                shutil.move(temp_filename, final_path)
                
                df = pd.read_csv(csv_filename) if os.path.exists(csv_filename) else pd.DataFrame()
                hkt_display = now_hkt.strftime('%Y-%m-%d %H:%M:%S')
                new_row = {
                    "Index": len(df) + 1,
                    "Time (HKT)": hkt_display,
                    "Photo 1 Name": ref_image_name,
                    "Photo 2 Name": final_name,
                    "Photo 1 Netlist": data['schematic_netlist'],
                    "Photo 2 Netlist": data['student_netlist'],
                    "Result": data['match_status'],
                    "Logic": f"ANALYSIS: {data['error_analysis']} | HINT: {data['remediation_hints']}"
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(csv_filename, index=False)
                print(f"✅ Data saved. Image: data2/saved/{final_name}")
                save_button.disabled = True
                no_save_button.disabled = True

        def on_no_save_clicked(b):
            with output_widget:
                clear_output()
                final_name = f"{timestamp_str}.jpg"
                final_path = os.path.join(unsaved_folder, final_name)
                shutil.move(temp_filename, final_path)
                print(f"❌ Discarded.")
                save_button.disabled = True
                no_save_button.disabled = True

        save_button.on_click(on_save_clicked)
        no_save_button.on_click(on_no_save_clicked)

    except Exception as e:
        print(f"Error: {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    task_input = input("Enter Task Number: ").strip()
    process_live_circuit(task_input)
