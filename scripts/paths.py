"""Shared paths and small helpers for automatic-storyteller-animate.

Nothing here renders. Every other script imports this so the skill keeps working
wherever it is installed: engine.py is borrowed from the sibling cinematic-film
skill (override with CINEMATIC_SCRIPTS).
"""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

SKILL = pathlib.Path(__file__).resolve().parents[1]          # .../automatic-storyteller-animate
SCRIPTS = SKILL / "scripts"
ASSETS = SKILL / "assets"
SKILLS_ROOT = SKILL.parent


def cinematic_scripts():
    cands = []
    env = os.environ.get("CINEMATIC_SCRIPTS")
    if env:
        cands.append(pathlib.Path(env))
    cands += [
        SKILLS_ROOT / "cinematic-film" / "scripts",
        pathlib.Path.home() / ".config" / "opencode" / "skills" / "cinematic-film" / "scripts",
        pathlib.Path.home() / ".claude" / "skills" / "cinematic-film" / "scripts",
    ]
    for c in cands:
        if (c / "engine.py").exists():
            return c
    raise SystemExit(
        "cinematic-film/scripts not found. Install the cinematic-film skill next to this one "
        "or set CINEMATIC_SCRIPTS to its scripts folder.")


def add_engine_path():
    p = str(cinematic_scripts())
    if p not in sys.path:
        sys.path.insert(0, p)
    return pathlib.Path(p)


def run(cmd, **kw):
    kw.setdefault("check", True)
    return subprocess.run([str(c) for c in cmd], **kw)


def ffmpeg(*args):
    run(["ffmpeg", "-v", "error", "-y", *args])


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,nb_frames:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True).stdout
    info = json.loads(out or "{}")
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    num, den = (map(int, v["r_frame_rate"].split("/")) if v.get("r_frame_rate") else (30, 1))
    return {
        "duration": float(info.get("format", {}).get("duration") or 0.0),
        "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
        "fps": num / den if den else 30.0,
        "frames": int(v.get("nb_frames") or 0),
        "has_audio": bool(a),
    }


def count_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True).stdout.strip()
    return int(r or 0)


def load_json(path, default=None):
    p = pathlib.Path(path)
    if not p.exists():
        return default
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return default


def dump_json(path, obj):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=True), encoding="utf-8")
    return p


# ------------------------------------------------------------------ production cache
def slug(text, limit=40):
    """Safe, readable filename slug: keeps bytes sortable and human-checkable."""
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower()
    s = re.sub(r"-{2,}", "-", s)
    return (s[:limit] or "x").rstrip("-")


def cache_root():
    """Shared production cache: 'E:\\Storyteller catche files' by default.

    Override with STORYTELLER_CACHE (must exist or be creatable). If neither is
    available the skill still works; caching silently disables itself. The root is
    self-describing: a README and an append-only index.jsonl manifest live there.
    """
    env = os.environ.get("STORYTELLER_CACHE")
    candidates = [pathlib.Path(env)] if env else [pathlib.Path(r"E:\Storyteller catche files")]
    candidates.append(pathlib.Path.home() / ".cache" / "storyteller")
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            _stamp_cache_root(c)
            return c
        except OSError:
            continue
    return None


def _stamp_cache_root(root):
    readme = root / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Storyteller production cache - automatic-storyteller-animate\n"
            "============================================================\n\n"
            "The skill regenerates every heavy artifact here so a re-run is a lookup,\n"
            "not a render. Everything is content-addressed; deleting a file is safe\n"
            "(it will simply be rebuilt). Files are sorted by kind and named\n"
            "'<label>-<content-hash>.<ext>' so a sorted listing reads naturally.\n\n"
            "Layout:\n"
            "  whisper/         faster-whisper word timings, per voice+model\n"
            "  commons_search/  Wikimedia Commons search results, per query\n"
            "  commons_files/   downloaded original Commons files, per title\n"
            "  blocks/          rendered style blocks, per scene+plan+size+crf\n"
            "  silent/          stitched silent film, per block set\n"
            "  captioned/       captioned film + SRT, per video+timing+crf\n"
            "  sfx/             synthesized effects bus, per cue sheet\n"
            "  mix/             mixed voice+sfx+music bed, per inputs\n"
            "  music/           looped score bed, per track+length\n"
            "  prep/            graded photo set, per source+grade (disabled by default)\n"
            "  index.jsonl      one JSON line per cache add: kind, key, label, bytes\n",
            encoding="utf-8")
    (root / "index.jsonl").touch(exist_ok=True)


def _index_add(root, kind, key, label, path, size):
    try:
        with open(root / "index.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind,
                                "key": key, "label": label, "file": os.path.basename(str(path)),
                                "bytes": size}, ensure_ascii=True) + "\n")
    except OSError:
        pass


def cache_dir(name):
    root = cache_root()
    if root is None:
        return None
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_sig(path):
    """Cheap, stable content signature for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def json_sig(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _name(label, key, suffix):
    return f"{slug(label)}-{key[:12]}{suffix}" if label else f"{key[:12]}{suffix}"


def cache_get(kind, key, suffix, label=None):
    d = cache_dir(kind)
    if d is None:
        return None
    f = d / _name(label, key, suffix)
    if f.exists():
        return f
    # legacy: pre-sorted cache wrote unlabelled <key12>.<ext> or <key>.<ext>
    for legacy in (d / f"{key[:12]}{suffix}", d / f"{key}{suffix}"):
        if legacy.exists():
            return legacy
    return None


def cache_put(kind, key, suffix, src, label=None):
    d = cache_dir(kind)
    if d is None:
        return None
    root = cache_root()
    dst = d / _name(label, key, suffix)
    tmp = d / f".{_name(label, key, suffix)}.part"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    if root:
        _index_add(root, kind, key, label or kind, dst, dst.stat().st_size)
    return dst


def cache_write(kind, key, suffix, content, label=None):
    d = cache_dir(kind)
    if d is None:
        return None
    root = cache_root()
    dst = d / _name(label, key, suffix)
    tmp = d / f".{dst.name}.part"
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dst)
    if root:
        _index_add(root, kind, key, label or kind, dst, dst.stat().st_size)
    return dst


def cache_restore(kind, key, suffix, dst, label=None):
    f = cache_get(kind, key, suffix, label=label)
    if f:
        pathlib.Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
    return f


def cache_bytes(root=None):
    root = root or cache_root()
    if not root or not root.exists():
        return 0, 0
    total, n, per = 0, 0, {}
    for dirpath, _, files in os.walk(root):
        for name in files:
            f = pathlib.Path(dirpath) / name
            try:
                total += f.stat().st_size
                n += 1
                rel = f.relative_to(root).parts[0] if len(f.relative_to(root).parts) > 1 else f.name
                per[rel] = per.get(rel, [0, 0])
                per[rel][0] += 1
                per[rel][1] += f.stat().st_size
            except OSError:
                pass
    return total, n, per


def cache_report():
    root = cache_root()
    if not root:
        print("cache: unavailable (E: drive or STORYTELLER_CACHE not writable)")
        return None
    total, n, per = cache_bytes(root)
    print(f"cache: {n} entries, {total / 1048576:.1f} MB at {root}")
    rows = sorted(per.items(), key=lambda kv: kv[1][1], reverse=True)
    for name, (cnt, size) in rows:
        print(f"  {name:<16} {cnt:>5} files  {size / 1048576:>8.1f} MB")
    return per


def project_dirs(project):
    proj = pathlib.Path(project).resolve()
    for d in ("audio", "assets/photos", "assets/prep", "out/blocks", "out/qa", "fonts"):
        (proj / d).mkdir(parents=True, exist_ok=True)
    return proj
