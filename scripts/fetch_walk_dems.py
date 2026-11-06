#!/usr/bin/env python3
"""
Fetch real AWS Terrarium DEM elevation patches (meters) for the 7 chronological
landscapes of Danny's 70-year memory walk, oriented so a natural valley/corridor
runs along the walk axis (-z = forward toward the horizon).
"""
import io
import json
import math
import urllib.request
from pathlib import Path
from PIL import Image
import numpy as np

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "walk_dems.json"

# 7 chronological realms grounded in real places from Danny's life
REALMS = [
    {
        "id": "plains",
        "roman": "I",
        "era": "1956 – 1975",
        "name": "Amarillo & Palo Duro Rim",
        "place": "Texas Panhandle",
        "lat": 34.955,
        "lon": -101.665,
        "zoom": 11,
        "rot_deg": 25.0,
    },
    {
        "id": "mesas",
        "roman": "II",
        "era": "1976 – 1986",
        "name": "Tucumcari & Vallecito Pines",
        "place": "New Mexico & Southern Colorado",
        "lat": 37.415,
        "lon": -107.540,
        "zoom": 11,
        "rot_deg": 0.0,
    },
    {
        "id": "foothills",
        "roman": "III",
        "era": "1988 – 2008",
        "name": "Monument & Pikes Peak Foothills",
        "place": "Colorado Front Range",
        "lat": 38.920,
        "lon": -104.975,
        "zoom": 11,
        "rot_deg": -65.0,
    },
    {
        "id": "france",
        "roman": "IV",
        "era": "2011 – 2018",
        "name": "Chalencon Gorge & Old-World Valleys",
        "place": "France & Italy",
        "lat": 45.288,
        "lon": 3.982,
        "zoom": 11,
        "rot_deg": 12.0,
    },
    {
        "id": "sanjuans",
        "roman": "V",
        "era": "2010 – 2021",
        "name": "Ouray & San Juan Elk Country",
        "place": "San Juan Mountains, Colorado",
        "lat": 37.995,
        "lon": -107.672,
        "zoom": 11,
        "rot_deg": 180.0,
    },
    {
        "id": "summits",
        "roman": "VI",
        "era": "2018 – 2025",
        "name": "Tenmile Ridge, Chamonix & Sea",
        "place": "High Summits & Horizons",
        "lat": 39.482,
        "lon": -106.065,
        "zoom": 11,
        "rot_deg": -80.0,
    },
    {
        "id": "morrison",
        "roman": "VII",
        "era": "2026 · 70th",
        "name": "Red Rocks & Mount Morrison",
        "place": "Morrison, Colorado",
        "lat": 39.666,
        "lon": -105.210,
        "zoom": 12,
        "rot_deg": -72.0,
    },
]


def deg2num(lat_deg: float, lon_deg: float, zoom: int):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


def fetch_terrarium_patch(lat: float, lon: float, zoom: int, rot_deg: float, nr: int = 160, nc: int = 176):
    xf, yf = deg2num(lat, lon, zoom)
    tx0 = int(math.floor(xf)) - 1
    ty0 = int(math.floor(yf)) - 1

    mosaic = np.zeros((256 * 3, 256 * 3), dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            tx = tx0 + dx
            ty = ty0 + dy
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{zoom}/{tx}/{ty}.png"
            req = urllib.request.Request(url, headers={"User-Agent": "danny70-sonicray/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGB")
            arr = np.asarray(img, dtype=np.float32)
            elev = (arr[:, :, 0] * 256.0 + arr[:, :, 1] + arr[:, :, 2] / 256.0) - 32768.0
            mosaic[dy * 256 : (dy + 1) * 256, dx * 256 : (dx + 1) * 256] = elev

    # Center pixel inside 768x768 mosaic
    cx = (xf - tx0) * 256.0
    cy = (yf - ty0) * 256.0

    # Sample rotated grid around (cx, cy) with bilinear interpolation
    span = 300.0  # ~22 km at z=11, ~11 km at z=12
    ys = np.linspace(-span * 0.5, span * 0.5, nr)
    xs = np.linspace(-span * 0.5, span * 0.5, nc)
    gx, gy = np.meshgrid(xs, ys)
    ang = math.radians(rot_deg)
    rx = cx + gx * math.cos(ang) - gy * math.sin(ang)
    ry = cy + gx * math.sin(ang) + gy * math.cos(ang)

    x0 = np.clip(np.floor(rx).astype(int), 0, mosaic.shape[1] - 2)
    y0 = np.clip(np.floor(ry).astype(int), 0, mosaic.shape[0] - 2)
    fx = np.clip(rx - x0, 0.0, 1.0)
    fy = np.clip(ry - y0, 0.0, 1.0)

    h00 = mosaic[y0, x0]
    h10 = mosaic[y0, x0 + 1]
    h01 = mosaic[y0 + 1, x0]
    h11 = mosaic[y0 + 1, x0 + 1]
    patch = (1 - fy) * ((1 - fx) * h00 + fx * h10) + fy * ((1 - fx) * h01 + fx * h11)
    return patch


def main():
    out = {"grid": {"nr": 160, "nc": 176}, "realms": []}
    for r in REALMS:
        patch = fetch_terrarium_patch(r["lat"], r["lon"], r["zoom"], r["rot_deg"], 160, 176)
        emin = float(np.min(patch))
        emax = float(np.max(patch))
        print(f"Fetched {r['roman']:3s} | {r['name']:36s} | elev {emin:6.1f}m .. {emax:6.1f}m (relief {emax - emin:6.1f}m)")
        entry = dict(r)
        entry["elev_min_m"] = round(emin, 1)
        entry["elev_max_m"] = round(emax, 1)
        entry["H"] = np.round(patch, 1).tolist()
        out["realms"].append(entry)

    OUT_PATH.write_text(json.dumps(out))
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
