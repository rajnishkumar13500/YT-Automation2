import urllib.request
import ssl
import shutil

ssl_context = ssl._create_unverified_context()
urls = [
    "https://github.com/google/fonts/raw/main/ofl/hind/Hind-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/mukta/Mukta-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/yantramanav/Yantramanav-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari-Bold.ttf"
]
for u in urls:
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ssl_context) as response:
            with open("d:\\Youtube songs\\assets\\fonts\\HindiFont.ttf", 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            print(f"Success with {u}")
            break
    except Exception as e:
        print(f"Failed {u}: {e}")
