"""
Viral Metadata Generator
Uses Gemini AI to generate highly engaging titles, descriptions, tags.
Uses the FULL song analysis (mood, genre, theme, lyrics) for context-relevant metadata.

Uses the new google.genai SDK with multi-model fallback.
"""

import json
from pathlib import Path
from google import genai
from google.genai import types

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GEMINI_API_KEY, CHANNEL_NAME

MODELS = [
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-lite",
    "gemini-3.0-deep-think-preview"
]


def _get_client():
    """Get configured Gemini client."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_viral_metadata(song_name, artist=None, duration=59,
                             analysis=None):
    """
    Generate viral YouTube Shorts metadata using Gemini AI.
    Tries multiple models to avoid quota issues.
    """
    client = _get_client()
    
    # Use CHANNEL_NAME if artist is not provided or is "Unknown Artist"
    if not artist or artist == "Unknown Artist":
        artist = CHANNEL_NAME

    # Build rich context from analysis
    genre = analysis.get("genre", "Music") if analysis else "Music"
    mood = analysis.get("mood", "") if analysis else ""
    language = analysis.get("language", "Hindi") if analysis else "Hindi"
    description = analysis.get("description", "") if analysis else ""
    lyrics = analysis.get("lyrics", "") if analysis else ""
    vibe_keywords = analysis.get("vibe_keywords", []) if analysis else []

    context_block = ""
    if analysis and song_name != "Unknown Song":
        context_block = f"""
IMPORTANT CONTEXT ABOUT THIS SONG:
- Genre: {genre}
- Mood/Feeling: {mood}
- Language: {language}
- About: {description}
- Vibe keywords: {', '.join(vibe_keywords)}
- Full Lyrics/Theme:
{lyrics}

USE THIS CONTEXT to make the title, description, and tags deeply relevant to the song's actual meaning and theme.
For example:
- If it's a devotional song about Hanuman Ji → title should mention Hanuman, Bajrangbali, Jai Hanuman
- If it's a Ram bhajan → title should mention Ram, Sita, Ayodhya
- If it's a romantic Bollywood song → title should feel romantic, emotional, use Hinglish phrases
- If it's a motivational rap → title should feel powerful, energetic
- NEVER use generic titles like "Audio Spectrum" or "Music Visualization"
"""

    prompt = f"""You are a YouTube Shorts VIRAL content expert specializing in MUSIC content.

Generate the PERFECT metadata for this YouTube Short:

🎵 Song: {song_name}
🎤 Artist: {artist}
⏱️ Duration: {duration} seconds
📐 Format: Vertical 9:16 music video with stunning visuals
{context_block}

RULES:

1. **TITLE** (max 80 chars):
   - MUST reflect the song's actual meaning and theme
   - Write the title strictly in HINGLISH (Hindi written in the English alphabet). Do NOT use Devanagari/Hindi script.
   - Include 1-2 relevant emojis
   - Use proven viral patterns:
     * For devotional: "🙏 Jai Bajrangbali | [Song] | Hanuman Bhajan #shorts"
     * For romantic: "💔 [Song Name] | Dil Ko Chu Jaye ✨ #shorts"
     * For party: "🔥 [Song Name] | Party Anthem 💃 #shorts"
     * For sad: "😢 [Song Name] | This Hits Different 💔 #shorts"
   - Include #shorts naturally
   - Make it SEARCHABLE — use words people actually search for

2. **DESCRIPTION** (300-500 chars):
   - First line: An emotional hook that matches the song's theme
   - If devotional: Include a prayer/blessing like "जय श्री राम 🙏"
   - If romantic: Include a relatable love quote
   - Song credit line with artist name
   - Call-to-action: "Like & Subscribe ❤️"
   - 6-8 hashtags at end including #shorts
   - Use the song's language where natural

3. **TAGS** (exactly 20 tags):
   - Song name + artist name
   - Theme-specific tags (e.g., "hanuman bhajan", "ram ji", "love song hindi")
   - Genre tags (e.g., "bhajan", "bollywood", "hip hop hindi")
   - Mood tags (e.g., "devotional", "romantic", "sad songs")
   - Broad reach tags: "shorts", "viral", "trending", "music"
   - Language tags: "hindi songs", "hindi music", etc.

4. **HASHTAGS** (exactly 8):
   - #shorts (first always)
   - Theme-specific (e.g., #hanumanji #jaishreeram #lovesong)
   - Genre (e.g., #bhajan #bollywood #hiphop)
   - #viral #trending

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no code block):
{{
  "title": "your viral title here",
  "description": "your full description here",
  "tags": ["tag1", "tag2", "..."],
  "hashtags": ["#shorts", "..."]
}}

ONLY return the JSON. Nothing else."""

    # Try each model
    for model_name in MODELS:
        try:
            print(f"  🔧 Trying model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            text = response.text.strip()

            # Clean up
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0]
            if text.startswith("json"):
                text = text[4:].strip()

            metadata = json.loads(text)

            # Validate
            for field in ["title", "description", "tags", "hashtags"]:
                if field not in metadata:
                    raise ValueError(f"Missing: {field}")

            if "#shorts" not in [h.lower() for h in metadata["hashtags"]]:
                metadata["hashtags"].insert(0, "#shorts")
            if len(metadata["title"]) > 100:
                metadata["title"] = metadata["title"][:97] + "..."

            print(f"  📝 Generated title: {metadata['title']}")
            return metadata

        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print(f"  ⚠️  {model_name} quota hit, trying next...")
                continue
            else:
                print(f"  ⚠️  {model_name} failed: {err[:80]}")
                continue

    # All models failed
    print(f"  ⚠️  All Gemini models exhausted, using fallback")
    return _generate_fallback_metadata(song_name, artist, analysis)


def _generate_fallback_metadata(song_name, artist, analysis=None):
    """Context-aware fallback metadata when all AI models fail."""
    # Use CHANNEL_NAME if artist is not provided or is "Unknown Artist"
    if not artist or artist == "Unknown Artist":
        artist = CHANNEL_NAME
        
    mood = analysis.get("mood", "chill") if analysis else "chill"
    genre = analysis.get("genre", "Music") if analysis else "Music"
    description_text = analysis.get("description", "") if analysis else ""

    emoji_map = {
        "devotional": "🙏", "spiritual": "🙏", "bhajan": "🙏",
        "romantic": "💔", "love": "💕", "sad": "😢",
        "energetic": "🔥", "party": "💃", "dance": "💃",
        "chill": "✨", "peaceful": "🌙", "motivational": "💪",
    }
    emoji = "🎵"
    for key, em in emoji_map.items():
        if key in mood.lower() or key in genre.lower():
            emoji = em
            break

    title = f"{emoji} {song_name} | {artist} {emoji} #shorts"
    if len(title) > 100:
        title = f"{emoji} {song_name} #shorts"

    desc = (
        f"{emoji} {song_name} by {artist}\n"
        f"{description_text}\n\n"
        f"Like & Subscribe for more! ❤️\n\n"
        f"#shorts #music #viral #{genre.lower().replace(' ', '')} "
        f"#trending #{mood.lower().replace(' ', '')} #songs #hindi"
    )

    tags = [
        song_name, artist, genre.lower(), mood, "music", "shorts",
        "viral", "trending", f"{genre.lower()} songs", "hindi",
        f"{song_name} song", "new music", "music video",
        f"{mood} songs", "popular music", "best songs",
        "youtube shorts", f"{genre.lower()} music", "songs 2026",
        "hit songs"
    ]

    hashtags = [
        "#shorts", "#music", "#viral", "#trending",
        f"#{genre.lower().replace(' ', '')}", f"#{mood.lower().replace(' ', '')}",
        "#songs", "#hindi"
    ]

    return {
        "title": title,
        "description": desc,
        "tags": tags,
        "hashtags": hashtags
    }
