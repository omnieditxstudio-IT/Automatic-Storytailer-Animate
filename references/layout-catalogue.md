# Layout catalogue

One layout per caption line. The director picks it from the line's words (`choose_layout` in `director.py`); you never place layouts by hand. Photo blocks draw the same beats in the night evidence-wall style (see SKILL.md).

## How a line is chosen

| Rule (first match wins, in order) | Layout |
|---|---|
| line index 0 or 1 | `title` |
| last two lines | `end` |
| `versus`, `vs.`, `compared`, `comparison`, `difference`, `changed`, `instead`, or `before` + `after` in the same line | `split` |
| `first`, `second`, `third`, `then`, `next`, `finally`, `step`, `steps`, `stage`, `pipeline`, `process`, `followed` | `chain` |
| `code`, `script`, `software`, `program`, `terminal`, `command`, `agent`, `model`, `algorithm`, `server` | `window` |
| `protect`, `prevent`, `secure`, `defense`/`defence`, `patch`, `fix`, `stop`, `block`, `never`, `no longer` | `check` |
| any number (digits or number-words one…hundred / thousand / million / billion) | `stat` |
| line ends with `?` | `quote` |
| everything else | cycles `quote / chain / stat / quote` by line index |

## What each one draws

| Layout | Board look | Photo look |
|---|---|---|
| `title` | neon icon above a huge chalk title (first lines of the film) | photo pinned + card with the line as headline |
| `end` | film title in chalk + `SOURCES IN CREDITS` | station with film-title card |
| `chain` | three wobbly sketch boxes joined by arrows, chalk step text | station (chain info in the card body) |
| `split` | two labelled chalk frames either side of a torn divider (real before/after halves) | station |
| `window` | hand-drawn terminal window: scribble code rows, highlighted line | paper `doc` with stamp |
| `check` | chalk check marks down a list of the line's content words | station |
| `stat` | one huge glowing numeral + supporting line | photo + big-number card |
| `quote` | chalk pull-quote with a large quote mark | station |

`check` lists only real words from the line; it never invents a checklist (no “SECURE / PATCHED / CLOSED” unless the line says it). `split` only triggers on genuine comparisons and draws the two halves as real comparison panels — no decorative “VS” stamp. `stat` strips trailing punctuation from the numeral (“16,” → “16”).

## Kickers, headlines, points

- **Kicker** (top-left tag): the nearest markdown heading, with any `T02_`-style prefix stripped and underscores → spaces, uppercased, ≤ 34 chars. With no headings it falls back to `STORY`.
- **Headline** (the big chalk line): the line's content words (function words, digit-only tokens and < 3-char words removed), display casing preserved, first 3.
- **Points** (small supporting lines): next content words after the headline, uppercased, ≤ 3.
- **Number**: digits with optional unit (`%`, `percent`, `million`, `billion`, `hours`, `people`, `servers`, …) or a number-word mapped to digits. Empty string when the line has none (the layout then draws no numeral).
- **Icon**: first match in the icon table (`hack|attack|threat…` → target, `code|terminal…` → terminal, `ai|agent|model…` → robot, `patch|secure|protect` → shield, `bug|flaw|vulnerability` → bug, `report|research|finding` → news, `server|data|cloud` → folder, `password|key` → key, `watch|monitor|eye` → eye, `hour|day|time` → clock, `lock|encrypt` → padlock, `search|scan` → search, `world|global|internet` → globe, `phone|wifi|24` → wifi, `human|operator|investigator` → finger, `warn|risk|critical` → warn, `before|after|vs` → vs, `france|paris|city` → pin, `website|web` → globe; default `news`).

## Forcing a layout

There is no flags-per-line override yet — the director is the authority. To force one, edit `beats.json` (change `layout` for the beat id), then re-run:

```
python scripts/render_blocks.py --project my-film   # re-renders only changed blocks
python scripts/stitch.py --project my-film
python scripts/captions_burn.py --project my-film
```

The storyboard reads `beats.json`/`plan.json` at render time, so a hand-edit is safe as long as the JSON stays valid.

## Block alternation

1–4 lines per block, ≤ 9 s, cut at sentence ends once ≥ 5 s have elapsed. Blocks alternate `board → photo → board` across the film; the first and last blocks are always board. World origins advance 30,000 px per block so parallax never repeats. `--photos existing` reuses a `photos.json` you already have (best for a documentary with fixed evidence photos); `--photos auto` queries Wikimedia Commons per visual keyword in the line; `--photos none` gives you boards only.

## Adding a layout

1. Add the drawing to `storyboard.py` (board branch in `build_board`, photo branch in `build_photo`).
2. Add the trigger to `choose_layout` and the mapping to `BOARD_OF` / `PHOTO_OF`.
3. Add an icon keyword rule if the new layout needs a new glyph, or a painter in `icons_painters.py` (20 glyphs ship today).
