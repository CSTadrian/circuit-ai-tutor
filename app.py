import os
import PIL.Image, PIL.ImageDraw
import ipywidgets as widgets
from IPython.display import display, clear_output, HTML
from google.genai import types

# --- 1. SETUP ---
# auth.authenticate_user() # 如果已認證可註解
PROJECT_ID = "project-b51ce4f6-9f92-4f6b-877"
client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

BASE_PATH = "/content/drive/MyDrive/Colab/Research_2026/ECCC_AI_cleaned"
target_img_name = "Task1_20260321_105232.jpg"
img_path = os.path.join(BASE_PATH, "0321", target_img_name)

# --- 2. STEP 1: INITIAL DETECTION ---
def get_initial_leads(path):
    img = PIL.Image.open(path)
    prompt = "Identify components and their pin endpoints. Output JSON list."
    try:
        resp = client.models.generate_content(
            model="gemini-3.1-pro-preview", 
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component": {"type": "STRING"},
                            "center": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                            "legs": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "INTEGER"}}}
                        },
                        "required": ["component", "center", "legs"]
                    }
                }
            )
        )
        if resp.parsed: return resp.parsed
    except Exception as e:
        print(f"⚠️ Initial detection failed: {e}")
    return [{"component": "LDR", "center": [500, 500], "legs": [[480, 480], [520, 520]]}]

# --- 3. STEP 2: ANALYZE BASED ON USER ADAPTATION ---
def run_final_analysis(img_path):
    global current_data
    with output:
        clear_output()
        print("🧠 3.1-Pro is analyzing, using YOUR corrected pins AND reinforced middle gap...")
    
    img = PIL.Image.open(img_path).convert('RGBA')
    w, h = img.size
    
    # --- A. 建立高對比度標註層 ---
    overlay = PIL.Image.new('RGBA', img.size, (0,0,0,0))
    draw = PIL.ImageDraw.Draw(overlay)
    
    inventory_text = ""
    for i, item in enumerate(current_data):
        cy, cx = item['center']
        comp = item.get('component', f'Part_{i}')
        inventory_text += f"- {comp}: "
        for j, leg in enumerate(item['legs']):
            ly, lx = leg
            # 畫粗橘線
            draw.line([(cx*w/1000, cy*h/1000), (lx*w/1000, ly*h/1000)], fill=(255, 165, 0, 200), width=15)
            # 畫青色孔位點 (AI 分析的精確依據)
            draw.ellipse([(lx*w/1000-12, ly*h/1000-12), (lx*w/1000+12, ly*h/1000+12)], fill=(0, 255, 255, 255))
            # 輔助 AI 定位引腳是在左(L)還是右(R)
            side = "LEFT (a-e)" if lx < 500 else "RIGHT (f-j)"
            inventory_text += f"Leg{j+1}[{side},y:{ly},x:{lx}]; "
        inventory_text += "\n"

    # --- B. 核心修正：在麵包板中間畫藍色隔離線 ---
    middle_x = w // 2 # 尋找圖片中心位置
    draw.line([(middle_x, 0), (middle_x, h)], fill=(0, 0, 255, 200), width=25) # 畫一條極粗的藍色線
    draw.text((middle_x - 100, 50), "LEFT SIDE (a-e)", fill=(0, 0, 255, 255), stroke_fill="white", stroke_width=2)
    draw.text((middle_x + 20, 50), "RIGHT SIDE (f-j)", fill=(0, 0, 255, 255), stroke_fill="white", stroke_width=2)

    # --- C. 合併標註與原圖 ---
    combined = PIL.Image.alpha_composite(img, overlay).convert('RGB')

    # --- D. 優化 Prompt，強調藍色隔離線和左右列的定義 ---
    prompt = f"""
    CRITICAL: Look at the image with reinforcements.
    A THICK BLUE LINE has been drawn in the middle to define the BREADBOARD GAP.
    - Area to the LEFT of the blue line is rows a, b, c, d, e.
    - Area to the RIGHT of the blue line is rows f, g, h, i, j.

    DO NOT ignore this blue line. It is the GROUND TRUTH for middle separation.
    
    Verified Component Map (USE CYAN DOTS for exact hole):
    {inventory_text}
    
    Task: 4b (LDR Control Circuit).
    Compare the connections (CYAN DOTS) to the schematic, paying close attention 
    to whether pins are on the LEFT or RIGHT of the blue gap line.

    1. RESULT: [✅ CORRECT] or [❌ INCORRECT]
    2. ANALYSIS: Max 50 words. Focus on specific component topology.
    3. SOCRATIC QUESTIONS: No limit. Guide student's thinking.
    """

    
    try:
        response = client.models.generate_content(model="gemini-3.1-pro-preview", contents=[combined, prompt])
        with output:
            clear_output(wait=True)
            res_text = response.text
            color = "green" if "[✅ CORRECT]" in res_text.upper() else "red"
            
            # 分解反饋內容
            parts = res_text.split("ANALYSIS:")
            header = parts[0]
            body_and_q = parts[1] if len(parts) > 1 else "No analysis provided."
            body = body_and_q.split("SOCRATIC QUESTIONS:")[0]
            questions = body_and_q.split("SOCRATIC QUESTIONS:")[1] if "SOCRATIC QUESTIONS:" in body_and_q else ""

            display(HTML(f"""
                <div style='border: 4px solid {color}; padding: 15px; border-radius: 10px; background-color: #fcfcfc;'>
                    <h2 style='color: {color}; margin-top: 0;'>{header}</h2>
                    <p><b>Analysis:</b> {body}</p>
                    <hr>
                    <p><b>Socratic Questions:</b></p>
                    <div style='font-family: sans-serif;'>{questions}</div>
                </div>
            """))
            display(combined.resize((700, int(700 * h / w))))
    except Exception as e:
        with output: print(f"❌ Analysis failed: {e}")

# --- 4. INTERACTIVE UI ---
current_data = []
output = widgets.Output()

def create_ui(img_path, initial_data):
    global current_data
    current_data = initial_data
    img = PIL.Image.open(img_path)
    w, h = img.size
    
    controls_list = []
    for i, item in enumerate(current_data):
        label = widgets.HTML(f"<b style='color: #2c3e50;'>({i+1}) {item['component']}</b>")
        leg_widgets = []
        for j, leg in enumerate(item['legs']):
            x_s = widgets.IntSlider(value=leg[1], min=0, max=1000, description=f'Pin {j+1} X')
            y_s = widgets.IntSlider(value=leg[0], min=0, max=1000, description=f'Pin {j+1} Y')
            
            def make_update(c_idx, l_idx, axis):
                return lambda change: [current_data[c_idx]['legs'][l_idx].__setitem__(0 if axis=='y' else 1, change['new']), redraw()]

            x_s.observe(make_update(i, j, 'x'), names='value')
            y_s.observe(make_update(i, j, 'y'), names='value')
            leg_widgets.append(widgets.HBox([x_s, y_s]))
        controls_list.append(widgets.VBox([label] + leg_widgets + [widgets.HTML("<hr style='margin: 2px 0;'>")]))

    def redraw():
        with output:
            clear_output(wait=True)
            temp_img = img.copy()
            d = PIL.ImageDraw.Draw(temp_img)
            for it in current_data:
                cy, cx = it['center']
                for ly, lx in it['legs']:
                    d.line([(cx*w/1000, cy*h/1000), (lx*w/1000, ly*h/1000)], fill="orange", width=8)
            temp_img.thumbnail((700, 700))
            display(temp_img)

    btn = widgets.Button(description="✅ Verify Corrected Pins & Analyze", 
                         button_style='success', layout={'width': '98%', 'height': '45px'})
    btn.on_click(lambda x: run_final_analysis(img_path))
    
    scroll_box = widgets.VBox(controls_list, layout={'max_height': '350px', 'overflow_y': 'scroll', 'border': '1px solid #ddd'})
    display(widgets.HTML("<h3>1. Correct Pin Locations (Cyan Dot Ground Truth)</h3>"), scroll_box, btn, output)
    redraw()

# --- RUN ---
print(f"🚀 Initializing Task 4b Tracker...")
initial_leads = get_initial_leads(img_path)
create_ui(img_path, initial_leads)
