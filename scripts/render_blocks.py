#!/usr/bin/env python3
"""Render every style block as its own file, so the cut between looks is a real cut.

  python scripts/render_blocks.py --project my-film --size 1920x1080 --crf 18
  python scripts/render_blocks.py --project my-film --size 640x360 --only 0,1 --force

Blocks come from plan.json: block b covers frames f0..f1-1. Each block is rendered
by cinematic-film's render.py with --t0/--t1, so the camera never travels across the
empty board between two stations. stitch.py joins them frame-exactly.

Existing block files are reused when they are newer than scene.py, beats.json and
plan.json; --force re-renders everything.
"""
import argparse
import hashlib
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--workers", type=int, default=0, help="0 = render.py decides")
    ap.add_argument("--only", default="", help="comma-separated block indices (default: all)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    proj = paths.project_dirs(a.project)
    plan = paths.load_json(proj / "plan.json")
    if not plan:
        raise SystemExit("plan.json missing: run director.py first")
    fps = plan.get("fps", 30)
    render_py = paths.cinematic_scripts() / "render.py"
    blocks_dir = proj / "out" / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)
    only = {int(x) for x in a.only.split(",") if x.strip()} if a.only else None
    deps = [proj / "scene.py", proj / "beats.json", proj / "plan.json"]
    newest = max((p.stat().st_mtime for p in deps if p.exists()), default=0)

    todo = [b for b in plan["blocks"] if only is None or b["index"] in only]
    total_frames = 0
    scene_sig = paths.file_sig(proj / "scene.py") if (proj / "scene.py").exists() else "noscene"
    beats_sig = paths.file_sig(proj / "beats.json") if (proj / "beats.json").exists() else "nobeats"
    for b in todo:
        f0, f1 = int(b["f0"]), int(b["f1"])
        n = f1 - f0
        if n <= 0:
            continue
        total_frames += n
        out = blocks_dir / f"b{b['index']:03d}.mp4"

        # production cache: identical scene + beats + block geometry -> skip the render entirely
        blk_sig = paths.json_sig({"i": b["index"], "style": b["style"], "start": b["start"],
                                  "end": b["end"], "f0": f0, "f1": f1, "x0": b["x0"],
                                  "x_last": b.get("x_last"), "size": a.size, "crf": a.crf})
        key = hashlib.sha256(f"{scene_sig}|{beats_sig}|{blk_sig}".encode("utf-8")).hexdigest()
        label = f"b{b['index']:03d}-{b['style']}"
        cached = paths.cache_restore("blocks", key, ".mp4", out, label=label)
        if cached:
            have = paths.count_frames(out)
            if have == n:
                print(f"block {b['index']:>2}: cache hit {out.name}  {n} frames")
                continue
            print(f"block {b['index']:>2}: cached copy has {have}/{n} frames, re-render")

        if out.exists() and not a.force and out.stat().st_mtime >= newest:
            have = paths.count_frames(out)
            if have == n:
                print(f"block {b['index']:>2}: reuse {out.name}  {n} frames")
                continue
            print(f"block {b['index']:>2}: {out.name} has {have}/{n} frames, re-render")
        cmd = [sys.executable, str(render_py), "--project", str(proj), "--size", a.size,
               "--crf", str(a.crf), "--t0", f"{f0 / fps:.6f}", "--t1", f"{f1 / fps:.6f}",
               "--out", str(out)]
        if a.workers:
            cmd += ["--workers", str(a.workers)]
        t = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout + "\n" + r.stderr)
            raise SystemExit(f"block {b['index']} failed")
        have = paths.count_frames(out)
        print(f"block {b['index']:>2}: {b['style']:<5} {n:>4} frames  {time.time() - t:5.1f}s"
              + ("" if have == n else f"  WARN rendered {have}, expected {n}"))
        if have == n:
            paths.cache_put("blocks", key, ".mp4", out, label=label)
    print(f"rendered/reused {len(todo)} blocks, {total_frames} frames "
          f"({total_frames / fps:.1f}s) at {a.size}")


if __name__ == "__main__":
    main()
