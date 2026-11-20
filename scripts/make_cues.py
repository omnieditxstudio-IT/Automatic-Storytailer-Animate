#!/usr/bin/env python3
"""Write sfx_cues.json from the plan: a whoosh on every style cut, a soft hit on every
line, and layout-aware detail (stamps on documents, ticks down a checklist, an impact
on a number).

  python scripts/make_cues.py --project my-film

Writes both <project>/sfx_cues.json (what build_sfx.py reads) and a copy in audio/.
Only cue kinds cinematic-film's build_sfx.py can synthesise are used, so the mix needs
no sample library. Levels are set later in audio_finish.py (-19 dB effects bus).
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    a = ap.parse_args()
    proj = paths.project_dirs(a.project)
    timing = paths.load_json(proj / "audio" / "timing.json")
    plan = paths.load_json(proj / "plan.json")
    beats_doc = paths.load_json(proj / "beats.json")
    if not (timing and plan and beats_doc):
        raise SystemExit("timing.json, plan.json and beats.json are required: run ingest.py and director.py")
    dur = timing["total_duration"]
    beats = {b["id"]: b for b in beats_doc["beats"]}
    blocks = plan["blocks"]

    cues = []

    def add(kind, t, gain, length=None):
        t = max(0.0, min(float(t), dur - 0.02))
        c = {"type": kind, "t": round(t, 3), "gain": round(gain, 3)}
        if length:
            c["dur"] = round(length, 2)
        cues.append(c)

    # opening
    add("riser", 0.05, 0.70, 2.0)
    add("boom", 0.55, 0.75)
    if dur > 8:
        add("heartbeat", 1.35, 0.42)

    # style cuts
    for n, blk in enumerate(blocks[1:], 1):
        add("whoosh", blk["start"] - 0.10, 0.48 + 0.06 * (n % 3))

    # per block / per line
    for bi, blk in enumerate(blocks):
        style = blk["style"]
        add("slide" if style == "board" else "pop", blk["start"] + 0.06, 0.42)
        for bid in blk["beats"]:
            b = beats[bid]
            lay = b["layout"]
            t = b["start"]
            if lay == "stat":
                add("impact", t + 0.08, 0.55)
            elif lay in ("check", "chain"):
                for k in range(min(3, max(1, len(b.get("points") or [])))):
                    add("tick", t + 0.38 + k * 0.26, 0.32)
            elif lay == "title":
                add("stamp", t + 0.55, 0.62)
            elif lay == "end":
                add("stamp", t + 0.60, 0.58)
            elif lay == "doc":
                add("stamp", t + 0.95, 0.52)
            if (b["id"] + bi) % 3 == 0:
                add("marker", t + 0.18, 0.28)
            elif b["end"] - t > 1.6:
                add("pencil", t + 0.70, 0.26, 1.2)

    # ending
    if dur > 7:
        add("riser", dur - 4.4, 0.66, 3.4)
        add("shimmer", dur - 2.4, 0.38)
        add("heartbeat", dur - 3.2, 0.40)
        add("boom", dur - 1.5, 0.68)

    # sort, drop near-duplicates of one kind, clamp
    cues.sort(key=lambda c: c["t"])
    clean, last = [], {}
    for c in cues:
        if c["t"] >= dur - 0.02:
            continue
        if c["t"] - last.get(c["type"], -9.0) < 0.18:
            continue
        last[c["type"]] = c["t"]
        clean.append(c)

    out = {"duration": round(dur, 4), "cues": clean}
    txt = json.dumps(out, indent=1)
    (proj / "sfx_cues.json").write_text(txt, encoding="utf-8")
    (proj / "audio" / "sfx_cues.json").write_text(txt, encoding="utf-8")
    kinds = {}
    for c in clean:
        kinds[c["type"]] = kinds.get(c["type"], 0) + 1
    print(f"cues: {len(clean)}  ({dur:.2f}s)  " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))


if __name__ == "__main__":
    main()
