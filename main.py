"""
YouTube Shorts Song Automation — Main Orchestrator

Downloads songs from Google Drive, analyzes them with AI,
creates stunning 9:16 visualizer videos with mood-matching backgrounds,
generates viral metadata, and uploads to YouTube as Shorts.

Usage:
    python main.py                     # Auto-pick song, generate, upload
    python main.py --list              # List available songs in Drive
    python main.py --song "name"       # Use a specific song name
    python main.py --no-upload         # Generate video only, skip upload
    python main.py --private           # Upload as private (for testing)
    python main.py --all               # Process ALL unprocessed songs
    python main.py --local "path.mp3"  # Use a local audio file
"""

import argparse
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Prevent print() from crashing when displaying Hindi/Unicode characters in the Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from config import (
    SONGS_DIR, VIDEOS_DIR, THUMBNAILS_DIR, DRIVE_FOLDER_ID, OUTPUT_DIR,
    SECONDS_PER_IMAGE, MIN_IMAGES, MAX_IMAGES
)
from modules.drive_downloader import (
    authenticate, list_songs, download_song,
    get_unprocessed_song, get_processed_songs, move_song_to_processed
)
from modules.audio_analyzer import analyze_song
from modules.image_generator import generate_background_images
from modules.video_creator import create_visualizer_video, get_audio_metadata
from modules.metadata_generator import generate_viral_metadata
from modules.thumbnail_creator import create_thumbnail
from modules.youtube_uploader import upload_to_youtube


def print_banner():
    print("""
╔══════════════════════════════════════════════════╗
║   🎵 YouTube Shorts Song Automation 🎵          ║
║   Drive → Analyze → Images → Video → Upload     ║
╚══════════════════════════════════════════════════╝
    """)


def list_drive_songs(creds):
    """List all songs available in Google Drive."""
    print("📂 Songs in Google Drive:")
    print("-" * 50)
    songs = list_songs(creds)
    processed_names = get_processed_songs()

    if not songs:
        print("  No audio files found in the specified folder.")
        print(f"  Folder ID: {DRIVE_FOLDER_ID}")
        return

    for i, song in enumerate(songs, 1):
        status = "✅" if song["name"] in processed_names else "⬜"
        size_mb = int(song.get("size", 0)) / (1024 * 1024)
        print(f"  {status} {i}. {song['name']} ({size_mb:.1f} MB)")

    print(f"\n  Total: {len(songs)} songs | "
          f"Processed: {len([s for s in songs if s['name'] in processed_names])} | "
          f"Remaining: {len([s for s in songs if s['name'] not in processed_names])}")


def process_song(creds, song_path, no_upload=False, privacy_status="public", file_id=None, test_mode=False):
    """
    Strict fail-stop pipeline for one song:
    1. Transcribe song (Gemini → lyrics, name, artist, mood, genre)
    2. Generate images (Nano Banana 2 → lyrics-based images)
    3. Compile animation video (images + audio → 9:16 video)
    4. Generate metadata (lyrics → viral title, description, tags)
    5. Create thumbnail
    6. Upload to YouTube as Shorts

    If ANY step fails, pipeline stops immediately.
    """
    song_path = Path(song_path)

    print(f"\n{'='*55}")
    print(f"🎵 Processing: {song_path.name}")
    print(f"{'='*55}")

    # ── Step 1: Read audio info ──
    print("\n📋 Step 1/7: Reading audio info...")
    metadata = get_audio_metadata(song_path)
    print(f"  Duration: {metadata['duration']:.1f}s")

    # ── Step 2: Transcribe song with Gemini AI ──
    print("\n🎧 Step 2/7: Transcribing song with AI...")
    try:
        analysis = analyze_song(song_path)
    except Exception as e:
        print(f"\n  ❌ FAILED: Song transcription failed: {e}")
        print(f"  🛑 Pipeline stopped. Cannot proceed without transcription.")
        return None

    song_name = analysis.get("song_name", "Unknown Song")
    artist = analysis.get("artist", "Unknown Artist")

    if song_name == "Unknown Song":
        print(f"\n  ❌ FAILED: Could not identify the song.")
        print(f"  🛑 Pipeline stopped. Gemini could not transcribe/identify the song.")
        return None

    print(f"  🎵 Song: {song_name}")
    print(f"  🎤 Artist: {artist}")
    print(f"  🎸 Genre: {analysis.get('genre', 'Unknown')}")
    print(f"  💫 Mood: {analysis.get('mood', 'Unknown')}")
    lyrics = analysis.get("lyrics", "")
    if lyrics:
        print(f"  📜 Lyrics: {lyrics[:80]}...")
    lyric_lines = analysis.get("lyric_lines", [])
    if lyric_lines:
        print(f"  📝 Caption lines: {len(lyric_lines)} lines for video")

    # ── Step 3: Generate images with Nano Banana 2 ──
    print("\n🎨 Step 3/7: Generating images with Nano Banana 2...")
    try:
        # Calculate optimal number of images based on duration
        # Configurable via SECONDS_PER_IMAGE, MIN_IMAGES, MAX_IMAGES in .env
        duration = metadata['duration']
        optimal_image_count = max(MIN_IMAGES, min(MAX_IMAGES, int(duration / SECONDS_PER_IMAGE)))
        print(f"  📊 Duration: {duration:.1f}s → Generating {optimal_image_count} images (~{SECONDS_PER_IMAGE}s each)")
        
        bg_images = generate_background_images(analysis, count=optimal_image_count)
    except Exception as e:
        print(f"\n  ❌ FAILED: Image generation crashed: {e}")
        print(f"  🛑 Pipeline stopped.")
        return None

    if not bg_images:
        print(f"\n  ⚠️  WARNING: No images generated. Falling back to waveform video.")

    # ── Step 4: Compile animation video ──
    print("\n🎬 Step 4/7: Compiling animation video...")
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in song_name)
    video_path = VIDEOS_DIR / f"{safe_name}.mp4"
    try:
        cta_text = analysis.get("cta_text") if analysis else None
        if cta_text:
            print(f"  📝 CTA Text: {cta_text}")
            
        video_path = create_visualizer_video(
            song_path, video_path, metadata,
            analysis=analysis,
            background_images=bg_images,
            cta_text=cta_text
        )
    except Exception as e:
        print(f"\n  ❌ FAILED: Video creation failed: {e}")
        print(f"  🛑 Pipeline stopped.")
        return None

    # ── Step 5: Generate viral metadata from lyrics ──
    print("\n📝 Step 5/7: Generating viral metadata...")
    try:
        yt_metadata = generate_viral_metadata(
            song_name, artist,
            min(metadata["duration"], 59),
            analysis=analysis
        )
    except Exception as e:
        print(f"\n  ❌ FAILED: Metadata generation failed: {e}")
        print(f"  🛑 Pipeline stopped.")
        return None

    # Enrich tags with analysis keywords
    vibe_keywords = analysis.get("vibe_keywords", [])
    genre = analysis.get("genre", "")
    mood = analysis.get("mood", "")
    extra_tags = vibe_keywords + [genre, mood, analysis.get("language", "")]
    extra_tags = [t for t in extra_tags if t and t != "Unknown"]
    yt_metadata["tags"] = list(set(yt_metadata["tags"] + extra_tags))[:30]

    print(f"  📝 Title: {yt_metadata['title']}")
    print(f"  🏷️  Tags: {', '.join(yt_metadata['tags'][:6])}...")

    # ── Step 6: Create thumbnail ──
    print("\n🖼️  Step 6/7: Creating thumbnail...")
    try:
        thumb_path = create_thumbnail(video_path, song_name, artist)
    except Exception as e:
        print(f"\n  ❌ FAILED: Thumbnail creation failed: {e}")
        print(f"  🛑 Pipeline stopped.")
        return None

    # ── Step 7: Upload to YouTube ──
    if no_upload:
        print("\n⏭️  Step 7/7: Skipping upload (--no-upload)")
        print(f"\n📁 Generated files:")
        print(f"  Video:     {video_path}")
        print(f"  Thumbnail: {thumb_path}")
        print(f"  Title:     {yt_metadata['title']}")
        result = {
            "song_file": song_path.name,
            "song_name": song_name,
            "artist": artist,
            "video": str(video_path),
            "thumbnail": str(thumb_path),
            "title": yt_metadata["title"],
            "uploaded": False,
            "timestamp": datetime.now().isoformat()
        }
    else:
        print(f"\n📤 Step 7/7: Uploading to YouTube ({privacy_status})...")
        try:
            upload_result = upload_to_youtube(
                creds=creds,
                video_path=video_path,
                title=yt_metadata["title"],
                description=yt_metadata["description"],
                tags=yt_metadata["tags"],
                thumbnail_path=thumb_path,
                privacy_status=privacy_status
            )
            result = {
                "song_file": song_path.name,
                "song_name": song_name,
                "artist": artist,
                "video": str(video_path),
                "thumbnail": str(thumb_path),
                "title": yt_metadata["title"],
                "uploaded": True,
                "video_id": upload_result["video_id"],
                "url": upload_result["url"],
                "privacy": privacy_status,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"\n  ❌ FAILED: Upload failed: {e}")
            print(f"  🛑 Pipeline stopped.")
            result = {
                "song_file": song_path.name,
                "song_name": song_name,
                "uploaded": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    # ── Step 8: Move to Processed ──
    if test_mode:
        print("\n📂 Step 8/8: Skipping move to Processed folder (--test mode)")
        result["moved"] = False
    elif file_id and (result.get("uploaded") or no_upload):
        print("\n📂 Step 8/8: Moving original file to Processed folder...")
        moved = move_song_to_processed(creds, file_id, song_name)
        result["moved"] = moved

    _save_result(result)
    return result


def _save_result(result):
    """Save pipeline result to log."""
    log_path = OUTPUT_DIR / "pipeline_log.json"
    log = []
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                log = json.load(f)
        except json.JSONDecodeError:
            log = []
    log.append(result)
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="YouTube Shorts Song Automation")
    parser.add_argument("--list", action="store_true", help="List songs in Drive")
    parser.add_argument("--song", type=str, help="Specific song name to process")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload")
    parser.add_argument("--private", action="store_true", help="Upload as private")
    parser.add_argument("--unlisted", action="store_true", help="Upload as unlisted")
    parser.add_argument("--all", action="store_true", help="Process all unprocessed songs")
    parser.add_argument("--local", type=str, help="Use a local audio file")
    parser.add_argument("--test", action="store_true", help="Test mode: skip upload and do not move file to processed folder")

    args = parser.parse_args()
    if args.test:
        args.no_upload = True

    privacy = "private" if args.private else ("unlisted" if args.unlisted else "public")

    # === Local file mode ===
    if args.local:
        local_path = Path(args.local)
        if not local_path.exists():
            print(f"❌ File not found: {local_path}")
            sys.exit(1)
            
        processed_names = get_processed_songs()
        if local_path.name in processed_names:
            print(f"\n⏭️  Song '{local_path.name}' has already been processed and uploaded (found in pipeline_log.json). Skipping.")
            return

        print("🔐 Authenticating...")
        creds = authenticate()
        result = process_song(creds, local_path, no_upload=args.no_upload,
                              privacy_status=privacy, test_mode=args.test)
        if result:
            print(f"\n🎉 Done!")
        return

    # === Authenticate ===
    print("🔐 Authenticating with Google...")
    try:
        creds = authenticate()
        print("  ✅ Authenticated!\n")
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        sys.exit(1)

    # === List mode ===
    if args.list:
        list_drive_songs(creds)
        return

    # === Process all ===
    if args.all:
        songs = list_songs(creds)
        processed_names = get_processed_songs()
        unprocessed = [s for s in songs if s["name"] not in processed_names]
        if not unprocessed:
            print("✅ All songs processed!")
            return
        print(f"📋 {len(unprocessed)} songs to process.\n")
        for i, song in enumerate(unprocessed, 1):
            print(f"\n{'#'*55}")
            print(f"# Song {i}/{len(unprocessed)}")
            print(f"{'#'*55}")
            song_path = download_song(creds, song["id"], song["name"])
            result = process_song(creds, song_path, no_upload=args.no_upload,
                                  privacy_status=privacy, file_id=song["id"], test_mode=args.test)
            if result and result.get("uploaded"):
                print(f"  🔗 {result['url']}")
            if i < len(unprocessed) and not args.no_upload:
                print(f"\n⏳ Waiting 30s before next upload...")
                time.sleep(30)
        print(f"\n🎉 All done!")
        return

    # === Specific song ===
    if args.song:
        songs = list_songs(creds)
        match = None
        for s in songs:
            if args.song.lower() in s["name"].lower():
                match = s
                break
        if not match:
            print(f"❌ Song '{args.song}' not found.")
            for s in songs[:10]:
                print(f"  - {s['name']}")
            sys.exit(1)
        song_path = download_song(creds, match["id"], match["name"])
        result = process_song(creds, song_path, no_upload=args.no_upload,
                              privacy_status=privacy, file_id=match["id"], test_mode=args.test)
        if result:
            print(f"\n🎉 Done!")
        return

    # === Auto-pick ===
    file_id, filename = get_unprocessed_song(creds)
    if not file_id:
        print("✅ All songs processed! Add more to Google Drive.")
        return
    print(f"🎲 Auto-selected: {filename}")
    song_path = download_song(creds, file_id, filename)
    result = process_song(creds, song_path, no_upload=args.no_upload,
                          privacy_status=privacy, file_id=file_id, test_mode=args.test)
    if result:
        if result.get("uploaded"):
            print(f"\n🎉 Published! {result.get('url', '')}")
        elif args.no_upload:
            print(f"\n🎉 Video generated! {result.get('video', '')}")


if __name__ == "__main__":
    main()
