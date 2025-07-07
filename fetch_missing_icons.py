import os
import requests

ICONS_DIR = "icons"
GITHUB_API_URL = "https://api.github.com/repos/metno/weathericons/contents/weather/png"

# 1. Collect all symbol_codes from the last API call (from a log or by running get_weather)
def get_symbol_codes():
    import main
    weather = main.get_weather()
    codes = set(period['icon'] for period in weather)
    return codes

# 2. List all icons in the local icons dir
def get_local_icons():
    return set(f[:-4] for f in os.listdir(ICONS_DIR) if f.endswith('.png'))

# 3. Download missing icons from GitHub
def download_icon(symbol_code):
    # Get the list of all icons from the GitHub API
    r = requests.get(GITHUB_API_URL)
    r.raise_for_status()
    files = r.json()
    for file in files:
        if file['name'] == f"{symbol_code}.png":
            print(f"Downloading {symbol_code}.png ...")
            img = requests.get(file['download_url'])
            img.raise_for_status()
            with open(os.path.join(ICONS_DIR, f"{symbol_code}.png"), 'wb') as f:
                f.write(img.content)
            return True
    print(f"Icon {symbol_code}.png not found in repo!")
    return False

if __name__ == "__main__":
    os.makedirs(ICONS_DIR, exist_ok=True)
    needed = get_symbol_codes()
    local = get_local_icons()
    missing = needed - local
    print(f"Missing icons: {missing}")
    for code in missing:
        download_icon(code)
    print("Done.")
