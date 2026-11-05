#!/usr/bin/env python3
"""
Syncs Danny Ross's 70th Birthday Memories from the Google Sheet + local Drive
uploads (or direct Drive download fallback) + data/extra_memories.json, converts
HEIC/PNG/JPEG/MOV files into web-ready media/, and writes data/memories.json.

Usage:
    python3 scripts/sync_sheet.py
"""

import csv
import io
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET_ID = "12sDwVj_WVe_L3MBfgASWkneV4Kh1bYLxa-G3KWS6L9M"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
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
GEOCACHE_PATH = ROOT / "scripts" / ".geocache.json"

CHAPTERS = [
    {"id": "roots", "roman": "I", "name": "Roots & Rebel Years", "color": "#c96a3b"},
    {"id": "debbie", "roman": "II", "name": "Debbie & Early Journeys", "color": "#d48c46"},
    {"id": "front-range", "roman": "III", "name": "Colorado Home Base", "color": "#5c8a6e"},
    {"id": "high-country", "roman": "IV", "name": "High Country & Campfires", "color": "#3f7a5c"},
    {"id": "far-horizons", "roman": "V", "name": "Far Horizons", "color": "#4b7fa8"},
    {"id": "seventy", "roman": "VI", "name": "Turning Seventy", "color": "#d99b38"},
]

# Curated location & narrative arc metadata keyed by 1-based sheet row index.
# New rows added to the sheet after row 37 are automatically geocoded & appended!
CURATED = {
    26: {
        "order": 1,
        "chapter": "roots",
        "title": "Aunt Elsie & Uncle Duane’s Farm",
        "place": "Near Latrobe, Pennsylvania",
        "coords": [-79.3840, 40.3173],
        "zoom": 13.9,
        "pitch": 73,
        "bearing": 122,
    },
    30: {
        "order": 2,
        "chapter": "roots",
        "title": "Ballfields of Amarillo",
        "place": "Amarillo, Texas",
        "coords": [-101.9044, 35.1660],
        "zoom": 14.8,
        "pitch": 71,
        "bearing": 28,
    },
    24: {
        "order": 3,
        "chapter": "roots",
        "title": "Record Pass for the Tascosa Rebels",
        "place": "Dick Bivins Stadium · Amarillo, TX",
        "coords": [-101.8010, 35.2032],
        "zoom": 15.8,
        "pitch": 72,
        "bearing": -26,
    },
    27: {
        "order": 4,
        "chapter": "roots",
        "title": "Quarterback & Running Back",
        "place": "Tascosa High School · Amarillo, TX",
        "coords": [-101.8792, 35.1938],
        "zoom": 15.6,
        "pitch": 72,
        "bearing": 22,
    },
    2: {
        "order": 5,
        "chapter": "roots",
        "title": "Big Rebel Shoes to Fill",
        "place": "Tascosa High School · Amarillo, TX",
        "coords": [-101.8809, 35.1946],
        "zoom": 15.5,
        "pitch": 72,
        "bearing": 74,
    },
    1: {
        "order": 6,
        "chapter": "roots",
        "title": "Campfire Showers & Fleetwood Walks",
        "place": "Fleetwood · Amarillo, TX",
        "coords": [-101.8784, 35.1737],
        "zoom": 14.8,
        "pitch": 71,
        "bearing": -22,
        "clean_suffix": "I will work on pictures…",
    },
    25: {
        "order": 7,
        "chapter": "debbie",
        "title": "The Night He Asked Debbie",
        "place": "Jeanne & David’s Home · Amarillo, TX",
        "coords": [-101.8625, 35.1845],
        "zoom": 14.8,
        "pitch": 71,
        "bearing": 35,
    },
    20: {
        "order": 8,
        "chapter": "debbie",
        "title": "Wedding Getaway in the Datsun B210",
        "place": "Tucumcari, New Mexico",
        "coords": [-103.7231, 35.1537],
        "zoom": 14.0,
        "pitch": 74,
        "bearing": 132,
    },
    19: {
        "order": 9,
        "chapter": "debbie",
        "title": "Honeymoon Cabins by the Water",
        "place": "Vallecito Lake, Colorado",
        "coords": [-107.5430, 37.4032],
        "zoom": 13.7,
        "pitch": 75,
        "bearing": 12,
    },
    21: {
        "order": 10,
        "chapter": "debbie",
        "title": "General Patton at the ’87 Reunion",
        "place": "Laurel Highlands · Southern PA",
        "coords": [-79.0800, 40.0150],
        "zoom": 13.2,
        "pitch": 73,
        "bearing": -32,
    },
    10: {
        "order": 11,
        "chapter": "front-range",
        "title": "First Home Beyond Amarillo",
        "place": "Half Turn Rd · Colorado Springs, CO",
        "coords": [-104.7565, 38.8860],
        "zoom": 14.3,
        "pitch": 74,
        "bearing": -96,
    },
    32: {
        "order": 12,
        "chapter": "front-range",
        "title": "Laughter & Gratitude From the Start",
        "place": "Colorado Springs, Colorado",
        "coords": [-104.7626, 38.9549],
        "zoom": 13.9,
        "pitch": 74,
        "bearing": -104,
    },
    8: {
        "order": 13,
        "chapter": "front-range",
        "title": "Open Doors on Pine Vista Place",
        "place": "18245 Pine Vista Pl · Monument, CO",
        "coords": [-104.7563, 39.0954],
        "zoom": 14.5,
        "pitch": 74,
        "bearing": -102,
    },
    28: {
        "order": 14,
        "chapter": "front-range",
        "title": "March 2020 Quarantine Dispatch",
        "place": "Pine Vista Pl · Monument, CO",
        "coords": [-104.7549, 39.0961],
        "zoom": 14.7,
        "pitch": 74,
        "bearing": -88,
    },
    22: {
        "order": 15,
        "chapter": "front-range",
        "title": "Golden Aspens With His Boys",
        "place": "Cripple Creek, Colorado",
        "coords": [-105.1783, 38.7467],
        "zoom": 13.9,
        "pitch": 75,
        "bearing": 48,
    },
    9: {
        "order": 16,
        "chapter": "front-range",
        "title": "Aggies vs. Buffs at Mile High",
        "place": "Empower Field · Denver, CO",
        "coords": [-105.0192, 39.7440],
        "zoom": 15.4,
        "pitch": 73,
        "bearing": -85,
    },
    23: {
        "order": 17,
        "chapter": "high-country",
        "title": "Carving Turns Together",
        "place": "Near Breckenridge, Colorado",
        "coords": [-106.0667, 39.4802],
        "zoom": 13.8,
        "pitch": 75,
        "bearing": -102,
    },
    17: {
        "order": 18,
        "chapter": "high-country",
        "title": "Grooving at Taylor’s Wedding",
        "place": "Breckenridge, Colorado",
        "coords": [-106.0465, 39.4829],
        "zoom": 14.4,
        "pitch": 75,
        "bearing": -96,
    },
    37: {
        "order": 19,
        "chapter": "high-country",
        "title": "Officiating in the Mountains",
        "place": "BlueSky · Breckenridge, CO",
        "coords": [-106.0522, 39.4765],
        "zoom": 14.6,
        "pitch": 75,
        "bearing": -82,
    },
    18: {
        "order": 20,
        "chapter": "high-country",
        "title": "Wedding Sightings in Austin",
        "place": "Four Seasons · Austin, TX",
        "coords": [-97.7419, 30.2616],
        "zoom": 15.5,
        "pitch": 72,
        "bearing": -58,
    },
    33: {
        "order": 21,
        "chapter": "high-country",
        "title": "Scouting Camp With Jim",
        "place": "Trujillo Meadows, Colorado",
        "coords": [-106.4495, 37.0466],
        "zoom": 14.0,
        "pitch": 75,
        "bearing": -38,
    },
    36: {
        "order": 22,
        "chapter": "high-country",
        "title": "2015 Elk Hunt",
        "place": "San Juan Wilderness, Colorado",
        "coords": [-106.6234, 37.3385],
        "zoom": 13.7,
        "pitch": 76,
        "bearing": 35,
    },
    7: {
        "order": 23,
        "chapter": "high-country",
        "title": "Two Classics From Platoro",
        "place": "Platoro, Colorado",
        "coords": [-106.5328, 37.3520],
        "zoom": 14.1,
        "pitch": 75,
        "bearing": -52,
    },
    35: {
        "order": 24,
        "chapter": "high-country",
        "title": "One Last Hunt for Jim",
        "place": "Mix Lake Campground · Platoro, CO",
        "coords": [-106.5427, 37.3578],
        "zoom": 14.3,
        "pitch": 75,
        "bearing": 24,
    },
    34: {
        "order": 25,
        "chapter": "high-country",
        "title": "Planning the Next Elk Hunt",
        "place": "Mountain Cabin · Near Telluride, CO",
        "coords": [-108.0136, 37.9182],
        "zoom": 13.7,
        "pitch": 76,
        "bearing": 132,
    },
    4: {
        "order": 26,
        "chapter": "high-country",
        "title": "Riding Horseback Under the Peaks",
        "place": "Telluride, Colorado",
        "coords": [-108.0528, 38.0753],
        "zoom": 13.6,
        "pitch": 76,
        "bearing": 158,
    },
    6: {
        "order": 27,
        "chapter": "high-country",
        "title": "Binoculars Down the Valley",
        "place": "Outside Ouray, Colorado",
        "coords": [-107.6707, 38.0228],
        "zoom": 13.9,
        "pitch": 76,
        "bearing": 172,
    },
    13: {
        "order": 28,
        "chapter": "high-country",
        "title": "Red Rock & Soils Visit",
        "place": "Mesa Arch · Moab, Utah",
        "coords": [-109.8658, 38.3885],
        "zoom": 14.4,
        "pitch": 75,
        "bearing": 112,
    },
    11: {
        "order": 29,
        "chapter": "far-horizons",
        "title": "Sun & Graduation in Cancún",
        "place": "Isla Mujeres · Cancún, Mexico",
        "coords": [-86.7527, 21.2146],
        "zoom": 14.0,
        "pitch": 72,
        "bearing": -32,
    },
    29: {
        "order": 30,
        "chapter": "far-horizons",
        "title": "Another Trip Around the Sun",
        "place": "Pelican Resort · Sint Maarten",
        "coords": [-63.0946, 18.0302],
        "zoom": 14.3,
        "pitch": 73,
        "bearing": 48,
    },
    31: {
        "order": 31,
        "chapter": "far-horizons",
        "title": "Geo & Danny on Kauaʻi",
        "place": "Pono Kai · Kapaʻa, Hawaii",
        "coords": [-159.3189, 22.0731],
        "zoom": 14.0,
        "pitch": 74,
        "bearing": -72,
    },
    14: {
        "order": 32,
        "chapter": "far-horizons",
        "title": "First Trip to France · 2011",
        "place": "Notre-Dame de Paris · France",
        "coords": [2.3499, 48.8530],
        "zoom": 15.8,
        "pitch": 72,
        "bearing": -36,
    },
    5: {
        "order": 33,
        "chapter": "far-horizons",
        "title": "The French ‘Entrée’ Surprise",
        "place": "Crespinhac · Haute-Loire, France",
        "coords": [4.0096, 45.2502],
        "zoom": 14.5,
        "pitch": 74,
        "bearing": 28,
    },
    15: {
        "order": 34,
        "chapter": "far-horizons",
        "title": "First Big Feast Chez Provost",
        "place": "Crespinhac · Solignac-sous-Roche, France",
        "coords": [4.0088, 45.2519],
        "zoom": 14.7,
        "pitch": 74,
        "bearing": 68,
    },
    16: {
        "order": 35,
        "chapter": "far-horizons",
        "title": "Grapes, Wine & French Cherries",
        "place": "Domaine Guion · Provence, France",
        "coords": [5.3947, 43.7371],
        "zoom": 14.2,
        "pitch": 74,
        "bearing": 12,
    },
    12: {
        "order": 36,
        "chapter": "far-horizons",
        "title": "Reunited in Ross, New Zealand",
        "place": "Ross · West Coast, New Zealand",
        "coords": [170.8174, -42.8992],
        "zoom": 13.5,
        "pitch": 75,
        "bearing": 132,
    },
    3: {
        "order": 37,
        "chapter": "seventy",
        "title": "Summit on His 70th Birthday",
        "place": "Mount Morrison · Colorado",
        "coords": [-105.2200, 39.6692],
        "zoom": 14.3,
        "pitch": 76,
        "bearing": -48,
    },
}


def load_geocache():
    if GEOCACHE_PATH.exists():
        return json.loads(GEOCACHE_PATH.read_text())
    return {}


def save_geocache(cache):
    GEOCACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCACHE_PATH.write_text(json.dumps(cache, indent=2))


def build_local_drive_index():
    """Map Google Drive file IDs to local paths via macOS DriveFS xattr."""
    idx = {}
    if not LOCAL_UPLOADS.exists():
        return idx
    for p in sorted(LOCAL_UPLOADS.iterdir()):
        if p.name.startswith("."):
            continue
        try:
            fid = subprocess.check_output(
                ["xattr", "-p", "com.google.drivefs.item-id#S", str(p)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if fid:
                idx[fid] = p
        except Exception:
            pass
    return idx


def get_image_dims(path: Path):
    out = subprocess.check_output(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        text=True,
    )
    w = int([l.split(":")[-1].strip() for l in out.splitlines() if "pixelWidth" in l][0])
    h = int([l.split(":")[-1].strip() for l in out.splitlines() if "pixelHeight" in l][0])
    return w, h


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


def process_media_item(row_idx: int, item_num: int, fid: str, local_index: dict):
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    src = local_index.get(fid)
    temp_dl = None

    if src is None:
        # Fallback: download directly from public Drive link if not synced locally yet
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

    # Image asset (.jpg, .jpeg, .png, .heic, .webp)
    # Clean out iOS Photos screenshot chrome on specific screenshot uploads
    SCREENSHOT_CROPS = {
        "m24_01": "iw:ih*0.705:0:ih*0.200",
        "m27_01": "iw:ih*0.610:0:ih*0.194",
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
        else:
            subprocess.run(
                [
                    "sips",
                    "-s",
                    "format",
                    "jpeg",
                    "-s",
                    "formatOptions",
                    "85",
                    "-Z",
                    "1600",
                    str(src),
                    "--out",
                    str(dst),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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
            "title": "A Shared Memory",
            "place": "Amarillo, Texas",
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
        disp = ", ".join(hits[0]["display_name"].split(",")[:2]).strip()
        res = {"title": disp, "place": disp, "coords": [lon, lat]}
    else:
        res = {"title": query_text[:48], "place": query_text[:60], "coords": [-104.7563, 39.0954]}
    geocache[loc] = res
    save_geocache(geocache)
    return res


def main():
    print("Fetching Google Sheet CSV...")
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    csv_bytes = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(csv_bytes)))
    print(f"Loaded {len(rows) - 1} form responses.")

    local_index = build_local_drive_index()
    print(f"Indexed {len(local_index)} local Drive media uploads.")
    geocache = load_geocache()

    memories = []
    for idx, r in enumerate(rows[1:], start=1):
        if not any(cell.strip() for cell in r):
            continue
        ts = r[0].strip() if len(r) > 0 else ""
        raw_text = r[1].strip() if len(r) > 1 else ""
        raw_loc = r[2].strip() if len(r) > 2 else ""
        raw_media = r[3].strip() if len(r) > 3 else ""

        cur = CURATED.get(idx)
        if cur:
            text = raw_text
            if cur.get("clean_suffix") and text.endswith(cur["clean_suffix"]):
                text = text[: -len(cur["clean_suffix"])].rstrip()
            meta = {
                "order": cur["order"],
                "chapter": cur["chapter"],
                "title": cur["title"],
                "place": cur["place"],
                "coords": cur["coords"],
                "zoom": cur.get("zoom", 14.3),
                "pitch": cur.get("pitch", 74),
                "bearing": cur.get("bearing", 0),
            }
        else:
            geo = resolve_new_location(raw_loc, geocache)
            text = raw_text
            meta = {
                "order": 100 + idx,
                "chapter": "seventy",
                "title": geo["title"],
                "place": geo["place"],
                "coords": geo["coords"],
                "zoom": 14.3,
                "pitch": 74,
                "bearing": (idx * 37) % 360 - 180,
            }

        fids = re.findall(r"id=([A-Za-z0-9_-]+)", raw_media)
        media_items = []
        for m_i, fid in enumerate(fids, start=1):
            media_items.append(process_media_item(idx, m_i, fid, local_index))

        memories.append(
            {
                "id": f"m{idx:02d}",
                "row": idx,
                "submittedAt": ts,
                "text": text,
                "rawLocation": raw_loc,
                **meta,
                "media": media_items,
            }
        )

    # Merge any manual memories from random texts/emails in data/extra_memories.json
    if EXTRA_IN.exists():
        extras = json.loads(EXTRA_IN.read_text())
        for ex_i, ex in enumerate(extras, start=1):
            memories.append(
                {
                    "id": ex.get("id", f"extra_{ex_i:02d}"),
                    "row": 1000 + ex_i,
                    "submittedAt": ex.get("submittedAt", ""),
                    "order": ex.get("order", 900 + ex_i),
                    "chapter": ex.get("chapter", "seventy"),
                    "title": ex["title"],
                    "place": ex["place"],
                    "coords": ex["coords"],
                    "zoom": ex.get("zoom", 13.8),
                    "pitch": ex.get("pitch", 62),
                    "bearing": ex.get("bearing", 0),
                    "text": ex["text"],
                    "media": ex.get("media", []),
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


if __name__ == "__main__":
    main()
