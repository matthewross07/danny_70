#!/usr/bin/env python3
"""
scripts/composite_walk_video.py

Calm, museum-grade compositor for Danny's sonic_ray Memory Walk:
  - Leaves the 3D terrain & 4,600 real OpenStreetMap neighborhood buildings
    completely uncluttered (only the soft path-traced glowing lanterns rest
    on the slopes and avenues—zero hovering/moving thumbnail clutter).
  - Memories bloom calmly ONE BY ONE (strictly solo, alternating Left <-> Right)
    in stationary upper-sky sanctuaries, tethered by a single whisper-thin
    gossamer thread to that memory's glowing 3D lantern below.
  - Every memory frame includes a jewel-like US State / Europe / World vector
    locator map (with crisp state/country badges like TX -> PA) + explicit
    two-line geographic acknowledgment whenever a memory from afar (e.g.
    Aunt Elsie & Uncle Duane's Farm in Pennsylvania) is carried along the
    physical trail below (e.g. Amarillo, Texas).
  - Paired with non-overlapping 3D ground-locked landmark signposts & a frosted
    obsidian-navy Terrain & Canto progress compass.

Usage:
  python3 scripts/composite_walk_video.py --hq-min1 --sheet-only
  python3 scripts/composite_walk_video.py --hq-min1
  python3 scripts/composite_walk_video.py --sheet-only
  python3 scripts/composite_walk_video.py
"""

import json
import math
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
LOCATOR_JSON = ROOT / "data" / "locator_outlines.json"
MEMORIES_JSON = ROOT / "data" / "memories.json"
SCRATCH_DIR = Path("/Users/mrvr/.gemini/antigravity/brain/5e72ea41-a55f-4feb-80f8-d649f9941e22/scratch")

FONT_SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
FONT_SERIF_IT = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
FONT_SANS = "/System/Library/Fonts/Avenir Next.ttc"
FONT_MONO = "/System/Library/Fonts/Menlo.ttc"
FONT_EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"


def load_font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size=max(8, int(round(size))), index=index)
    except Exception:
        return ImageFont.load_default()


_EMOJI_STRIKE_CACHE = {}


def get_emoji_glyph_rgba(ch: str, target_px: int) -> Image.Image:
    key = (ch, target_px)
    if key in _EMOJI_STRIKE_CACHE:
        return _EMOJI_STRIKE_CACHE[key]
    for strike in (64, 48, 40, 32):
        try:
            ef = ImageFont.truetype(FONT_EMOJI, strike)
            canvas = Image.new("RGBA", (strike * 2, strike * 2), (0, 0, 0, 0))
            ImageDraw.Draw(canvas).text((strike // 4, strike // 4), ch, font=ef, embedded_color=True)
            bb = canvas.getbbox()
            if bb:
                cropped = canvas.crop(bb)
                sc = target_px / max(1, cropped.height)
                nw = max(1, int(round(cropped.width * sc)))
                out = cropped.resize((nw, max(1, target_px)), Image.Resampling.LANCZOS)
                _EMOJI_STRIKE_CACHE[key] = out
                return out
        except Exception:
            continue
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    _EMOJI_STRIKE_CACHE[key] = empty
    return empty


def is_emoji_char(ch: str) -> bool:
    cp = ord(ch)
    return cp >= 0x1F000 or (0x2600 <= cp <= 0x27BF) or cp == 0xFE0F


def measure_rich_text_w(draw: ImageDraw.ImageDraw, text: str, font, emoji_px: int) -> int:
    if not any(is_emoji_char(c) for c in text):
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    w = 0
    buf = ""
    for ch in text:
        if ord(ch) == 0xFE0F:
            continue
        if is_emoji_char(ch):
            if buf:
                bb = draw.textbbox((0, 0), buf, font=font)
                w += bb[2] - bb[0]
                buf = ""
            w += emoji_px + max(2, emoji_px // 8)
        else:
            buf += ch
    if buf:
        bb = draw.textbbox((0, 0), buf, font=font)
        w += bb[2] - bb[0]
    return w


def draw_rich_text(card_im: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font, fill, emoji_px: int):
    """Renders Georgia text cleanly while compositing native Apple Color Emoji inline (zero missing-glyph boxes!)."""
    if not any(is_emoji_char(c) for c in text):
        draw.text((x, y), text, font=font, fill=fill)
        return
    cx = x
    buf = ""
    for ch in text:
        if ord(ch) == 0xFE0F:
            continue
        if is_emoji_char(ch):
            if buf:
                draw.text((cx, y), buf, font=font, fill=fill)
                bb = draw.textbbox((0, 0), buf, font=font)
                cx += bb[2] - bb[0]
                buf = ""
            eg = get_emoji_glyph_rgba(ch, emoji_px)
            if eg.width > 1:
                card_im.alpha_composite(eg, (int(round(cx + 1)), int(round(y + emoji_px * 0.08))))
                cx += eg.width + max(2, emoji_px // 8)
        else:
            buf += ch
    if buf:
        draw.text((cx, y), buf, font=font, fill=fill)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smoothstep(edge0, edge1, x):
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def haversine_miles(lon1, lat1, lon2, lat2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp * 0.5) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl * 0.5) ** 2
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def region_code_from_place(place_str: str, coords) -> str:
    p = (place_str or "").lower()
    mapping = [
        ("pennsylvania", "PA"),
        ("new mexico", "NM"),
        ("tucumcari", "NM"),
        ("texas", "TX"),
        (", tx", "TX"),
        ("amarillo", "TX"),
        ("colorado", "CO"),
        (", co", "CO"),
        ("utah", "UT"),
        ("moab", "UT"),
        ("hawai", "HI"),
        ("kaua", "HI"),
        ("mexico", "MX"),
        ("canc", "MX"),
        ("sint maarten", "SXM"),
        ("france", "FR"),
        ("italy", "IT"),
        ("new zealand", "NZ"),
    ]
    for needle, code in mapping:
        if needle in p:
            return code
    lon, lat = float(coords[0]), float(coords[1])
    if 160 <= lon <= 180 and lat < -30:
        return "NZ"
    if -165 <= lon <= -150:
        return "HI"
    if -6 <= lon <= 9 and 42 <= lat <= 51:
        return "FR"
    if 9 < lon <= 19 and 36 <= lat <= 47:
        return "IT"
    if -82 <= lon <= -74 and 39 <= lat <= 43:
        return "PA"
    if -109.1 <= lon <= -102.05 and 36.95 <= lat <= 41.05:
        return "CO"
    if -109.1 <= lon <= -103.0 and 31.3 <= lat < 37.0:
        return "NM"
    return "TX"


def extract_video_still(video_path: Path, t_sec: float = 4.0) -> Image.Image:
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{t_sec:.2f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png", "-",
    ]
    raw = subprocess.check_output(cmd)
    return Image.open(BytesIO(raw)).convert("RGB")


def smart_cover_crop(img: Image.Image, target_w: int, target_h: int, bias_y: float = 0.32) -> Image.Image:
    src_w, src_h = img.size
    target_ratio = target_w / max(1, target_h)
    src_ratio = src_w / max(1, src_h)
    if src_ratio > target_ratio:
        new_w = int(round(src_h * target_ratio))
        x0 = (src_w - new_w) // 2
        box = (x0, 0, x0 + new_w, src_h)
    else:
        new_h = int(round(src_w / target_ratio))
        y0 = int(round((src_h - new_h) * bias_y))
        y0 = max(0, min(src_h - new_h, y0))
        box = (0, y0, src_w, y0 + new_h)
    return img.crop(box).resize((target_w, target_h), Image.Resampling.LANCZOS)


def fit_uncropped(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = min(max_w / max(1, src_w), max_h / max(1, src_h))
    nw = max(1, int(round(src_w * scale)))
    nh = max(1, int(round(src_h * scale)))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def rounded_photo_rgba(img: Image.Image, radius: int, border_rgba=(255, 250, 240, 62)) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    if border_rgba:
        ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, outline=border_rgba, width=2)
        out = Image.alpha_composite(out, ov)
    return out


def wrap_text_lines(draw: ImageDraw.ImageDraw, text: str, font, max_px: int, emoji_px: int = 16):
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n") if p.strip()]
    lines = []
    for p_idx, para in enumerate(paragraphs):
        words = para.split()
        cur = ""
        for w in words:
            cand = f"{cur} {w}".strip()
            if measure_rich_text_w(draw, cand, font, emoji_px) <= max_px or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if p_idx < len(paragraphs) - 1:
            lines.append("")
    return lines


def load_memory_images(m: dict):
    imgs = []
    for item in m.get("media", []):
        p = ROOT / item["src"]
        if not p.exists():
            continue
        if item.get("type") == "image":
            try:
                imgs.append(Image.open(p).convert("RGB"))
            except Exception:
                pass
        elif item.get("type") == "video" and not imgs:
            try:
                imgs.append(extract_video_still(p, 4.0))
            except Exception:
                pass
    return imgs


def compose_photo_strip(imgs: list, max_w: int, max_h: int, S: float) -> Image.Image:
    gap = int(round(8 * S))
    r_main = int(round(9 * S))
    r_sub = int(round(7 * S))

    if len(imgs) == 1:
        p = fit_uncropped(imgs[0], max_w, max_h)
        return rounded_photo_rgba(p, radius=r_main)

    if len(imgs) == 2:
        a1 = imgs[0].width / max(1, imgs[0].height)
        a2 = imgs[1].width / max(1, imgs[1].height)
        h = min(max_h, int((max_w - gap) / max(0.4, a1 + a2)))
        h = max(int(round(96 * S)), h)
        w1 = max(int(round(64 * S)), int(round(h * a1)))
        w2 = max(int(round(64 * S)), int(round(h * a2)))
        if w1 + w2 + gap > max_w:
            sc = (max_w - gap) / (w1 + w2)
            w1, w2, h = int(w1 * sc), int(w2 * sc), int(h * sc)
        p1 = rounded_photo_rgba(imgs[0].resize((w1, h), Image.Resampling.LANCZOS), radius=r_sub)
        p2 = rounded_photo_rgba(imgs[1].resize((w2, h), Image.Resampling.LANCZOS), radius=r_sub)
        out = Image.new("RGBA", (w1 + gap + w2, h), (0, 0, 0, 0))
        out.alpha_composite(p1, (0, 0))
        out.alpha_composite(p2, (w1 + gap, 0))
        return out

    h = max_h
    w_left = int(round((max_w - gap) * 0.58))
    w_right = max_w - gap - w_left
    h_half = (h - gap) // 2
    p0 = rounded_photo_rgba(smart_cover_crop(imgs[0], w_left, h, bias_y=0.30), radius=r_sub)
    p1 = rounded_photo_rgba(smart_cover_crop(imgs[1], w_right, h_half, bias_y=0.32), radius=r_sub)
    p2 = rounded_photo_rgba(smart_cover_crop(imgs[2], w_right, h - gap - h_half, bias_y=0.32), radius=r_sub)
    out = Image.new("RGBA", (max_w, h), (0, 0, 0, 0))
    out.alpha_composite(p0, (0, 0))
    out.alpha_composite(p1, (w_left + gap, 0))
    out.alpha_composite(p2, (w_left + gap, h_half + gap))
    return out


def make_locator_map_rgba(
    locator_db: dict,
    mem_coords,
    terrain_coords,
    mem_code: str,
    terr_code: str,
    is_distant: bool,
    S: float,
) -> Image.Image:
    """
    Jewel-like cartographic mini-map (US states / Europe / World) with crisp state/country tags:
      - If is_distant: Klein-blue ring at Trail Below (`TX`) + curved golden arc to Memory Pin (`PA`)!
      - If on-trail:   Glowing Klein-blue + ivory target pin (`TX` / `NM` / `CO`) right on the trail!
    """
    mw = int(round(122 * S))
    mh = int(round(74 * S))
    im = Image.new("RGBA", (mw, mh), (4, 10, 27, 236))
    d = ImageDraw.Draw(im)

    mlon, mlat = float(mem_coords[0]), float(mem_coords[1])
    tlon, tlat = float(terrain_coords[0]), float(terrain_coords[1])

    in_na = (-130 <= mlon <= -60 and 16 <= mlat <= 54) and (-130 <= tlon <= -60 and 16 <= tlat <= 54)
    in_eu = (-11 <= mlon <= 24 and 35 <= mlat <= 56) and (-11 <= tlon <= 24 and 35 <= tlat <= 56)

    if in_na:
        lon0, lon1, lat0, lat1 = -126.5, -66.0, 23.5, 50.5
        segs_bg = locator_db.get("usa_bg", [])
        segs_fg = locator_db.get("usa", [])
    elif in_eu:
        lon0, lon1, lat0, lat1 = -9.5, 20.5, 36.5, 53.5
        segs_bg = []
        segs_fg = locator_db.get("europe", [])
    else:
        lon0, lon1, lat0, lat1 = -175.0, 180.0, -52.0, 68.0
        segs_bg = []
        segs_fg = locator_db.get("world", [])

    pad_x = 7 * S
    pad_y = 6 * S

    def proj(lon, lat):
        u = (lon - lon0) / (lon1 - lon0)
        v = 1.0 - (lat - lat0) / (lat1 - lat0)
        return (pad_x + u * (mw - 2 * pad_x), pad_y + v * (mh - 2 * pad_y))

    for seg in segs_bg:
        pts = [proj(p[0], p[1]) for p in seg]
        if len(pts) >= 2:
            d.line(pts, fill=(84, 120, 198, 76), width=max(1, int(round(0.95 * S))))

    for seg in segs_fg:
        pts = [proj(p[0], p[1]) for p in seg]
        if len(pts) >= 2:
            d.line(pts, fill=(134, 178, 255, 136), width=max(1, int(round(1.15 * S))))

    tx, ty = proj(tlon, tlat)
    mx, my = proj(mlon, mlat)
    tx, ty = clamp(tx, 7 * S, mw - 7 * S), clamp(ty, 7 * S, mh - 7 * S)
    mx, my = clamp(mx, 7 * S, mw - 7 * S), clamp(my, 7 * S, mh - 7 * S)

    f_tag = load_font(FONT_MONO, 7.6 * S)

    def draw_code_tag(px, py, code_str: str, col_fg, prefer_dx: float, prefer_dy: float):
        bb = d.textbbox((0, 0), code_str, font=f_tag)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        lx = clamp(px + prefer_dx - tw * 0.5, 4 * S, mw - tw - 4 * S)
        ly = clamp(py + prefer_dy - th * 0.5, 3 * S, mh - th - 4 * S)
        d.rounded_rectangle(
            (lx - 2.2 * S, ly - 1.2 * S, lx + tw + 2.2 * S, ly + th + 1.8 * S),
            radius=int(round(2.5 * S)),
            fill=(4, 10, 26, 214),
        )
        d.text((lx, ly), code_str, font=f_tag, fill=col_fg)

    if is_distant:
        mid_x = 0.5 * (tx + mx)
        dist_p = math.hypot(mx - tx, my - ty)
        mid_y = 0.5 * (ty + my) - max(7 * S, dist_p * 0.30)
        steps = 18
        for k in range(0, steps, 2):
            u0 = k / steps
            u1 = (k + 1) / steps
            x0 = (1 - u0) ** 2 * tx + 2 * (1 - u0) * u0 * mid_x + u0 ** 2 * mx
            y0 = (1 - u0) ** 2 * ty + 2 * (1 - u0) * u0 * mid_y + u0 ** 2 * my
            x1 = (1 - u1) ** 2 * tx + 2 * (1 - u1) * u1 * mid_x + u1 ** 2 * mx
            y1 = (1 - u1) ** 2 * ty + 2 * (1 - u1) * u1 * mid_y + u1 ** 2 * my
            d.line([(x0, y0), (x1, y1)], fill=(252, 214, 138, 236), width=max(1, int(round(1.5 * S))))

        # Klein-Blue ring on Trail Underfoot
        rt = 3.8 * S
        d.ellipse((tx - rt, ty - rt, tx + rt, ty + rt), fill=(10, 34, 108, 235), outline=(108, 166, 255, 255), width=max(1, int(round(1.6 * S))))

        # Warm Gold Pin on Distant Memory Location
        rm_glow = 6.8 * S
        rm = 3.6 * S
        d.ellipse((mx - rm_glow, my - rm_glow, mx + rm_glow, my + rm_glow), fill=(250, 194, 92, 86))
        d.ellipse((mx - rm, my - rm, mx + rm, my + rm), fill=(255, 212, 118, 255), outline=(255, 252, 244, 248), width=max(1, int(round(1.2 * S))))

        # Place crisp state/country tags pushed cleanly in opposite directions along (tx,ty)<->(mx,my) so they NEVER collide!
        vx, vy = mx - tx, my - ty
        vlen = math.hypot(vx, vy)
        if vlen > 1e-3:
            ux, uy = vx / vlen, vy / vlen
        else:
            ux, uy = 1.0, 0.0
        draw_code_tag(tx, ty, terr_code, (152, 194, 255, 248), -ux * 14.5 * S, -uy * 11.5 * S + (4.0 * S if abs(uy) < 0.35 else 0.0))
        draw_code_tag(mx, my, mem_code, (255, 220, 142, 255), ux * 14.5 * S, uy * 11.5 * S - (4.0 * S if abs(uy) < 0.35 else 0.0))
    else:
        rg = 8.0 * S
        r1 = 4.4 * S
        r2 = 2.0 * S
        d.ellipse((mx - rg, my - rg, mx + rg, my + rg), fill=(36, 102, 255, 96))
        d.ellipse((mx - r1, my - r1, mx + r1, my + r1), fill=(0, 47, 167, 248), outline=(156, 198, 255, 255), width=max(1, int(round(1.5 * S))))
        d.ellipse((mx - r2, my - r2, mx + r2, my + r2), fill=(255, 252, 244, 255))
        draw_code_tag(mx, my, mem_code, (186, 214, 255, 250), 13.5 * S if mx < mw * 0.72 else -13.5 * S, -7.5 * S if my > 18 * S else 8.5 * S)

    rad = int(round(8 * S))
    mask = Image.new("L", (mw, mh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, mw - 1, mh - 1), radius=rad, fill=255)
    im.putalpha(mask)
    ov = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle((0, 0, mw - 1, mh - 1), radius=rad, outline=(116, 164, 255, 118), width=max(1, int(round(1.3 * S))))
    return Image.alpha_composite(im, ov)


def make_hero_sprite(m: dict, imgs: list, locator_db: dict, terrain_ref: dict, U: float) -> Image.Image:
    """
    Build a calm, stationary museum-grade memory frame (rendered at 2x * U supersampling -> 1x * U).
    Zero missing-glyph boxes, strict header wrapping so text never touches the US/World mini-map,
    and crystal-clear human acknowledgment of memory location vs. physical terrain underfoot.
    """
    SS = 2.0 * U
    pad = int(round(22 * SS))
    inner_pad = int(round(20 * SS))
    dummy = ImageDraw.Draw(Image.new("RGBA", (16, 16)))

    era_txt = m.get("era", "")
    place_txt = (m.get("place") or "").strip()
    title_txt = (m.get("title") or "").strip()
    quote_txt = (m.get("text") or "").strip()
    author_txt = (m.get("author") or "").strip()

    mem_coords = m.get("coords") or [-101.83, 35.20]
    terr_coords = [terrain_ref["lon"], terrain_ref["lat"]]
    terr_short = terrain_ref["short_name"]

    mem_code = region_code_from_place(place_txt or title_txt, mem_coords)
    terr_code = region_code_from_place(terrain_ref["label"], terr_coords)
    dist_mi = haversine_miles(mem_coords[0], mem_coords[1], terr_coords[0], terr_coords[1])
    if mem_code in ("FR", "IT") and mem_code == terr_code:
        is_distant = False
    else:
        is_distant = (mem_code != terr_code) or (dist_mi >= 90.0)

    loc_map = make_locator_map_rgba(locator_db, mem_coords, terr_coords, mem_code, terr_code, is_distant, SS)
    lm_w, lm_h = loc_map.size

    f_kicker = load_font(FONT_MONO, 9.5 * SS)
    f_title = load_font(FONT_SERIF, 19.5 * SS)
    f_geo = load_font(FONT_SERIF_IT, 12.2 * SS)
    f_author = load_font(FONT_SANS, 11.5 * SS)

    tlen = len(quote_txt)
    if tlen > 520:
        q_pt = 12.8
    elif tlen > 300:
        q_pt = 13.8
    elif tlen > 150:
        q_pt = 14.8
    else:
        q_pt = 15.6
    f_quote = load_font(FONT_SERIF_IT if tlen < 220 else FONT_SERIF, q_pt * SS)
    line_h = int(round(q_pt * 1.43 * SS))
    emoji_px = int(round(q_pt * 1.12 * SS))

    kicker_str = f"CANTO {m.get('roman', '')}  ·  {era_txt}".strip(" ·").upper()
    if is_distant:
        geo_line1 = f"Memory in {place_txt or title_txt}"
        geo_line2 = f"Carried along the {terr_short} trail below"
        geo_col_1 = (252, 214, 138, 248)
        geo_col_2 = (160, 190, 246, 224)
    else:
        geo_line1 = f"{place_txt or terr_short}  ·  right here on the trail"
        geo_line2 = ""
        geo_col_1 = (164, 202, 255, 245)
        geo_col_2 = (182, 196, 222, 200)

    single_side = (
        len(imgs) == 1
        and len(quote_txt) > 0
        and (imgs[0].width / max(1, imgs[0].height)) <= 1.58
    )

    def draw_header_and_body(cd: ImageDraw.ImageDraw, card_im: Image.Image, tx: int, ty: int, text_w: int):
        hdr_gap = int(round(14 * SS))
        hdr_w = max(int(round(170 * SS)), text_w - lm_w - hdr_gap)
        card_im.alpha_composite(loc_map, (tx + text_w - lm_w, ty))

        cy = ty + int(round(1 * SS))
        cd.text((tx, cy), kicker_str, font=f_kicker, fill=(138, 178, 255, 232))
        cy += int(round(16 * SS))

        t_lines = wrap_text_lines(dummy, title_txt, f_title, hdr_w, int(round(19 * SS)))
        for ln in t_lines:
            draw_rich_text(card_im, cd, tx, cy, ln, f_title, (255, 251, 244, 252), int(round(19 * SS)))
            cy += int(round(23.5 * SS))

        cy += int(round(1 * SS))
        icon_indent = int(round(13 * SS))
        geo_wrap_w = max(int(round(140 * SS)), hdr_w - icon_indent)

        # Draw crisp vector pin/diamond gem at start of Line 1 (never a missing font glyph!)
        gx = tx + 4.5 * SS
        gy = cy + 7.5 * SS
        if is_distant:
            rg = 3.8 * SS
            cd.polygon([(gx, gy - rg), (gx + rg, gy), (gx, gy + rg), (gx - rg, gy)], fill=(252, 208, 116, 252))
        else:
            rg = 3.2 * SS
            cd.ellipse((gx - rg, gy - rg, gx + rg, gy + rg), fill=(86, 152, 255, 252))

        g1_lines = wrap_text_lines(dummy, geo_line1, f_geo, geo_wrap_w)
        for idx_g, gln in enumerate(g1_lines):
            cd.text((tx + (icon_indent if idx_g == 0 else icon_indent), cy), gln, font=f_geo, fill=geo_col_1)
            cy += int(round(15.5 * SS))

        if geo_line2:
            g2_lines = wrap_text_lines(dummy, geo_line2, f_geo, geo_wrap_w)
            for gln in g2_lines:
                cd.text((tx + icon_indent, cy), gln, font=f_geo, fill=geo_col_2)
                cy += int(round(15.5 * SS))

        cy = max(cy + int(round(3 * SS)), ty + lm_h + int(round(8 * SS)))

        if quote_txt:
            cd.line([(tx, cy), (tx + text_w, cy)], fill=(120, 162, 255, 46), width=max(1, int(round(1.0 * SS))))
            cy += int(round(9 * SS))
            q_lines = wrap_text_lines(dummy, f"“{quote_txt}”", f_quote, text_w, emoji_px)
            for ln in q_lines:
                if ln == "":
                    cy += int(line_h * 0.45)
                else:
                    draw_rich_text(card_im, cd, tx, cy, ln, f_quote, (241, 237, 229, 246), emoji_px)
                    cy += line_h

        if author_txt:
            cy += int(round(5 * SS))
            draw_rich_text(card_im, cd, tx, cy, f"— {author_txt}", f_author, (166, 196, 255, 228), int(round(12 * SS)))
            cy += int(round(16 * SS))

        return cy - ty

    def measure_text_block(text_w: int) -> int:
        tmp = Image.new("RGBA", (max(64, text_w + 64), int(round(960 * SS))), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        return draw_header_and_body(td, tmp, 0, 0, text_w)

    r_card = int(round(15 * SS))

    if single_side:
        photo_rgba = compose_photo_strip(imgs, int(round(236 * SS)), int(round(256 * SS)), SS)
        pw, ph = photo_rgba.size
        col_gap = int(round(18 * SS))
        text_w = int(round(362 * SS))
        th = measure_text_block(text_w)
        content_h = max(ph, th)
        card_w = inner_pad * 2 + pw + col_gap + text_w
        card_h = inner_pad * 2 + content_h

        card = Image.new("RGBA", (card_w, card_h), (6, 14, 34, 222))
        cd = ImageDraw.Draw(card)
        py = inner_pad + (content_h - ph) // 2
        card.alpha_composite(photo_rgba, (inner_pad, py))
        draw_header_and_body(cd, card, inner_pad + pw + col_gap, inner_pad + (content_h - th) // 2, text_w)

    elif imgs:
        max_pw = int(round((464 if not quote_txt else 504) * SS))
        max_ph = int(round((248 if not quote_txt else 208) * SS))
        photo_rgba = compose_photo_strip(imgs, max_pw, max_ph, SS)
        pw, ph = photo_rgba.size
        min_tw = int(round((368 if not quote_txt else 404) * SS))
        text_w = max(pw, min_tw)
        th = measure_text_block(text_w)
        gap_pt = int(round(14 * SS))
        card_w = inner_pad * 2 + text_w
        card_h = inner_pad * 2 + ph + gap_pt + th

        card = Image.new("RGBA", (card_w, card_h), (6, 14, 34, 222))
        cd = ImageDraw.Draw(card)
        card.alpha_composite(photo_rgba, ((card_w - pw) // 2, inner_pad))
        draw_header_and_body(cd, card, inner_pad, inner_pad + ph + gap_pt, text_w)

    else:
        text_w = int(round(520 * SS))
        th = measure_text_block(text_w)
        bar_off = int(round(14 * SS))
        card_w = inner_pad * 2 + bar_off + text_w
        card_h = inner_pad * 2 + th

        card = Image.new("RGBA", (card_w, card_h), (6, 14, 34, 224))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle(
            (inner_pad, inner_pad + int(round(3 * SS)), inner_pad + int(round(3 * SS)), card_h - inner_pad - int(round(3 * SS))),
            radius=int(round(2 * SS)),
            fill=(46, 112, 252, 238),
        )
        draw_header_and_body(cd, card, inner_pad + bar_off, inner_pad, text_w)

    cd_b = ImageDraw.Draw(card)
    cd_b.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=r_card, outline=(106, 156, 255, 134), width=max(2, int(round(1.6 * SS))))
    cd_b.rounded_rectangle(
        (int(round(2 * SS)), int(round(2 * SS)), card_w - int(round(3 * SS)), card_h - int(round(3 * SS))),
        radius=max(4, r_card - int(round(2 * SS))),
        outline=(255, 255, 255, 24),
        width=1,
    )

    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=r_card, fill=255)
    card.putalpha(ImageChops.multiply(card.split()[3], mask))

    full = Image.new("RGBA", (card_w + 2 * pad, card_h + 2 * pad), (0, 0, 0, 0))
    shad = Image.new("RGBA", full.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shad)
    sd.rounded_rectangle(
        (pad - int(round(2 * SS)), pad + int(round(5 * SS)), pad + card_w + int(round(2 * SS)), pad + card_h + int(round(9 * SS))),
        radius=r_card + 2,
        fill=(2, 7, 22, 168),
    )
    sd.rounded_rectangle(
        (pad - int(round(4 * SS)), pad - int(round(2 * SS)), pad + card_w + int(round(4 * SS)), pad + card_h + int(round(2 * SS))),
        radius=r_card + 4,
        fill=(0, 47, 167, 56),
    )
    shad = shad.filter(ImageFilter.GaussianBlur(radius=10 * SS))
    full = Image.alpha_composite(full, shad)
    full.alpha_composite(card, (pad, pad))

    out_w = max(8, int(round(full.width / 2.0)))
    out_h = max(8, int(round(full.height / 2.0)))
    return full.resize((out_w, out_h), Image.Resampling.LANCZOS)


def compute_calm_one_by_one_schedule(walk_data: dict):
    """
    Strictly solo, unhurried one-by-one schedule alternating Left <-> Right across the sky:
      - Only ONE memory card is ever shown at a time (0.14s calm breath between handoffs).
      - Every memory gets 5.1s .. 7.6s of rock-steady reading time!
    """
    dur_clip = float(walk_data.get("duration_s", 300.0))
    tl = walk_data["timeline"]

    spans = {}
    peaks = {}
    for row in tl:
        t = row["t"]
        for mm in row.get("mems", []):
            mid = mm["id"]
            if mm["w"] >= 0.05 and 0.01 <= mm["u"] <= 0.99 and 0.03 <= mm["v"] <= 0.97:
                spans.setdefault(mid, []).append((t, mm["w"], mm["u"], mm["v"]))
                if mid not in peaks or mm["w"] > peaks[mid][0]:
                    peaks[mid] = (mm["w"], t, mm["u"], mm["v"])

    vis_mems = [
        m for m in walk_data["memories"]
        if m["id"] in spans and spans[m["id"]][0][0] <= dur_clip - 3.5
    ]
    if dur_clip <= 65.0:
        vis_mems = [m for m in vis_mems if m["canto"] in (1, 2)]

    ordered = sorted(vis_mems, key=lambda m: (m["canto"], peaks[m["id"]][1], spans[m["id"]][-1][0]))
    n = len(ordered)

    ideal_durs = []
    targets = []
    lo_bounds = []
    hi_bounds = []
    end_cap = (dur_clip - 0.7) if dur_clip <= 65.0 else min(dur_clip - 8.5, 291.5)

    for m in ordered:
        mid = m["id"]
        tlen = len(m.get("text", ""))
        nimg = len([x for x in m.get("media", []) if x.get("type") == "image"])
        dur = 5.0 + min(2.8, tlen / 190.0) + (0.45 if nimg >= 2 else 0.0)
        v0 = max(0.7, spans[mid][0][0] - 2.5)
        v1 = min(end_cap, spans[mid][-1][0] + 13.5)
        tp = min(end_cap - dur * 0.5, peaks[mid][1])
        ideal_durs.append(dur)
        targets.append(clamp(tp, v0 + dur * 0.5, max(v0 + dur * 0.5, v1 - dur * 0.5)))
        lo_bounds.append(v0)
        hi_bounds.append(max(v0 + 4.8, v1))

    eff_durs = list(ideal_durs)
    centers = list(targets)
    handoff_gap = 0.14  # Strictly 1-by-1 solo: 0.14s calm breath as one card fades out before the next blooms!

    for _ in range(650):
        for i in range(n):
            centers[i] += 0.045 * (targets[i] - centers[i])
            if eff_durs[i] < ideal_durs[i]:
                eff_durs[i] = min(ideal_durs[i], eff_durs[i] + 0.012)
        for i in range(n - 1):
            req = 0.5 * (eff_durs[i] + eff_durs[i + 1]) + handoff_gap
            diff = centers[i + 1] - centers[i]
            if diff < req:
                push = 0.5 * (req - diff)
                centers[i] -= push
                centers[i + 1] += push
                if req - diff > 0.05:
                    if eff_durs[i] > 4.85:
                        eff_durs[i] -= 0.018
                    if eff_durs[i + 1] > 4.85:
                        eff_durs[i + 1] -= 0.018
        for i in range(n):
            eff_durs[i] = min(eff_durs[i], max(4.6, hi_bounds[i] - lo_bounds[i]))
            centers[i] = clamp(centers[i], lo_bounds[i] + 0.5 * eff_durs[i], hi_bounds[i] - 0.5 * eff_durs[i])

    for i in range(1, n):
        lo = centers[i - 1] + 0.5 * (eff_durs[i - 1] + eff_durs[i]) + handoff_gap
        if centers[i] < lo:
            centers[i] = lo

    sched = {}
    prev_side = None
    for i, m in enumerate(ordered):
        mid = m["id"]
        t0 = centers[i] - 0.5 * eff_durs[i]
        t1 = min(end_cap, centers[i] + 0.5 * eff_durs[i])
        u_peak = peaks[mid][2]
        natural_side = "left" if u_peak < 0.50 else "right"
        if prev_side == natural_side:
            side = "right" if prev_side == "left" else "left"
        else:
            side = natural_side
        prev_side = side
        sched[mid] = {"t0": t0, "t1": t1, "t_mid": 0.5 * (t0 + t1), "side": side, "order_idx": i}
    return sched


TERRAIN_Z_NODES = [
    # (z_center, lon, lat, elev_ft, label, short_name)
    (0.0,   -101.86, 35.20, 3655, "Amarillo Plains, Texas",               "Amarillo, TX"),
    (-6.2,  -101.79, 35.19, 3645, "Amarillo & Palo Duro Rim, TX",         "Amarillo, TX"),
    (-9.6,  -102.35, 35.08, 3820, "Caprock Escarpment, TX",               "Caprock Rim, TX"),
    (-13.0, -103.73, 35.17, 4090, "Route 66 · Tucumcari, New Mexico",     "Tucumcari, NM"),
    (-17.2, -107.57, 37.38, 7890, "Vallecito Pines · San Juan Range, CO", "Vallecito, CO"),
    (-24.0, -104.85, 39.02, 6950, "Front Range Foothills, Colorado",      "Colorado Foothills"),
    (-32.0,    2.35, 48.85,  280, "Paris & Haute-Loire, France",          "France"),
    (-35.6,   12.49, 41.89,  320, "Tuscany & Rome, Italy",                "Italy"),
    (-44.5, -107.67, 38.02, 11200, "San Juan Elk Country, Colorado",      "San Juan Mtns, CO"),
    (-54.5, -106.05, 39.48, 11600, "Tenmile Alpine Ridge, Colorado",      "Breckenridge, CO"),
    (-65.3, -105.22, 39.67,  7881, "Red Rocks & Mount Morrison, CO",      "Mount Morrison, CO"),
]


def terrain_info_at(walk_data: dict, t: float) -> dict:
    """
    Ground-truth landscape in the midground center of the camera's sightline (`z_mid = z_danny - 2.5 km`),
    consistent across both the 60s HQ review clip and the full 300s walk!
    """
    full_s = float(walk_data.get("full_walk_s", 300.0))
    u = clamp(t / max(1.0, full_s))
    u_smooth = 0.04 * (u * u * (3.0 - 2.0 * u)) + 0.96 * u
    z_danny = -65.3 * u_smooth
    z_mid = clamp(z_danny - 2.45, -65.3, 0.0)

    # Nearest region label + smoothly interpolated elevation & coordinates
    best = min(TERRAIN_Z_NODES, key=lambda nd: abs(nd[0] - z_mid))
    # Linearly interpolate elevation between bracketing nodes
    ordered = sorted(TERRAIN_Z_NODES, key=lambda nd: nd[0])  # ascending z (-65.3 .. 0.0)
    elev = best[3]
    for i in range(len(ordered) - 1):
        z0, _, _, e0, _, _ = ordered[i]
        z1, _, _, e1, _, _ = ordered[i + 1]
        if z0 <= z_mid <= z1:
            frac = (z_mid - z0) / max(1e-6, z1 - z0)
            elev = int(round((e0 + frac * (e1 - e0)) / 10.0) * 10)
            break

    return {
        "lon": best[1],
        "lat": best[2],
        "elev_ft": elev,
        "label": best[4],
        "short_name": best[5],
    }


def sample_timeline(walk_data: dict, t: float, W: int, H: int):
    tl = walk_data["timeline"]
    dur = float(walk_data.get("duration_s", 300.0))
    tc = clamp(t, 0.0, dur)
    f_idx = (tc / max(1e-3, dur)) * (len(tl) - 1)
    i0 = max(0, min(len(tl) - 2, int(math.floor(f_idx))))
    alpha = f_idx - i0
    a, b = tl[i0], tl[i0 + 1]

    du = a["danny"][0] * (1 - alpha) + b["danny"][0] * alpha
    dv = a["danny"][1] * (1 - alpha) + b["danny"][1] * alpha

    def interp_items(key):
        ma_map = {x["id"]: x for x in a.get(key, [])}
        mb_map = {x["id"]: x for x in b.get(key, [])}
        out = {}
        for k in set(ma_map.keys()) | set(mb_map.keys()):
            xa, xb = ma_map.get(k), mb_map.get(k)
            u = xa["u"] * (1 - alpha) + xb["u"] * alpha if (xa and xb) else (xa or xb)["u"]
            v = xa["v"] * (1 - alpha) + xb["v"] * alpha if (xa and xb) else (xa or xb)["v"]
            w = (xa["w"] if xa else 0.0) * (1 - alpha) + (xb["w"] if xb else 0.0) * alpha
            out[k] = {"id": k, "u": u, "v": v, "w": w}
        return out

    return (du * W, dv * H), interp_items("mems"), interp_items("wpts")


def paste_rgba_at(dest_rgba: Image.Image, sprite: Image.Image, cx: float, cy: float, opacity: float):
    if opacity <= 0.008:
        return None
    im = sprite
    if opacity < 0.995:
        r, g, b, a = im.split()
        a = a.point(lambda v: int(v * opacity))
        im = Image.merge("RGBA", (r, g, b, a))
    x0 = int(round(cx - im.width * 0.5))
    y0 = int(round(cy - im.height * 0.5))
    dest_rgba.alpha_composite(im, (x0, y0))
    return (x0, y0, x0 + im.width, y0 + im.height)


def draw_gossamer_tether(draw: ImageDraw.ImageDraw, x_top, y_top, x_bot, y_bot, alpha: float, U: float):
    a_i = int(clamp(alpha) * 255)
    if a_i <= 4:
        return
    ctrl_x = x_top * 0.42 + x_bot * 0.58
    ctrl_y = y_top * 0.55 + y_bot * 0.45 + 18.0 * U
    steps = 24
    pts = []
    for k in range(steps + 1):
        u = k / steps
        px = (1 - u) ** 2 * x_top + 2 * (1 - u) * u * ctrl_x + u ** 2 * x_bot
        py = (1 - u) ** 2 * y_top + 2 * (1 - u) * u * ctrl_y + u ** 2 * y_bot
        pts.append((px, py))

    w_glow = max(2, int(round(3.4 * U)))
    w_core = max(1, int(round(1.3 * U)))
    draw.line(pts, fill=(43, 105, 255, int(a_i * 0.32)), width=w_glow)
    draw.line(pts, fill=(182, 210, 255, int(a_i * 0.76)), width=w_core)
    r = 4.2 * U
    draw.ellipse((x_bot - r, y_bot - r, x_bot + r, y_bot + r), outline=(192, 218, 255, int(a_i * 0.85)), width=max(1, int(round(1.4 * U))))


class WalkCompositor:
    def __init__(self, walk_data: dict, width: int, height: int):
        self.walk_data = walk_data
        self.W = width
        self.H = height
        self.U = width / 1280.0
        self.cantos = walk_data["cantos"]

        with open(MEMORIES_JSON, "r", encoding="utf-8") as fm:
            raw_mems = {x["id"]: x for x in json.load(fm)["memories"]}
        for m in walk_data["memories"]:
            if not m.get("coords") and m["id"] in raw_mems:
                m["coords"] = raw_mems[m["id"]].get("coords", [-101.83, 35.20])

        with open(LOCATOR_JSON, "r", encoding="utf-8") as fl:
            self.locator_db = json.load(fl)

        self.mem_map = {m["id"]: m for m in walk_data["memories"]}
        self.wpt_map = {w["id"]: w for w in walk_data.get("waypoints", [])}
        self.sched = compute_calm_one_by_one_schedule(walk_data)

        print(f"[comp] Pre-rendering {len(self.sched)} calm solo 1-by-1 gallery frames + US/World maps ({width}x{height})...")
        self.hero_sprites = {}
        for mid, sl in self.sched.items():
            m = self.mem_map[mid]
            imgs = load_memory_images(m)
            t_ref = terrain_info_at(walk_data, sl["t_mid"])
            if len(imgs) >= 6:
                h_a = make_hero_sprite(m, imgs[:3], self.locator_db, t_ref, self.U)
                h_b = make_hero_sprite(m, imgs[3:6], self.locator_db, t_ref, self.U)
                self.hero_sprites[mid] = (h_a, h_b)
            else:
                h_a = make_hero_sprite(m, imgs, self.locator_db, t_ref, self.U)
                self.hero_sprites[mid] = (h_a, None)

        self.wpt_sprites = {wid: self._make_waypoint_signpost(w) for wid, w in self.wpt_map.items()}
        self.closing_card = self._make_closing_card()
        self._compass_cache = {}

    def _make_waypoint_signpost(self, wp: dict) -> Image.Image:
        SS = 2.0 * self.U
        f_lbl = load_font(FONT_SERIF_IT, 12.8 * SS)
        f_sub = load_font(FONT_MONO, 8.8 * SS)
        lbl = wp["label"]
        sub = wp["sub"].upper()
        dummy = ImageDraw.Draw(Image.new("RGBA", (12, 12)))
        w1 = dummy.textbbox((0, 0), lbl, font=f_lbl)[2]
        w2 = dummy.textbbox((0, 0), sub, font=f_sub)[2]
        pw = int(round(max(w1, w2) + 32 * SS))
        ph = int(round(40 * SS))
        im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        rad = int(round(9 * SS))
        d.rounded_rectangle(
            (2 * SS, 2 * SS, pw - 2 * SS, ph - 3 * SS),
            radius=rad,
            fill=(5, 12, 30, 192),
            outline=(98, 150, 255, 92),
            width=max(1, int(round(1.1 * SS))),
        )

        cx_d, cy_d, r_d = 13 * SS, 14 * SS, 4.2 * SS
        d.polygon([(cx_d, cy_d - r_d), (cx_d + r_d, cy_d), (cx_d, cy_d + r_d), (cx_d - r_d, cy_d)], fill=(86, 148, 255, 248))
        d.text((23 * SS, 5 * SS), lbl, font=f_lbl, fill=(250, 246, 238, 244))
        d.text((23 * SS, 22 * SS), sub, font=f_sub, fill=(156, 194, 255, 224))
        return im.resize((int(round(pw / 2.0)), int(round(ph / 2.0))), Image.Resampling.LANCZOS)

    def _get_compass_bar(self, canto: dict, terrain: dict, progress_bucket: int) -> Image.Image:
        key = (canto["idx"], terrain["label"], terrain["elev_ft"], progress_bucket)
        if key in self._compass_cache:
            return self._compass_cache[key]
        SS = 2.0 * self.U
        f_top = load_font(FONT_MONO, 9.6 * SS)
        f_bot = load_font(FONT_SERIF_IT, 13.0 * SS)
        f_yr = load_font(FONT_MONO, 8.2 * SS)
        top_txt = f"TRAIL LANDSCAPE: {terrain['label'].upper()}  ·  {terrain['elev_ft']:,} FT"
        bot_txt = f"Canto {canto['roman']} ({canto['era']})  ·  {canto['title']}"
        dummy = ImageDraw.Draw(Image.new("RGBA", (12, 12)))
        w1 = dummy.textbbox((0, 0), top_txt, font=f_top)[2]
        w2 = dummy.textbbox((0, 0), bot_txt, font=f_bot)[2]
        pw = int(round(max(w1, w2) + 36 * SS))
        ph = int(round(54 * SS))
        im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        rad = int(round(11 * SS))
        d.rounded_rectangle(
            (1 * SS, 1 * SS, pw - 2 * SS, ph - 2 * SS),
            radius=rad,
            fill=(5, 12, 30, 212),
            outline=(102, 154, 255, 108),
            width=max(1, int(round(1.3 * SS))),
        )

        # Glowing Klein-blue compass orb
        d.ellipse((11 * SS, 9 * SS, 18 * SS, 16 * SS), fill=(52, 118, 255, 250), outline=(176, 208, 255, 235), width=max(1, int(round(1.0 * SS))))
        d.text((24 * SS, 6 * SS), top_txt, font=f_top, fill=(158, 198, 255, 245))
        d.text((24 * SS, 20 * SS), bot_txt, font=f_bot, fill=(248, 244, 236, 242))

        # Subtle 1956 ───●─── 2026 chronological trail progress bar at bottom of pill
        u_prog = clamp(progress_bucket / 100.0)
        d.text((24 * SS, 38 * SS), "1956", font=f_yr, fill=(138, 174, 236, 195))
        yr_end_x = pw - 16 * SS
        w_2026 = dummy.textbbox((0, 0), "2026", font=f_yr)[2]
        d.text((yr_end_x - w_2026, 38 * SS), "2026", font=f_yr, fill=(138, 174, 236, 195))
        bar_x0 = 52 * SS
        bar_x1 = yr_end_x - w_2026 - 8 * SS
        bar_y = 43 * SS
        if bar_x1 > bar_x0 + 20 * SS:
            d.line([(bar_x0, bar_y), (bar_x1, bar_y)], fill=(96, 140, 224, 92), width=max(1, int(round(1.4 * SS))))
            # 7 tiny ticks for the 7 Cantos
            for k_tick in range(7):
                tx_i = bar_x0 + (bar_x1 - bar_x0) * (k_tick / 6.0)
                d.ellipse((tx_i - 1.4 * SS, bar_y - 1.4 * SS, tx_i + 1.4 * SS, bar_y + 1.4 * SS), fill=(130, 170, 245, 140))
            bx_p = bar_x0 + (bar_x1 - bar_x0) * u_prog
            d.line([(bar_x0, bar_y), (bx_p, bar_y)], fill=(78, 142, 255, 228), width=max(1, int(round(1.8 * SS))))
            d.ellipse((bx_p - 3.2 * SS, bar_y - 3.2 * SS, bx_p + 3.2 * SS, bar_y + 3.2 * SS), fill=(255, 248, 232, 255), outline=(56, 126, 255, 255), width=max(1, int(round(1.2 * SS))))

        out = im.resize((int(round(pw / 2.0)), int(round(ph / 2.0))), Image.Resampling.LANCZOS)
        self._compass_cache[key] = out
        return out

    def _make_closing_card(self) -> Image.Image:
        SS = 2.0 * self.U
        cw, ch = int(round(560 * SS)), int(round(160 * SS))
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        f1 = load_font(FONT_MONO, 13 * SS)
        f2 = load_font(FONT_SERIF, 34 * SS)
        f3 = load_font(FONT_SERIF_IT, 16 * SS)
        for txt, fnt, yy, col in [
            ("1956 — 2026  ·  SEVENTY YEARS", f1, 24 * SS, (162, 196, 255, 240)),
            ("Happy 70th Birthday, Danny", f2, 54 * SS, (255, 251, 244, 255)),
            ("Amarillo  ·  Colorado  ·  The World", f3, 108 * SS, (245, 235, 220, 225)),
        ]:
            bb = d.textbbox((0, 0), txt, font=fnt)
            tw = bb[2] - bb[0]
            d.text(((cw - tw) // 2 + 2, yy + 3), txt, font=fnt, fill=(8, 14, 34, 165))
            d.text(((cw - tw) // 2, yy), txt, font=fnt, fill=col)
        return im.resize((int(round(cw / 2.0)), int(round(ch / 2.0))), Image.Resampling.LANCZOS)

    def composite_frame(self, base_rgb: Image.Image, t: float) -> Image.Image:
        W, H, U = self.W, self.H, self.U
        dur_clip = float(self.walk_data.get("duration_s", 300.0))
        full_walk_s = float(self.walk_data.get("full_walk_s", 300.0))
        frame = base_rgb.convert("RGBA")
        (dx, dy), active_mems, active_wpts = sample_timeline(self.walk_data, t, W, H)

        active_heroes = []
        for mid, sl in self.sched.items():
            if sl["t0"] <= t <= sl["t1"]:
                active_heroes.append((mid, sl))
        active_heroes.sort(key=lambda x: x[1]["order_idx"])

        hero_boxes = []
        tether_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td = ImageDraw.Draw(tether_layer)

        # Compute stationary Hero Frame position(s) first so ground signpost avoids them cleanly
        hero_renders = []
        for mid, sl in active_heroes:
            h_a, h_b = self.hero_sprites[mid]
            t0, t1 = sl["t0"], sl["t1"]
            spr = h_b if (h_b is not None and (t - t0) > 0.52 * (t1 - t0)) else h_a

            op_in = smoothstep(0.0, 0.72, t - t0)
            op_out = smoothstep(0.0, 0.72, t1 - t)
            op = op_in * op_out

            margin_x = 36.0 * U
            pad_allow = 22.0 * U
            cx = (margin_x + spr.width * 0.5 - pad_allow) if sl["side"] == "left" else (W - margin_x - spr.width * 0.5 + pad_allow)
            cy = (34.0 * U + spr.height * 0.5 - 10.0 * U) + (1.0 - op_in) * (3.5 * U)

            hero_boxes.append((cx - spr.width * 0.5 - 12 * U, cy - spr.height * 0.5 - 8 * U, cx + spr.width * 0.5 + 12 * U, cy + spr.height * 0.5 + 12 * U))
            hero_renders.append((mid, spr, cx, cy, op))

        # 1) Ground-Anchored Physical Landmark Signpost — filter non-overlapping candidates FIRST!
        best_wp_choice = None
        for wid, wp_p in active_wpts.items():
            if wid not in self.wpt_sprites:
                continue
            if wp_p["w"] < 0.22 or not (0.10 <= wp_p["u"] <= 0.90 and 0.36 <= wp_p["v"] <= 0.80):
                continue
            wspr = self.wpt_sprites[wid]
            wx, wy = wp_p["u"] * W, wp_p["v"] * H
            wcy = wy - wspr.height * 0.5 - 14.0 * U
            wbox = (wx - wspr.width * 0.5, wcy - wspr.height * 0.5, wx + wspr.width * 0.5, wcy + wspr.height * 0.5)
            overlaps_hero = any(
                not (wbox[2] < hb[0] or wbox[0] > hb[2] or wbox[3] < hb[1] or wbox[1] > hb[3])
                for hb in hero_boxes
            )
            near_danny = math.hypot(wx - dx, wy - dy) < 105.0 * U
            near_compass = (wbox[0] < 430 * U and wbox[3] > H - 88 * U)
            if not overlaps_hero and not near_danny and not near_compass:
                if best_wp_choice is None or wp_p["w"] > best_wp_choice[0]["w"]:
                    best_wp_choice = (wp_p, wspr, wx, wy, wcy)

        if best_wp_choice is not None:
            wp_p, wspr, wx, wy, wcy = best_wp_choice
            w_op = smoothstep(0.22, 0.52, wp_p["w"]) * 0.84
            td.line([(wx, wcy + wspr.height * 0.46), (wx, wy)], fill=(128, 176, 255, int(w_op * 175)), width=max(1, int(round(1.3 * U))))
            td.ellipse((wx - 2.6 * U, wy - 2.6 * U, wx + 2.6 * U, wy + 2.6 * U), fill=(166, 204, 255, int(w_op * 215)))
            paste_rgba_at(tether_layer, wspr, wx, wcy, w_op)

        # 2) Single delicate gossamer tether from stationary Hero Frame down to its ONE glowing 3D lantern
        for mid, spr, cx, cy, op in hero_renders:
            if mid in active_mems:
                bm = active_mems[mid]
                bx, by = bm["u"] * W, bm["v"] * H
                vis_fade = (
                    smoothstep(0.04, 0.14, bm["u"])
                    * (1.0 - smoothstep(0.86, 0.96, bm["u"]))
                    * smoothstep(0.14, 0.24, bm["v"])
                    * (1.0 - smoothstep(0.82, 0.93, bm["v"]))
                    * smoothstep(0.06, 0.22, bm["w"])
                )
                if vis_fade > 0.02:
                    bottom_y = cy + spr.height * 0.5 - 20.0 * U
                    anchor_x = clamp(bx, cx - spr.width * 0.28, cx + spr.width * 0.28)
                    draw_gossamer_tether(td, anchor_x, bottom_y, bx, by, op * vis_fade * 0.62, U)

        frame = Image.alpha_composite(frame, tether_layer)

        # 3) Render stationary Hero Memory Frame
        for mid, spr, cx, cy, op in hero_renders:
            paste_rgba_at(frame, spr, cx, cy, op)

        # 4) Frosted Obsidian-Navy Trail Landscape & Canto Progress Compass (Bottom-Left)
        t_info = terrain_info_at(self.walk_data, t)
        if active_heroes:
            c_idx = self.mem_map[active_heroes[-1][0]]["canto"]
            canto = next((c for c in self.cantos if c["idx"] == c_idx), self.cantos[-1])
        else:
            canto = next((c for c in self.cantos if c["t0"] <= t <= c["t1"]), self.cantos[-1])
        prog_bucket = int(round(clamp(t / max(1.0, full_walk_s)) * 100.0))
        comp_bar = self._get_compass_bar(canto, t_info, prog_bucket)
        end_fade_start = dur_clip - 2.4 if dur_clip <= 65.0 else 293.5
        end_fade_end = dur_clip - 0.3 if dur_clip <= 65.0 else 298.0
        comp_op = smoothstep(0.3, 1.8, t) * (1.0 - smoothstep(end_fade_start, end_fade_end, t)) * 0.95
        paste_rgba_at(frame, comp_bar, 24.0 * U + comp_bar.width * 0.5, H - 18.0 * U - comp_bar.height * 0.5, comp_op)

        # 5) Closing dedication on full 5-minute film
        if dur_clip > 200.0 and t >= 290.2:
            c_op = smoothstep(290.2, 292.4, t) * (1.0 - smoothstep(297.6, 299.8, t))
            paste_rgba_at(frame, self.closing_card, W * 0.5, H * 0.21, c_op)

        return frame.convert("RGB")


def decode_single_frame(mp4_path: Path, t_sec: float, W: int, H: int) -> Image.Image:
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{t_sec:.3f}",
        "-i", str(mp4_path),
        "-frames:v", "1",
        "-vf", f"scale={W}:{H}:flags=lanczos",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    raw = subprocess.check_output(cmd)
    return Image.frombytes("RGB", (W, H), raw)


def render_contact_sheet(comp: WalkCompositor, base_mp4: Path, out_path: Path, sample_times: list):
    W, H = comp.W, comp.H
    cols = 3
    rows = math.ceil(len(sample_times) / cols)
    pad = 10
    sheet = Image.new("RGB", (cols * W + (cols + 1) * pad, rows * H + (rows + 1) * pad), (8, 12, 26))
    for i, ts in enumerate(sample_times):
        base = decode_single_frame(base_mp4, ts, W, H)
        im = comp.composite_frame(base, ts)
        r, c = divmod(i, cols)
        sheet.paste(im, (pad + c * (W + pad), pad + r * (H + pad)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG")
    print(f"[comp] Wrote contact sheet -> {out_path}")


def render_video(comp: WalkCompositor, base_mp4: Path, out_mp4: Path, fps: int, crf: int = 19):
    W, H = comp.W, comp.H
    dur = float(comp.walk_data.get("duration_s", 300.0))
    total_frames = int(round(dur * fps))
    print(f"[comp] Streaming {total_frames} frames @ {fps} fps ({W}x{H}) -> {out_mp4} ...")

    dec_cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(base_mp4),
        "-vf", f"scale={W}:{H}:flags=lanczos",
        "-r", str(fps),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    enc_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_mp4),
    ]

    dec_proc = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE)
    enc_proc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)

    frame_bytes = W * H * 3
    idx = 0
    t0_wall = time.time()
    log_step = max(120, total_frames // 6)

    while True:
        buf = dec_proc.stdout.read(frame_bytes)
        if not buf or len(buf) < frame_bytes:
            break
        t_sec = idx / float(fps)
        base_img = Image.frombytes("RGB", (W, H), buf)
        out_img = comp.composite_frame(base_img, t_sec)
        enc_proc.stdin.write(out_img.tobytes())
        idx += 1
        if idx % log_step == 0 or idx == total_frames:
            el = time.time() - t0_wall
            print(f"  [{100.0 * idx / max(1, total_frames):5.1f}%] frame {idx}/{total_frames} (t={t_sec:5.1f}s) | {idx / max(0.01, el):.1f} fps | elapsed {el:.1f}s", flush=True)

    dec_proc.stdout.close()
    dec_proc.wait()
    enc_proc.stdin.close()
    enc_proc.wait()
    print(f"[comp] Done! Wrote -> {out_mp4}")


def main():
    hq_min1 = "--hq-min1" in sys.argv
    sheet_only = "--sheet-only" in sys.argv

    if hq_min1:
        walk_json = ROOT / "data" / "sonicray_walk_hq_min1.json"
        base_mp4 = ROOT / "media" / "sonicray_walk_hq_min1_base.mp4"
        out_mp4 = ROOT / "media" / "sonicray_walk_hq_min1.mp4"
        sheet_out = (SCRATCH_DIR / "walk_hq_min1_comp_sheet.png") if sheet_only else (ROOT / "media" / "sonicray_walk_hq_min1_sheet.png")
        W, H, fps, crf = 1920, 1080, 24, 19
        # Sample Aunt Elsie's Farm (PA -> TX), Amarillo Ballfields, Tascosa High, Tucumcari Route 66, Vallecito CO, Fleetwood Park!
        sample_times = [9.0, 15.0, 26.5, 43.0, 49.0, 55.5]
    else:
        walk_json = ROOT / "data" / "sonicray_walk.json"
        base_mp4 = ROOT / "media" / "sonicray_walk_draft_v2.mp4"
        out_mp4 = ROOT / "media" / "sonicray_walk_with_memories.mp4"
        sheet_out = (SCRATCH_DIR / "walk_composited_sheet.png") if sheet_only else (ROOT / "media" / "sonicray_walk_memories_sheet.png")
        W, H, fps, crf = 1280, 720, 20, 22
        sample_times = [9.0, 26.5, 43.0, 90.0, 129.0, 143.2, 189.2, 240.0, 283.6]

    with open(walk_json, "r", encoding="utf-8") as f:
        walk_data = json.load(f)

    comp = WalkCompositor(walk_data, W, H)
    render_contact_sheet(comp, base_mp4, sheet_out, sample_times)
    if not sheet_only:
        render_video(comp, base_mp4, out_mp4, fps=fps, crf=crf)


if __name__ == "__main__":
    main()
