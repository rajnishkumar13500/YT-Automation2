"""
Google Drive Song Downloader
Downloads songs from a specified Google Drive folder.
"""

import json
import io
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CLIENT_SECRET_PATH, TOKEN_PATH, SCOPES, SONGS_DIR,
    DRIVE_FOLDER_ID, DRIVE_PROCESSED_FOLDER_ID, AUDIO_EXTENSIONS, PROCESSED_LOG
)


def authenticate():
    """
    Authenticate with Google APIs using OAuth2.
    First run opens a browser for consent. Token is cached for subsequent runs.
    Returns credentials object usable by both Drive and YouTube APIs.
    """
    creds = None

    # Load cached token if it exists and is not empty
    if TOKEN_PATH.exists() and TOKEN_PATH.stat().st_size > 10:
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            raise ValueError(
                f"❌ Failed to parse {TOKEN_PATH}: {e}\n"
                "   If you are using GitHub Actions, ensure the YOUTUBE_TOKEN secret contains the full JSON contents."
            )
    elif TOKEN_PATH.exists() and TOKEN_PATH.stat().st_size > 0:
        print(f"⚠️  Warning: {TOKEN_PATH} exists but seems empty. If on GitHub Actions, check YOUTUBE_TOKEN secret.")

    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists() or CLIENT_SECRET_PATH.stat().st_size < 10:
                raise FileNotFoundError(
                    f"❌ client_secret.json is missing or empty at {CLIENT_SECRET_PATH}\n"
                    "   If you are using GitHub Actions, ensure the YOUTUBE_CLIENT_SECRET secret contains the full JSON contents.\n"
                    "   Otherwise, download it from Google Cloud Console:\n"
                    "   1. Go to https://console.cloud.google.com/\n"
                    "   2. Create/select project → Enable YouTube Data API v3 + Google Drive API\n"
                    "   3. Credentials → Create OAuth 2.0 Client ID (Desktop app)\n"
                    "   4. Download JSON → save as credentials/client_secret.json"
                )
            
            # Prevent running local server if we're in an environment without a display (like GH Actions)
            import os
            if os.environ.get("GITHUB_ACTIONS") == "true":
                raise RuntimeError(
                    "❌ Attempted to open a browser for Google OAuth inside GitHub Actions.\n"
                    "   This happens because 'token.json' is missing, empty, or invalid.\n"
                    "   Please run `python main.py` locally to authenticate, then copy the ENTIRE "
                    "contents of credentials/token.json into the YOUTUBE_TOKEN GitHub Secret."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for next run
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def list_songs(creds, folder_id=None):
    """
    List all audio files in the specified Google Drive folder.
    Returns a list of dicts with 'id', 'name', 'mimeType', and 'size'.
    """
    folder_id = folder_id or DRIVE_FOLDER_ID
    if not folder_id:
        raise ValueError(
            "❌ DRIVE_FOLDER_ID is not set in .env\n"
            "   Set it to the Google Drive folder ID containing your songs."
        )

    service = build("drive", "v3", credentials=creds)

    # Query for audio files in the folder
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size)",
        orderBy="name",
        pageSize=100
    ).execute()

    files = results.get("files", [])

    # Filter to audio files only
    audio_files = []
    for f in files:
        ext = Path(f["name"]).suffix.lower()
        if ext in AUDIO_EXTENSIONS or "audio" in f.get("mimeType", ""):
            audio_files.append(f)

    return audio_files


def download_song(creds, file_id, filename):
    """
    Download a specific song file from Google Drive.
    Returns the local path to the downloaded file.
    """
    service = build("drive", "v3", credentials=creds)
    output_path = SONGS_DIR / filename

    # Skip if already downloaded
    if output_path.exists():
        print(f"  ⏭️  Already downloaded: {filename}")
        return output_path

    request = service.files().get_media(fileId=file_id)
    with open(output_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  ⬇️  Downloading {filename}: {int(status.progress() * 100)}%")

    print(f"  ✅ Downloaded: {filename}")
    return output_path


def get_processed_songs():
    """Load the list of already-processed song filenames from the pipeline log."""
    processed = []
    if PROCESSED_LOG.exists():
        try:
            with open(PROCESSED_LOG, "r") as f:
                logs = json.load(f)
                for log in logs:
                    if log.get("uploaded") == True or log.get("video"):
                        processed.append(log.get("song_file"))
        except:
            pass
    return processed


def get_unprocessed_song(creds, folder_id=None):
    """
    Get the first song from Drive that hasn't been processed yet.
    Returns (file_id, filename) or (None, None) if all processed.
    """
    songs = list_songs(creds, folder_id)
    processed_names = get_processed_songs()

    for song in songs:
        if song["name"] not in processed_names:
            return song["id"], song["name"]

    return None, None


def move_song_to_processed(creds, file_id, filename):
    """
    Move a file from the main input folder to the Processed folder.
    Requires full 'https://www.googleapis.com/auth/drive' scope.
    """
    if not DRIVE_PROCESSED_FOLDER_ID:
        print("  ⚠️  DRIVE_PROCESSED_FOLDER_ID not set in .env. Skipping move.")
        return False

    try:
        service = build("drive", "v3", credentials=creds)
        
        # Retrieve the existing parents to remove
        file = service.files().get(fileId=file_id, fields='parents', supportsAllDrives=True).execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # Move the file to the new folder
        kwargs = {
            'fileId': file_id,
            'addParents': DRIVE_PROCESSED_FOLDER_ID,
            'fields': 'id, parents',
            'supportsAllDrives': True
        }
        
        # Do not include removeParents if there are no previous parents, otherwise API throws 400
        if previous_parents:
            kwargs['removeParents'] = previous_parents
            
        service.files().update(**kwargs).execute()
        
        print(f"  📂 Moved '{filename}' to Processed folder on Google Drive")
        return True
    except Exception as e:
        print(f"  ❌ Failed to move '{filename}' to Processed folder: {e}")
        return False
