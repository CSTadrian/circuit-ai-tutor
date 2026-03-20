import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta, timezone
from PIL import Image as PILImage, ImageOps  # Added ImageOps for flipping

# Google Auth & Drive Imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request

# --- 1. CONFIGURATION ---
PARENT_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"
SUBFOLDER_NAME = "0321"
LOG_FILE_NAME = "circuit_log_0321.csv"

TASK_OPTIONS = [
    "1) turn on LED", "2) use a button", "3a) button -- series", 
    "3b) button -- parallel", "3c) button -- NOT", "4a) bright-activated LDR", 
    "4b) dark-activated LDR", "5) light up parallel LED", "6) capacitor and VR", 
    "7) using one slide-switch", "8) using Two slide-switch", "9) diode", 
    "10) NPN transistor - v1", "11) NPN transistor - v2", "12) IR emitter & detector", 
    "13) 555 IC", "14) 74LS90 IC", "15) IR with 74LS90"
]

st.set_page_config(page_title="Circuit Logger", layout="centered", page_icon="🔌")

# --- 2. INITIALIZE DRIVE SERVICE ---
@st.cache_resource
def init_drive():
    oauth_info = st.secrets["google_oauth"]
    drive_creds = Credentials(
        token=None,
        refresh_token=oauth_info["refresh_token"],
        client_id=oauth_info["client_id"],
        client_secret=oauth_info["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    if not drive_creds.valid:
        drive_creds.refresh(Request())
    return build('drive', 'v3', credentials=drive_creds)

drive_service = init_drive()

# --- 3. HELPER FUNCTIONS ---

def get_or_create_subfolder():
    query = f"name = '{SUBFOLDER_NAME}' and '{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    else:
        file_metadata = {'name': SUBFOLDER_NAME, 'parents': [PARENT_FOLDER_ID], 'mimeType': 'application/vnd.google-apps.folder'}
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def process_image(uploaded_file, flip_h, rotate_val):
    img = PILImage.open(uploaded_file)
    
    # Fix mirroring if enabled
    if flip_h:
        img = ImageOps.mirror(img)
    
    # Rotate if needed
    if rotate_val != 0:
        img = img.rotate(-rotate_val, expand=True) # Negative for clockwise

    img.thumbnail((1600, 1600)) 
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85) 
    return buf.getvalue()

def upload_to_drive(file_bytes, file_name, folder_id):
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def save_log_csv(new_row_df, folder_id):
    try:
        query = f"name = '{LOG_FILE_NAME}' and '{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        
        if files:
            file_id = files[0]['id']
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            existing_df = pd.read_csv(fh)
            updated_df = pd.concat([existing_df, new_row_df], ignore_index=True)
        else:
            file_id = None
            updated_df = new_row_df

        csv_buffer = io.BytesIO()
        updated_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        media = MediaIoBaseUpload(csv_buffer, mimetype='text/csv', resumable=True)
        if file_id:
            drive_service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata = {'name': LOG_FILE_NAME, 'parents': [folder_id]}
            drive_service.files().create(body=file_metadata, media_body=media).execute()
        return True
    except Exception as e:
        st.error(f"Log update failed: {e}")
        return False

# --- 4. UI LAYOUT ---
st.title("🔌 Circuit Task Logger")

with st.sidebar:
    st.header("1. Task Info")
    selected_task = st.selectbox("Select Task:", TASK_OPTIONS)
    
    st.header("2. Result")
    status = st.radio("Status:", ["✅ Correct", "❌ Wrong"], horizontal=True)
    
    notes = st.text_area("Notes/Why wrong? (Optional)", placeholder="Enter details here...")

    st.header("3. Image Fixes")
    flip_h = st.checkbox("Un-mirror Image (Flip Horizontal)", value=True)
    rotate_angle = st.select_slider("Rotate Image", options=[0, 90, 180, 270], value=0)

    if st.button("🔄 Reset Form"):
        st.rerun()

# --- CAMERA SELECTION ---
tabs = st.tabs(["📷 Camera", "🤳 Selfie", "📁 Upload"])
img_file = None

with tabs[0]:
    cam_file = st.file_uploader("Take Photo", type=['jpg', 'jpeg', 'png'], key="back_cam")
    if cam_file: img_file = cam_file
with tabs[1]:
    selfie_file = st.camera_input("Capture")
    if selfie_file: img_file = selfie_file
with tabs[2]:
    up_file = st.file_uploader("Gallery", type=['jpg', 'jpeg', 'png'], key="gallery")
    if up_file: img_file = up_file

# --- 5. SAVE LOGIC ---
if img_file:
    # Preview with fixes applied locally for the user to see
    preview_img = PILImage.open(img_file)
    if flip_h: preview_img = ImageOps.mirror(preview_img)
    if rotate_angle != 0: preview_img = preview_img.rotate(-rotate_angle, expand=True)
    
    st.image(preview_img, caption="Final Preview (As it will be saved)", width=400)
    
    if st.button("🚀 Click to Save to Drive"):
        with st.spinner("Saving..."):
            target_folder_id = get_or_create_subfolder()
            
            # Process image with the selected flip/rotate settings
            img_bytes = process_image(img_file, flip_h, rotate_angle)
            
            now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
            timestamp_str = now_hkt.strftime('%Y%m%d_%H%M%S')
            task_num = selected_task.split(')')[0].strip()
            file_name = f"Task{task_num}_{timestamp_str}.jpg"
            
            drive_id = upload_to_drive(img_bytes, file_name, target_folder_id)
            
            if drive_id:
                new_entry = pd.DataFrame([{
                    "Timestamp": now_hkt.strftime('%Y-%m-%d %H:%M:%S'),
                    "Task": selected_task,
                    "Status": status,
                    "Notes": notes,
                    "Filename": file_name,
                    "Drive_Link": f"https://drive.google.com/open?id={drive_id}"
                }])
                
                if save_log_csv(new_entry, target_folder_id):
                    st.balloons()
                    st.success(f"Saved: {selected_task}")

st.divider()
st.caption("Circuit Collector | 2026-03-21")
