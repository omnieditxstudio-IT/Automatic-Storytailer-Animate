#!/usr/bin/env python3
"""Turn the timed script into a visual plan: beats, layout, icon, palette and alternating blocks.

  python scripts/director.py --project my-film [--photos auto|existing|none] [--seed 7]

Reads  audio/timing.json, script.json, optional photos.json
Writes beats.json, plan.json, beats.md

Every caption line becomes one beat. A beat gets exactly one layout and at most one
photo; consecutive beats are grouped into style blocks that alternate board -> photo ->
board, so the film cuts between the two looks every 4-10 seconds. The plan never moves
text between lines: a beat starts and ends when its line does.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

FPS = 30
BLOCK_SPAN = 30000          # world px reserved per block
BOARD_STEP = 6600
PHOTO_STEP = 6600

STOP = set("""a an and are as at be been being but by can could did do does doing done for from had has have having he her here hers
him his how i if in into is it its itself just like may me might more most my no nor not of off on once only or other our out over
own same she should so some such than that the their them then there these they this those through to too under until up very was we
were what when whenever where whereas which while who whom why will with would you your yours about after again against all also any because before both
each few further get got make makes made many much now one two three first second next last new see seen say says said""".split())

VISUALS = {
    "server": "server room", "data center": "data center", "datacenter": "data center",
    "cloud": "cloud computing", "network": "computer network cables", "internet": "internet cables",
    "code": "computer source code screen", "software": "software developer screen",
    "program": "programmer at computer", "terminal": "computer terminal screen",
    "laptop": "laptop on desk", "computer": "computer workstation", "chip": "microchip",
    "circuit": "circuit board", "robot": "industrial robot", "machine": "machine factory",
    "ai": "artificial intelligence laboratory", "algorithm": "computer code screen",
    "hack": "hacker computer", "hacker": "hacker computer", "cyber": "cybersecurity operations centre",
    "security": "security operations center", "password": "password keyboard",
    "office": "office workers", "team": "business team meeting", "people": "people walking street",
    "business": "small business owner shop", "businesses": "small business owner shop",
    "entrepreneur": "small business owner shop", "founder": "small business owner shop",
    "owner": "small business owner shop", "shop": "small shop counter",
    "store": "shop front street", "storefront": "shop front street", "counter": "shop counter",
    "customer": "customer paying shop", "customers": "shop counter customer",
    "sales": "cash register receipt", "sell": "market stall seller", "market": "market stall",
    "cash": "banknotes wallet", "invoice": "invoice paperwork", "bills": "paper bills desk",
    "budget": "notebook calculator desk", "ledger": "accounting ledger book",
    "ads": "advertising billboard street", "ad": "advertising billboard street",
    "advertising": "advertising billboard street", "marketing": "advertising billboard street",
    "commercial": "film set camera", "video": "video camera studio", "videos": "video camera studio",
    "camera": "film camera", "crew": "film crew camera", "film": "film crew camera",
    "studio": "video production studio", "production": "film set camera",
    "post": "smartphone social media", "posts": "smartphone social media",
    "feed": "smartphone social media", "scroll": "smartphone social media",
    "scrolls": "smartphone social media", "social": "smartphone social media",
    "graphics": "graphic design desk", "images": "photographs spread table",
    "product": "product packaging shelf", "shelf": "product shelf shop",
    "monday": "calendar planner desk", "weekly": "calendar planner desk",
    "calendar": "calendar planner desk", "data": "printed report",
    "city": "city skyline night", "street": "city street", "station": "train station platform",
    "train": "high speed train", "airport": "airport terminal", "plane": "airplane sky",
    "car": "car on road", "factory": "factory floor", "lab": "research laboratory",
    "space": "earth from space", "satellite": "satellite orbit", "rocket": "rocket launch",
    "phone": "smartphone in hand", "document": "paper documents desk", "report": "printed report",
    "money": "banknotes", "bank": "bank building", "government": "government building",
    "court": "courtroom", "police": "police car", "military": "soldiers", "soldier": "soldiers",
    "school": "school classroom", "university": "university building", "hospital": "hospital corridor",
    "energy": "power plant", "power": "electricity pylons", "water": "water treatment plant",
    "climate": "wind turbines", "map": "world map", "globe": "globe earth", "france": "paris street",
    "europe": "european city", "america": "american city", "china": "shanghai skyline",
    "war": "military vehicles", "history": "old archive photograph", "archive": "archive shelves",
    "book": "old books library", "newspaper": "newspaper printing press",
    "ফোনকল": "smartphone in hand", "ফোন": "smartphone in hand", "টাকা": "banknotes",
    "প্রতারিত": "hacker computer", "ফাঁদ": "cybersecurity operations centre",
    "কোড": "password keyboard", "পিন": "password keyboard", "ওটিপি": "password keyboard",
    "ব্যাংকিং": "mobile banking smartphone", "হেল্পলাইন": "call center headset operator",
    "সতর্ক": "security shield lock", "শেয়ার": "social media smartphone", "মানুষ": "people walking street",
}

ICON_RULES = [
    (r"ফোন|কল|মোবাইল|নম্বর", "wifi"),
    (r"টাকা|পেমেন্ট|ব্যাংক", "folder"),
    (r"প্রতারিত|ফাঁদ|প্রতারণা|ভুল", "warn"),
    (r"পিন|ওটিপি|কোড|পাসওয়ার্ড", "key"),
    (r"সতর্ক|বাঁচতে|রক্ষা|হেল্পলাইন", "shield"),
    (r"শেয়ার|ভিডিও", "target"),
    (r"রিপোর্ট|ব্লক", "lock"),
    (r"hack|exploit|attack|threat|breach|target|victim", "target"),
    (r"\bcode\b|script|terminal|command|program|software|tool", "terminal"),
    (r"\bai\b|agent|machine|model|automat|robot|system", "robot"),
    (r"patch|fix|update|secure|defen[cs]e|protect|shield", "shield"),
    (r"flaw|bug|vulnerab|weakness|error", "bug"),
    (r"report|news|study|published|research|finding", "news"),
    (r"server|data|cloud|database|records", "folder"),
    (r"password|key|credential|login|access", "key"),
    (r"watch|see|seen|observ|monitor|eye|spy", "eye"),
    (r"hour|minute|second|day|week|month|year|time|speed|fast|slow", "clock"),
    (r"lock|private|secret|encrypt", "padlock"),
    (r"launch|rocket|space|orbit", "rocket"),
    (r"search|find|found|discover|scan", "search"),
    (r"world|global|countr|nation|globe|internet", "globe"),
    (r"phone|wireless|wifi|network|signal|24", "wifi"),
    (r"human|people|person|team|investigator|operator|user", "finger"),
    (r"warn|danger|risk|important|critical|serious", "warn"),
    (r"before|after|versus|vs|compare|difference", "vs"),
    (r"france|french|paris|europe|city|location", "pin"),
    (r"site|website|browser|web", "globe"),
]
INKS = ["cyan", "amber", "coral", "lime", "violet", "peach", "mint", "pink", "white"]
INK_RGB = {"cyan": (72, 226, 255), "amber": (255, 210, 77), "coral": (255, 99, 88),
           "lime": (145, 255, 147), "violet": (198, 132, 255), "peach": (255, 158, 102),
           "mint": (110, 231, 197), "pink": (255, 110, 170), "white": (245, 243, 235)}


def words_of(s):
    return [w.strip(".,?!;:\"'()।") for w in s.split() if w.strip(".,?!;:\"'()।")]


def content_words(text):
    out = []
    for w in words_of(text):
        c = re.sub(r"[.,!?:;\"'()।]", "", w).strip()
        if len(c) < 2 or c.lower() in STOP or c.isdigit():
            continue
        if c not in out:
            out.append(c)
    return out


def pick_icon(text):
    for rx, icon in ICON_RULES:
        if re.search(rx, text, re.I):
            return icon
    return "news"


NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
             "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
             "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000}
PERCENT_RX = re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s?(?:%|percent\b)", re.I)
# "one in five", "nine out of ten": the line says a ratio, the screen says the rate
IN_RX = re.compile(r"\bone in (two|three|four|five|six|seven|eight|nine|ten)\b", re.I)
OUT_OF_RX = re.compile(r"\b(two|three|four|five|six|seven|eight|nine)\s+(?:out of|in)\s+ten\b", re.I)
WORD_PCT_RX = re.compile(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\s+percent\b", re.I)


def _spec(value, suffix, at):
    return {"value": value, "suffix": suffix,
            "display": f"{value}{suffix}", "at": max(0.0, min(0.95, at))}


def num_spec(text):
    """What number the line speaks, as a counter value, and where in the line it is said.

    Returns {value, suffix, display, at}; at is the fraction of the line where the number
    finishes being spoken, so a count-up can land on the word.
    """
    bn_digits = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    text = text.translate(bn_digits)
    low = text.lower()
    n = max(1, len(text))
    m = WORD_PCT_RX.search(low)
    if m:
        return _spec(NUM_WORDS[m.group(1)], "%", m.end() / n)
    m = PERCENT_RX.search(text)
    if m:
        v = float(m.group(1))
        return _spec(int(v) if v == int(v) else v, "%", m.end() / n)
    m = IN_RX.search(low)
    if m:
        return _spec(round(100 / NUM_WORDS[m.group(1)]), "%", m.end() / n)
    m = OUT_OF_RX.search(low)
    if m:
        return _spec(round(NUM_WORDS[m.group(1)] * 10), "%", m.end() / n)
    if re.search(r"\bhalf\b", low):
        m = re.search(r"\bhalf\b", low)
        return _spec(50, "%", m.end() / n)
    m = re.search(r"\b(\d[\d,]*)\b", text)
    if m:
        return _spec(int(m.group(1).replace(",", "")), "", m.end() / n)
    for w in words_of(text):
        c = w.lower()
        if c in NUM_WORDS:
            toks = words_of(text)
            j = [t.lower() for t in toks].index(c)
            before = toks[j - 1].lower().strip("\"'.,!?:;") if j else ""
            if c == "one" and before in ("the", "this", "that", "no", "every", "year"):
                continue                    # "the one nobody admits" is not a count
            if c in ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten") \
                    and before in ("mistake", "step", "part"):
                # an ordinal ("Mistake one"): a static numeral that pops on the word, no 0->1 roll
                return {"value": 0, "suffix": "", "display": c.upper(),
                        "at": max(0.0, min(0.95, text.lower().index(c) / n + 0.04))}
            return _spec(NUM_WORDS[c], "", text.lower().index(c) / n + 0.04)
    return None


def pick_number(text):
    spec = num_spec(text)
    if spec:
        return spec["display"]
    m = re.search(r"\b\d[\d,.]*\s?(?:million|billion|thousand|hours?|minutes?|seconds?|days?|weeks?|months?|years?|people|servers?)?\b", text, re.I)
    if m:
        return m.group(0).strip().rstrip(",.")
    return ""


def is_negation(text):
    """'That's a lie.' knocks down the number before it."""
    return bool(re.search(r"\b(lie|lies|wrong|false|myth|nonsense|no)\b", text.lower()))


def bars_for(text):
    """The bars a line's own numbers should draw: [(label, value), ...] or None."""
    low = text.lower()
    if "one in five" in low or "one in 5" in low:
        return [("YEAR 1", 20)]
    if re.search(r"\bhalf\b", low) or ("five" in low and "year" in low):
        return [("YEAR 1", 20), ("YEAR 5", 50)]
    if re.search(r"\b(ninety|eighty|seventy|sixty|fifty|forty|thirty|twenty)\s+percent\b", low) \
            or re.search(r"\b(90|80|70|60|50|40|30|20)\s?%", low):
        return [("THE CLAIM", num_spec(text)["value"] if num_spec(text) else 90)]
    return None


def pose_for(text):
    """A stickman pose and prop for a line about a person doing something."""
    low = text.lower()
    if re.search(r"\b(video|videos|camera|film|commercial|shoot|shooting)\b", low):
        return "camera", "camera"
    if re.search(r"\b(post|posts|posting|feed|scroll|scrolls|phone|social|images|graphics)\b", low):
        return "phone", "phone"
    if re.search(r"\b(build|building|product|offer|launch|launching|produce|producing)\b", low):
        return "build", "box"
    if re.search(r"\b(sales|cash|pay|paying|bills|money|spend|spending|watch|budget)\b", low):
        return "watch", "chart"
    if re.search(r"\b(nobody|notice|people|customer|customers)\b", low):
        return "idle", None
    return "walk", None


STICK_CUES = re.compile(r"\b(watch|watching|scroll|scrolls|scrolling|post|posts|posting|"
                        r"build|building|spend|spending|launch|launching|feed|camera|"
                        r"video|videos|shoot|shooting|film|films|pay|paying|produce|producing)\b", re.I)
CHAIN_CUES = re.compile(r"\b(three mistakes|three fixes|steps|step by step|stage|stages|"
                        r"pipeline|process|followed)\b", re.I)
CHECK_CUES = re.compile(r"\b(protect|prevent|secure|defen[cs]e|patch|fix|fixes|block|never|no longer)\b", re.I)
ACTION_CUES = re.compile(r"\b(do this|don't do this|do not do this)\b", re.I)
SPLIT_CUES = re.compile(r"\b(versus|vs\.?|compared|comparison|difference|changed|instead)\b|\bnot\b", re.I)
WINDOW_CUES = re.compile(r"\b(code|script|software|program|terminal|command|agent|model|algorithm|server)\b", re.I)
LAYOUTS = ("quote", "chain", "check", "split", "window", "stat", "graph", "stick")


def layout_scores(text, prev_bars=None):
    """How well each layout fits the line. Variety is enforced by the caller's use counts."""
    low = text.lower()
    sc = {"quote": 1.00, "chain": 0.45, "check": 0.55, "split": 0.00,
          "window": 0.60, "stat": 0.65, "graph": 0.30, "stick": 0.85}
    spec = num_spec(text)
    if spec:
        sc["stat"] += 1.40
        sc["graph"] += 0.55 if spec["suffix"] == "%" else 0.15
    if bars_for(text):
        sc["graph"] += 2.20
    if prev_bars and is_negation(text):
        sc["graph"] += 2.60                 # "that's a lie" gets the claim, struck out
    if STICK_CUES.search(low):
        sc["stick"] += 2.40
    elif not re.search(r"\bnobody\b", low):
        sc["stick"] -= 1.20                    # a stickman only for a line about doing something
    if CHAIN_CUES.search(low):
        sc["chain"] += 3.20
    if len(content_words(text)) < 2:
        sc["chain"] -= 2.00                    # a chain needs at least two words to link
        sc["check"] -= 2.00
    if CHECK_CUES.search(low):
        sc["check"] += 2.20
    if ACTION_CUES.search(low):
        sc["check"] += 3.00
    if not (CHECK_CUES.search(low) or ACTION_CUES.search(low)):
        sc["check"] -= 1.50                    # ticks only make sense on advice lines
    if SPLIT_CUES.search(low):
        sc["split"] += 2.80
    if re.search(r"(এক|দুই|তিন|কল কেটে|হেল্পলাইন|ব্লক|রিপোর্ট|কাউকে বলবেন না|কাউকে না|চাইবে না)", text):
        sc["check"] += 3.50
    if re.search(r"(ফোনে বলবে|কোড বলুন|ভাই|নম্বরে টাকা)", text):
        sc["window"] += 3.00
    if re.search(r"(অথবা|কিন্তু)", text):
        sc["split"] += 2.50
    if re.search(r"(সন্দেহ হলে|কী করবেন)", text):
        sc["chain"] += 2.80
    if WINDOW_CUES.search(low):
        sc["window"] += 3.20
    if text.rstrip().endswith("?"):
        sc["quote"] += 1.20
    if re.search(r"\b(is what|is how|is the one)\b", low):
        sc["quote"] += 1.20                 # a thesis line reads best at poster scale
    if re.search(r"\bnobody notices?\b", low):
        sc["quote"] += 1.20
    if len(content_words(text)) <= 1:
        sc["quote"] += 0.90                     # a two-word line wants big words, not a chart
    return sc


def choose_layout(idx, total, text, recent=(), counts=None, prev_bars=None):
    """Pick the best-fitting layout that has not just been used.

    recent: the last few layouts in order; counts: how often each has run in the film.
    A repeated layout loses weight, so the film keeps cutting to something new.
    """
    if idx == 0:
        return "title"
    if idx >= total - 2:
        return "end"
    sc = layout_scores(text, prev_bars)
    counts = counts or {}
    for lay in sc:
        sc[lay] -= 0.55 * list(recent).count(lay)
    if recent:
        if recent[-1] in sc:
            sc[recent[-1]] -= 3.00
        if len(recent) >= 2 and recent[-1] == recent[-2] and recent[-1] in sc:
            sc[recent[-1]] -= 1.20
    # a stat with no numeral would draw a content word at 700 px
    if not num_spec(text):
        sc["stat"] -= 4.0
    if not bars_for(text) and not (prev_bars and is_negation(text)):
        sc["graph"] -= 4.0
    return max(sc, key=sc.get)


def headline_of(text, limit=3):
    cw = content_words(text)
    if not cw:
        cw = [w for w in words_of(text) if len(w) >= 2][:limit]
    return " ".join(cw[:limit])


def kicker_of(scene):
    """'T02_patch_whiteboard' -> 'PATCH WHITEBOARD'; a markdown heading passes through."""
    s = re.sub(r"^[Tt]\d+[\s_-]*", "", scene or "")
    s = re.sub(r"[_\-]+", " ", s).strip()
    return s[:34].upper() or "STORY"


def points_of(text, n=3):
    cw = content_words(text)
    if len(cw) < n:
        extra = [w for w in words_of(text) if w not in cw and len(w) >= 2]
        cw += extra
    return cw[:n]


# No layout may repeat more than twice in a row: eight giant numerals in a row read as
# one long shot. The third repeat takes the quietest alternative that still fits.
BOARD_OF = {"title": "title", "split": "split", "chain": "chain", "window": "window",
            "check": "check", "stat": "stat", "end": "end", "quote": "quote",
            "graph": "graph", "stick": "stick"}
PHOTO_OF = {"title": "station", "split": "duo", "chain": "chain", "window": "doc",
            "check": "check", "stat": "stat", "end": "station", "quote": "quote",
            "graph": "graph", "stick": "stick"}


def visual_query(text):
    low = text.lower()
    best = None
    for key, q in VISUALS.items():
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            if best is None or len(key) > len(best[0]):
                best = (key, q)
    return best[1] if best else None


def group_blocks(segs, max_beats=2, max_span=4.6):
    """Short groups of 1-3 lines: the film cuts between the two looks every 3-5 seconds.

    A long block is where a storyboard starts repeating itself, so the default is tight;
    a line under 1.5s is folded into the block before it instead of flickering alone.
    """
    groups, cur = [], []
    for s in segs:
        if cur:
            span = s["end"] - cur[0]["start"]
            if len(cur) >= max_beats or span > max_span:
                groups.append(cur); cur = []
        cur.append(s)
    if cur:
        groups.append(cur)
    merged = []
    for g in groups:
        if merged:
            span = g[-1]["end"] - merged[-1][0]["start"]
            if (g[-1]["end"] - g[0]["start"]) < 1.5 and len(merged[-1]) < 3 and span <= 6.6:
                merged[-1] += g
                continue
        merged.append(g)
    return merged


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--photos", choices=["auto", "existing", "none"], default="auto")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    proj = paths.project_dirs(a.project)
    timing = paths.load_json(proj / "audio" / "timing.json")
    if not timing:
        raise SystemExit("audio/timing.json missing: run ingest.py first")
    script = paths.load_json(proj / "script.json", {"takes": []})
    title = (script.get("title") or "Untitled").strip()
    segs = timing["segments"]
    total = timing["total_duration"]
    photos = paths.load_json(proj / "photos.json", {}) or {}
    existing = [p["id"] for p in photos.get("photos", []) if p.get("id")]

    # ---- beats -------------------------------------------------------------
    beats = []
    seen_sections = set()
    recent, counts = [], {}
    prev_bars = None
    for i, s in enumerate(segs):
        text = s["caption"]
        lay = choose_layout(i, len(segs), text, recent, counts, prev_bars)
        spec = num_spec(text)
        num = spec["display"] if spec else ""
        line_len = max(0.05, s["end"] - s["start"])
        number_t = s["start"] + (spec["at"] if spec else 0.0) * line_len
        bars = bars_for(text)
        if bars:
            last = len(bars) - 1
            bars = [{"label": lbl, "value": val,
                     "at": (0.16 + k * 0.22) if k < last else None}
                    for k, (lbl, val) in enumerate(bars)]
        elif prev_bars and is_negation(text):
            claim = max(prev_bars, key=lambda x: x[1])
            bars = [{"label": "THE CLAIM", "value": claim[1], "at": 0.10, "strike": True}]
        pose, prop = pose_for(text)
        pts = points_of(text, 3)
        sec = s.get("scene") or ""
        section_first = sec not in seen_sections
        seen_sections.add(sec)
        beats.append({
            "id": s["id"], "start": s["start"], "end": s["end"], "caption": text,
            "spoken": s.get("vo", text), "block": None, "style": None, "layout": lay,
            "kicker": kicker_of(sec) if section_first else "", "headline": headline_of(text),
            "sub": "", "points": pts, "number": num,
            "number_value": spec["value"] if spec else 0,
            "number_suffix": spec["suffix"] if spec else "",
            "number_t": round(number_t, 3),
            "bars": bars, "strike": [k for k, bar in enumerate(bars or []) if bar.get("strike")],
            "pose": pose, "prop": prop,
            "icon": pick_icon(text),
            "ink": INKS[(i * 5 + a.seed) % len(INKS)], "photo": None,
            "query": visual_query(text),
        })
        prev_bars = bars_for(text)
        recent.append(lay)
        recent[:] = recent[-4:]
        counts[lay] = counts.get(lay, 0) + 1
    by_id = {b["id"]: b for b in beats}

    # ---- blocks ------------------------------------------------------------
    groups = group_blocks(segs)
    blocks = []
    for bi, g in enumerate(groups):
        style = "board" if bi % 2 == 0 else "photo"
        blocks.append({"index": bi, "style": style,
                       "start": g[0]["start"], "end": g[-1]["end"],
                       "beats": [s["id"] for s in g], "x0": bi * BLOCK_SPAN,
                       "photo": None, "query": None})
    if blocks and blocks[-1]["style"] != "board":     # end on the whiteboard, like the open
        blocks[-1]["style"] = "board"
        if len(blocks) > 2 and blocks[-2]["style"] == "board":
            blocks[-2]["style"] = "photo"

    # ---- photos ------------------------------------------------------------
    used_photos, photo_idx = {}, 0
    for blk in blocks:
        blk_beats = [by_id[i] for i in blk["beats"]]
        q = next((b["query"] for b in blk_beats if b["query"]), None)
        blk["query"] = q if blk["style"] == "photo" else None
        if a.photos == "none":
            continue
        if a.photos == "existing" and existing:
            blk["photo"] = existing[blk["index"] % len(existing)]
        elif q:
            if q in used_photos:
                blk["photo"] = used_photos[q]
            else:
                photo_idx += 1
                pid = f"P{photo_idx:02d}"
                used_photos[q] = pid
                blk["photo"] = pid
    for blk in blocks:
        for bid in blk["beats"]:
            b = by_id[bid]
            b["block"] = blk["index"]
            b["style"] = blk["style"]
            b["layout"] = (BOARD_OF if blk["style"] == "board" else PHOTO_OF)[b["layout"]]
            b["photo"] = blk["photo"]
            b["query"] = blk["query"] if blk["style"] == "photo" else None

    # ---- world layout + frames --------------------------------------------
    prev_f1 = 0
    for blk in blocks:
        step = BOARD_STEP if blk["style"] == "board" else PHOTO_STEP
        for k, bid in enumerate(blk["beats"]):
            by_id[bid]["x"] = blk["x0"] + 4700 + k * step
            by_id[bid]["y"] = 0
        # blocks are contiguous: each one starts where the previous ended, so the
        # stitch covers every frame of the film with no gaps between style changes
        blk["f0"] = prev_f1
        blk["f1"] = round(blk["end"] * FPS)
        blk["x_last"] = blk["x0"] + 4700 + (len(blk["beats"]) - 1) * step
        prev_f1 = blk["f1"]
    blocks[-1]["f1"] = round(total * FPS)

    plan = {"title": title, "fps": FPS, "duration": total, "blocks": blocks}
    paths.dump_json(proj / "beats.json", {"title": title, "fps": FPS, "duration": total,
                                          "beats": beats})
    paths.dump_json(proj / "plan.json", plan)

    # ---- human-readable table --------------------------------------------
    lines = [f"# {title} - beat table", "",
             f"{len(beats)} lines, {total / 60:.0f}:{total % 60:04.1f}, "
             f"{len(blocks)} blocks alternating board/photo.", "",
             "| # | Start | Len | Style | Layout | Headline | Photo | Narration |",
             "|---|---|---|---|---|---|---|---|"]
    for b in beats:
        lines.append(f"| {b['id']} | {int(b['start'] // 60)}:{b['start'] % 60:04.1f} | "
                     f"{b['end'] - b['start']:.1f}s | {b['style']} | {b['layout']} | "
                     f"{b['headline']} | {b['photo'] or ''} | {b['caption']} |")
    (proj / "beats.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    kinds = {}
    for b in beats:
        kinds[b["layout"]] = kinds.get(b["layout"], 0) + 1
    print(f"plan: {len(beats)} beats, {len(blocks)} blocks, {total:.1f}s")
    print("  layouts: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    print("  block lengths: " + " ".join(f"{b['end'] - b['start']:.1f}" for b in blocks))
    short = [b for b in blocks if b["end"] - b["start"] < 3.2]
    long = [b for b in blocks if b["end"] - b["start"] > 11.0]
    if short:
        print(f"  WARN {len(short)} block(s) under 3.2s: " + ", ".join(str(b['index']) for b in short))
    if long:
        print(f"  WARN {len(long)} block(s) over 11s: " + ", ".join(str(b['index']) for b in long))
    if len(blocks) < 5:
        print("  WARN fewer than 5 blocks: the two-style alternation will barely read")
    print(f"  wrote beats.json, plan.json, beats.md")
    queries = sorted({b["query"] for b in blocks if b["query"]})
    if queries:
        print("  photo queries: " + ", ".join(queries))


if __name__ == "__main__":
    main()
