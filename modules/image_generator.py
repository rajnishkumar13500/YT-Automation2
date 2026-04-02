"""
Image Generator — Creates song-relevant background images using Cloudflare Workers AI.
Models tried in order (best quality to fastest fallback):
  1. @cf/stabilityai/stable-diffusion-xl-base-1.0
  2. @cf/black-forest-labs/flux-1-schnell
  3. @cf/lykon/dreamshaper-8-lcm
  4. @cf/bytedance/stable-diffusion-xl-lightning
"""

import io
import time
import base64
import requests
from pathlib import Path
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import VIDEO_WIDTH, VIDEO_HEIGHT, BACKGROUNDS_DIR, CF_ACCOUNT_ID, CF_API_TOKEN

# Cloudflare image generation models (tried in order)
IMAGE_MODELS = [
    "@cf/stabilityai/stable-diffusion-xl-base-1.0",
    "@cf/black-forest-labs/flux-1-schnell",
    "@cf/lykon/dreamshaper-8-lcm",
    "@cf/bytedance/stable-diffusion-xl-lightning",
]


def generate_background_images(analysis, count=8):
    """
    Generate background images matching the song's actual content.
    Uses Cloudflare AI free image models. Returns list of paths, or empty on failure.
    """
    song_name = analysis.get("song_name", "Unknown")
    image_prompts = analysis.get("image_prompts", [])

    if not image_prompts:
        print("  ❌ No image prompts from audio analysis")
        return []

    print(f"  🎨 Generating {min(count, len(image_prompts))} images via Cloudflare AI...")
    print(f"  ⭐ Best models prioritized (SDXL -> Flux -> SDXL Lightning)")

    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in song_name)
    img_dir = BACKGROUNDS_DIR / safe_name
    img_dir.mkdir(parents=True, exist_ok=True)

    generated_paths = []

    song_name = analysis.get("song_name", "Unknown Song")
    mood = analysis.get("mood", "")
    genre = analysis.get("genre", "")
    
    context = ""
    if mood and genre:
        context = f"A {mood.lower()} scene matching the vibe of a {genre.lower()} song titled '{song_name}': "
    elif song_name != "Unknown Song":
        context = f"A scene matching the vibe of the song '{song_name}': "
        
    for i, prompt in enumerate(image_prompts[:count]):
        enhanced = (
    f"{context}{prompt}. "
    f"The image MUST strongly reflect the emotional and musical vibe of the song — "
    f"including its mood, energy, rhythm, and atmosphere. "
    f"Visualize the feeling of listening to this song as a cinematic moment. "
    f"If the song is emotional, show deep expressions and soft lighting; "
    f"if energetic, show motion, intensity, dynamic lighting; "
    f"if devotional, show divine aura, spiritual glow, भक्तिमय वातावरण. "

    f"Highly immersive scene that feels synced to music beats and lyrics. "

    f"If any historical or real person is mentioned, strictly ensure their face, attire, and likeness are highly accurate and match their real-world appearance. "

    f"Vertical 9:16 portrait photography, highly realistic, natural lighting, "
    f"cinematic composition, shallow depth of field, shot on 35mm lens, "
    f"photorealistic, ultra-detailed, authentic textures, "
    f"NO cartoon, NO digital art, no text, no watermarks"
    )

        print(f"    🖌️  Image {i+1}/{min(count, len(image_prompts))}...")

        saved = _try_generate_image(enhanced, img_dir / f"img_{i+1}.png")

        if saved:
            generated_paths.append(saved)
            print(f"    ✅ Image {i+1} saved")
            time.sleep(1)  # Small gap between requests
        else:
            print(f"    ⚠️  Image {i+1} skipped (all models failed)")

    if generated_paths:
        print(f"  ✅ Generated {len(generated_paths)} images")
    else:
        print(f"  ⚠️ No images generated — falling back to gradient waveform background")

    return generated_paths


def _try_generate_image(prompt, output_path):
    """
    Try generating an image using Cloudflare AI models.
    Returns the path if successful, None otherwise.
    """
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Cloudflare AI expects 'prompt' for text-to-image
    payload = {"prompt": prompt}

    for model_name in IMAGE_MODELS:
        try:
            url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{model_name}"
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 429:
                print(f"      ⏳ {model_name.split('/')[-1]} rate limited, trying next...")
                continue
                
            if response.status_code != 200:
                print(f"      ⚠️  {model_name.split('/')[-1]}: HTTP {response.status_code}")
                # Print a small snippet of the error if it's text
                if "application/json" in response.headers.get("content-type", ""):
                    try:
                        err_json = response.json()
                        errors = err_json.get("errors", [])
                        if errors:
                            print(f"         {errors[0].get('message', 'Unknown error')}")
                    except:
                        pass
                continue

            content_type = response.headers.get("content-type", "")
            
            # Case 1: Raw image bytes returned (e.g., SDXL)
            if "image" in content_type.lower():
                try:
                    img = Image.open(io.BytesIO(response.content))
                    # Center crop to 9:16 aspect ratio before resizing
                    img = _crop_center_9_16(img)
                    img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
                    img.save(str(output_path), "PNG")
                    return output_path
                except Exception as e:
                    print(f"      ⚠️  Failed to process raw image: {e}")
                    continue
                    
            # Case 2: JSON response with base64 string (e.g., Flux)
            elif "application/json" in content_type.lower():
                try:
                    data = response.json()
                    # Structure is usually {"result": {"image": "base64_string..."}}
                    result = data.get("result", {})
                    b64_data = result.get("image", "")
                    
                    if b64_data:
                        img_bytes = base64.b64decode(b64_data)
                        img = Image.open(io.BytesIO(img_bytes))
                        img = _crop_center_9_16(img)
                        img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
                        img.save(str(output_path), "PNG")
                        return output_path
                    else:
                        print(f"      ⚠️  {model_name.split('/')[-1]}: JSON without 'image' field")
                except Exception as e:
                    print(f"      ⚠️  Failed to process JSON image: {e}")
                    continue
            else:
                print(f"      ⚠️  {model_name.split('/')[-1]}: Unexpected content type {content_type}")
                
        except requests.exceptions.Timeout:
            print(f"      ⏳ {model_name.split('/')[-1]} timed out")
            continue
        except Exception as e:
            print(f"      ⚠️  {model_name.split('/')[-1]}: {str(e)[:80]}")
            continue

    return None

def _crop_center_9_16(img):
    """Crop any image to 9:16 aspect ratio from the center."""
    width, height = img.size
    target_ratio = 9.0 / 16.0
    current_ratio = width / height
    
    if current_ratio > target_ratio:
        # Image is too wide
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        return img.crop((left, 0, left + new_width, height))
    elif current_ratio < target_ratio:
        # Image is too tall
        new_height = int(width / target_ratio)
        top = (height - new_height) // 2
        return img.crop((0, top, width, top + new_height))
    
    return img
