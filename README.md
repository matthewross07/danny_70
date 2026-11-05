# Danny Ross · Seventy Years Across the Landscape

An interactive 3D terrain atlas and autorunning field-journal memory walk celebrating **Danny Ross’s 70th Birthday**—built both for recording a clean birthday tribute video and for hosting permanently as a standalone website on GitHub Pages.

## Local Preview

```bash
python3 -m http.server 8770
```
Then open <http://localhost:8770>.

## Controls & Recording Tips

- **`Space`** — Start, pause, or continue the memory walk
- **`←` / `→`** — Step to the previous or next trailhead stop
- **`C`** — Toggle **Cinema Mode** (hides all navigation chrome so you can screen-record a clean birthday video)
- **`M`** — Open/close the **Field Notes** drawer (`All Places & Memories`)
- **`Esc`** — Exit lightbox, drawer, Cinema Mode, or pull back to the full Earth atlas
- **Pace button** — Cycle between *Stroll*, *Unhurried*, and *Brisk* walking & reading speeds

## Updating Memories

1. **New Google Form / Sheet entries:**  
   Make sure Google Drive for Desktop has synced any newly uploaded photos, then run:
   ```bash
   python3 scripts/sync_sheet.py
   ```
   This fetches the live sheet, converts any new `.heic`/`.png`/`.mov` files into `media/`, geocodes new locations, fetches real-world elevations, and updates `data/memories.json`.

2. **Random texts or emails:**  
   Add entries to `data/extra_memories.json` (drop any accompanying photos into `media/`) and re-run `python3 scripts/sync_sheet.py`.
