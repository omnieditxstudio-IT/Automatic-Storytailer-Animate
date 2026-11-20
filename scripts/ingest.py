#!/usr/bin/env python3
"""Turn one voiceover file + one script file into the timing every later stage uses.

  python scripts/ingest.py --project my-film --voice voice.mp3 --script script.md
  python scripts/ingest.py --project my-film --voice v.wav --script s.txt --model base.en

Writes:
  audio/narration.m4a   the voice, normalised to 48 kHz stereo AAC
  script.json           takes/lines, ids in speaking order, caption = display text
  audio/timing.json     per-line start/end/duration/vo, exactly the schema engine.Doc reads

Alignment uses faster-whisper word timestamps and a fuzzy, monotonic matcher, so
ASR slips ("exploit" vs "exploits") do not break a line. Without faster-whisper (or
with --no-whisper) it falls back to speech-pause detection and syllable shares: the
film still builds, captions drift by a few tenths of a second.

Nothing here invents or edits the script. The text you pass is the text on screen.
"""
import argparse
import difflib
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

MAX_CHARS = 64
MAX_WORDS = 9


# ---------------------------------------------------------------- script parsing
def strip_md(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[*_`>#]+", "", s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2014", ", ").replace("\u2013", "-")
    return re.sub(r"\s+", " ", s).strip()


def sentences(par):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", par)
    return [p.strip() for p in parts if p.strip()]


def chunk(sentence, max_chars=MAX_CHARS, max_words=MAX_WORDS):
    """Split one sentence into caption-sized pieces, preferring punctuation breaks."""
    words = sentence.split()
    if len(sentence) <= max_chars and len(words) <= max_words:
        return [sentence]
    clauses, cur = [], []
    for w in words:
        cur.append(w)
        if w[-1] in ",;:" and len(" ".join(cur)) >= max_chars * 0.45:
            clauses.append(" ".join(cur)); cur = []
    if cur:
        clauses.append(" ".join(cur))
    out, cur = [], []
    for c in clauses:
        if cur and len(" ".join(cur + [c])) > max_chars:
            out.append(" ".join(cur)); cur = []
        cur.append(c)
    if cur:
        out.append(" ".join(cur))
    final = []
    for c in out:
        ws = c.split()
        while ws and (len(" ".join(ws)) > max_chars or len(ws) > max_words):
            take = ws[:max_words]
            while len(" ".join(take)) > max_chars and len(take) > 1:
                take.pop()
            final.append(" ".join(take)); ws = ws[len(take):]
        if ws:
            final.append(" ".join(ws))
    return [f for f in final if f]


def parse_text(text):
    takes, cur = [], {"take": "Narration", "lines": []}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            title = strip_md(line).strip(" :-")
            if cur["lines"]:
                takes.append(cur)
            cur = {"take": title or f"Section {len(takes) + 1}", "lines": []}
            continue
        if not line:
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        for s in sentences(strip_md(line)):
            for c in chunk(s):
                cur["lines"].append({"text": c, "spoken": c})
    if cur["lines"]:
        takes.append(cur)
    return takes


def parse_script(path):
    p = pathlib.Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        spec = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(spec, dict) and "takes" in spec:
            takes = spec["takes"]
        elif isinstance(spec, list):
            takes = [{"take": spec[0].get("take", "Narration") if isinstance(spec[0], dict) else "Narration",
                      "lines": [{"text": l, "spoken": l} if isinstance(l, str) else l for l in spec]}]
        else:
            raise SystemExit("script.json: expected {'takes': [...]} or a list of lines")
    elif suffix == ".srt":
        raw = p.read_text(encoding="utf-8", errors="ignore")
        cues = re.split(r"\n\s*\n", raw)
        lines = []
        for c in cues:
            body = [l for l in c.splitlines() if l.strip() and not l.strip().isdigit()
                    and "-->" not in l]
            if body:
                lines.append({"text": strip_md(" ".join(body)), "spoken": strip_md(" ".join(body))})
        takes = [{"take": "Narration", "lines": lines}]
    else:
        takes = parse_text(p.read_text(encoding="utf-8", errors="ignore"))
    flat = []
    for t in takes:
        for l in t["lines"]:
            text = strip_md(l.get("text") or l.get("spoken") or "")
            if not text:
                continue
            flat.append({"take": t["take"], "text": text,
                         "spoken": l.get("spoken") or text})
    if not flat:
        raise SystemExit(f"{path}: no lines found")
    return flat


def spoken_form(s):
    s = s.replace("&", " and ").replace("%", " percent ").replace("$", " dollars ")
    s = s.replace("@", " at ").replace("+", " plus ").replace("=", " equals ")
    s = re.sub(r"[/\\]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------- alignment
def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def fuzzy(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4:
        if a.startswith(b) or b.startswith(a):
            return 0.92
        r = difflib.SequenceMatcher(None, a, b).ratio()
        return r if r >= 0.80 else 0.0
    return 0.0


def whisper_words(voice, model_size, device):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device=device,
                         compute_type="int8" if device == "cpu" else "float16")
    segments, info = model.transcribe(str(voice), word_timestamps=True, language="en",
                                      vad_filter=True, beam_size=1)
    words = []
    for seg in segments:
        for w in seg.words or []:
            c = norm(w.word)
            if c:
                words.append({"w": c, "start": float(w.start), "end": float(w.end)})
    return words, float(info.duration or 0.0)


def align_line(targets, words, pointer, lookahead=12):
    """Greedy fuzzy match of the line's words into the transcript from `pointer`.
    Returns (matched transcript indices, new pointer, matched fraction)."""
    i, hits = pointer, []
    for t in targets:
        found = -1
        for j in range(i, min(len(words), i + lookahead)):
            if fuzzy(t, words[j]["w"]) >= 0.82:
                found = j
                break
        if found >= 0:
            hits.append(found)
            i = found + 1
    frac = len(hits) / max(1, len(targets))
    return hits, i, frac


def speech_spans(voice, dur):
    """[(start, end)] of speech, from ffmpeg silencedetect; one span if detection fails."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(voice), "-af",
                        "silencedetect=noise=-34dB:d=0.30", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(m.group(1)) for m in re.finditer(r"silence_end: ([\d.]+)", r.stderr)]
    spans, t = [], 0.0
    for s in starts:
        if s > t + 0.05:
            spans.append((t, s))
        t = max(t, s)
        for e in ends:
            if e > t:
                t = e
                break
    if dur > t + 0.05:
        spans.append((t, dur))
    return spans or [(0.0, dur)]


def fallback_times(lines, voice, dur):
    """Distribute lines over detected speech spans by syllable share."""
    spans = speech_spans(voice, dur)
    speech = sum(b - a for a, b in spans)
    weights = [max(3, len(re.findall(r"[aeiouy]+", l["spoken"].lower()))) for l in lines]
    total = sum(weights)
    out, si, used = [], 0, 0.0
    for l, w in zip(lines, weights):
        want = speech * w / total
        a, b = spans[min(si, len(spans) - 1)]
        start = a + used
        while si < len(spans) - 1 and start + want > spans[si][1]:
            si += 1; used = 0.0
            a, b = spans[si]
            start = a
        end = min(b, start + want)
        out.append((start, max(start + 0.4, end)))
        used += want
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--model", default="tiny.en", help="faster-whisper size (tiny.en, base.en, small.en)")
    ap.add_argument("--device", default="cpu", help="cpu or cuda")
    ap.add_argument("--no-whisper", action="store_true")
    a = ap.parse_args()

    proj = paths.project_dirs(a.project)
    voice_src = pathlib.Path(a.voice).resolve()
    if not voice_src.exists():
        raise SystemExit(f"voice not found: {voice_src}")
    narration = proj / "audio" / "narration.m4a"
    paths.ffmpeg("-i", voice_src, "-vn", "-ac", "2", "-ar", "48000",
                 "-c:a", "aac", "-b:a", "256k", narration)
    dur = paths.probe(narration)["duration"]

    flat = parse_script(a.script)
    title = pathlib.Path(a.script).stem.replace("_", " ").replace("-", " ").strip().title()
    if pathlib.Path(a.script).suffix.lower() == ".json":
        try:
            spec = json.loads(pathlib.Path(a.script).read_text(encoding="utf-8", errors="ignore"))
            if isinstance(spec, dict) and spec.get("title"):
                title = str(spec["title"]).strip()
        except Exception:
            pass
    lines = []
    for i, l in enumerate(flat, 1):
        lines.append({"id": i, "take": l["take"], "caption": l["text"],
                      "spoken": spoken_form(l["spoken"])})
    print(f"script: {len(lines)} lines, {len(set(l['take'] for l in lines))} sections, "
          f"voice {dur:.2f}s")

    timed, used_whisper = [], False
    if not a.no_whisper:
        cache_key = hashlib.sha256(
            f"{paths.file_sig(voice_src)}|{a.model}|{a.device}|en".encode("utf-8")
        ).hexdigest()
        wlabel = f"{pathlib.Path(a.voice).stem}-{a.model}"
        cached = paths.cache_get("whisper", cache_key, ".json", label=wlabel)
        if cached:
            try:
                payload = paths.load_json(cached)
                words, wdur = payload["words"], payload["duration"]
                print(f"whisper: cached ({len(words)} words, key {cache_key[:10]}) for {a.model}")
                used_whisper = True
                pointer = 0
                for l in lines:
                    targets = [norm(w) for w in l["spoken"].split()]
                    targets = [t for t in targets if t]
                    hits, pointer, frac = align_line(targets, words, pointer)
                    if frac >= 0.45 and hits:
                        timed.append({"start": words[hits[0]]["start"],
                                      "end": words[hits[-1]]["end"], "frac": frac})
                    else:
                        timed.append({"start": None, "end": None, "frac": frac})
            except Exception as e:
                print(f"whisper cache unreadable ({e}); re-transcribing")
                cached = None
        if not cached and not used_whisper:
            try:
                print(f"transcribing with {a.model} ({a.device}) ...", flush=True)
                words, wdur = whisper_words(narration, a.model, a.device)
                print(f"whisper: {len(words)} words, {wdur:.2f}s", flush=True)
                tmp = paths.dump_json(proj / "audio" / ".whisper_cache.json",
                                      {"words": words, "duration": wdur})
                paths.cache_put("whisper", cache_key, ".json", tmp, label=wlabel)
                tmp.unlink(missing_ok=True)
                if len(words) < len(lines):
                    raise RuntimeError(f"only {len(words)} words for {len(lines)} lines")
                pointer = 0
                for l in lines:
                    targets = [norm(w) for w in l["spoken"].split()]
                    targets = [t for t in targets if t]
                    hits, pointer, frac = align_line(targets, words, pointer)
                    if frac >= 0.45 and hits:
                        timed.append({"start": words[hits[0]]["start"],
                                      "end": words[hits[-1]]["end"], "frac": frac})
                    else:
                        timed.append({"start": None, "end": None, "frac": frac})
                used_whisper = True
            except SystemExit:
                raise
            except Exception as e:               # keep the pipeline alive; say exactly why
                print(f"whisper unavailable ({type(e).__name__}: {e}); using pause alignment", flush=True)

    if not used_whisper:
        for l, (s, e) in zip(lines, fallback_times(lines, narration, dur)):
            timed.append({"start": s, "end": e, "frac": 1.0})

    # weak lines: interpolate between strong neighbours
    for i, t in enumerate(timed):
        if t["start"] is not None:
            continue
        prev_end = next((timed[j]["end"] for j in range(i - 1, -1, -1) if timed[j]["end"] is not None), 0.0)
        nxt = next((timed[j]["start"] for j in range(i + 1, len(timed)) if timed[j]["start"] is not None), dur)
        span = max(0.6, (nxt - prev_end) / max(1, sum(1 for j in range(i, len(timed)) if timed[j]["start"] is None) + 1))
        t["start"], t["end"] = prev_end + 0.02, min(nxt, prev_end + span)

    # monotonic pass
    prev = 0.0
    for i, (l, t) in enumerate(zip(lines, timed)):
        start = max(t["start"], prev + 0.01)
        end = max(t["end"], start + 0.45)
        t["start"], t["end"] = start, end
        prev = end

    segments = []
    for l, t in zip(lines, timed):
        segments.append({
            "id": l["id"], "scene": l["take"], "caption": l["caption"], "vo": l["spoken"],
            "start": round(t["start"], 3), "end": round(t["end"], 3),
            "duration": round(t["end"] - t["start"], 3),
        })
    total = round(max(dur, segments[-1]["end"] + 2.0), 3)
    timing = {"total_duration": total, "lead_in": segments[0]["start"],
              "tail_out": round(total - segments[-1]["end"], 3), "tempo": 1.0,
              "segments": segments}
    paths.dump_json(proj / "audio" / "timing.json", timing)

    takes, order = {}, []
    for seg in segments:
        if seg["scene"] not in takes:
            takes[seg["scene"]] = []
            order.append(seg["scene"])
        takes[seg["scene"]].append({"id": seg["id"], "text": seg["caption"], "spoken": seg["vo"]})
    paths.dump_json(proj / "script.json",
                    {"title": title,
                     "takes": [{"take": k, "lines": takes[k]} for k in order]})

    weak = sum(1 for t in timed if t["frac"] < 0.45)
    print(f"timing: audio/timing.json  total {total:.2f}s  lead-in {segments[0]['start']:.2f}s")
    print(f"  weak lines {weak}/{len(segments)}   method {'whisper' if used_whisper else 'pauses'}")
    for s in segments[:3] + segments[-3:]:
        print(f"  {s['id']:>3} {s['start']:7.2f}-{s['end']:7.2f} "
              f"({s['duration']:4.1f}s) {s['caption'][:58]}")
    bad = [s for s in segments if s["duration"] > 12 or s["duration"] < 0.55]
    if bad:
        print("  check these line lengths (caption readability):")
        for s in bad[:8]:
            print(f"    {s['id']:>3} {s['duration']:5.2f}s  {s['caption']}")


if __name__ == "__main__":
    main()
