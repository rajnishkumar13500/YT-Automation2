import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(os.getcwd())))

from modules.drive_downloader import authenticate, build, DRIVE_FOLDER_ID
from config import DRIVE_PROCESSED_FOLDER_ID

try:
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # 1. Fetch file using list to get ID
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])

    if not files:
        print("No files found!")
        sys.exit(0)

    f = files[0]
    print(f"File found: {f['name']} (ID: {f['id']})")
    
    # Try fetching parents using GET like in the app
    file = service.files().get(fileId=f['id'], fields='parents').execute()
    print("get() response directly:", file)
    
    previous_parents = ",".join(file.get('parents', []))
    print("previous_parents formatted:", previous_parents)

    if not previous_parents:
        print("Wait! GET returned no parents. Let me try retrieving without specific fields parameter...")
        file = service.files().get(fileId=f['id']).execute()
        print("get() response without fields:", file.keys())


except Exception as e:
    print(f"Error: {e}")
