# Sound: cues, levels, music

Every effect is synthesised in code by cinematic-film's `build_sfx.py` (numpy noise + partials, no sample library, nothing to license). Levels are applied once, in `audio_finish.py`, after all cues exist.

## Signal chain

```
voice (48 kHz) --\n                  > mix_soundtrack.py -> mix.m4a -> mux with captioned.mp4 -> FILM.mp4
sfx.wav   -------/   -15 LUFS / -1.5 dBTP target
music    -----------/
```

| Stage | Setting |
|---|---|
| Voice pad | `apad` to film duration (mix uses `duration=first`) |
| SFX bus | `--sfx-db -19` |
| Music | `--music-db -18` |
| Music duck | 4:1 at threshold 0.025 (voice presence pulls the bed down) |
| Music EQ dip | 4 dB around the voice fundamentals |
| Normalise | `--lufs -15` (deliverable sits at −15 LUFS) |

## What the director cues, and when

`make_cues.py` builds `sfx_cues.json` (root + `audio/` copies). Gains are relative to a full-scale synth; the −19 dB bus does the real level-setting:

| Cue | Fires on | Gain |
|---|---|---|
| riser | 0.05 s in (2.0 s), and again 4.4 s before the end (3.4 s) | 0.70 / 0.66 |
| boom | 0.55 s in; and 1.5 s before the end | 0.75 / 0.68 |
| heartbeat | 1.35 s in; and 3.2 s before the end | 0.42 / 0.40 |
| heartbeat | only if film > 8 s | |
| whoosh | every style cut, 0.10 s before the block boundary; gain cycles 0.48/0.54/0.60 | ~0.5 |
| slide / pop | block start + 0.06 s (slide = board, pop = photo) | 0.42 |
| stamp | `title` / `end` beats (t+0.55/0.60), `doc` photo beats (t+0.95) | 0.52–0.62 |
| impact | `stat` beats (t+0.08) | 0.55 |
| tick | `check` and `chain` beats, up to 3 ticks 0.26 s apart | 0.32 |
| marker | every 3rd beat (t+0.18) | 0.28 |
| pencil | beats longer than 1.6 s, alternating with marker (t+0.70, 1.2 s) | 0.26 |

Near-duplicates of one kind closer than 0.18 s apart are coalesced; cues past film end are dropped.

## The synth catalogue (all synthesised, no licences)

pop print/card landing · slide newspaper/string slide · whoosh camera move · pencil pen circle/underline (`dur`) · tick pencil tick · snip tiny cut · click shutter/film clamp · stamp rubber-stamp slam · impact low thump · boom sub drop · ticks counter roll-up · shimmer dot cluster · drop falling swoop · riser crescendo into a section (`dur`, peaks at t+dur) · heartbeat low lub-dub · clock dry ticks (`dur`)

## Music

Default: **Kevin MacLeod — “Crypto”** (incompetech.com, CC BY 4.0), bundled at `assets/music/Crypto.mp3` (≈ 6.5 MB). If the film is longer than the track it is looped with `-stream_loop -1`. Pass `--music none` to mix dry, or `--music path.mp3` for a different track (any licence you are entitled to use — the mix itself adds no attribution for your file, so credit it in `credits.md` yourself).

Every film made with `--music auto` must carry the credit, and `run.py` writes it into `credits.md`:

> Music: “Crypto” Kevin MacLeod (incompetech.com), CC BY 4.0

## Changing levels

Edit the `--music-db / --sfx-db / --lufs` defaults in `audio_finish.py`, or pass them directly for a one-off mix. The −19/−18 pair is the house level: loud enough to feel, quiet enough for the voice to sit on top. Do not raise the SFX bus above the music without checking the −15 LUFS reading afterwards.

## QA

`qa.py` fails on loudness outside −15 ± 1.5 LUFS and true peak > −0.8 dBTP. If the mix fails, lower `--music-db` first, then `--sfx-db`; never chase LUFS by pushing the voice harder.
