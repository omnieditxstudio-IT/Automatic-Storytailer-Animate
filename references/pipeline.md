# The pipeline, stage by stage

All paths are relative to `--project`. Every stage is idempotent; `run.py` re-uses what is still fresh.

## 1. ingest.py
```
python scripts/ingest.py --project my-film --voice v.mp3 --script script.md [--model tiny.en] [--no-whisper]
```
- Converts the voice to `audio/narration.m4a` (48 kHz stereo, 256 kbps).
- Parses the script: markdown headings -> sections; blank-line separated paragraphs -> sentences; sentences -> chunks of <= 9 words / <= 64 chars preferring `,;:` breaks. Each chunk gets an `id` in speaking order; `take` is the nearest preceding heading.
- faster-whisper (`word_timestamps=True`, VAD on) produces words; a greedy fuzzy monotonic matcher (difflib >= 0.82, prefix containment >= 0.92, gaps up to 12 transcript words) assigns each line its first/last matched transcript timestamp. Lines below a 0.45 match fraction are linearly interpolated between strong neighbours. Result is forced monotonic with >= 0.45 s per line.
- `audio/timing.json` (engine schema: `total_duration`, `lead_in`, `tail_out`, `segments[] {id, scene, caption, vo, start, end, duration}`) and `script.json` (`title`, `takes[]`) are written.
- Weak-line count and per-line durations are printed; > 12 s or < 0.55 s lines are flagged for review.

Without whisper (or on failure), speech spans come from `ffmpeg silencedetect=noise=-34dB:d=0.30` and lines are placed by syllable weight.

## 2. director.py
```
python scripts/director.py --project my-film [--photos auto|existing|none] [--seed 7]
```
- Reads timing; each line gets a layout from keyword rules (see layout-catalogue.md), a kicker (the section heading, digit prefixes stripped), a headline (content words, function words removed), 3 `points`, a `number` (digits or number-words), an `icon`, and an `ink` colour.
- Lines are grouped into blocks of <= 4 / <= 9.2 s / sentence-ends; blocks alternate board/photo (start and end blocks are board). Block world origins advance by 30000 px.
- `plan.json`: `blocks[] {index, style, start, end, beats, x0, x_last, photo, query, f0, f1}`, fps 30. `beats.json` holds the per-beat record. `beats.md` is the human table.
- Photo queries are mapped from visual keywords in the line (server -> "security operations center", code -> "computer source code screen", ...); every photo query appearing in photo blocks is assigned the same photo id so reused subjects stay continuous.

## 3. fetch_photos.py (only for `--photos auto`)
- For each photo id, queries Wikimedia Commons (`generator=search`, namespace 6). Keeps only JPEG/PNG >= 1000x600, free licence (PD/CC0/CC BY/CC BY-SA), landscape-ish, penalising maps/diagrams/logos/covers/screenshots. If a query fails it retries shorter queries, then gives up and the block renders a card.
- Writes `photos.json`, downloads via the sibling `fetch_commons.py get` (fills file/credit/licence/source/date, refuses non-free licences unless you pass `--allow-nonfree` yourself), grades with `prep_assets.py --grade bw` (can override with `--grade natural`), credits and writes `credits.md`.

## 4. make_scene.py
Writes `scene.py` that imports `storyboard.build_film(doc)`. Never edit it by hand; re-run the script if the skill moves. The storyboard reads `beats.json` and `plan.json` **at render time**, so plan edits need no scene regeneration.

## 5. make_cues.py
Writes `sfx_cues.json` (both at project root, which `build_sfx.py` expects, and under `audio/`). See references/sound.md.

## 6. render_blocks.py
Calls the sibling `render.py` once per block with `--t0/--t1` at `round(start*30)/30` .. `round(end*30)/30`. Skips blocks whose `out/blocks/bNNN.mp4` is newer than scene/beats/plan and has the right frame count (`ffprobe -count_frames`).

## 7. stitch.py
Trims every block to its exact frame count and joins with the `concat` **filter** re-encoding once (`libx264`, `--crf`, `yuv420p`, `faststart`). The concat demuxer with `-c copy` is never used: it drops packets at joins and produces one-frame holes.

## 8. captions_burn.py
- Chunks lines into <= 7-word chunks (breaking at sentence punctuation), reusing the engine's clock-shares (`captions.words_with_times`).
- Draws in screen space after the film finish: seeded candy ink, entrance (rise/pop/slide/tilt/fade/wipe/stagger) and exit (fade/drop/riseout/shrink), four-radius blurred bloom halo + rainbow-gradient sweep with a white neon-tube stroke on the spoken word, uppercase `cond` face, 47/1920 of frame width, wraps to two lines above 74% width, last baseline at `H - 6k - 0.22*size`, gradient from `0.74 H`.
- Parallel decoding/encoding with `multiprocessing spawn`; chunks are joined with the concat filter. Writes `<out>.srt` alongside.

## 9. audio_finish.py
- `audio/voice_padded.m4a` = voice + silence to film duration (fixes the mix's `duration=first` cut).
- Score: the bundled `assets/music/Crypto.mp3` (Kevin MacLeod, CC BY 4.0) looped with `-stream_loop -1` if shorter than the film.
- `build_sfx.py` synthesises the effects bus; `mix_soundtrack.py` mixes at `--music-db -18 --sfx-db -19 --duck-ratio 4 --duck-threshold 0.025 --music-eq-dip 4 --lufs -15`.
- Muxes picture + mix and reports final size/duration/streams.

## 10. qa.py
See SKILL.md "QA gates". Exit code 0 = finished; 1 = do not watch it yet.

## 11. Production cache (E:\Storyteller catche files)

Every heavy stage writes through the shared production cache (override with `STORYTELLER_CACHE`). Keys are content hashes, so a cache hit is an exact rebuild of the same artifact. All cache I/O lives in `paths.py` (`cache_root`, `cache_get`/`cache_put`/`cache_restore`, `file_sig`, `json_sig`).

| Folder | Written by | Key (sha256 of) | Restored when |
|---|---|---|---|
| `whisper/` | ingest.py | voice file + model + device | same voice + model re-aligned |
| `commons_search/` | fetch_photos.py | query + limit | same query searched |
| `commons_files/` | fetch_photos.py | Commons title (+`.credit.json` sidecar) | same title downloaded |
| `blocks/` | render_blocks.py | scene.py + beats.json + block geometry + size + CRF | identical block |
| `silent/` | stitch.py | block file hashes + CRF + fps | identical block set |
| `captioned/` | captions_burn.py | stitched video + timing.json + captions_burn.py itself + CRF | identical caption inputs |
| `sfx/` | audio_finish.py | sfx_cues.json + build_sfx.py | identical cue sheet |
| `music/` | audio_finish.py | score file + film length | identical bed needed |
| `mix/` | audio_finish.py | narration + cues + music + levels + LUFS + duration | identical mix inputs |

Layout is sorted and self-documenting: per-kind folders, `<label>-<hash12>.<ext>` filenames (e.g. `b001-photo-93d415aeef74.mp4`), `index.jsonl` (one JSON line per add: time/kind/key/label/file/bytes), `README.txt` at the root, and `cache_report()` prints per-folder counts/MB after a full run (and in `run.py` at the end). Deleting the cache is always safe; misses just rebuild. Legacy unlabelled cache files are still served. The cache layer itself is Python (I/O-bound work; adding Node/TS spawns would cost more than it saves, and the whole skill is Python).

## plan.json schema
```
{ "title": str, "fps": 30, "duration": sec, "blocks": [
    { "index": int, "style": "board"|"photo",
      "start": sec, "end": sec, "f0": int, "f1": int,
      "beats": [beat ids], "x0": world px, "x_last": world px,
      "photo": "P01"|null, "query": str|null } ] }
```

## beats.json schema
```
{ "title": str, "fps": 30, "duration": sec, "beats": [
    { "id", "start", "end", "caption", "spoken", "block", "style",
      "layout", "kicker", "headline", "sub", "points": [<=3 str],
      "number": str, "icon": str, "ink": str,
      "photo": str|null, "query": str|null, "x": int, "y": int } ] }
```

## The render memory rule
Blocks render sequentially with `render.py`, one chunk pool per block. A 1080p block uses < 2 GB. If the machine is busy, pass `--workers 2` to `run.py`.
