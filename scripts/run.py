#!/usr/bin/env python3
"""One command from a voice file and a script to a finished, captioned, scored film.

  python scripts/run.py --project my-film --voice voice.mp3 --script script.md
  python scripts/run.py --project my-film --voice v.wav --script s.txt --size 1920x1080 --crf 16
  python scripts/run.py --project my-film --preview          # 2 blocks, 640x360, no score

What it runs, in order:
  ingest.py        voice -> audio/narration.m4a; script -> script.json + audio/timing.json
  director.py      beats, layouts, style blocks -> beats.json, plan.json, beats.md
  fetch_photos.py  one real Commons photo per photo block -> photos.json, assets/prep
  make_scene.py    the project's scene.py
  make_cues.py     effects cue sheet -> sfx_cues.json
  render_blocks.py one render per style block -> out/blocks/bNNN.mp4
  stitch.py        frame-exact join -> out/silent.mp4
  captions_burn.py bottom-flush neon captions + SRT -> out/captioned.mp4
  audio_finish.py  voice pad, SFX -19 dB, score -18 dB, mix -15 LUFS -> out/FILM.mp4
  qa.py            frame/length/loudness/caption gate; review stills in out/qa

Re-running after a script edit rebuilds timing and plan, re-renders only blocks whose
files are older than the plan, and reuses downloaded photos.
"""
import argparse
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402


def stage(name, script, *args, **kw):
    print(f"\n== {name} ==", flush=True)
    cmd = [sys.executable, "-X", "utf8", HERE / script, *args]
    t = time.time()
    r = subprocess.run([str(c) for c in cmd], **kw)
    if r.returncode != 0:
        raise SystemExit(f"{name} failed ({r.returncode})")
    print(f"-- {name} {time.time() - t:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--voice", default="")
    ap.add_argument("--script", default="")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--photos", choices=["auto", "existing", "none"], default="auto")
    ap.add_argument("--music", default="auto")
    ap.add_argument("--workers", type=int, default=0, help="render + caption workers (0 = all cores minus one)")
    ap.add_argument("--force", action="store_true", help="rebuild even if a finished out/FILM.mp4 already exists")
    ap.add_argument("--model", default="tiny.en", help="faster-whisper model for alignment")
    ap.add_argument("--preview", action="store_true", help="2 blocks at 640x360, captioned, silent")
    ap.add_argument("--skip-render", action="store_true", help="rebuild plan/scene only")
    a = ap.parse_args()
    proj = paths.project_dirs(a.project)

    # ---- prerequisite check ------------------------------------------------
    # Every run starts here: auto-installs pip-able packages, or exits with one
    # clear line if something essential (ffmpeg, cinematic-film) is missing.
    stage("check", "check_requirements.py")

    # ---- resume gate ------------------------------------------------------
    # A finished project (out/FILM.mp4 + plan/scene/cues all present) is never
    # re-built on re-run: we just re-verify with QA and exit.  Only an explicit
    # --force forces a fresh render.  New users who have everything cached keep
    # their work; only missing pieces get built.
    if not a.preview and (proj / "out" / "FILM.mp4").exists() and not a.force:
        print(f"\nresume: {proj / 'out' / 'FILM.mp4'} already exists;")
        print("        nothing to re-download or re-render; running QA only. Use --force to rebuild.")
        stage("qa", "qa.py", "--project", proj, "--video", "out/FILM.mp4")
        paths.cache_report()
        return

    if a.preview:
        a.size = "640x360"
        a.crf = 26
        a.music = "none"

    have_timing = (proj / "audio" / "timing.json").exists() and (proj / "script.json").exists()
    if not have_timing:
        if not (a.voice and a.script):
            raise SystemExit("first run needs --voice and --script (or an existing audio/timing.json)")
        stage("ingest", "ingest.py", "--project", proj, "--voice", a.voice, "--script", a.script,
              "--model", a.model)

    if a.photos == "auto" and (proj / "photos.json").exists() and not a.preview:
        existing = paths.load_json(proj / "photos.json", {}).get("photos", [])
        if existing:
            a.photos = "existing"
            print(f"photos: reusing {len(existing)} entries in photos.json")

    stage("director", "director.py", "--project", proj, "--photos", a.photos)

    if a.photos == "auto":
        stage("photos", "fetch_photos.py", "--project", proj)
    if not (proj / "photos.json").exists():
        paths.dump_json(proj / "photos.json", {"grade": "bw", "photos": []})

    # prep_assets.py ships with cinematic-film, not this skill
    scripts = paths.cinematic_scripts()
    prep_script = scripts / "prep_assets.py"
    if not prep_script.exists():
        raise SystemExit(f"prep_assets.py missing: {prep_script}")

    stage("prep", prep_script, "--project", proj)
    stage("scene", "make_scene.py", "--project", proj)
    stage("cues", "make_cues.py", "--project", proj)

    if a.skip_render:
        print("\nplan, scene and cues are ready; render skipped")
        return

    only = "0,1" if a.preview else ""
    rb = ["--project", proj, "--size", a.size, "--crf", a.crf]
    if only:
        rb += ["--only", only]
    if a.workers:
        rb += ["--workers", a.workers]
    stage("render", "render_blocks.py", *rb)

    st = ["--project", proj, "--crf", max(10, a.crf - 2)]
    if only:
        st += ["--only", only]
        st += ["--out", "out/preview_silent.mp4"]
    else:
        st += ["--out", "out/silent.mp4"]
    stage("stitch", "stitch.py", *st)

    cb = ["--project", proj, "--video", "out/preview_silent.mp4" if only else "out/silent.mp4",
          "--out", "out/preview_captioned.mp4" if only else "out/captioned.mp4", "--crf", a.crf]
    if a.workers:
        cb += ["--workers", str(a.workers)]
    stage("captions", "captions_burn.py", *cb)

    if a.preview:
        final = proj / "out" / "preview_captioned.mp4"
        print(f"\npreview: {final}")
        return

    stage("audio", "audio_finish.py", "--project", proj, "--video", "out/captioned.mp4",
          "--out", "out/FILM.mp4", "--music", a.music)

    # credits: images already credited by fetch_commons; add the score
    cred = proj / "credits.md"
    txt = cred.read_text(encoding="utf-8") if cred.exists() else "# Credits\n"
    if "## Music" not in txt and a.music != "none":
        txt += ("\n## Music\n\n| Crypto | Kevin MacLeod | CC BY 4.0 | "
                "https://incompetech.com/music/royalty-free/ |\n")
        cred.write_text(txt, encoding="utf-8")
        print(f"credits: {cred}")

    stage("qa", "qa.py", "--project", proj, "--video", "out/FILM.mp4")
    paths.cache_report()
    print(f"\nfinished: {proj / 'out' / 'FILM.mp4'}")


if __name__ == "__main__":
    main()
