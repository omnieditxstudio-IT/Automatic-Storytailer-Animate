#!/usr/bin/env python3
"""Burn the bottom-flush neon captions onto the stitched film, and write the SRT.

  python scripts/captions_burn.py --project my-film --video out/silent.mp4 --out out/captioned.mp4

Style is deterministic from the caption index: one of nine saturated candy inks, one of
seven eased entrances (rise, pop, slide, tilt, fade, wipe, stagger), one of four exits
(fade, drop, riseout, shrink), a three-pass bloom behind the line and a rainbow-gradient
sweep on the word being spoken (plus a white-hot core). Text is the voiceover, verbatim;
the last baseline sits 6 px above the bottom edge of a 720p frame and scales with the
render height.

Captions are drawn in screen space after the film finish, so they stay crisp at any
render size. The SRT is written next to the video.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

paths.add_engine_path()                       # engine, and the cinematic captions module
import engine
import skia

_orig_draw_text = engine.draw_text
_orig_text_width = engine.text_width

def _patched_draw_text(c, res, text, x, y, size, font="serif", rgb=engine.CREAM, a=1.0, track=0.0, align="left", reveal=None):
    if any(ord(ch) > 127 for ch in text):
        f = res.font(font, size)
        n = len(text) if reveal is None else int(reveal)
        shown = text[:n]
        if not shown:
            return 0
        total = f.measureText(shown)
        x0 = x - total / 2 if align == "center" else x - total if align == "right" else x
        p = engine.paint(rgb, a)
        blob = skia.TextBlob.MakeFromShapedText(shown, f)
        if blob:
            c.drawTextBlob(blob, x0, y, p)
        else:
            c.drawString(shown, x0, y, f, p)
        return total
    return _orig_draw_text(c, res, text, x, y, size, font, rgb, a, track, align, reveal)

def _patched_text_width(res, text, size, font="serif", track=0.0):
    if any(ord(ch) > 127 for ch in text):
        f = res.font(font, size)
        return f.measureText(text) + track * size * max(0, len(text) - 1)
    return _orig_text_width(res, text, size, font, track)

engine.draw_text = _patched_draw_text
engine.text_width = _patched_text_width

def draw_shaped(cv, text, x, y, font, p):
    if any(ord(ch) > 127 for ch in text):
        blob = skia.TextBlob.MakeFromShapedText(text, font)
        if blob:
            cv.drawTextBlob(blob, x, y, p)
            return
    cv.drawString(text, x, y, font, p)

MAX_WORDS = 7
PALETTE = [   # saturated candy inks, hot enough to bloom on a near-black board
    (56, 238, 255),    # cyan
    (255, 203, 41),    # amber
    (255, 79, 64),     # coral
    (128, 255, 96),    # lime
    (210, 110, 255),   # violet
    (255, 133, 74),    # peach
    (76, 255, 191),    # mint
    (255, 84, 178),    # pink
    (248, 246, 238),   # off-white
]
STYLES = ["rise", "pop", "slide", "tilt", "fade", "wipe", "stagger"]
EXITS = ["fade", "drop", "riseout", "shrink"]
# rainbow sweep for the hot word: violet -> blue -> cyan -> green -> yellow -> orange -> red
RAINBOW = [(178, 102, 255), (92, 148, 255), (72, 226, 255), (126, 255, 126),
           (255, 240, 92), (255, 158, 66), (255, 92, 92)]


def chunks(timing, max_words=MAX_WORDS):
    """[{'words': [(w, t)], 't0', 't1', 'idx'}], breaking at punctuation where sensible."""
    out, idx = [], 0
    for seg in timing["segments"]:
        disp = seg["caption"].replace('"', "").split()
        lens = [max(1, len(re.sub(r"[\s.,?!;:\"'()।]+", "", w))) for w in disp]
        s = sum(lens); acc = 0; ws = []
        dur = seg["end"] - seg["start"]
        for w, l in zip(disp, lens):
            ws.append((w, seg["start"] + dur * acc / s)); acc += l

        cur, lines = [], []
        for i, (w, t) in enumerate(ws):
            cur.append((w, t))
            if (len(cur) >= max_words or (w[-1] in ".,?!;:।" and len(cur) >= 3)
                    or i == len(ws) - 1):
                lines.append({"words": cur, "t0": cur[0][1]})
                cur = []
        if not lines:
            continue
        for a, b in zip(lines, lines[1:]):
            a["t1"] = b["t0"]
        lines[-1]["t1"] = seg["end"] + 0.3
        for c in lines:
            c["idx"] = idx
            idx += 1
        out += lines
    return out


def srt(timing, out, max_words=9):
    total = timing["total_duration"]

    def ts(x):
        ms = int(round(max(0.0, x) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    rows = chunks(timing, max_words)
    lines = []
    for i, c in enumerate(rows, 1):
        lines += [str(i), f"{ts(c['t0'])} --> {ts(min(c['t1'], total))}",
                  " ".join(w for w, _ in c["words"]), ""]
    pathlib.Path(out).write_text("\n".join(lines), encoding="utf-8")
    print(f"srt: {out} ({len(rows)} cues)")


def probe(video):
    info = paths.probe(video)
    return info["width"], info["height"], info["fps"], info["frames"]


class NeonCaptions:
    """Screen-space caption layer: bottom-centre, seeded ink + entrance, additive glow."""

    def __init__(self, width, height, timing, fonts_dir=None):
        import numpy as np
        import skia
        from engine import Res
        self.numpy = np
        self.skia = skia
        self.W, self.H = width, height
        self.k = width / 1920.0
        self.res = Res(width / 3840.0, None, fonts_dir)
        self.chunks = chunks(timing)
        self.surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(width, height, skia.ColorType.kRGBA_8888_ColorType,
                                skia.AlphaType.kPremul_AlphaType))

    def active(self, t):
        for c in self.chunks:
            if c["t0"] - 0.06 <= t < c["t1"]:
                return c
        return None

    def layer(self, t):
        c = self.active(t)
        if c is None:
            return None
        skia = self.skia
        with self.surface as cv:
            cv.clear(skia.Color(0, 0, 0, 0))
            self.draw(cv, c, t)
        return self.surface.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)

    def colors(self, c):
        rng = self.numpy.random.default_rng(c["idx"] * 7919 + 101)
        ink = PALETTE[(c["idx"] * 7 + 3) % len(PALETTE)]   # coprime cycle: neighbours never repeat
        style = STYLES[int(rng.integers(0, len(STYLES)))]
        exit_style = EXITS[int(rng.integers(0, len(EXITS)))]
        glow_gain = float(rng.uniform(1.05, 1.6))
        return ink, style, exit_style, glow_gain

    def draw(self, cv, c, t):
        from engine import paint, ramp, ease_out_cubic, draw_text, text_width
        skia, k = self.skia, self.k
        ink, style, exit_style, glow_gain = self.colors(c)
        size = 47 * k
        f = "cond"
        txt = " ".join(w for w, _ in c["words"]).upper()

        lines = [txt]
        if text_width(self.res, txt, size, f) > self.W * 0.74:
            ws = txt.split()
            half = len(ws) // 2 + len(ws) % 2
            lines = [" ".join(ws[:half]), " ".join(ws[half:])]

        e = ease_out_cubic(ramp(t, c["t0"] - 0.06, 0.26))          # entrance 0->1
        a_in = ramp(t, c["t0"] - 0.06, 0.16)
        e2 = ramp(t, c["t1"] - 0.12, 0.14)                         # exit 0->1
        a = a_in * (1 - e2)
        if style == "rise":
            oy, dx, rot, sc = (1 - e) * 52 * k, 0.0, 0.0, 1.0
        elif style == "pop":
            oy, dx, rot, sc = (1 - e) * 20 * k, 0.0, (1 - e) * 1.6, 0.58 + 0.42 * e
        elif style == "slide":
            oy, dx, rot, sc = 0.0, -(1 - e) * 88 * k, (1 - e) * -1.2, 1.0
        elif style == "tilt":
            oy, dx, rot, sc = (1 - e) * 30 * k, 0.0, -(1 - e) * 5.0, 1.0
        elif style == "fade":
            oy, dx, rot, sc = (1 - e) * 12 * k, 0.0, 0.0, 0.94 + 0.06 * e
        else:  # wipe / stagger: the motion lives in clip / per-word scale, not in bx/by
            oy, dx, rot, sc = 0.0, 0.0, 0.0, 1.0
        if exit_style == "drop":
            oy += e2 * e2 * 48 * k
            rot += e2 * 2.2
        elif exit_style == "riseout":
            oy -= e2 * e2 * 36 * k
        elif exit_style == "shrink":
            sc *= 1 - 0.15 * e2
        # "fade" exit: alpha only

        line_h = size * 1.24
        last_y = self.H - 6 * k - 0.22 * size        # last baseline: flush to the bottom edge
        y0 = last_y - (len(lines) - 1) * line_h
        bx, by = self.W / 2, y0 + (len(lines) - 1) * line_h / 2

        g = skia.GradientShader.MakeLinear(
            [skia.Point(0, self.H * 0.74), skia.Point(0, self.H)],
            [skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, int(165 * a))])
        gp = skia.Paint(); gp.setShader(g)
        cv.drawRect(skia.Rect.MakeXYWH(0, self.H * 0.74, self.W, self.H * 0.26), gp)

        def glow_passes(text, x, y, alpha, font):
            draw_shaped(cv, text, x, y, font,
                        paint(ink, min(1.0, 0.15 * glow_gain * alpha), blur=12 * k))
            draw_shaped(cv, text, x, y, font,
                        paint(ink, min(1.0, 0.1125 * glow_gain * alpha), blur=30 * k))
            draw_shaped(cv, text, x, y, font,
                        paint(ink, min(1.0, 0.0825 * glow_gain * alpha), blur=62 * k))
            draw_shaped(cv, text, x, y, font,
                        paint(ink, min(1.0, 0.05 * glow_gain * alpha), blur=95 * k))

        cv.save()
        if style == "wipe":                          # left-to-right reveal of the scrim line
            cv.clipRect(skia.Rect.MakeXYWH(0, 0, self.W * e, self.H))
        cv.translate(bx, by); cv.rotate(rot); cv.scale(sc, sc); cv.translate(-bx, -by)
        cv.translate(0, oy)
        gfont = self.res.font(f, size)
        for li, ln in enumerate(lines):
            y = y0 + li * line_h
            tw = text_width(self.res, ln, size, f)
            x_left = bx + dx - tw / 2
            cv.save(); cv.translate(0, 3.5 * k)
            if style != "stagger":        # stagger draws its shadow per word, with the word
                draw_shaped(cv, ln, x_left, y, gfont, paint((0, 0, 0), 0.75 * a, blur=5 * k))
            cv.restore()
            if style != "stagger":
                glow_passes(ln, x_left, y, a, gfont)
            x = x_left
            for wi, w in enumerate(ln.split()):
                gi = sum(len(l.split()) for l in lines[:li]) + wi
                if style == "stagger":
                    we = ease_out_cubic(ramp(t, c["t0"] - 0.06 + gi * 0.055, 0.24))
                    if we <= 0.0:
                        x += text_width(self.res, w, size, f) + text_width(self.res, " ", size, f)
                        continue
                    ww = text_width(self.res, w, size, f)
                    wa = a * we
                    cv.save(); cv.translate(0, 3.5 * k)
                    draw_shaped(cv, w, x, y, gfont, paint((0, 0, 0), 0.75 * wa, blur=5 * k))
                    cv.restore()
                    cv.save()
                    cv.translate(x + ww / 2, y)
                    cv.scale(0.55 + 0.45 * we, 0.55 + 0.45 * we)
                    cv.translate(-(x + ww / 2), -y)
                    glow_passes(w, x, y, wa, gfont)
                else:
                    wa = a
                is_cur = gi < len(c["words"]) and c["words"][gi][1] <= t + 0.02 and (
                    gi == len(c["words"]) - 1 or c["words"][gi + 1][1] > t + 0.02)
                if is_cur:
                    # bloom + rainbow sweep across the word + a thin white neon-tube stroke
                    ww = text_width(self.res, w, size, f)
                    draw_shaped(cv, w, x, y, gfont,
                                paint(ink, min(1.0, 0.2375 * wa), blur=12 * k))
                    rpts = [skia.Point(x, y), skia.Point(x + ww, y)]
                    rp = skia.Paint(); rp.setAntiAlias(True)
                    rp.setShader(skia.GradientShader.MakeLinear(
                        rpts, [skia.Color(r, g, b, int(255 * wa)) for r, g, b in RAINBOW]))
                    draw_shaped(cv, w, x, y, gfont, rp)
                    sp = skia.Paint(); sp.setAntiAlias(True)
                    sp.setStyle(skia.Paint.Style.kStroke_Style)
                    sp.setStrokeWidth(1.5 * k)
                    sp.setColor(skia.Color(255, 255, 255, int(225 * wa)))
                    draw_shaped(cv, w, x, y, gfont, sp)
                elif gi < len(c["words"]) and c["words"][gi][1] <= t + 0.02:
                    draw_text(cv, self.res, w, x, y, size, f, ink, wa)
                else:
                    draw_text(cv, self.res, w, x, y, size, f, ink, 0.5 * wa)
                if style == "stagger":
                    cv.restore()
                x += text_width(self.res, w, size, f) + text_width(self.res, " ", size, f)
        cv.restore()


def worker(args):
    video, f0, f1, fps, w, h, out, crf, timing, fonts_dir = args
    import numpy as np
    cap = NeonCaptions(w, h, timing, fonts_dir)
    y0 = int(h * 0.74)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video),
                            "-vf", f"trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                            *(["-rc-lookahead", "10", "-threads", "2"] if w >= 2000 else []),
                            "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    size = w * h * 3
    for n in range(f0, f1):
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        layer = cap.layer(n / fps)
        if layer is not None:
            frame = frame.copy()
            alpha = layer[y0:, :, 3:4].astype(np.float32) * (1 / 255.0)
            frame[y0:] = np.clip(frame[y0:].astype(np.float32) * (1 - alpha) + layer[y0:, :, :3],
                                 0, 255).astype(np.uint8)
        enc.stdin.write(frame.tobytes())
    enc.stdin.close(); enc.wait(); dec.wait()
    return f0, f1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default="out/captioned.mp4")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--srt-only", action="store_true")
    a = ap.parse_args()

    proj = pathlib.Path(a.project).resolve()
    timing = json.loads((proj / "audio" / "timing.json").read_text())
    out = pathlib.Path(a.out)
    out = (out if out.is_absolute() else proj / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if a.srt_only:
        srt(timing, out)
        return

    video = pathlib.Path(a.video)
    video = (video if video.is_absolute() else proj / video).resolve()

    # production cache: same stitched film + same timing + same encode + same caption code -> skip the burn
    cap_key = hashlib.sha256(
        paths.json_sig({"video": paths.file_sig(video),
                        "timing": paths.file_sig(proj / "audio" / "timing.json"),
                        "code": paths.file_sig(pathlib.Path(__file__)),
                        "crf": a.crf}).encode("utf-8")).hexdigest()
    hit_v = paths.cache_restore("captioned", cap_key, ".mp4", out, label="captioned")
    hit_s = paths.cache_restore("captioned", cap_key, ".srt",
                                out.with_suffix(".srt"), label="captioned")
    if hit_v and hit_s:
        print(f"captions: cache hit -> {out}  (srt restored)")
        return

    w, h, fps, nb = probe(video)
    work = proj / "out" / "burn"; work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("*.mp4"):
        old.unlink()
    k = max(1, min(a.workers, nb // 60 or 1))
    b = [nb * i // k for i in range(k + 1)]
    fonts_dir = str(proj / "fonts") if (proj / "fonts").exists() else None
    jobs = [(str(video), b[i], b[i + 1], fps, w, h, work / f"b{i:02d}.mp4", a.crf, timing, fonts_dir)
            for i in range(k)]
    t0 = time.time()
    with mp.get_context("spawn").Pool(k) as pool:
        for f0, f1 in pool.imap_unordered(worker, jobs):
            print(f"  captions {f0}-{f1}", flush=True)

    cmd = ["ffmpeg", "-v", "error", "-y"]
    for j in jobs:
        cmd += ["-i", str(j[6].resolve())]
    fc = "".join(f"[{i}:v]" for i in range(len(jobs))) + f"concat=n={len(jobs)}:v=1:a=0[outv]"
    cmd += ["-filter_complex", fc, "-map", "[outv]",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    srt(timing, out.with_suffix(".srt"))
    paths.cache_put("captioned", cap_key, ".mp4", out, label="captioned")
    paths.cache_put("captioned", cap_key, ".srt", out.with_suffix(".srt"), label="captioned")
    print(f"captioned: {out}  ({nb} frames) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
