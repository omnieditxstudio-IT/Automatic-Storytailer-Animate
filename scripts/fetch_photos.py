#!/usr/bin/env python3
"""Find a real, freely licensed photo for every photo block, download it, and grade it.

  python scripts/fetch_photos.py --project my-film
  python scripts/fetch_photos.py --project my-film --no-download   # just report the picks

Queries come from plan.json (written by director.py). For each one this searches
Wikimedia Commons, rejects anything not public-domain/CC0/CC BY/CC BY-SA, rejects
diagrams, logos, maps and screenshots, prefers large landscape photographs, writes
photos.json and then lets cinematic-film's fetch_commons.py fill in the file name,
author and licence. prep_assets.py grades the set into the film's black-and-white look.

If a query finds nothing usable, its block renders with a card instead of a photo;
the film still builds.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

paths.add_engine_path()
import fetch_commons as fc  # noqa: E402

BAD = re.compile(r"\b(logo|icon|map|diagram|chart|graph|svg|poster|cover|screenshot|drawing|"
                 r"illustration|seal|coat[ _]of[ _]arms|flag|sign|banner|clipart|cartoon)\b", re.I)
GOOD = re.compile(r"\b(photo|photograph|center|centre|room|building|office|people|person|server|"
                  r"computer|hacker|crowd|street|city|lab|laboratory|station|train|airport|"
                  r"factory|machine|network|cable|code|screen|keyboard|terminal)\b", re.I)


def score(d):
    lic = d.get("license") or ""
    if not fc.FREE.search(lic):
        return -99
    if (d.get("mime") or "") not in ("image/jpeg", "image/png"):
        return -99
    w, h = d.get("w") or 0, d.get("h") or 0
    if w < 1000 or h < 600:
        return -99
    text = f"{d.get('title','')} {d.get('desc','')}"
    s = 0.0
    if BAD.search(text):
        s -= 6
    if GOOD.search(text):
        s += 2
    aspect = w / max(1, h)
    if 1.15 <= aspect <= 2.4:
        s += 2
    elif aspect < 1.0:
        s -= 2
    if w >= 2200:
        s += 1
    s += min(2.0, w / 2500.0)
    return s


def search(query, limit=16):
    key = f"{query}|{limit}".encode("utf-8")
    import hashlib as _hl
    ck = _hl.sha256(key).hexdigest()
    hit = paths.cache_get("commons_search", ck, ".json")
    if hit:
        payload = paths.load_json(hit, {"found": []}) or {"found": []}
        found = [(s, d) for s, d in payload.get("found", []) if s > -50]
        if found:
            return found
    r = fc.api(action="query", generator="search", gsrsearch=query, gsrnamespace=6,
               gsrlimit=limit, **fc.IIPROP)
    pages = (r.get("query") or {}).get("pages", [])
    found = []
    for p in pages:
        d = fc.info(p)
        s = score(d)
        if s > -50:
            found.append((s, d))
    found.sort(key=lambda x: -x[0])
    try:
        paths.cache_write("commons_search", ck, ".json",
                          json.dumps({"found": [(s, d) for s, d in found]}, ensure_ascii=True))
    except OSError:
        pass
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--keep-existing", action="store_true",
                    help="keep photos.json entries that already have a downloaded file")
    ap.add_argument("--grade", default="bw", choices=["bw", "sepia", "natural"])
    a = ap.parse_args()

    proj = paths.project_dirs(a.project)
    plan = paths.load_json(proj / "plan.json")
    if not plan:
        raise SystemExit("plan.json missing: run director.py first")
    old = paths.load_json(proj / "photos.json", {"photos": []}) or {"photos": []}
    old_by_id = {p["id"]: p for p in old.get("photos", []) if p.get("id")}
    wanted = {}
    for blk in plan["blocks"]:
        pid, q = blk.get("photo"), blk.get("query")
        if pid and q and pid not in wanted:
            wanted[pid] = q
    if not wanted:
        print("no photo blocks in the plan: nothing to fetch")
        paths.dump_json(proj / "photos.json", {"grade": a.grade, "photos": []})
        return

    entries, failed = [], []
    for pid, q in wanted.items():
        prev = old_by_id.get(pid)
        if a.keep_existing and prev and prev.get("file") and (proj / "assets" / "photos" / prev["file"]).exists():
            entries.append(prev)
            print(f"{pid}: keep {prev['file']}")
            continue
        pick = None
        for attempt in (q, " ".join(q.split()[:2]), q.split()[0]):
            hits = search(attempt)
            if hits:
                pick = hits[0][1]
                print(f"{pid}: {q!r} -> {pick['title']}  [{pick['license']}]  {pick['w']}x{pick['h']}")
                break
        if not pick:
            failed.append((pid, q))
            print(f"{pid}: no free landscape photo for {q!r}; block will use a card")
            continue
        entries.append({"id": pid, "kind": "photo", "commons": pick["title"],
                        "what": q.title(), "query": q})

    # pre-seed anything the production cache already holds, so Commons downloads
    # and licence/credit lookups are skipped entirely for known files
    assets_dir = proj / "assets" / "photos"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for e in entries:
        commons = e.get("commons") or ""
        if not commons or e.get("file"):
            continue
        title = commons if commons.startswith("File:") else "File:" + commons
        stem = re.sub(r"[^A-Za-z0-9]+", "_", title[5:].rsplit(".", 1)[0])[:48]
        ext = pathlib.Path(title).suffix.lower() or ".jpg"
        dst = assets_dir / f"{e['id']}_{stem}{ext}"
        ck = hashlib.sha256(title.encode("utf-8")).hexdigest()
        hit = paths.cache_restore("commons_files", ck, ext, dst, label=title)
        if not hit:
            continue
        e["file"] = dst.name
        sidecar = paths.cache_get("commons_files", ck, ".credit.json", label=title)
        if sidecar:
            try:
                e.update(paths.load_json(sidecar, {}))
                print(f"{e['id']}: cache hit (file+credits) {dst.name}")
                continue
            except Exception:
                pass
        print(f"{e['id']}: cache hit (file) {dst.name}")

    spec = {"grade": a.grade, "photos": entries}
    paths.dump_json(proj / "photos.json", spec)
    if a.no_download:
        print(f"{len(entries)} picks written to photos.json (not downloaded)")
        return
    if not entries:
        print("nothing downloaded")
        return

    scripts = paths.cinematic_scripts()
    get = [sys.executable, "-X", "utf8", scripts / "fetch_commons.py", "get", "--project", proj]
    r = subprocess.run([str(c) for c in get])
    if r.returncode != 0:
        # drop whatever failed to arrive, then continue with the rest
        ok = []
        for p in entries:
            f = p.get("file")
            if f and (proj / "assets" / "photos" / f).exists():
                ok.append(p)
        paths.dump_json(proj / "photos.json", {"grade": a.grade, "photos": ok})
        if ok:
            subprocess.run([str(c) for c in get], check=False)
        print(f"WARN {len(entries) - len(ok)} photo(s) unavailable; film continues with {len(ok)}")

    subprocess.run([sys.executable, "-X", "utf8", scripts / "prep_assets.py", "--project", proj,
                    "--grade", a.grade], check=True)
    subprocess.run([sys.executable, "-X", "utf8", scripts / "fetch_commons.py", "credits", "--project", proj],
                   check=False)

    # snapshot the downloaded originals and their credits into the production cache
    spec = paths.load_json(proj / "photos.json", {"photos": []}) or {"photos": []}
    for e in (spec.get("photos") or []):
        f, commons = e.get("file"), e.get("commons")
        if not (f and commons):
            continue
        title = commons if commons.startswith("File:") else "File:" + commons
        ck = hashlib.sha256(title.encode("utf-8")).hexdigest()
        src = assets_dir / f
        if src.exists():
            paths.cache_put("commons_files", ck, pathlib.Path(f).suffix.lower() or ".jpg",
                            src, label=title)
            meta = {k: e.get(k) for k in ("source", "credit", "license", "license_url",
                                          "date", "license_ok", "what", "query", "kind")
                    if e.get(k) is not None}
            paths.cache_write("commons_files", ck, ".credit.json", json.dumps(meta, ensure_ascii=True),
                              label=title)


if __name__ == "__main__":
    main()
