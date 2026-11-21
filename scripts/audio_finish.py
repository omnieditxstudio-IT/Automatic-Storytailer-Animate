#!/usr/bin/env python3
"""Finish the sound: pad the voice to the film, build the effects, mix the score, mux.

  python scripts/audio_finish.py --project my-film --video out/captioned.mp4 --out out/FILM.mp4
  python scripts/audio_finish.py --project my-film --music none --mix-only

Voice is padded with silence to the film duration (mix_soundtrack mixes duration=first,
so an unpadded voice would cut the last line of score). Score sits at -18 dB and the
effects bus at -19 dB under the voice, the score ducks against it by 4:1, and the whole
mix is normalised to -15 LUFS / -1.5 dBTP.

--music accepts a file or "none"; the default is the skill's bundled CC BY track
(assets/music/Crypto.mp3, Kevin MacLeod), looped if the film is longer than the track.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402


def run(cmd):
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(str(c) for c in cmd)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--music", default="auto", help="auto (bundled track), none, or a file")
    ap.add_argument("--video", default="")
    ap.add_argument("--out", default="out/FILM.mp4")
    ap.add_argument("--mix-only", action="store_true")
    ap.add_argument("--music-db", type=float, default=-18.0)
    ap.add_argument("--sfx-db", type=float, default=-19.0)
    ap.add_argument("--lufs", type=float, default=-15.0)
    a = ap.parse_args()

    proj = paths.project_dirs(a.project)
    timing = paths.load_json(proj / "audio" / "timing.json")
    if not timing:
        raise SystemExit("audio/timing.json missing: run ingest.py first")
    dur = float(timing["total_duration"])
    scripts = paths.cinematic_scripts()

    # 1. voice, padded to the film length
    padded = proj / "audio" / "voice_padded.m4a"
    run(["ffmpeg", "-v", "error", "-y", "-i", proj / "audio" / "narration.m4a",
         "-af", "apad", "-t", f"{dur:.3f}", "-c:a", "aac", "-b:a", "256k", padded])

    # 2. score, looped if the film is longer than the track
    music = None
    music_key = "none"
    if a.music != "none":
        src = None
        if a.music == "auto":
            for c in (paths.ASSETS / "music" / "Crypto.mp3",
                      proj / "assets" / "music" / "Crypto.mp3"):
                if c.exists():
                    src = c
                    break
            if src is None:
                print("no bundled score found, mixing without music")
        else:
            src = pathlib.Path(a.music)
            if not src.is_absolute():
                src = (proj / src).resolve()
        if src and src.exists():
            ml = paths.probe(src)["duration"]
            src_sig = paths.file_sig(src)
            music_key = f"file:{src_sig}"
            if ml < dur - 0.5:
                bed = proj / "audio" / "music_bed.m4a"
                bed_key = hashlib.sha256(
                    paths.json_sig({"src": src_sig, "dur": round(dur, 3)}).encode("utf-8")).hexdigest()
                if paths.cache_restore("music", bed_key, ".m4a", bed, label="score-loop"):
                    print(f"score: cache hit ({ml:.1f}s -> {dur:.1f}s)")
                else:
                    music = bed
                    run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", src,
                         "-t", f"{dur:.3f}", "-c:a", "aac", "-b:a", "256k", music])
                    paths.cache_put("music", bed_key, ".m4a", bed, label="score-loop")
                    print(f"score looped {ml:.1f}s -> {dur:.1f}s")
                music = bed
            else:
                music = src

    # 3. effects from the cue sheet — production cache: identical cue sheet -> reuse the bus
    sfx = proj / "audio" / "sfx.wav"
    cues = proj / "sfx_cues.json"
    cues_sig = paths.file_sig(cues) if cues.exists() else "nocues"
    sfx_key = hashlib.sha256(
        paths.json_sig({"cues": cues_sig,
                        "builder": paths.file_sig(scripts / "build_sfx.py")}).encode("utf-8")).hexdigest()
    if paths.cache_restore("sfx", sfx_key, ".wav", sfx, label="sfx-bus"):
        print("sfx: cache hit")
    else:
        run([sys.executable, "-X", "utf8", scripts / "build_sfx.py", "--project", proj])
        paths.cache_put("sfx", sfx_key, ".wav", sfx, label="sfx-bus")

    # 4. mix — production cache: same inputs + same mix settings -> reuse the mix
    mix = proj / "audio" / "mix.m4a"
    mix_key = hashlib.sha256(
        paths.json_sig({"voice": paths.file_sig(proj / "audio" / "narration.m4a"),
                        "cues": cues_sig, "music": music_key,
                        "music_db": a.music_db, "sfx_db": a.sfx_db, "lufs": a.lufs,
                        "dur": round(dur, 3)}).encode("utf-8")).hexdigest()
    if paths.cache_restore("mix", mix_key, ".m4a", mix, label="mix"):
        print("mix: cache hit")
    else:
        cmd = [sys.executable, "-X", "utf8", scripts / "mix_soundtrack.py", "--project", proj,
               "--voice", padded, "--sfx", sfx,
               "--music-db", a.music_db, "--sfx-db", a.sfx_db,
               "--duck-ratio", 4.0, "--duck-threshold", 0.025, "--music-eq-dip", 4.0,
               "--lufs", a.lufs, "--out", mix]
        if music:
            cmd += ["--music", music]
        run(cmd)
        paths.cache_put("mix", mix_key, ".m4a", mix, label="mix")

    if a.mix_only or not a.video:
        return

    # 5. mux the finished picture and mix
    video = pathlib.Path(a.video)
    video = (video if video.is_absolute() else proj / video).resolve()
    out = pathlib.Path(a.out)
    out = (out if out.is_absolute() else proj / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", mix,
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "apad",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
    info = paths.probe(out)
    print(f"film: {out}  {info['width']}x{info['height']}  {info['duration']:.2f}s  "
          f"audio={'yes' if info['has_audio'] else 'NO'}")


if __name__ == "__main__":
    main()
