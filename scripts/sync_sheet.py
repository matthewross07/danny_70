#!/usr/bin/env python3
"""
Syncs Danny Ross's 70th Birthday Memories from the Google Sheet + local Drive
uploads (or direct Drive download fallback) + supplemental media + data/extra_memories.json,
organizes the trail geographically by Place around the globe, and writes data/memories.json.

Usage:
    python3 scripts/sync_sheet.py
"""

import csv
import io
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SHEET_ID = "12sDwVj_WVe_L3MBfgASWkneV4Kh1bYLxa-G3KWS6L9M"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
GITHUB_PAGES_BASE = "https://matthewross07.github.io/danny_70/"
LOCAL_UPLOADS = next(
    (Path.home() / "Library/CloudStorage").glob(
        "GoogleDrive-*/My Drive/Untitled form (File responses)/"
        "Photos or videos associated with the memory (optional) (File responses)"
    ),
    Path("/nonexistent"),
)
MEDIA_DIR = ROOT / "media"
DATA_OUT = ROOT / "data" / "memories.json"
EXTRA_IN = ROOT / "data" / "extra_memories.json"
SHEET_MIRROR_CSV = ROOT / "danny_70_sheet_mirror.csv"
SHEET_SYNC_JSON = ROOT / "data" / "google_sheet_sync_payload.json"
GEOCACHE_PATH = ROOT / "scripts" / ".geocache.json"

# Purely Place-based geographic regions in a continuous West-to-East loop around the Earth,
# beginning in Amarillo & the Texas Plains and returning home to the Colorado Front Range.
CHAPTERS = [
    {"id": "texas-plains", "roman": "I", "name": "Texas & the High Plains", "color": "#002fa7"},
    {"id": "caribbean", "roman": "II", "name": "Caribbean Coasts", "color": "#0e7490"},
    {"id": "pennsylvania", "roman": "III", "name": "Pennsylvania Hills", "color": "#3d6b52"},
    {"id": "france", "roman": "IV", "name": "France & Italy", "color": "#1d4ed8"},
    {"id": "pacific", "roman": "V", "name": "Pacific Horizons", "color": "#0369a1"},
    {"id": "high-country", "roman": "VI", "name": "Red Rock & High Country", "color": "#b4532a"},
    {"id": "front-range", "roman": "VII", "name": "Front Range & Foothills", "color": "#284594"},
]

#Supplemental photos sent outside the Google Form that pair onto existing Sheet rows:
SUPPLEMENTAL_ROW_MEDIA = {
    25: ["media/m25_01.jpg"],
    29: ["media/m29_01.jpg", "media/m29_02.jpg", "media/m29_03.jpg", "media/m29_04.jpg"],
    34: ["media/m34_02.jpg", "media/m34_03.jpg"],
    36: ["media/m36_01.jpg", "media/m36_02.jpg", "media/m36_03.jpg"],
}

# Place-first geographic curation keyed by 1-based sheet row index.
# Titles strictly name the authentic Place (no editorialized AI headlines).
CURATED = {
    # I · Texas & the High Plains (8 stops)
    24: {
        "order": 1,
        "chapter": "texas-plains",
        "title": "Dick Bivins Stadium",
        "place": "Amarillo, Texas",
        "coords": [-101.8010, 35.2032],
        "zoom": 14.8,
        "pitch": 45,
        "bearing": -18,
    },
    27: {
        "order": 2,
        "chapter": "texas-plains",
        "title": "Tascosa High School",
        "place": "Amarillo, Texas",
        "coords": [-101.8792, 35.1938],
        "zoom": 14.8,
        "pitch": 45,
        "bearing": 10,
    },
    2: {
        "order": 3,
        "chapter": "texas-plains",
        "title": "Tascosa High School",
        "place": "Amarillo, Texas",
        "coords": [-101.8809, 35.1946],
        "zoom": 14.7,
        "pitch": 45,
        "bearing": 28,
    },
    30: {
        "order": 4,
        "chapter": "texas-plains",
        "title": "Amarillo Ballfields",
        "place": "Amarillo, Texas",
        "coords": [-101.9044, 35.1660],
        "zoom": 14.3,
        "pitch": 45,
        "bearing": 16,
    },
    1: {
        "order": 5,
        "chapter": "texas-plains",
        "title": "Fleetwood Park",
        "place": "Amarillo, Texas",
        "coords": [-101.8784, 35.1737],
        "zoom": 14.3,
        "pitch": 45,
        "bearing": -10,
        "clean_suffix": "I will work on pictures…",
    },
    25: {
        "order": 6,
        "chapter": "texas-plains",
        "title": "Jeanne & David’s Home",
        "place": "Amarillo, Texas",
        "coords": [-101.8625, 35.1845],
        "zoom": 14.4,
        "pitch": 45,
        "bearing": 14,
    },
    20: {
        "order": 7,
        "chapter": "texas-plains",
        "title": "Tucumcari",
        "place": "Route 66 · New Mexico",
        "coords": [-103.7231, 35.1537],
        "zoom": 13.5,
        "pitch": 44,
        "bearing": 42,
    },
    18: {
        "order": 8,
        "chapter": "texas-plains",
        "title": "Four Seasons Hotel",
        "place": "Austin, Texas",
        "coords": [-97.7419, 30.2616],
        "zoom": 14.6,
        "pitch": 45,
        "bearing": -28,
    },
    # II · Caribbean Coasts (2 stops)
    11: {
        "order": 9,
        "chapter": "caribbean",
        "title": "Isla Mujeres",
        "place": "Cancún, Mexico",
        "coords": [-86.7527, 21.2146],
        "zoom": 13.5,
        "pitch": 44,
        "bearing": -24,
    },
    29: {
        "order": 10,
        "chapter": "caribbean",
        "title": "Pelican Resort",
        "place": "Simpson Bay, Sint Maarten",
        "coords": [-63.0946, 18.0302],
        "zoom": 13.7,
        "pitch": 44,
        "bearing": 36,
    },
    # III · Pennsylvania Hills (2 stops)
    21: {
        "order": 11,
        "chapter": "pennsylvania",
        "title": "Laurel Highlands",
        "place": "Southern Pennsylvania",
        "coords": [-79.0800, 40.0150],
        "zoom": 12.9,
        "pitch": 43,
        "bearing": -24,
    },
    26: {
        "order": 12,
        "chapter": "pennsylvania",
        "title": "Aunt Elsie & Uncle Duane’s Farm",
        "place": "Near Latrobe, Pennsylvania",
        "coords": [-79.3840, 40.3173],
        "zoom": 13.4,
        "pitch": 44,
        "bearing": 20,
    },
    # IV · France & Italy (14 stops across Sheet + extra_memories.json)
    # orders 13..15 -> Mont-Saint-Michel, Omaha Beach, Étretat
    14: {
        "order": 16,
        "chapter": "france",
        "title": "Notre-Dame de Paris",
        "place": "Paris, France",
        "coords": [2.3499, 48.8530],
        "zoom": 14.9,
        "pitch": 45,
        "bearing": -32,
    },
    # orders 17..18 -> Chalencon, Le Cros · Tiranges
    15: {
        "order": 19,
        "chapter": "france",
        "title": "Chez Provost · Crespinhac",
        "place": "Solignac-sous-Roche, France",
        "coords": [4.0088, 45.2519],
        "zoom": 13.9,
        "pitch": 43,
        "bearing": 28,
    },
    5: {
        "order": 20,
        "chapter": "france",
        "title": "Crespinhac",
        "place": "Haute-Loire, France",
        "coords": [4.0096, 45.2502],
        "zoom": 13.8,
        "pitch": 43,
        "bearing": 16,
    },
    16: {
        "order": 21,
        "chapter": "france",
        "title": "Domaine Guion",
        "place": "Provence, France",
        "coords": [5.3947, 43.7371],
        "zoom": 13.6,
        "pitch": 44,
        "bearing": 12,
    },
    # orders 22..26 -> Saint-Cyr-sur-Mer, Chamonix, Venice, Florence, Rome
    # V · Pacific Horizons (2 stops)
    12: {
        "order": 27,
        "chapter": "pacific",
        "title": "Ross",
        "place": "West Coast, New Zealand",
        "coords": [170.8174, -42.8992],
        "zoom": 12.8,
        "pitch": 43,
        "bearing": 125,
    },
    31: {
        "order": 28,
        "chapter": "pacific",
        "title": "Pono Kai · Kapaʻa",
        "place": "Kauaʻi, Hawaiʻi",
        "coords": [-159.3189, 22.0731],
        "zoom": 13.5,
        "pitch": 44,
        "bearing": -72,
    },
    # VI · Red Rock & High Country (14 stops, including extra_seanor=33, extra_ryan=35)
    13: {
        "order": 29,
        "chapter": "high-country",
        "title": "Mesa Arch",
        "place": "Canyonlands · Moab, Utah",
        "coords": [-109.8658, 38.3885],
        "zoom": 13.4,
        "pitch": 43,
        "bearing": 112,
    },
    34: {
        "order": 30,
        "chapter": "high-country",
        "title": "Mountain Cabin",
        "place": "Near Telluride, Colorado",
        "coords": [-108.0136, 37.9182],
        "zoom": 12.8,
        "pitch": 41,
        "bearing": 128,
    },
    4: {
        "order": 31,
        "chapter": "high-country",
        "title": "Telluride Valley",
        "place": "Telluride, Colorado",
        "coords": [-108.0528, 38.0753],
        "zoom": 12.7,
        "pitch": 41,
        "bearing": 142,
    },
    6: {
        "order": 32,
        "chapter": "high-country",
        "title": "Outside Ouray",
        "place": "San Juan Mountains, Colorado",
        "coords": [-107.6707, 38.0228],
        "zoom": 12.5,
        "pitch": 39,
        "bearing": 162,
    },
    # order 33 -> extra_seanor (Alpine Ridge Outside Ouray)
    19: {
        "order": 34,
        "chapter": "high-country",
        "title": "Vallecito Lake",
        "place": "Bayfield, Colorado",
        "coords": [-107.5430, 37.4032],
        "zoom": 12.8,
        "pitch": 41,
        "bearing": 12,
    },
    # order 35 -> extra_ryan (Colorado Backcountry)
    36: {
        "order": 36,
        "chapter": "high-country",
        "title": "San Juan Wilderness",
        "place": "Conejos County, Colorado",
        "coords": [-106.6234, 37.3385],
        "zoom": 12.6,
        "pitch": 40,
        "bearing": 35,
    },
    35: {
        "order": 37,
        "chapter": "high-country",
        "title": "Mix Lake Campground",
        "place": "Platoro, Colorado",
        "coords": [-106.5427, 37.3578],
        "zoom": 13.0,
        "pitch": 41,
        "bearing": 20,
    },
    7: {
        "order": 38,
        "chapter": "high-country",
        "title": "Platoro",
        "place": "Conejos River Valley, Colorado",
        "coords": [-106.5328, 37.3520],
        "zoom": 13.0,
        "pitch": 41,
        "bearing": -12,
    },
    33: {
        "order": 39,
        "chapter": "high-country",
        "title": "Trujillo Meadows",
        "place": "Cumbres Pass, Colorado",
        "coords": [-106.4495, 37.0466],
        "zoom": 12.9,
        "pitch": 41,
        "bearing": -28,
    },
    23: {
        "order": 40,
        "chapter": "high-country",
        "title": "Tenmile Range",
        "place": "Near Breckenridge, Colorado",
        "coords": [-106.0667, 39.4802],
        "zoom": 12.7,
        "pitch": 41,
        "bearing": -88,
    },
    37: {
        "order": 41,
        "chapter": "high-country",
        "title": "BlueSky Breckenridge",
        "place": "Breckenridge, Colorado",
        "coords": [-106.0522, 39.4765],
        "zoom": 13.2,
        "pitch": 42,
        "bearing": -82,
    },
    17: {
        "order": 42,
        "chapter": "high-country",
        "title": "Breckenridge",
        "place": "Summit County, Colorado",
        "coords": [-106.0465, 39.4829],
        "zoom": 13.1,
        "pitch": 42,
        "bearing": -90,
    },
    # VII · Front Range & Foothills (7 stops, culminating on Mount Morrison!)
    22: {
        "order": 43,
        "chapter": "front-range",
        "title": "Cripple Creek",
        "place": "Teller County, Colorado",
        "coords": [-105.1783, 38.7467],
        "zoom": 13.0,
        "pitch": 42,
        "bearing": 42,
    },
    10: {
        "order": 44,
        "chapter": "front-range",
        "title": "Half Turn Road",
        "place": "Colorado Springs, Colorado",
        "coords": [-104.7565, 38.8860],
        "zoom": 13.6,
        "pitch": 44,
        "bearing": -96,
    },
    32: {
        "order": 45,
        "chapter": "front-range",
        "title": "Colorado Springs",
        "place": "El Paso County, Colorado",
        "coords": [-104.7626, 38.9549],
        "zoom": 13.3,
        "pitch": 44,
        "bearing": -102,
    },
    8: {
        "order": 46,
        "chapter": "front-range",
        "title": "18245 Pine Vista Place",
        "place": "Monument, Colorado",
        "coords": [-104.7563, 39.0954],
        "zoom": 13.8,
        "pitch": 44,
        "bearing": -96,
    },
    28: {
        "order": 47,
        "chapter": "front-range",
        "title": "Pine Vista Place",
        "place": "Monument, Colorado",
        "coords": [-104.7549, 39.0961],
        "zoom": 13.9,
        "pitch": 44,
        "bearing": -88,
    },
    9: {
        "order": 48,
        "chapter": "front-range",
        "title": "Empower Field at Mile High",
        "place": "Denver, Colorado",
        "coords": [-105.0192, 39.7440],
        "zoom": 14.6,
        "pitch": 45,
        "bearing": -85,
    },
    3: {
        "order": 49,
        "chapter": "front-range",
        "title": "Mount Morrison",
        "place": "Morrison, Colorado",
        "coords": [-105.2200, 39.6692],
        "zoom": 13.2,
        "pitch": 43,
        "bearing": -68,
    },
}


def load_geocache():
    if GEOCACHE_PATH.exists():
        return json.loads(GEOCACHE_PATH.read_text())
    return {}


def save_geocache(cache):
    GEOCACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCACHE_PATH.write_text(json.dumps(cache, indent=2))


def get_drive_file_id(p: Path):
    """Return Google Drive item ID from macOS DriveFS extended attributes if synced."""
    try:
        fid = subprocess.check_output(
            ["xattr", "-p", "com.google.drivefs.item-id#S", str(p)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return fid or None
    except Exception:
        return None


def build_local_drive_index():
    """Map Google Drive file IDs to local paths across both Form Uploads and media/."""
    idx = {}
    for folder in (LOCAL_UPLOADS, MEDIA_DIR):
        if not folder.exists():
            continue
        for p in sorted(folder.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            fid = get_drive_file_id(p)
            if fid and fid not in idx:
                idx[fid] = p
    return idx


def get_image_dims(path: Path):
    with Image.open(path) as im:
        return im.size


def get_video_dims(path: Path):
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    d = json.loads(out)
    st = d["streams"][0]
    dur = float(d.get("format", {}).get("duration", 12.0))
    return int(st["width"]), int(st["height"]), round(dur, 1)


def enrich_media_entry(item: dict):
    rel = item["src"]
    p = ROOT / rel
    if item.get("type") == "image" and p.exists() and ("width" not in item or "height" not in item):
        w, h = get_image_dims(p)
        return {**item, "width": w, "height": h}
    return item


def process_media_item(row_idx: int, item_num: int, fid: str, local_index: dict):
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    src = local_index.get(fid)
    temp_dl = None

    if src is None:
        dl_url = f"https://drive.google.com/uc?export=download&id={fid}"
        temp_dl = Path(f"/tmp/danny_dl_{fid}")
        if not temp_dl.exists():
            req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                temp_dl.write_bytes(resp.read())
        src = temp_dl

    ext = src.suffix.lower()
    stem = f"m{row_idx:02d}_{item_num:02d}"

    if ext in (".mov", ".mp4", ".m4v"):
        dst = MEDIA_DIR / f"{stem}.mp4"
        poster = MEDIA_DIR / f"{stem}_poster.jpg"
        if not dst.exists():
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(src),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-crf",
                    "22",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    str(dst),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if not poster.exists():
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    "0.5",
                    "-i",
                    str(dst),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(poster),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        w, h, dur = get_video_dims(dst)
        return {
            "type": "video",
            "src": f"media/{dst.name}",
            "poster": f"media/{poster.name}",
            "width": w,
            "height": h,
            "duration": dur,
        }

    SCREENSHOT_CROPS = {
        "m24_01": "iw:ih*0.705:0:ih*0.200",
        "m27_01": "iw:ih*0.610:0:ih*0.194",
    }
    # If `src` is already a curated web asset inside `media/` (e.g. synced back into the Google Sheet!),
    # reference it directly without re-encoding or duplicating files!
    if src.parent.resolve() == MEDIA_DIR.resolve() and src.suffix.lower() == ".jpg":
        w, h = get_image_dims(src)
        return {
            "type": "image",
            "src": f"media/{src.name}",
            "width": w,
            "height": h,
        }

    dst = MEDIA_DIR / f"{stem}.jpg"
    if not dst.exists():
        if stem in SCREENSHOT_CROPS:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(src),
                    "-vf",
                    f"crop={SCREENSHOT_CROPS[stem]},scale='min(1600,iw)':-2",
                    "-q:v",
                    "3",
                    str(dst),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif ext == ".heic":
            tmp_png = Path(f"/tmp/danny_heic_{stem}.png")
            subprocess.run(
                ["sips", "-s", "format", "png", "-Z", "1600", str(src), "--out", str(tmp_png)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with Image.open(tmp_png) as im:
                ImageOps.exif_transpose(im).convert("RGB").save(dst, format="JPEG", quality=86)
            tmp_png.unlink(missing_ok=True)
        else:
            with Image.open(src) as im:
                im_up = ImageOps.exif_transpose(im).convert("RGB")
                im_up.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                im_up.save(dst, format="JPEG", quality=86)
    w, h = get_image_dims(dst)
    return {
        "type": "image",
        "src": f"media/{dst.name}",
        "width": w,
        "height": h,
    }


def resolve_new_location(raw_loc: str, geocache: dict):
    """Automatic geocoding fallback for future rows added to the Google Sheet."""
    loc = raw_loc.strip()
    if not loc:
        return {
            "title": "Amarillo",
            "place": "Texas",
            "coords": [-101.8313, 35.2220],
        }
    if loc in geocache:
        return geocache[loc]

    urls = re.findall(r"https?://\S+", loc)
    query_text = loc
    if urls:
        try:
            req = urllib.request.Request(urls[0], headers={"User-Agent": "Mozilla/5.0"})
            final = urllib.request.urlopen(req, timeout=10).geturl()
            m_pin = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", final)
            m_at = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", final)
            m_q = re.search(r"[?&](?:q|coordinate)=(-?\d+\.\d+),\s*\+?(-?\d+\.\d+)", final)
            m_place = re.search(r"/maps/place/([^/@]+)", final)
            place_label = (
                urllib.parse.unquote_plus(m_place.group(1))
                if m_place and not re.match(r"^-?\d", m_place.group(1))
                else "Pinned Location"
            )
            for m in (m_pin, m_q, m_at):
                if m:
                    lat, lon = float(m.group(1)), float(m.group(2))
                    res = {"title": place_label, "place": place_label, "coords": [lon, lat]}
                    geocache[loc] = res
                    save_geocache(geocache)
                    return res
            q_param = urllib.parse.parse_qs(urllib.parse.urlparse(final).query).get("q", [None])[0]
            if q_param:
                query_text = q_param
        except Exception:
            pass

    time.sleep(1.05)
    nom_url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query_text, "format": "jsonv2", "limit": 1}
    )
    req = urllib.request.Request(nom_url, headers={"User-Agent": "danny-70-map/1.0"})
    hits = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
    if hits:
        lat, lon = float(hits[0]["lat"]), float(hits[0]["lon"])
        parts = [p.strip() for p in hits[0]["display_name"].split(",")]
        title = parts[0]
        place = ", ".join(parts[1:3]) if len(parts) > 1 else title
        res = {"title": title, "place": place, "coords": [lon, lat]}
    else:
        res = {"title": query_text[:48], "place": query_text[:60], "coords": [-104.7563, 39.0954]}
    geocache[loc] = res
    save_geocache(geocache)
    return res


def classify_region(coords):
    lon, lat = coords
    if -20 <= lon <= 30 and lat >= 35:
        return "france"
    if lon > 100 or lon < -130:
        return "pacific"
    if lat < 27 and -95 <= lon <= -55:
        return "caribbean"
    if -85 <= lon <= -73 and 38 <= lat <= 43:
        return "pennsylvania"
    if -104.2 <= lon <= -93 and lat <= 37:
        return "texas-plains"
    if -111.5 <= lon <= -105.5 and 36 <= lat <= 41:
        return "high-country"
    return "front-range"


def main():
    print("Fetching Google Sheet CSV...")
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    csv_bytes = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(csv_bytes)))
    print(f"Loaded {len(rows) - 1} form responses.")

    local_index = build_local_drive_index()
    print(f"Indexed {len(local_index)} local Drive media uploads.")
    geocache = load_geocache()

    extras_list = json.loads(EXTRA_IN.read_text()) if EXTRA_IN.exists() else []
    # Index extra_memories by first media src and by (round(lon,3), round(lat,3)) so that once
    # they are pushed into the Google Sheet, Sheet rows inherit their curated settings without duplicating!
    extra_by_media = {}
    for ex in extras_list:
        for em in ex.get("media", []):
            extra_by_media[em["src"]] = ex

    matched_extra_ids = set()
    memories = []
    for idx, r in enumerate(rows[1:], start=1):
        if not any(cell.strip() for cell in r):
            continue
        ts = r[0].strip() if len(r) > 0 else ""
        raw_text = r[1].strip() if len(r) > 1 else ""
        raw_loc = r[2].strip() if len(r) > 2 else ""
        raw_media = r[3].strip() if len(r) > 3 else ""

        fids = re.findall(r"id=([A-Za-z0-9_-]+)", raw_media)
        direct_rels = re.findall(r"(?:https?://[^\s,]+/)?(media/[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png|mp4))", raw_media)
        media_items = []
        seen_srcs = set()

        for m_i, fid in enumerate(fids, start=1):
            item = process_media_item(idx, m_i, fid, local_index)
            if item["src"] not in seen_srcs:
                seen_srcs.add(item["src"])
                media_items.append(item)

        for rel in direct_rels:
            p = ROOT / rel
            if p.exists() and rel not in seen_srcs:
                seen_srcs.add(rel)
                if p.suffix.lower() == ".mp4":
                    w, h, dur = get_video_dims(p)
                    media_items.append({"type": "video", "src": rel, "width": w, "height": h, "duration": dur})
                else:
                    w, h = get_image_dims(p)
                    media_items.append({"type": "image", "src": rel, "width": w, "height": h})

        for sup_rel in SUPPLEMENTAL_ROW_MEDIA.get(idx, []):
            sup_path = ROOT / sup_rel
            if sup_path.exists() and sup_rel not in seen_srcs:
                seen_srcs.add(sup_rel)
                w, h = get_image_dims(sup_path)
                media_items.append({"type": "image", "src": sup_rel, "width": w, "height": h})

        # Check if this Sheet row corresponds to a pushed extra_memories entry
        matched_ex = None
        for it in media_items:
            if it["src"] in extra_by_media:
                matched_ex = extra_by_media[it["src"]]
                break

        cur = CURATED.get(idx)
        if cur:
            text = raw_text
            if cur.get("clean_suffix") and text.endswith(cur["clean_suffix"]):
                text = text[: -len(cur["clean_suffix"])].rstrip()
            mem_id = f"m{idx:02d}"
            meta = {
                "order": cur["order"],
                "chapter": cur["chapter"],
                "title": cur["title"],
                "place": cur["place"],
                "coords": cur["coords"],
                "zoom": cur.get("zoom", 13.5),
                "pitch": cur.get("pitch", 44),
                "bearing": cur.get("bearing", 0),
            }
        elif matched_ex:
            matched_extra_ids.add(matched_ex["id"])
            mem_id = matched_ex["id"]
            text = raw_text
            meta = {
                "order": matched_ex["order"],
                "chapter": matched_ex.get("chapter", classify_region(matched_ex["coords"])),
                "title": matched_ex["title"],
                "place": matched_ex["place"],
                "coords": matched_ex["coords"],
                "zoom": matched_ex.get("zoom", 13.5),
                "pitch": matched_ex.get("pitch", 43),
                "bearing": matched_ex.get("bearing", 0),
            }
        else:
            geo = resolve_new_location(raw_loc, geocache)
            mem_id = f"m{idx:02d}"
            text = raw_text
            meta = {
                "order": 100 + idx,
                "chapter": classify_region(geo["coords"]),
                "title": geo["title"],
                "place": geo["place"],
                "coords": geo["coords"],
                "zoom": 13.5,
                "pitch": 44,
                "bearing": (idx * 37) % 360 - 180,
            }

        memories.append(
            {
                "id": mem_id,
                "row": idx,
                "submittedAt": ts,
                "text": text,
                "rawLocation": raw_loc,
                **meta,
                "media": media_items,
            }
        )

    # Merge any manual memories from data/extra_memories.json not yet pushed to the Google Sheet
    for ex_i, ex in enumerate(extras_list, start=1):
        if ex.get("id") in matched_extra_ids:
            continue
        ex_media = [enrich_media_entry(m) for m in ex.get("media", [])]
        memories.append(
            {
                "id": ex.get("id", f"extra_{ex_i:02d}"),
                "row": 1000 + ex_i,
                "submittedAt": ex.get("submittedAt", ""),
                "order": ex.get("order", 900 + ex_i),
                "chapter": ex.get("chapter", classify_region(ex["coords"])),
                "title": ex["title"],
                "place": ex["place"],
                "coords": ex["coords"],
                "zoom": ex.get("zoom", 13.5),
                "pitch": ex.get("pitch", 43),
                "bearing": ex.get("bearing", 0),
                "text": ex.get("text", ""),
                "media": ex_media,
            }
        )

    memories.sort(key=lambda m: (m["order"], m["row"]))

    # Fetch real-world elevations in a single batch from Open-Meteo
    try:
        lats = ",".join(f"{m['coords'][1]:.5f}" for m in memories)
        lons = ",".join(f"{m['coords'][0]:.5f}" for m in memories)
        elev_url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
        elev_data = json.loads(urllib.request.urlopen(elev_url, timeout=15).read().decode())
        for m, el_m in zip(memories, elev_data.get("elevation", [])):
            if el_m is not None:
                m["elevM"] = round(float(el_m))
                m["elevFt"] = round(float(el_m) * 3.28084)
    except Exception as e:
        print("Elevation lookup skipped:", e)

    # Also write a 100% Google-Sheet-compatible CSV mirror + JSON writeback payload
    # resolving every improved local media asset to its real Google Drive link (via DriveFS xattr)
    # and GitHub Pages fallback URL so the Google Sheet and web app stay permanently unified!
    def media_to_drive_links(media_list):
        links = []
        for it in media_list:
            p = ROOT / it["src"]
            fid = get_drive_file_id(p) if p.exists() else None
            if fid:
                links.append(f"https://drive.google.com/open?id={fid}")
            else:
                links.append(GITHUB_PAGES_BASE + it["src"])
        return ", ".join(links)

    row_updates = []
    for r_idx, sup_list in sorted(SUPPLEMENTAL_ROW_MEDIA.items()):
        # Combine any existing row media links with supplemental Drive links
        orig_cell = rows[r_idx][3].strip() if r_idx < len(rows) and len(rows[r_idx]) > 3 else ""
        existing_parts = [x.strip() for x in orig_cell.split(",") if x.strip()]
        for sup_rel in sup_list:
            fid = get_drive_file_id(ROOT / sup_rel)
            dlink = f"https://drive.google.com/open?id={fid}" if fid else (GITHUB_PAGES_BASE + sup_rel)
            if dlink not in existing_parts:
                existing_parts.append(dlink)
        row_updates.append({"sheet_row": r_idx + 1, "form_row": r_idx, "media_col_d": ", ".join(existing_parts)})

    append_rows = []
    for ex in extras_list:
        if ex.get("id") in matched_extra_ids:
            continue
        lon, lat = ex["coords"]
        gmaps = f"https://www.google.com/maps?q={lat:.5f},{lon:.5f}"
        append_rows.append({
            "id": ex["id"],
            "timestamp": "11/5/2026 16:00:00",
            "description": ex.get("text", ""),
            "location": f"{ex['title']} ({ex['place']}) {gmaps}",
            "media": media_to_drive_links(ex.get("media", [])),
        })

    SHEET_SYNC_JSON.write_text(json.dumps({
        "sheet_id": SHEET_ID,
        "row_updates": row_updates,
        "append_rows": append_rows,
    }, indent=2, ensure_ascii=False))

    with SHEET_MIRROR_CSV.open("w", newline="", encoding="utf-8") as cf:
        w_csv = csv.writer(cf)
        w_csv.writerow([
            "Timestamp",
            "Written description of a memory with Danny",
            "Location where that memory occurred (ideally a Google Maps link)",
            "Photos or videos associated with the memory (optional)",
            "id",
            "title",
            "place",
            "longitude",
            "latitude",
            "web_media_srcs",
        ])
        for m in sorted(memories, key=lambda x: x["row"]):
            lon, lat = m["coords"]
            loc_str = m.get("rawLocation") or f"{m['title']} ({m['place']}) https://www.google.com/maps?q={lat:.5f},{lon:.5f}"
            w_csv.writerow([
                m.get("submittedAt") or "11/5/2026 16:00:00",
                m.get("text", ""),
                loc_str,
                media_to_drive_links(m.get("media", [])),
                m["id"],
                m["title"],
                m["place"],
                lon,
                lat,
                ", ".join(it["src"] for it in m.get("media", [])),
            ])

    payload = {
        "person": "Danny Ross",
        "occasion": "70th Birthday",
        "sheetUrl": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chapters": CHAPTERS,
        "memories": memories,
    }
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    total_media = sum(len(m["media"]) for m in memories)
    print(f"Wrote {DATA_OUT} ({len(memories)} memories, {total_media} media items).")
    print(f"Wrote {SHEET_MIRROR_CSV} & {SHEET_SYNC_JSON} ({len(row_updates)} row updates, {len(append_rows)} new rows ready for Google Sheet).")


if __name__ == "__main__":
    main()
