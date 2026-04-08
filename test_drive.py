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

    # 1. Fetch file
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false"
    print("Executing query:", query)
    results = service.files().list(q=query, fields="files(id, name, parents)").execute()
    files = results.get('files', [])

    if not files:
        print("No files found!")
        sys.exit(0)

    f = files[0]
    print(f"File found: {f['name']} (ID: {f['id']})")
    
    parents = f.get('parents', [])
    previous_parents = ",".join(parents)
    print("Current parents:", previous_parents)

    # Move logic snippet from drive_downloader.py
    print(f"Moving to PROCESSED: {DRIVE_PROCESSED_FOLDER_ID}")
    
    res = service.files().update(
        fileId=f['id'],
        addParents=DRIVE_PROCESSED_FOLDER_ID,
        removeParents=previous_parents,
        fields='id, parents'
    ).execute()
    
    print("Move success! Reverting...")
    
    # Revert back
    service.files().update(
        fileId=f['id'],
        addParents=previous_parents,
        removeParents=DRIVE_PROCESSED_FOLDER_ID,
        fields='id, parents'
    ).execute()
    
    print("Reverted successfully.")

except Exception as e:
    print(f"Error: {e}")
