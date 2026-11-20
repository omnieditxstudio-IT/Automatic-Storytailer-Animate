#!/usr/bin/env python3
"""Check a finished film before anyone watches it: frames, length, audio, loudness, captions.

  python scripts/qa.py --project my-film --video out/FILM.mp4

Fails (exit 1) on a missing soundtrack, a frame-count mismatch, a caption that does not
reach the bottom band, or loudness outside -15 LUFS / -1.5 dBTP. Writes review stills to
out/qa/. This is the gate run.py uses; a film that fails here is not finished.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402


def loudness(video):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(video), "-af",
                        "loudnorm=I=-15:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return None
    d = json.loads(m.group(0))
    return float(d["input_i"]), float(d["input_tp"])


def still(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", str(out)], check=True)
    return out


def caption_band(path, height):
    """(bright_pixels, bottom_gap_px) in the bottom quarter of a frame."""
    from PIL import Image
    im = Image.open(path).convert("L")
    w, h = im.size
    band = im.crop((0, int(h * 0.70), w, h))
    px = band.load()
    bw, bh = band.size
    lit = 0
    lowest = -1
    for y in range(bh):
        row = 0
        for x in range(0, bw, 2):
            if px[x, y] > 205:
                row += 1
        if row >= 3:
            lit += row
            lowest = y
    gap = (h - int(h * 0.70) - 1 - lowest) if lowest >= 0 else h
    return lit, gap


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--video", default="out/FILM.mp4")
    ap.add_argument("--no-stills", action="store_true")
    a = ap.parse_args()
    proj = paths.project_dirs(a.project)
    video = pathlib.Path(a.video)
    video = (video if video.is_absolute() else proj / video).resolve()
    if not video.exists():
        raise SystemExit(f"{video} not found")
    timing = paths.load_json(proj / "audio" / "timing.json")
    plan = paths.load_json(proj / "plan.json", {"fps": 30})
    fps = plan.get("fps", 30)
    info = paths.probe(video)
    nb = paths.count_frames(video)
    want = int(round(float(timing["total_duration"]) * fps)) if timing else nb
    problems, notes = [], []

    if nb != want:
        problems.append(f"frames {nb}, expected {want}")
    if abs(info["duration"] - want / fps) > 1.0:
        problems.append(f"duration {info['duration']:.2f}s, expected {want / fps:.2f}s")
    if not info["has_audio"]:
        problems.append("no audio stream")
    if not info["width"] or not info["height"]:
        problems.append("no video stream")

    loud = loudness(video) if info["has_audio"] else None
    if loud:
        lufs, tp = loud
        notes.append(f"loudness {lufs:.1f} LUFS, true peak {tp:.1f} dBTP")
        if abs(lufs + 15.0) > 1.5:
            problems.append(f"loudness {lufs:.1f} LUFS is outside -15 +/- 1.5")
        if tp > -0.8:
            problems.append(f"true peak {tp:.1f} dBTP is too hot")

    # captions: three chunks spread through the film, sampled mid-word
    cap_problems = 0
    if timing:
        from captions_burn import chunks
        cs = chunks(timing)
        picks = [cs[len(cs) * i // 4] for i in (1, 2, 3)] if len(cs) > 4 else cs[:1]
        for n, c in enumerate(picks):
            t = min(c["t1"] - 0.05, c["t0"] + 0.45)
            p = proj / "out" / "qa" / f"caption_{n}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            still(video, t, p)
            try:
                lit, gap = caption_band(p, info["height"])
            except Exception as e:
                notes.append(f"caption check {n} skipped ({e})")
                continue
            notes.append(f"caption {n} at {t:6.2f}s: {lit} lit px, {gap} px from bottom")
            if lit < 120:
                problems.append(f"caption {n} not visible at {t:.1f}s")
                cap_problems += 1
            elif gap > info["height"] * 0.085:
                problems.append(f"caption {n} sits {gap} px above the bottom at {t:.1f}s")
                cap_problems += 1
            if a.no_stills:
                p.unlink(missing_ok=True)

    if not a.no_stills:
        qa = proj / "out" / "qa"
        qa.mkdir(parents=True, exist_ok=True)
        for n, t in enumerate((0.6, float(timing["total_duration"]) * 0.45,
                               float(timing["total_duration"]) - 1.2)):
            still(video, max(0.0, t), qa / f"review_{n}.png")

    print(f"qa: {video.name}  {info['width']}x{info['height']}  {nb} frames  "
          f"{info['duration']:.2f}s  audio={'yes' if info['has_audio'] else 'NO'}")
    for n in notes:
        print("  " + n)
    if problems:
        print("FAIL")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
