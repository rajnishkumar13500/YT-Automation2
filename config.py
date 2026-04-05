"""
Central configuration for YouTube Shorts Song Automation.
Loads settings from .env and defines paths, constants, and defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Paths ===
BASE_DIR = Path(__file__).parent
MODULES_DIR = BASE_DIR / "modules"
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
CREDENTIALS_DIR = BASE_DIR / "credentials"

# Output subdirectories
SONGS_DIR = OUTPUT_DIR / "songs"
VIDEOS_DIR = OUTPUT_DIR / "videos"
THUMBNAILS_DIR = OUTPUT_DIR / "thumbnails"

# Asset subdirectories
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
FONTS_DIR = ASSETS_DIR / "fonts"

# Ensure directories exist
for d in [SONGS_DIR, VIDEOS_DIR, THUMBNAILS_DIR, BACKGROUNDS_DIR, FONTS_DIR, CREDENTIALS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# === API Keys ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CF_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "")
DRIVE_PROCESSED_FOLDER_ID = os.getenv("DRIVE_PROCESSED_FOLDER_ID", "")
CLIENT_SECRET_PATH = BASE_DIR / os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "credentials/client_secret.json")

# Token storage (auto-generated after first auth)
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

# === Google API Scopes ===
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# === Video Settings ===
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", "59"))
INTRO_SKIP_SECONDS = int(os.getenv("INTRO_SKIP_SECONDS", "10"))
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "Shlok")
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Shlok")  # Default artist/channel name

# === Image Generation Settings ===
SECONDS_PER_IMAGE = int(os.getenv("SECONDS_PER_IMAGE", "5"))  # Target duration per image
MIN_IMAGES = int(os.getenv("MIN_IMAGES", "4"))  # Minimum images to generate
MAX_IMAGES = int(os.getenv("MAX_IMAGES", "15"))  # Maximum images to generate

# === Call-to-Action Settings ===
CTA_TEXT = os.getenv("CTA_TEXT", "Like & Subscribe ❤️")  # Text shown in last seconds
CTA_DURATION = int(os.getenv("CTA_DURATION", "7"))  # How many seconds to show CTA

# === Upload Settings ===
DEFAULT_PRIVACY = os.getenv("DEFAULT_PRIVACY", "public")
UPLOAD_CATEGORY_ID = os.getenv("UPLOAD_CATEGORY_ID", "10")  # 10 = Music

# === Supported Audio Formats ===
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma"}

# === Processing Log (tracks which songs have been processed) ===
PROCESSED_LOG = OUTPUT_DIR / "pipeline_log.json"

# === FFmpeg path (use system default) ===
FFMPEG_PATH = "ffmpeg"
FFPROBE_PATH = "ffprobe"
