---
name: automatic-storyteller-animate
description: Turns one voiceover file and one script file into a finished narrated cinematic film, automatically. No storyboarding by hand: it transcribes the voice, times every caption line, chooses a layout per line (blueprint whiteboard sketches with hand-drawn chalk, neon icons and wobbly strokes alternating with a dark evidence-wall of real Wikimedia Commons photos, documents and cards), renders each style block as its own clip, cuts them frame-exactly, burns bottom-flush neon captions, mixes word-synced sound effects at -19 dB with a ducked CC score at -18 dB, normalises to -15 LUFS and QA-checks frames, loudness and caption placement. Use for "make a film from this voice and script", "automatic storyteller animate", "turn my narration into a video", "video like the AI exploit agent film", "scripted narrated short from one audio file", or any request where the input is a voice file plus a script.
---

# Automatic storyteller animate

Give it a **voice file** and a **script**. It finishes the whole film: timing, layout, render, cuts, captions, sound, mix and QA. No manual storyboarding, no scene code, no editing timeline.

```
python scripts/run.py --project my-film --voice voice.mp3 --script script.md
```

That one command runs the full pipeline and leaves `my-film/out/FILM.mp4`, `my-film/out/FILM.srt` (beside `captioned.mp4`), `credits.md`, `beats.json`, `plan.json`, `beats.md`, review stills in `out/qa/` and all intermediates.

## Before you start — the prerequisite check (automatic)

Every run starts with `check_requirements.py`, before anything else. **If all available tools are installed, production continues immediately — no setup needed. If something is missing, it is downloaded/installed automatically, and then production continues.**

It checks, in order:

1. **Python 3.8+**
2. **Python packages** — numpy, skia-python, Pillow, faster-whisper — pip-installed automatically if missing
3. **ffmpeg + ffprobe** on PATH — auto-installed via `winget` (Windows), `brew` (macOS) or `apt-get` (Linux) if missing
4. **cinematic-film** next to this skill (or `CINEMATIC_SCRIPTS=<path to its scripts>`)

If everything is present: one line — `requirements: ok` — and the build starts. If a Python package can't install, the script prints the exact command to fix it and exits instead of starting a doomed build. If cinematic-film can't be found, same — you get exactly what's missing and what to set.

## What it makes (the look)

Two visual languages that **alternate hard every 3-10 seconds**, decided per block by the director:

- **Board** - a full-bleed blueprint sheet. The words appear as hand-drawn chalk typography on a dark blue grid, with sketch-rect callout boxes, wobbly strokes, scribble-code windows, checkmarks, dividers and **neon icons** (two glow passes + hot core) that are drawn in code.
- **Photo** - the night evidence wall from cinematic-film: real licensed Wikimedia Commons photos pinned with a drop shadow and pin, typeset paper documents, jittered highlight rules, glowing neon icons, all credited in `credits.md`.

Captions are bottom-centre and **flush to the bottom edge** (6 px at 720p, scaling with resolution), uppercase, one of nine seeded candy inks, eased entrance (rise/pop/slide/tilt/fade/wipe/stagger) and exit (fade/drop/riseout/shrink), three-pass bloom halo, a rainbow-gradient sweep on the spoken word (neon-tube white stroke). A gradient behind the band keeps them legible on anything. Text mirrors the voice exactly.

## Starting fresh vs. resuming

- **New project**: give it the voice and the script; the skill builds everything.
  ```
  python scripts/run.py --project my-film --voice voice.mp3 --script script.md
  ```
- **Resuming**: re-running on a project that already has `out/FILM.mp4` (and the plan/photos) re-verifies with QA only — nothing is re-downloaded or re-rendered. Add `--force` to rebuild from scratch.

## Inputs

- `--voice`: any audio file ffmpeg reads (mp3/wav/m4a...). Best results from a clean single-take narration. It is used as-is, only converted to 48 kHz stereo AAC.
- `--script`: `.md` / `.txt` / `.srt` / `.json`. Markdown headings become section kickers on screen; blank lines and paragraphs are split into sentences, then into caption chunks (<= 9 words / <= 64 chars). The text on screen is the text in the file, verbatim. `script.json` with `{"title": ..., "takes": [...]}` is honoured when present.

## Options

| Flag | Effect |
|---|---|
| `--size 1920x1080` | render size (default 1920x1080) |
| `--crf 16` | quality (lower = better; 16 film, 26 preview) |
| `--photos auto|existing|none` | fetch per block (Wikimedia Commons, free licences only) / reuse `photos.json` / no photos |
| `--music auto|none|file` | bundled Kevin MacLeod "Crypto" (CC BY 4.0) looped to film length / silent / your file |
| `--model tiny.en` | faster-whisper size for alignment (`base.en`/`small.en` are more accurate) |
| `--preview` | render only blocks 0-1 at 640x360 for a fast look |
| `--skip-render` | re-plan only (no rendering) |
  | `--workers WORKERS` | render + caption workers (0 = all cores minus one) |
  | `--force` | rebuild even if a finished `out/FILM.mp4` already exists |

## Performance & safety

- **Production cache** at `E:\Storyteller catche files` (override with `STORYTELLER_CACHE`). Every heavy artifact is cached under a content hash, so re-running or tweaking later stages only redoes what changed:

| Folder | What is cached | Key |
|---|---|---|
| `whisper/` | faster-whisper word timings | voice file + model + device |
| `commons_search/` | Commons search result sets | query + limit |
| `commons_files/` | downloaded Commons originals + credit sidecars | Commons title |
| `blocks/` | rendered style blocks | scene + beats + block geometry + size + CRF |
| `silent/` | stitched silent film | block files + CRF + fps |
| `captioned/` | captioned film + SRT | video + timing + caption code + CRF |
| `sfx/` | synthesized SFX bus | cue sheet + build_sfx.py |
| `music/` | looped score bed | score file + film length |
| `mix/` | finished audio mix | voice + cues + music + levels + LUFS |

  Files are named `<label>-<hash12>.<ext>` and sorted by kind (a `sort` listing reads naturally), with an append-only `index.jsonl` manifest and a `README.txt` at the root. Cache misses rebuild automatically; deleting the cache is always safe. A full re-run of unchanged stages is seconds (whisper/blocks/stitch/captions/sfx/mix all hit).
- Every block renders separately, then blocks are stitched with a frame-exact `concat` filter. Re-running after a script edit only re-renders blocks whose plan changed (`render_blocks.py` reuses fresh block files, plus the production cache as a second layer).
- 12 cores / plenty of RAM: use `--workers 6`. A 3-minute 1080p film is roughly 15-30 min.
- **Never render the final film without the user asking for it**: use `--preview` or a small `--size` first, show it, and only then produce `FILM.mp4` at full size.
- Whisper tiny.en is ~1x real time on CPU; use `--model base.en` if timings drift on long lines.

## What the director does

Each caption line becomes one **beat**. A beat gets exactly one layout chosen from its words:

| Layout | Trigger | Drawing |
|---|---|---|
| `title` / `end` | first 2 / last 2 lines | neon icon + big chalk title (title = title case of the line's content words) |
| `chain` | first/second/then/process/pipeline | 3 sketch boxes with arrows |
| `split` | before/after/versus/compared/instead | two labelled frames either side of a torn divider |
| `window` | code/script/terminal/agent/model/server | hand-drawn terminal window with scribble rows + highlighted line |
| `check` | protect/patch/secure/prevent/never | chalk checkmarks down a list |
| `stat` | any number | huge glowing numeral |
| `quote` | everything else / questions | chalk pull-quote |
| photo variants | every other block | `station` (photo + card), `doc` (paper doc + stamp), `stat` |

Consecutive lines (1-4, max ~9 s, cut at sentence ends) group into **blocks**; blocks alternate board/photo across the film. First and last blocks are always board.

## Files written

```
audio/narration.m4a   normalised voice
audio/timing.json     per-line start/end (engine schema)
script.json           takes in speaking order, id order preserved
beats.json            per-line: start/end/layout/kicker/headline/points/number/icon/ink/photo/x
plan.json             blocks (style, frame range, world x), fps, duration
beats.md              human table of the whole plan
sfx_cues.json         synthesised effects for build_sfx.py
photos.json           Commons picks with licence/credit/source
out/blocks/bNNN.mp4   one clip per style block
out/silent.mp4        stitched picture
out/captioned.mp4     + burned neon captions (+ .srt)
out/FILM.mp4          final, with mixed audio
out/qa/*.png          review stills
credits.md            image + music credits
```

## QA gates (`scripts/qa.py`, run automatically by run.py)

Fails the build on: frame-count mismatch vs `timing.total_duration * fps`, missing/!audio stream, loudness outside -15 +/- 1.5 LUFS, true peak > -0.8 dBTP, a caption chunk not visible, or a caption baseline more than 8.5 % of frame height above the bottom edge.

## Companion skills (how a production actually completes)

This skill is the dedicated orchestrator for the education/explainer film workflow ("video like the AI exploit agent film"). It drives **two companion skills** to finish a production, exactly as the previous films were made — you never call them directly; `run.py` and `qa.py` do. The rule is absolute: **never edit a companion skill — or any other project (e.g. `C:\remotion-build\dark-reality-explainer`) — to make this one work**; drive them as they ship. All orchestration logic, cache, QA and style decisions live here in this skill.

### 1. cinematic-film — the world, the photos, the sound (required, hard dependency)

Located next to this skill (override with `CINEMATIC_SCRIPTS=<path to its scripts dir>`). Called by:

| Script | Used by | What it does for this film |
|---|---|---|
| `prep_assets.py` | `prep` stage | grades the Commons photos into the black-and-white look (`--grade bw|sepia|natural`) and generates the board textures (cork, blueprint, night, slate, ...) |
| `fetch_commons.py` | `fetch_photos.py` | downloads the licensed originals (`get`), fills file/credit/licence, and writes `credits.md` (`credits`) |
| `render.py` | `render_blocks.py` | renders each style block with `--t0/--t1`; draws the board/photo world, the camera and every item per frame |
| `engine.py` | `storyboard.py`, every render | the world model: `Film`, camera keys, `Board`, `PaperDoc`, `StylePanel`, the spline camera |
| `captions.py` | `captions_burn.py` | the word clock (`words_with_times`) used to time the hot word |
| `build_sfx.py` | `audio_finish.py` | synthesises the effects bus from `sfx_cues.json` (no sample library to license) |
| `mix_soundtrack.py` | `audio_finish.py` | voice + SFX + score: `-19 dB` SFX, `-18 dB` music, 4:1 duck, `-15 LUFS / -1.5 dBTP` master |

Rules of engagement: do not edit its scripts for this skill — behaviour changes belong in `storyboard.py` / `render_blocks.py` / here. Its CLI contracts (`--t0/--t1`, `fetch_commons get|credits`, `mix_soundtrack --lufs`) are what the production cache hashes; if cinematic-film changes one, update the stage here and delete `E:\Storyteller catche files` so no stale hits survive.

### 2. remotion-studio — browser preview / steering (optional, review only)

`npx remotion studio` (open the printed URL; or `--no-open` and open the URL yourself).

Honest scope, so nobody wastes time: **Studio only previews Remotion compositions** — React components registered in a Remotion project. It cannot play this skill's completed master (`out/FILM.mp4` is a skia/ffmpeg render, not a Remotion project; neither was the AI-attack film). Use it when the deliverable also exists as a Remotion project and you want the preview-as-you-edit experience (or to steer a Remotion-based variant). To *review* this skill's own output, use `out/FILM.mp4` / `out/preview_captioned.mp4` plus the `out/qa/` stills — Studio has nothing to attach to.

### The production recipe (how all three skills complete a film, like last time)

1. **Voice + script** -> `run.py --preview` (2 blocks, 640x360, ~2 min). Check the look, the board/photo rhythm, caption size and bottom-flush, and that `qa.py` says PASS.
2. **Full plan** — ingest (whisper alignment) -> director (beats, layouts, style alternation) -> Commons photos (free licence, credits in `credits.md`) -> prep (bw grade) -> scene -> cues.
3. **Render** — every block separately at 1080p; reuse via the production cache on `E:\Storyteller catche files`.
4. **Finish** — stitch (concat filter) -> bottom-flush neon captions -> SFX `-19 dB` / score `-18 dB`, ducked, `-15 LUFS` master.
5. **Review** — `out/FILM.mp4` plays; `out/qa/` holds the stills. If a Remotion packaging/review step is wanted, open that Remotion project with `remotion studio` and verify it loads there.
6. **Deliver** — `FILM.mp4` + `FILM.srt` + `credits.md`. Upload/export happens outside this skill.

### SRT / distribution side of the production

After `qa PASS`: `out/captioned.srt` sits beside `out/captioned.mp4` (the finishing step can copy it next to `FILM.mp4`). For social variants (9:16 re-cuts, platform exports, thumbnail staging), use a distribution skill rather than re-rendering in this one — this skill produces the 16:9 master only.

## Requirements

See **Before you start — the prerequisite check** above: Python 3.8+, numpy, skia-python, Pillow, faster-whisper, ffmpeg/ffprobe on PATH, and the cinematic-film skill next to this one (override with `CINEMATIC_SCRIPTS`). The check runs automatically at the top of every run.

## Known limits

- Alignment uses whisper tiny.en by default; a mumbled take may drift within a line. Check `audio/timing.json` (weak-line warnings are printed) or pass `--model base.en`.
- Commons search matches filenames/descriptions; a very specific query can miss. Unmatched photo blocks fall back to a card, never to an invented photo.
- Music is looped, not re-composed. For a different mood drop any mp3 into the project and pass `--music path.mp3`.
- No lip-synced characters, no talking heads, no live action: this is a scripted animated short.

## See also

- `references/pipeline.md` - stage-by-stage internals and every file's schema
- `references/sound.md` - cue kinds, levels, music licence
- `references/layout-catalogue.md` - what each layout draws and when to force one
