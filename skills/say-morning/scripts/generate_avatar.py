#!/usr/bin/env python3
"""Generate FIFA kid avatar saying 早晨 via Unorouter gpt-image-2.5."""

import argparse
import base64
import json
import os
import random
import sys
import time
import urllib.request
from io import BytesIO
from PIL import Image

FIFA_TOP_48 = [
    ("Argentina", "sky blue and white vertical striped jersey, gold details, sun emblem"),
    ("France", "deep royal blue jersey with subtle rooster crest, red and white collar trim"),
    ("Spain", "vibrant red jersey with yellow shoulder accents, Spanish crest"),
    ("England", "classic white home jersey with navy blue trim and Three Lions crest"),
    ("Brazil", "iconic bright yellow jersey with green collar trim and five stars"),
    ("Belgium", "rich red jersey with black and yellow geometric accents"),
    ("Netherlands", "iconic vibrant orange jersey with black lion crest"),
    ("Portugal", "deep red and forest green jersey with Portuguese federation shield"),
    ("Colombia", "bright yellow jersey with navy and red shoulder stripes"),
    ("Italy", "classic Azzurri royal blue jersey with gold star details"),
    ("Uruguay", "sky blue celeste jersey with black trim and four gold stars"),
    ("Croatia", "distinctive red and white checkerboard pattern jersey"),
    ("Germany", "crisp white jersey with black collar and shoulder trim"),
    ("Morocco", "vibrant red jersey with green collar accents and federation crest"),
    ("Japan", "Samurai Blue navy jersey with white patterned accents and Hinomaru flag badge"),
    ("USA", "clean white jersey with navy blue and red stripe details"),
    ("Senegal", "white home jersey with vibrant green, yellow, and red trim accents"),
    ("Iran", "white jersey with red and green collar trim and Persian cheetah pattern"),
    ("Denmark", "classic Danish red jersey with white chevron accents"),
    ("Switzerland", "red jersey with crisp white cross details and white collar"),
    ("Korea Republic", "vibrant pinkish-red jersey with black and white tiger stripe pattern"),
    ("Austria", "vibrant red jersey with white shoulder trim and eagle crest"),
    ("Australia", "gold and green Socceroos jersey with subtle green sleeve patterns"),
    ("Ukraine", "sunflower yellow jersey with blue shoulder accents and trident crest"),
    ("Turkey", "white jersey with bold red horizontal chest band and white crescent moon and star"),
    ("Ecuador", "bright yellow jersey with blue and red side panels"),
    ("Sweden", "bright yellow jersey with royal blue trim and Swedish crest"),
    ("Wales", "red dragon jersey with subtle yellow and green trim details"),
    ("Poland", "clean white jersey with red collar trim and Polish white eagle crest"),
    ("Hungary", "cherry red jersey with green and white tricolor collar trim"),
    ("Serbia", "deep red jersey with gold cross accents and white trim"),
    ("Egypt", "classic red jersey with black and gold accents and Pharaoh crest"),
    ("Nigeria", "vibrant green and white patterned Super Eagles jersey"),
    ("Algeria", "clean white jersey with emerald green accents and federation crest"),
    ("Qatar", "maroon jersey with serrated white edge cuffs and crest"),
    ("Peru", "classic white jersey with iconic diagonal red sash across the chest"),
    ("Tunisia", "white jersey with red accents and eagle crest"),
    ("Panama", "red jersey with blue and white geometric shoulder trim"),
    ("Scotland", "dark navy tartan-textured jersey with white and red accents"),
    ("Canada", "bold crimson red jersey with white geometric maple leaf accents"),
    ("Czechia", "rich red jersey with blue collar trim and Czech lion crest"),
    ("Norway", "vibrant red jersey with navy and white cross stripe details"),
    ("Slovakia", "blue home jersey with subtle white geometric pattern and Slovak cross"),
    ("Romania", "golden yellow jersey with blue and red tricolor cuff accents"),
    ("Greece", "classic blue and white striped accents jersey with Greek cross badge"),
    ("Chile", "vibrant red jersey with royal blue collar and white star"),
    ("Paraguay", "red and white vertical striped jersey with blue collar trim"),
    ("Mali", "green, yellow, and red tricolor patterned jersey with eagle emblem"),
]

HAIR_STYLES = [
    "cute double high buns with bangs",
    "adorable short wavy bob with side part",
    "bubbly twin pigtails with cute round hair ties",
    "fluffy messy short hair with straight bangs",
    "cute braided pigtails resting on shoulders",
    "topknot bun with loose wispy side strands",
]

HAIR_COLORS = [
    "warm chestnut brown", "soft espresso black", "honey brown", "warm caramel brown", "deep chocolate brown"
]

EYE_COLORS = [
    "warm hazel brown", "sparkling dark obsidian", "deep amber", "clear chestnut brown", "soft dark brown"
]

FACIAL_DETAILS = [
    "subtle cute freckles on the nose bridge",
    "adorable dimples on chubby rosy cheeks",
    "tiny star-shaped hair clip",
    "cute national flag ribbon in the hair",
    "delicate flower pin above the ear",
]

ACCESSORIES = [
    "matching national flag wristband",
    "mini national team flag cheek paint",
    "cute hair tie with flag colors",
    "mini team scarf pin on the collar",
    "colorful silicone cheer wristband",
]


def generate_avatar(team_name=None, text="早晨", output_path=None):
    api_key = os.environ.get("UNOROUTER_API_KEY") or os.environ.get("HERMES_CUSTOM_API_UNOROUTER_COM_API_KEY")
    if not api_key:
        print("ERROR: UNOROUTER_API_KEY not set in environment", file=sys.stderr)
        return None

    if team_name:
        matched = [t for t in FIFA_TOP_48 if t[0].lower() == team_name.lower()]
        if matched:
            team, jersey_desc = matched[0]
        else:
            team, jersey_desc = team_name, "official national team jersey in team colors"
    else:
        team, jersey_desc = random.choice(FIFA_TOP_48)

    hair_style = random.choice(HAIR_STYLES)
    hair_color = random.choice(HAIR_COLORS)
    eye_color = random.choice(EYE_COLORS)
    facial_detail = random.choice(FACIAL_DETAILS)
    accessory = random.choice(ACCESSORIES)
    team_slug = team.lower().replace(" ", "_").replace("-", "_")

    prompt = (
        f"A 1:1 square head-and-shoulders cartoon avatar of a cheerful 3-year-old chibi anime kid, "
        f"authentic classic 1980s-1990s Studio Ghibli cel animation style, Hayao Miyazaki watercolor and ink character art. "
        f"Character has {hair_color} hair styled in {hair_style}, large expressive {eye_color} eyes angled 15 degrees looking towards the camera, "
        f"chubby rosy cheeks, {facial_detail}, and a bright authentic happy smile. "
        f"The kid is holding up one hand in a cheerful peace sign (V-sign). "
        f"Wearing {team}'s national football team jersey: {jersey_desc}, with a {accessory}. "
        f"A clean white cartoon speech bubble next to the child clearly containing the Chinese text '{text}'. "
        f"Clean, subtle muted geometric patterns in team-complementary soft pastel tones for the background. "
        f"Traditional hand-drawn gouache background, flat cel shading, soft hand-inked lineart, matte paper texture finish, "
        f"soft natural studio lighting with gentle diffused shadows. "
        f"Optimized for social profile avatar: crisp edges, high resolution, expressive facial details. "
        f"Zero 3D digital gloss, no CGI plastic sheen, no watermark, no extra text, no logo."
    )

    url = "https://api.unorouter.com/v1/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "gpt-image-2.5",
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1,
        "response_format": "b64_json"
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"API Request Failed: {e}", file=sys.stderr)
        return None

    img_b64 = None
    if "data" in res_data and len(res_data["data"]) > 0:
        item = res_data["data"][0]
        if "b64_json" in item:
            img_b64 = item["b64_json"]
        elif "url" in item:
            img_url = item["url"]
            with urllib.request.urlopen(img_url, timeout=30) as img_resp:
                img_bytes = img_resp.read()
                img = Image.open(BytesIO(img_bytes))
                img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
                timestamp = int(time.time())
                if not output_path:
                    out_dir = os.environ.get("OUTPUT_DIR", "./images")
                    os.makedirs(out_dir, exist_ok=True)
                    output_path = os.path.join(out_dir, f"avatar_{team_slug}_{timestamp}.png")
                else:
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                img_512.save(output_path, format="PNG")
                return {
                    "success": True,
                    "team": team,
                    "output_path": output_path,
                    "prompt": prompt
                }

    if not img_b64:
        print("ERROR: No image data returned", file=sys.stderr)
        return None

    img_data = base64.b64decode(img_b64)
    img = Image.open(BytesIO(img_data))
    img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)

    timestamp = int(time.time())
    if not output_path:
        out_dir = os.environ.get("OUTPUT_DIR", "./images")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"avatar_{team_slug}_{timestamp}.png")
    else:
        out_parent = os.path.dirname(os.path.abspath(output_path))
        if out_parent:
            os.makedirs(out_parent, exist_ok=True)

    img_512.save(output_path, format="PNG")
    try:
        os.chmod(output_path, 0o644)
    except Exception:
        pass

    return {
        "success": True,
        "team": team,
        "output_path": output_path,
        "prompt": prompt
    }


def main():
    parser = argparse.ArgumentParser(description="Generate FIFA kid cartoon avatar saying 早晨 via gpt-image-2.5")
    parser.add_argument("--team", type=str, default=None, help="FIFA team name (default: random from Top 48)")
    parser.add_argument("--text", type=str, default="早晨", help="Greeting text for speech bubble (default: 早晨)")
    parser.add_argument("--output", type=str, default=None, help="Output image file path (.png)")
    args = parser.parse_args()

    res = generate_avatar(team_name=args.team, text=args.text, output_path=args.output)
    if res:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
