#!/usr/bin/env python3
"""Join the block renders into one silent film, frame-exactly.

  python scripts/stitch.py --project my-film --size 1920x1080 --crf 14

Every block is trimmed to its exact frame count and the pieces are joined with the
concat *filter* and re-encoded once. (The concat demuxer with -c copy silently drops
packets at some joins; a one-frame hole in a caption film is very visible.)
"""
import argparse
import hashlib
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--crf", type=int, default=14)
    ap.add_argument("--out", default="out/silent.mp4")
    ap.add_argument("--only", default="", help="comma-separated block indices, for previews")
    a = ap.parse_args()

    proj = paths.project_dirs(a.project)
    plan = paths.load_json(proj / "plan.json")
    if not plan:
        raise SystemExit("plan.json missing: run director.py first")
    fps = plan.get("fps", 30)
    only = {int(x) for x in a.only.split(",") if x.strip()} if a.only else None
    files, counts = [], []
    for b in plan["blocks"]:
        if only is not None and b["index"] not in only:
            continue
        p = proj / "out" / "blocks" / f"b{b['index']:03d}.mp4"
        if not p.exists():
            raise SystemExit(f"{p} missing: run render_blocks.py (or use --only)")
        n = paths.count_frames(p)
        want = int(b["f1"]) - int(b["f0"])
        if n != want:
            print(f"WARN block {b['index']}: {n} frames, plan says {want}; using the file's frames")
        files.append(p)
        counts.append(n)
    if not files:
        raise SystemExit("no blocks selected")

    out = pathlib.Path(a.out)
    out = (out if out.is_absolute() else proj / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # production cache: same blocks + same encoder settings -> reuse the stitched film
    sigs = [paths.file_sig(p) for p in files]
    stitch_key = hashlib.sha256(
        paths.json_sig({"blocks": sigs, "crf": a.crf, "fps": fps}).encode("utf-8")).hexdigest()
    if paths.cache_restore("silent", stitch_key, ".mp4", out, label="silent"):
        got = paths.count_frames(out)
        if got == sum(counts):
            print(f"stitch: cache hit -> {out}  {got} frames ({got / fps:.2f}s)")
            return
        print("stitch: cached copy failed frame check, re-stitching")

    if len(files) == 1:
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(files[0]),
               "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf),
               "-pix_fmt", "yuv420p", "-r", str(fps), "-an", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)
    else:
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for p in files:
            cmd += ["-i", str(p)]
        parts = "".join(f"[{i}:v]trim=start_frame=0:end_frame={counts[i]},"
                        f"setpts=PTS-STARTPTS,setsar=1[v{i}];" for i in range(len(files)))
        fc = parts + "".join(f"[v{i}]" for i in range(len(files))) + \
            f"concat=n={len(files)}:v=1:a=0[outv]"
        cmd += ["-filter_complex", fc, "-map", "[outv]",
                "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf),
                "-pix_fmt", "yuv420p", "-r", str(fps), "-an",
                "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)

    got = paths.count_frames(out)
    want = sum(counts)
    print(f"stitched {len(files)} blocks -> {out}  {got} frames ({got / fps:.2f}s)"
          + ("" if got == want else f"  WARN expected {want}"))
    if got != want:
        raise SystemExit(1)
    paths.cache_put("silent", stitch_key, ".mp4", out, label="silent")


if __name__ == "__main__":
    main()
