"""
Audio Analyzer — Uses Gemini AI to understand song content.
Sends the actual audio file to Gemini for analysis.
Returns song details, mood, genre, and image prompts.

Uses the new google.genai SDK (not deprecated google.generativeai).
"""

import json
import time
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
        raise ValueError(
            "❌ GEMINI_API_KEY not set in .env\n"
            "   Get a free key from https://aistudio.google.com/"
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def analyze_song(audio_path):
    """
    Send the audio file to Gemini for deep analysis.
    Tries multiple models to work around per-model daily quota limits.
    """
    client = _get_client()
    audio_path = Path(audio_path)

    print(f"  🎧 Analyzing audio with Gemini AI...")

    # Upload the audio file
    audio_file = None
    for attempt in range(3):
        try:
            audio_file = client.files.upload(file=str(audio_path))
            break
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait = 20 * (attempt + 1)
                print(f"  ⏳ Upload rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise

    if audio_file is None:
        raise RuntimeError("Failed to upload audio file")

    # Wait for processing
    while audio_file.state.name == "PROCESSING":
        print(f"  ⏳ Processing audio...")
        time.sleep(3)
        audio_file = client.files.get(name=audio_file.name)

    prompt = _build_prompt()

    # Try each model until one works
    for model_name in MODELS:
        try:
            print(f"  🔧 Trying model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=[audio_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            text = response.text.strip()

            # Clean up markdown wrappers
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("\n", 1)[0]
            if text.startswith("json"):
                text = text[4:].strip()

            analysis = json.loads(text)

            # Validate
            required = ["song_name", "artist", "lyrics", "genre", "mood", "colors", "image_prompts", "timed_lyrics", "cta_text"]
            for field in required:
                if field not in analysis:
                    raise ValueError(f"Missing field: {field}")

            print(f"  🎵 Song: {analysis['song_name']}")
            print(f"  🎤 Artist: {analysis['artist']}")
            print(f"  🎸 Genre: {analysis['genre']}")
            print(f"  💫 Mood: {analysis['mood']}")
            print(f"  🌍 Language: {analysis.get('language', 'Unknown')}")

            # Clean up uploaded file
            try:
                client.files.delete(name=audio_file.name)
            except Exception:
                pass

            return analysis

        except json.JSONDecodeError as e:
            print(f"  ⚠️  Bad JSON from {model_name}: {e}")
            continue

        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print(f"  ⚠️  {model_name} quota exceeded, trying next model...")
                continue
            else:
                print(f"  ⚠️  {model_name} failed: {err[:100]}")
                continue

    # All models failed — clean up and fallback
    try:
        client.files.delete(name=audio_file.name)
    except Exception:
        pass

    print(f"  ⚠️  All models exhausted, using fallback analysis")
    return _fallback_analysis(audio_path)


def _build_prompt():
    return """Listen to this song carefully and analyze it in detail.

I need you to identify and return the following information about this song:

1. **song_name**: The actual name of this song. If you can recognize it, give the real name. If not, create an appropriate name based on the lyrics/melody.
2. **artist**: The artist/singer. If unknown, say "{CHANNEL_NAME}".
3. **lyrics**: THE MOST IMPORTANT FIELD. Extract the FULL lyrics of the song, or a very detailed text summary of the main themes and spoken words if it's very long or mostly instrumental. We need this exact content to generate highly specific images and metadata.
4. **genre**: The music genre (e.g., Pop, Bollywood, Hip-Hop, Classical, Lo-fi, EDM, Rock, R&B, Indie, Bhajan, Devotional, etc.)
5. **mood**: The emotional mood (e.g., romantic, energetic, melancholic, uplifting, chill, intense, dreamy, nostalgic, devotional, spiritual)
6. **language**: The language of the song
7. **description**: A 1-2 sentence description of what the song is about or the feeling it conveys
8. **colors**: A list of 4 hex color codes that match the song's mood and vibe. For example:
   - Romantic/love songs → warm pinks, reds, purples (#FF69B4, #C71585, #8B008B, #FF1493)
   - Energetic/party → bright neon colors (#FF0066, #00FF88, #FFD700, #FF4500)
   - Sad/melancholic → deep blues, grays (#191970, #4169E1, #2F4F4F, #483D8B)
   - Devotional/spiritual → saffron, gold, orange (#FF9933, #FFD700, #FF6600, #CC5500)
   - Chill/lo-fi → soft pastels, warm tones (#DDA0DD, #98FB98, #FFE4B5, #87CEEB)
9. **timed_lyrics**: A list of 15-30 objects representing individual lyric lines with EXACT starting and ending timestamps in seconds. Listen closely to the audio to timestamp when the singer starts and stops singing each line. Each line should be a SHORT phrase (3-10 words max). Cover the entire song from start to end. Example:
   [
     {"text": "Tujhe dekha toh ye jaana sanam", "start": 12.5, "end": 15.2},
     {"text": "Pyaar hota hai deewana sanam", "start": 16.0, "end": 19.5}
   ]
   Do NOT use the audio file name as a lyric line. Only extract the ACTUAL sung words. For long instrumentals, add {"text": "🎵", "start": X, "end": Y}.
10. **image_prompts**: A list of 10 image descriptions for AI-generated backgrounds. These images should depict the ACTUAL SUBJECT of the song — EXACTLY matching the extracted lyrics, characters, scenes, and themes. Generate images that match EACH SECTION of the song (intro, verse 1, chorus, verse 2, bridge, outro etc.) so the visuals flow with the music.
   CRITICAL: DO NOT create generic abstract backgrounds. Create images of EXACTLY what the song lyrics are about.
   Examples:
   - For a Hanuman bhajan: "Majestic Lord Hanuman flying through golden clouds carrying a mountain, divine glow, epic Indian mythology art style, devotional atmosphere, highly detailed digital painting"
   - For a Ram bhajan: "Lord Ram with bow and arrow in a beautiful forest setting, divine golden aura, Indian mythology art style, serene and powerful, epic composition"
   - For a Krishna song: "Lord Krishna playing flute under a banyan tree, peacock feather crown, Vrindavan setting, divine blue skin, beautiful Indian art"
   - For a romantic Bollywood song: "Beautiful couple walking hand in hand through rain in an Indian city, cinematic mood, romantic atmosphere, warm golden lighting, Bollywood style"
   - For a sad song: "Person sitting alone by a window on a rainy night, melancholic atmosphere, soft dim lighting, emotional and cinematic, Indian setting"
   - For a party/dance song: "Vibrant Bollywood dance scene with colorful lights, energetic crowd, neon glow, celebration, festive Indian atmosphere"
   - Each prompt should be 40-60 words and describe a SPECIFIC visual scene related to the song
11. **vibe_keywords**: 5-8 keywords describing the song's overall vibe (used for YouTube tags)
12. **cta_text**: A short, highly engaging Call-To-Action (max 50 chars) for the end of the video.
   - MUST MATCH the song's theme.
   - If Devotional/Spiritual: Use faith-based or blessing-oriented text (e.g., "जय श्री राम लिखकर अपनी श्रद्धा दिखाओ 🙏", "भगवान के भक्त हो तो चैनल को सब्सक्राइब करो 🙏", "अगर आप सच्चे भक्त हैं तो लाइक करें 🔱").
   - If Romantic: "Like & Subscribe for more love songs ❤️" or similar relatable quote.
   - If Party/Energetic: "Subscribe for more viral beats 🔥"
   - Keep it short and impactful. Do not use generic CTAs if the song has a strong theme.

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no code block, no extra text):
{
  "song_name": "...",
  "artist": "...",
  "lyrics": "...",
  "genre": "...",
  "mood": "...",
  "language": "...",
  "description": "...",
  "colors": ["#hex1", "#hex2", "#hex3", "#hex4"],
  "timed_lyrics": [
    {"text": "line1", "start": 0.0, "end": 3.5},
    {"text": "line2", "start": 4.0, "end": 7.2}
  ],
  "image_prompts": ["prompt1", "prompt2", "...up to 10 prompts"],
  "vibe_keywords": ["keyword1", "keyword2", "..."],
  "cta_text": "..."
}

ONLY return the JSON. Nothing else."""


def _fallback_analysis(audio_path):
    """Fallback analysis when all Gemini models fail."""
    return {
        "song_name": "Unknown Song",
        "artist": CHANNEL_NAME,
        "lyrics": "Instrumental or lyrics unavailable",
        "genre": "Music",
        "mood": "chill",
        "language": "Unknown",
        "description": "A beautiful music track",
        "colors": ["#7B68EE", "#00CED1", "#FF69B4", "#4B0082"],
        "timed_lyrics": [],
        "image_prompts": [
            "Abstract music visualization with flowing neon waves, dark background, purple and blue gradients, ethereal atmosphere, cinematic quality",
            "Dreamy landscape with soft glowing lights, musical notes floating in air, peaceful night sky, stars twinkling, atmospheric mood",
            "Silhouette of a person with headphones against colorful bokeh lights, urban night setting, musical vibes, cinematic composition",
            "Abstract art with flowing liquid colors, purple blue and pink gradients merging, dynamic motion, artistic digital art style",
            "Cosmic space scene with nebula colors, musical energy waves, stars and galaxies, deep purple and blue tones, cinematic",
            "Mystical forest pathway with glowing fireflies, moonlight filtering through trees, enchanted atmosphere, fantasy digital art",
            "Ocean waves under a starry night sky, bioluminescent water, peaceful and serene, cinematic wide shot, ethereal mood",
            "Neon city streets at night with rain reflections, cyberpunk atmosphere, vibrant purple and blue lights, cinematic composition",
            "Mountain landscape at golden hour with dramatic clouds, warm sunlight, epic wide angle, cinematic nature photography style",
            "Aurora borealis over a calm lake, mirror reflections, greens and purples dancing in sky, magical atmosphere, ultra detailed"
        ],
        "vibe_keywords": ["music", "vibes", "mood", "chill", "songs"],
        "cta_text": "Like & Subscribe ❤️"
    }
