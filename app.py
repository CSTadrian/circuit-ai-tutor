import streamlit as st
import pandas as pd
import os
import io
import hashlib
from datetime import datetime, timedelta, timezone
from PIL import Image as PILImage

# Google Auth & Drive Imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request

# --- 1. CONFIGURATION ---
# The Parent Folder ID you provided
PARENT_FOLDER_ID = "1gw_UvfQmVx-epCTZwIbVbXlKUKRfaitx"
SUBFOLDER_NAME = "0321"
LOG_FILE_NAME = "photo_log_0321.csv"

st.set_page_config(page_title="Circuit Photo Uploader", layout="centered", page_icon="📷")

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
    """Checks for '0321' folder inside Parent, creates it if missing."""
    query = f"name = '{SUBFOLDER_NAME}' and '{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        file_metadata = {
            'name': SUBFOLDER_NAME,
            'parents': [PARENT_FOLDER_ID],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def process_image_high_res(uploaded_file):
    """Resizes to 2048px for high quality while keeping file size reasonable."""
    img = PILImage.open(uploaded_file)
    img.thumbnail((2048, 2048)) 
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, subsampling=0) 
    return buf.getvalue()

def upload_to_drive(file_bytes, file_name, folder_id):
    try:
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

def save_log_csv(new_row_df, folder_id):
    """Saves/Updates the CSV log in the same '0321' folder."""
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
            while not done:
                _, done = downloader.next_chunk()
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
        st.error(f"CSV Log Error: {e}")
        return False

# --- 4. UI LAYOUT ---
st.title("📷 Circuit Photo Collector")
st.info("Photos will be saved to Google Drive in folder: `0321`")

with st.sidebar:
    st.header("Student Info")
    student_id = st.text_input("Student ID", placeholder="e.g. 42")
    task_id = st.number_input("Task Number", 1, 20, 1)
    if st.button("Clear Screen"):
        st.rerun()

# --- CAMERA SELECTION ---
tabs = st.tabs(["📷 Camera (iPad/Mobile)", "🤳 Selfie Cam", "📁 Upload"])

img_file = None
with tabs[0]:
    # This uses the native camera on iPad/Android
    cam_file = st.file_uploader("Tap to take photo with Back Camera", type=['jpg', 'jpeg', 'png'], key="back_cam")
    if cam_file: img_file = cam_file
with tabs[1]:
    selfie_file = st.camera_input("Capture with Front Camera")
    if selfie_file: img_file = selfie_file
with tabs[2]:
    up_file = st.file_uploader("Choose from Gallery", type=['jpg', 'jpeg', 'png'], key="gallery")
    if up_file: img_file = up_file

# --- 5. SAVE LOGIC ---
if img_file:
    if not student_id:
        st.warning("⚠️ Please enter a Student ID in the sidebar before saving.")
    else:
        st.image(img_file, caption="Preview", width=300)
        
        if st.button("🚀 Upload Photo to Drive"):
            with st.spinner("Processing and Uploading..."):
                # 1. Get the 0321 folder ID
                target_folder_id = get_or_create_subfolder()
                
                # 2. Process image (High Res)
                img_bytes = process_image_high_res(img_file)
                
                # 3. Create Filename
                now_hkt = datetime.now(timezone.utc) + timedelta(hours=8)
                timestamp_str = now_hkt.strftime('%Y%m%d_%H%M%S')
                file_name = f"SID{student_id}_Task{task_id}_{timestamp_str}.jpg"
                
                # 4. Upload Image
                drive_id = upload_to_drive(img_bytes, file_name, target_folder_id)
                
                if drive_id:
                    # 5. Update CSV Log
                    new_entry = pd.DataFrame([{
                        "Timestamp": now_hkt.strftime('%Y-%m-%d %H:%M:%S'),
                        "Student_ID": student_id,
                        "Task": task_id,
                        "Filename": file_name,
                        "Drive_Link": f"https://drive.google.com/open?id={drive_id}"
                    }])
                    
                    if save_log_csv(new_entry, target_folder_id):
                        st.balloons()
                        st.success(f"Successfully saved as {file_name}")
                        st.markdown(f"[🔗 View in Google Drive](https://drive.google.com/open?id={drive_id})")

st.divider()
st.caption("v2.1 | Direct Drive Upload (No AI Costs)")
