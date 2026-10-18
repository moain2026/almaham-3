"""Synthetic meter scenes with PER-DIGIT boxes, for training the digit detector (training data only).

Every sample is rendered from scratch: background -> meter body(ies) -> LCD window -> seven-segment lines
(main reading + optional secondary lines) -> printed labels / serial / barcode / Arabic handwriting ->
geometric + photometric degradation. No real customer photo is ever read here.

Two sample kinds share one renderer:
  * scene_sample(): 256x256 crop that simulates the reader's rectangle (pass 1 of the engine).
  * line_sample():  64x320 crop around the main line with localisation jitter (pass 2 of the engine).

Labels: list of (cls, x1, y1, x2, y2) in output-pixel coordinates.
  cls 0..9 = seven-segment digit, 10 = decimal dot, 11 = a whole main reading line (integer + decimals).
  In panels every visible meter's main line is labelled LINE; choosing the target line is post-processing.
Printed (non seven-segment) digits are deliberately NOT labelled: they are hard negatives.
Seven-segment digits of secondary lines (A/V/Hz/kW) ARE labelled as digits; the assembly step picks the main line.
"""
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import paths

SCENE = 256
LINE_H, LINE_W = 64, 448
CLS_DOT, CLS_LINE = 10, 11
RENDER = 640  # internal render size; line crops are taken from this resolution
PAD_GREY = (128, 128, 128)  # == MeterReader.letterboxed() border colour

SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
       "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}
ALL = "abcdefg"
DSEG_DIR = paths.FONTS / "dseg"
DSEG_FONTS = sorted(str(p) for p in DSEG_DIR.glob("DSEG7*.ttf"))
FONTS_AR = [str(paths.FONTS / "Tajawal-Bold.ttf"), str(paths.FONTS / "IBMPlexSansArabic-Bold.ttf")]
FONT_LAT = str(paths.FONTS / "DejaVuSans-Bold.ttf")
AR_WORDS = ["محمد", "عبدالله", "احمد", "علي", "صالح", "ابراهيم", "حسن", "منزل", "عداد", "فاطمة", "سعيد", "ناصر",
            "دور", "شقة", "محل", "مسجد"]
LAT_TEXT = ["Single Phase Static kWh Meter", "IEC62052-11", "IEC62053-21", "5(60)A 230V 50Hz", "10(100)A 220V",
            "1600imp/kWh", "1000 imp/kWh", "SMART MT10-ALPHA", "TOMAS", "CRYSTAL", "TAGADOD", "Class 1.0",
            "DDS238-2", "kWh", "Imp", "Model", "Type", "Made in China", "YEMEN ELECTRICITY"]
UNITS = ["kWh", "kW", "V", "A", "Hz", "kvarh", "T1", "T2", "IMP", "EXP", "LAST", "DATE"]
_font_cache = {}


def font(path, size):
    key = (path, int(size))
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, max(6, int(size)))
    return _font_cache[key]


def rand_color(lo=0, hi=255):
    return tuple(int(random.uniform(lo, hi)) for _ in range(3))


def mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


# ----------------------------------------------------------------------------------------------
# seven-segment glyph renderers (procedural polygons and DSEG fonts), both return digit boxes
# ----------------------------------------------------------------------------------------------
def seg_polys(x, y, w, h, t, slant):
    g = t * 0.12
    hh = h / 2

    def P(pts):
        return np.array([(px + slant * (h - py), py) for px, py in pts], np.float32) + (x, y)

    def hseg(yc):
        return P([(g + t / 2, yc), (g + t, yc - t / 2), (w - g - t, yc - t / 2), (w - g - t / 2, yc),
                  (w - g - t, yc + t / 2), (g + t, yc + t / 2)])

    def vseg(xc, y0, y1):
        return P([(xc, y0 + g + t / 2), (xc + t / 2, y0 + g + t), (xc + t / 2, y1 - g - t), (xc, y1 - g - t / 2),
                  (xc - t / 2, y1 - g - t), (xc - t / 2, y0 + g + t)])

    return {"a": hseg(t / 2), "g": hseg(hh), "d": hseg(h - t / 2), "f": vseg(t / 2, 0, hh), "b": vseg(w - t / 2, 0, hh),
            "e": vseg(t / 2, hh, h), "c": vseg(w - t / 2, hh, h)}


def draw_digit_proc(canvas, ch, x, y, w, h, t, slant, fg, ghost, ghost_on):
    polys = seg_polys(x, y, w, h, t, slant)
    on = SEG.get(ch, "")
    for s in ALL:
        if s in on:
            col = fg
        elif ghost_on:
            col = ghost
        else:
            continue
        cv2.fillPoly(canvas, [np.round(polys[s] * 4).astype(np.int32)], col, cv2.LINE_AA, shift=2)
    return (x, y, x + w + slant * h, y + h)


class SegStyle:
    """One consistent seven-segment typeface for a whole display."""

    def __init__(self, dh):
        self.dh = dh
        self.use_font = bool(DSEG_FONTS) and random.random() < 0.5
        self.slant = random.uniform(0.0, 0.16) if random.random() < 0.6 else 0.0
        self.t = dh * random.uniform(0.09, 0.18)
        self.dw = dh * random.uniform(0.46, 0.62)
        self.pitch = self.dw * random.uniform(1.12, 1.4)
        if self.use_font:
            self.path = random.choice(DSEG_FONTS)
            self.f = font(self.path, dh * 1.3)
            bb = self.f.getbbox("8")
            self.scale = dh / max(1, (bb[3] - bb[1]))
            self.f = font(self.path, dh * 1.3 * self.scale)
            bb = self.f.getbbox("8")
            self.gh = bb[3] - bb[1]
            self.gw = bb[2] - bb[0]
            self.goff = (bb[0], bb[1])
            self.dw = self.gw
            self.pitch = self.f.getlength("8") * random.uniform(1.0, 1.15)

    def scaled(self, k):
        s = SegStyle.__new__(SegStyle)
        s.__dict__.update(self.__dict__)
        s.dh = self.dh * k
        s.t = self.t * k
        s.dw = self.dw * k
        s.pitch = self.pitch * k
        if self.use_font:
            s.f = font(self.path, self.dh * 1.3 * self.scale * k)
            bb = s.f.getbbox("8")
            s.gh, s.gw, s.goff = bb[3] - bb[1], bb[2] - bb[0], (bb[0], bb[1])
            s.dw = s.gw
            s.pitch = s.f.getlength("8") * (self.pitch / self.f.getlength("8"))
        return s

    def draw_text(self, canvas, text, x, y, fg, ghost, ghost_on):
        """Draw a run of seven-segment characters; return list of (ch, box). Spaces advance only."""
        boxes = []
        if self.use_font:
            pim = Image.fromarray(canvas)
            d = ImageDraw.Draw(pim)
            cx = x
            for ch in text:
                if ch == " ":
                    if ghost_on:
                        d.text((cx - self.goff[0], y - self.goff[1]), "8", font=self.f, fill=ghost)
                    cx += self.pitch
                    continue
                if ch == ".":
                    continue
                if ghost_on:
                    d.text((cx - self.goff[0], y - self.goff[1]), "8", font=self.f, fill=ghost)
                d.text((cx - self.goff[0], y - self.goff[1]), ch, font=self.f, fill=fg)
                boxes.append((ch, (cx, y, cx + self.gw, y + self.gh)))
                cx += self.pitch
            canvas[:] = np.asarray(pim)
            return boxes, cx
        cx = x
        for ch in text:
            if ch == " ":
                if ghost_on:
                    draw_digit_proc(canvas, "", cx, y, self.dw, self.dh, self.t, self.slant, fg, ghost, True)
                cx += self.pitch
                continue
            if ch == ".":
                continue
            b = draw_digit_proc(canvas, ch, cx, y, self.dw, self.dh, self.t, self.slant, fg, ghost, ghost_on)
            boxes.append((ch, b))
            cx += self.pitch
        return boxes, cx


# ----------------------------------------------------------------------------------------------
# display content
# ----------------------------------------------------------------------------------------------
def random_reading():
    style = random.choices(["six_dec2_big", "six_dec2_small", "six_dec1", "crystal", "five_dec2", "seven_dec1",
                            "six_nodec"], [0.28, 0.3, 0.1, 0.14, 0.06, 0.05, 0.07])[0]
    if style == "crystal":
        n = random.choices([1, 2, 3, 4, 5], [0.1, 0.35, 0.3, 0.15, 0.1])[0]
        ip = str(random.randint(10 ** (n - 1) if n > 1 else 0, 10 ** n - 1))
        return style, ip, "%02d" % random.randint(0, 99)
    ndig = {"six_dec2_big": 6, "six_dec2_small": 6, "six_dec1": 6, "five_dec2": 5, "seven_dec1": 7, "six_nodec": 6}[style]
    mag = random.choices([1, 2, 3, 4, 5, 6], [0.03, 0.1, 0.25, 0.4, 0.17, 0.05])[0]
    mag = min(mag, ndig)
    v = random.randint(0, 10 ** mag - 1)
    ip = str(v).zfill(ndig)
    if style == "six_nodec":
        return style, ip, ""
    dec = "%d" % random.randint(0, 9) if style in ("six_dec1", "seven_dec1") else "%02d" % random.randint(0, 99)
    return style, ip, dec


def lcd_palette():
    kind = random.choices(["grey", "green", "blue", "white", "yellow", "dark", "amber"],
                          [0.3, 0.17, 0.15, 0.12, 0.14, 0.06, 0.06])[0]
    bg = {"grey": (160, 170, 165), "green": (120, 190, 140), "blue": (215, 180, 130), "white": (228, 232, 228),
          "yellow": (110, 185, 200), "dark": (60, 70, 65), "amber": (60, 150, 230)}[kind]
    bg = tuple(int(np.clip(c + random.randint(-30, 30), 15, 250)) for c in bg)
    base = float(np.mean(bg))
    dark = base > 95
    fg_l = random.uniform(5, 55) if dark else random.uniform(170, 255)
    fg = tuple(int(np.clip(fg_l + random.randint(-15, 15), 0, 255)) for _ in range(3))
    if kind == "blue" and random.random() < 0.5:  # bluish dark segments
        fg = (int(min(255, fg[0] + 60)), fg[1], fg[2])
    contrast = random.choices([random.uniform(0.1, 0.3), random.uniform(0.3, 0.65), random.uniform(0.65, 1.0)],
                              [0.3, 0.35, 0.35])[0]
    fg = mix(bg, fg, contrast)
    ga = random.choices([0.0, random.uniform(0.05, 0.2), random.uniform(0.2, 0.5)], [0.3, 0.4, 0.3])[0]
    ghost = mix(bg, fg, ga)
    if kind == "blue" and random.random() < 0.5:  # TAGADOD-like light-blue ghosts
        ghost = mix(bg, (240, 200, 150), ga * 1.2)
    return bg, fg, ghost, ga > 0


def render_display(lw, lh):
    """Render an LCD panel (lw x lh) with a main line + optional secondary lines/icons.
    Returns panel BGR, boxes [(cls, x1,y1,x2,y2)] (digits, dots and the main line box)."""
    bg, fg, ghost, ghost_on = lcd_palette()
    panel = np.full((lh, lw, 3), bg, np.uint8)
    # subtle LCD texture / gradient
    gy = np.linspace(random.uniform(0.9, 1.05), random.uniform(0.9, 1.05), lh)[:, None, None]
    panel = np.clip(panel.astype(np.float32) * gy, 0, 255).astype(np.uint8)
    style, ip, dec = random_reading()
    ncell = len(ip) + len(dec) + (1 if dec else 0)
    dh = lh * random.uniform(0.38, 0.6)
    st = SegStyle(dh)
    total_w = st.pitch * (len(ip) + 0.2)
    small = style in ("six_dec2_small", "crystal") and random.random() < 0.8
    dec_k = random.uniform(0.42, 0.65) if small else 1.0
    total_w += st.pitch * dec_k * len(dec) + (st.pitch * 0.25 if dec else 0)
    if total_w > lw * 0.9:  # shrink to fit
        k = lw * 0.9 / total_w
        st = st.scaled(k)
        dh *= k
        total_w *= k
    x0 = random.uniform(lw * 0.03, max(lw * 0.03, lw - total_w - lw * 0.03))
    y0 = lh * random.uniform(0.08, 0.3)
    if lh - dh < y0:
        y0 = max(0, (lh - dh) / 2)
    boxes = []
    cells = list(ip)
    if style == "crystal":
        cells = [" "] * random.randint(0, 6 - len(ip)) + cells
    bx, cx = st.draw_text(panel, "".join(cells), x0, y0, fg, ghost, ghost_on)
    for ch, b in bx:
        boxes.append((int(ch), *b))
    line_boxes = [b for _, b in bx]
    if dec:
        dot_r = max(1.5, st.t * random.uniform(0.3, 0.6))
        dot_x = cx - st.pitch * random.uniform(0.08, 0.2)
        dot_y = y0 + dh - dot_r
        if dec_k >= 1 or random.random() < 0.9:  # full-size decimals always carry a visible dot
            cv2.circle(panel, (int(dot_x), int(dot_y)), int(round(dot_r)), fg, -1, cv2.LINE_AA)
            boxes.append((CLS_DOT, dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r))
        sst = st.scaled(dec_k) if dec_k < 1 else st
        sy = y0 + dh - sst.dh
        sx = cx + st.pitch * random.uniform(0.02, 0.2)
        bx2, cx = sst.draw_text(panel, dec, sx, sy, fg, ghost, ghost_on)
        for ch, b in bx2:
            boxes.append((int(ch), *b))
        line_boxes += [b for _, b in bx2]
    lb = np.array(line_boxes)
    boxes.append((CLS_LINE, lb[:, 0].min(), lb[:, 1].min(), lb[:, 2].max(), lb[:, 3].max()))
    # unit text right of / above the line
    if random.random() < 0.75:
        put_text(panel, random.choice(UNITS), cx + random.uniform(2, lw * 0.04), y0 + dh * random.uniform(0.3, 1.0),
                 dh * random.uniform(0.25, 0.5), fg)
    if random.random() < 0.4:
        put_text(panel, random.choice(UNITS + ["T1", "Σ", "IMP"]), x0, y0 - dh * 0.15, dh * 0.25, fg)
    # secondary seven-segment lines below (labelled as digits, not as main line)
    yy = y0 + dh * random.uniform(1.2, 1.6)
    n_sec = random.choices([0, 1, 2], [0.5, 0.35, 0.15])[0]
    for _ in range(n_sec):
        if yy + dh * 0.5 > lh:
            break
        k = random.uniform(0.35, 0.6)
        sst = st.scaled(k)
        txt = random.choice(["%d.%03d" % (random.randint(0, 9), random.randint(0, 999)),
                             "%02d.%02d" % (random.randint(0, 59), random.randint(0, 99)),
                             "%03d.%d" % (random.randint(100, 250), random.randint(0, 9)),
                             "%d.%d" % (random.randint(0, 9), random.randint(0, 9)), str(random.randint(0, 99999))])
        sx = x0 + random.uniform(0, st.pitch * 2)
        bxs, ex = sst.draw_text(panel, txt.replace(".", ""), sx, yy, fg, ghost, ghost_on)
        for ch, b in bxs:
            boxes.append((int(ch), *b))
        if "." in txt:
            i = txt.index(".")
            dx = sx + sst.pitch * i - sst.pitch * 0.12
            r = max(1, sst.t * 0.4)
            cv2.circle(panel, (int(dx), int(yy + sst.dh - r)), int(r), fg, -1, cv2.LINE_AA)
            boxes.append((CLS_DOT, dx - r, yy + sst.dh - 2 * r, dx + r, yy + sst.dh))
        put_text(panel, random.choice(["A", "V", "Hz", "kW", "kWh"]), ex + 2, yy + sst.dh, sst.dh * 0.6, fg)
        yy += sst.dh * random.uniform(1.3, 1.8)
    # icons / battery / arrows
    for _ in range(random.randint(0, 4)):
        ix, iy = random.uniform(0, lw * 0.9), random.uniform(0, lh * 0.9)
        s = dh * random.uniform(0.15, 0.4)
        kind = random.random()
        if kind < 0.4:
            cv2.rectangle(panel, (int(ix), int(iy)), (int(ix + s * 1.6), int(iy + s * 0.8)), fg, 1)
        elif kind < 0.7:
            pts = np.array([(ix, iy + s), (ix + s / 2, iy), (ix + s, iy + s)], np.int32)
            cv2.polylines(panel, [pts], True, fg, 1, cv2.LINE_AA)
        else:
            cv2.circle(panel, (int(ix), int(iy)), int(s / 2), fg, -1)
    # coarse LCD pixel grain (23069-like) and faint column lines
    if random.random() < 0.35:
        g = np.random.normal(0, random.uniform(6, 18), (lh // 2 + 1, lw // 2 + 1, 1)).astype(np.float32)
        g = cv2.resize(g, (lw, lh), interpolation=cv2.INTER_NEAREST)[..., None]
        panel = np.clip(panel.astype(np.float32) + g, 0, 255).astype(np.uint8)
    if random.random() < 0.25:
        step = random.randint(3, 7)
        panel[:, ::step] = np.clip(panel[:, ::step].astype(np.int16) - random.randint(5, 20), 0, 255).astype(np.uint8)
    # polariser streaks / reflections inside glass
    if random.random() < 0.5:
        f = panel.astype(np.float32)
        for _ in range(random.randint(1, 3)):
            p1 = (random.randint(0, lw), random.randint(0, lh))
            p2 = (random.randint(0, lw), random.randint(0, lh))
            cv2.line(f, p1, p2, (random.uniform(200, 255),) * 3, random.randint(1, max(2, lh // 10)), cv2.LINE_AA)
        panel = np.clip(panel * 0.75 + f * 0.25, 0, 255).astype(np.uint8)
    return panel, boxes


def put_text(img, txt, x, y, size, color, fpath=FONT_LAT):
    """Printed text with PIL (baseline-bottom at y). Non seven-segment: never labelled."""
    pim = Image.fromarray(img)
    d = ImageDraw.Draw(pim)
    f = font(fpath, size)
    d.text((x, y - size), txt, font=f, fill=tuple(int(c) for c in color))
    img[:] = np.asarray(pim)


def handwriting(img, x, y, h):
    txt = " ".join(random.sample(AR_WORDS, random.randint(1, 3)))
    if random.random() < 0.45:
        txt = str(random.randint(1, 99999))
    col = random.choice([(20, 20, 20), (120, 40, 20), (30, 30, 150), (10, 10, 160)])
    put_text(img, txt, x, y, h, col, random.choice(FONTS_AR + [FONT_LAT]))


def barcode(img, x, y, w, h):
    for i in range(int(w // 2)):
        if random.random() < 0.55:
            cv2.line(img, (int(x + i * 2), int(y)), (int(x + i * 2), int(y + h)), (15, 15, 15), 1)


def printed_digits(img, x, y, h):
    """Serial numbers / model codes in print font: strong hard negatives."""
    txt = random.choice(["%08d" % random.randint(0, 99999999), "No.%d" % random.randint(10 ** 9, 10 ** 10 - 1),
                         "%04d-%06d" % (random.randint(2015, 2026), random.randint(0, 999999)),
                         "S/N %d" % random.randint(10 ** 7, 10 ** 8 - 1), "%d" % random.randint(1000, 999999)])
    put_text(img, txt, x, y, h, (20, 20, 20))


# ----------------------------------------------------------------------------------------------
# meter face and scene
# ----------------------------------------------------------------------------------------------
def meter(img, x0, y0, mw, mh, with_display=True):
    """Draw a meter body at (x0,y0) size (mw,mh); return label boxes in img coordinates."""
    body = random.choice([rand_color(170, 250), rand_color(170, 250), (40, 190, 235), (70, 150, 70), (200, 160, 90),
                          (90, 90, 95)])
    cv2.rectangle(img, (int(x0), int(y0)), (int(x0 + mw), int(y0 + mh)), body, -1)
    shade = mix(body, (0, 0, 0), 0.25)
    cv2.rectangle(img, (int(x0), int(y0)), (int(x0 + mw), int(y0 + mh)), shade, max(1, int(mw * 0.012)))
    if random.random() < 0.5:  # coloured band
        by = y0 + mh * random.uniform(0.4, 0.62)
        cv2.rectangle(img, (int(x0), int(by)), (int(x0 + mw), int(by + mh * random.uniform(0.04, 0.15))),
                      rand_color(60, 230), -1)
    if random.random() < 0.6:  # terminal cover / wires at bottom
        ty = y0 + mh * random.uniform(0.78, 0.9)
        cv2.rectangle(img, (int(x0), int(ty)), (int(x0 + mw), int(y0 + mh)), mix(body, (0, 0, 0), 0.15), -1)
        for _ in range(random.randint(2, 5)):
            wx = random.uniform(x0, x0 + mw)
            cv2.line(img, (int(wx), int(ty)), (int(wx + random.uniform(-20, 20)), int(y0 + mh + mh * 0.3)),
                     random.choice([(0, 0, 200), (200, 0, 0), (0, 200, 200), (30, 30, 30), (0, 160, 0)]),
                     max(2, int(mw * 0.03)))
    boxes = []
    if with_display:
        lw = int(mw * random.uniform(0.5, 0.82))
        lh = int(lw * random.uniform(0.26, 0.5))
        lx = int(x0 + (mw - lw) / 2 + random.uniform(-mw * 0.08, mw * 0.08))
        ly = int(y0 + mh * random.uniform(0.07, 0.32))
        panel, pb = render_display(lw, lh)
        if random.random() < 0.3:  # dark frame around display
            cv2.rectangle(img, (lx - 3, ly - 3), (lx + lw + 3, ly + lh + 3), rand_color(0, 80), -1)
        H, W = img.shape[:2]
        xa, ya, xb, yb = max(0, lx), max(0, ly), min(W, lx + lw), min(H, ly + lh)
        if xb > xa and yb > ya:
            img[ya:yb, xa:xb] = panel[ya - ly:yb - ly, xa - lx:xb - lx]
            cv2.rectangle(img, (lx, ly), (lx + lw, ly + lh), rand_color(0, 90), 1)
            boxes = [(c, x1 + lx, y1 + ly, x2 + lx, y2 + ly) for c, x1, y1, x2, y2 in pb]
        text_top = ly + lh
    else:
        text_top = y0 + mh * 0.3
    # printed text, serial, barcode, screws, handwriting
    for _ in range(random.randint(1, 5)):
        tx = x0 + random.uniform(0.03, 0.4) * mw
        ty = random.uniform(text_top + mh * 0.05, y0 + mh * 0.95)
        put_text(img, random.choice(LAT_TEXT), tx, ty, mh * random.uniform(0.025, 0.055), (25, 25, 25))
    for _ in range(random.randint(1, 3)):
        printed_digits(img, x0 + random.uniform(0.05, 0.4) * mw, random.uniform(text_top + mh * 0.05, y0 + mh * 0.95),
                       mh * random.uniform(0.03, 0.07))
    if random.random() < 0.4:  # printed digits above the display too (model numbers)
        printed_digits(img, x0 + random.uniform(0.05, 0.4) * mw, y0 + mh * random.uniform(0.03, 0.07), mh * 0.035)
    if random.random() < 0.6:
        barcode(img, x0 + random.uniform(0.05, 0.5) * mw, y0 + mh * random.uniform(0.6, 0.8), mw * 0.35, mh * 0.06)
    for _ in range(random.randint(0, 3)):
        handwriting(img, x0 + random.uniform(0, 0.6) * mw, y0 + random.uniform(0.05, 1.0) * mh, mh * random.uniform(0.05, 0.13))
    for _ in range(random.randint(0, 4)):
        cv2.circle(img, (int(x0 + random.uniform(0.05, 0.95) * mw), int(y0 + random.uniform(0.05, 0.95) * mh)),
                   max(2, int(mw * 0.02)), rand_color(20, 120), -1)
    if random.random() < 0.35:  # scratches on cover
        for _ in range(random.randint(3, 20)):
            p1 = (int(random.uniform(x0, x0 + mw)), int(random.uniform(y0, y0 + mh)))
            p2 = (p1[0] + random.randint(-int(mw / 3), int(mw / 3)), p1[1] + random.randint(-int(mh / 3), int(mh / 3)))
            cv2.line(img, p1, p2, (random.randint(180, 255),) * 3, 1, cv2.LINE_AA)
    return boxes


def background(size):
    bg = np.full((size, size, 3), rand_color(20, 210), np.uint8)
    for _ in range(random.randint(5, 40)):
        c = rand_color()
        if random.random() < 0.6:
            p = [(random.randint(0, size), random.randint(0, size)) for _ in range(3)]
            cv2.polylines(bg, [np.array(p)], False, c, random.randint(1, 8), cv2.LINE_AA)
        else:
            cv2.rectangle(bg, (random.randint(0, size), random.randint(0, size)),
                          (random.randint(0, size), random.randint(0, size)), c, -1)
    if random.random() < 0.3:
        handwriting(bg, random.uniform(0, size * 0.6), random.uniform(size * 0.1, size), size * random.uniform(0.04, 0.1))
    return cv2.GaussianBlur(bg, (0, 0), random.uniform(0.5, 3))


def build_scene():
    """Full-resolution scene (RENDER x RENDER) + boxes, before degradation."""
    S = RENDER
    img = background(S)
    boxes = []
    layout = random.choices(["single", "panel", "pair"], [0.6, 0.25, 0.15])[0]
    if layout == "single":
        mw = S * random.uniform(0.5, 0.95)
        mh = mw * random.uniform(1.05, 1.5)
        x0 = random.uniform(-mw * 0.1, S - mw * 0.9)
        y0 = random.uniform(-mh * 0.15, S - mh * 0.7)
        boxes += meter(img, x0, y0, mw, mh)
    elif layout == "pair":
        mw = S * random.uniform(0.4, 0.6)
        mh = mw * random.uniform(1.05, 1.5)
        x0 = random.uniform(0, S - mw)
        y0 = random.uniform(-mh * 0.1, S - mh * 0.8)
        side = random.choice([-1, 1])
        meter(img, x0 + side * (mw + random.uniform(5, 30)), y0 + random.uniform(-30, 30), mw, mh)
        boxes += meter(img, x0, y0, mw, mh)
    else:
        cols, rows = random.randint(2, 5), random.randint(2, 3)
        mw = S / cols * random.uniform(0.85, 0.98)
        mh = mw * random.uniform(1.1, 1.4)
        t = (random.randrange(rows), random.randrange(cols))
        gap = S / cols - mw
        for r in range(rows):
            for c in range(cols):
                b = meter(img, c * (mw + gap), r * (mh + gap), mw, mh)
                boxes += b  # every meter's main line is a LINE; the assembly step picks the target
        # zoom on the target meter like the reader's rectangle would
        cx, cy = t[1] * (mw + gap) + mw / 2, t[0] * (mh + gap) + mh / 2
        half = max(mw, mh) * random.uniform(0.55, 0.95)
        M = np.float32([[S / (2 * half), 0, S / 2 - cx * S / (2 * half)], [0, S / (2 * half), S / 2 - cy * S / (2 * half)]])
        img = cv2.warpAffine(img, M, (S, S), borderMode=cv2.BORDER_REFLECT)
        boxes = transform_boxes(boxes, M)
    return img, boxes


def transform_boxes(boxes, M):
    """Apply a 2x3 affine or 3x3 perspective matrix to boxes; returns axis-aligned boxes."""
    if not boxes:
        return []
    arr = np.array([[b[1], b[2], b[3], b[4]] for b in boxes], np.float32)
    pts = np.stack([arr[:, [0, 1]], arr[:, [2, 1]], arr[:, [2, 3]], arr[:, [0, 3]]], 1)  # N,4,2
    if M.shape[0] == 2:
        out = pts @ M[:, :2].T + M[:, 2]
    else:
        out = cv2.perspectiveTransform(pts.reshape(1, -1, 2), M).reshape(-1, 4, 2)
    res = []
    for b, p in zip(boxes, out):
        res.append((b[0], p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()))
    return res


def geometric(img, boxes):
    """Scene-level rotation / perspective (reader holds the phone at an angle)."""
    h, w = img.shape[:2]
    ang = random.choices([0.0, random.uniform(-8, 8), random.uniform(-35, 35)], [0.35, 0.45, 0.2])[0]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, random.uniform(0.9, 1.1))
    M3 = np.vstack([M, [0, 0, 1]]).astype(np.float32)
    if random.random() < 0.7:
        d = random.uniform(0.0, 0.12)
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = src + np.float32([[random.uniform(-d, d) * w, random.uniform(-d, d) * h] for _ in range(4)])
        M3 = cv2.getPerspectiveTransform(src, dst) @ M3
    img = cv2.warpPerspective(img, M3, (w, h), borderMode=cv2.BORDER_REFLECT)
    return img, transform_boxes(boxes, M3)


def photometric(img, strength=1.0):
    f = img.astype(np.float32)
    h, w = f.shape[:2]
    # exposure / colour cast / low light
    gain = random.choices([random.uniform(0.25, 0.6), random.uniform(0.6, 1.3)], [0.2, 0.8])[0]
    cast = np.array([random.uniform(0.85, 1.15) for _ in range(3)], np.float32)
    f = f * gain * cast
    gx = np.linspace(random.uniform(0.5, 1.2), random.uniform(0.5, 1.2), w)[None, :, None]
    gy = np.linspace(random.uniform(0.6, 1.2), random.uniform(0.6, 1.2), h)[:, None, None]
    f = f * gx * gy
    for _ in range(random.choices([0, 1, 2, 3], [0.4, 0.35, 0.18, 0.07])[0]):  # flash glare blobs
        cx, cy, r = random.uniform(0, w), random.uniform(0, h), random.uniform(0.04, 0.35) * h
        yy, xx = np.mgrid[0:h, 0:w]
        m = np.exp(-(((xx - cx) / (r * random.uniform(1, 2.5))) ** 2 + ((yy - cy) / r) ** 2))
        f += m[..., None] * random.uniform(60, 240)
    f = np.clip(f, 0, 255)
    k = random.choices([0, 1, 2, 3], [0.4, 0.3, 0.2, 0.1])[0] * strength
    if k:
        if random.random() < 0.55:
            f = cv2.GaussianBlur(f, (0, 0), k * random.uniform(0.4, 1.0) * h / 256)
        else:
            L = max(3, int(k * 4 * h / 256)) | 1
            ker = np.zeros((L, L), np.float32)
            ker[L // 2, :] = 1
            ker = cv2.warpAffine(ker, cv2.getRotationMatrix2D((L / 2, L / 2), random.uniform(0, 180), 1), (L, L))
            f = cv2.filter2D(f, -1, ker / max(ker.sum(), 1e-6))
    if random.random() < 0.75:
        f = f + np.random.normal(0, random.uniform(1, 14), f.shape)
    f = np.clip(f, 0, 255).astype(np.uint8)
    if random.random() < 0.75:
        _, b = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, random.randint(30, 92)])
        f = cv2.imdecode(b, cv2.IMREAD_COLOR)
    return f


def clip_boxes(boxes, w, h, min_vis=0.6):
    out = []
    for c, x1, y1, x2, y2 in boxes:
        area = max(1e-3, (x2 - x1) * (y2 - y1))
        cx1, cy1, cx2, cy2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        if cx2 <= cx1 or cy2 <= cy1:
            continue
        if (cx2 - cx1) * (cy2 - cy1) / area < min_vis:
            continue
        out.append((c, cx1, cy1, cx2, cy2))
    return out


def scene_sample():
    """Reader-rectangle crop: BGR SCENE x SCENE + boxes."""
    img, boxes = build_scene()
    img, boxes = geometric(img, boxes)
    # simulate the reader's rectangle: random crop that keeps the main line visible (if any)
    S = img.shape[0]
    main = [b for b in boxes if b[0] == CLS_LINE]
    if main and random.random() < 0.85:
        _, x1, y1, x2, y2 = main[0]
        cw = random.uniform(max(x2 - x1, S * 0.35), S)
        ch = random.uniform(max(y2 - y1, S * 0.35), S)
        cx0 = random.uniform(max(0, x2 - cw), min(x1, S - cw)) if x2 - cw <= min(x1, S - cw) else max(0, x1 - (cw - (x2 - x1)) / 2)
        cy0 = random.uniform(max(0, y2 - ch), min(y1, S - ch)) if y2 - ch <= min(y1, S - ch) else max(0, y1 - (ch - (y2 - y1)) / 2)
        cx0, cy0 = int(np.clip(cx0, 0, S - 1)), int(np.clip(cy0, 0, S - 1))
        cw, ch = int(min(cw, S - cx0)), int(min(ch, S - cy0))
        img = img[cy0:cy0 + ch, cx0:cx0 + cw]
        boxes = [(c, a - cx0, b - cy0, d - cx0, e - cy0) for c, a, b, d, e in boxes]
    h, w = img.shape[:2]
    # letterbox to square (the app pads the rectangle crop the same way)
    side = max(h, w)
    pad = np.full((side, side, 3), PAD_GREY, np.uint8)  # the app letterboxes with the same mid-grey
    ox, oy = (side - w) // 2, (side - h) // 2
    pad[oy:oy + h, ox:ox + w] = img
    boxes = [(c, a + ox, b + oy, d + ox, e + oy) for c, a, b, d, e in boxes]
    k = SCENE / side
    out = cv2.resize(pad, (SCENE, SCENE), interpolation=cv2.INTER_AREA)
    boxes = [(c, a * k, b * k, d * k, e * k) for c, a, b, d, e in boxes]
    out = photometric(out)
    return out, clip_boxes(boxes, SCENE, SCENE)


def line_sample():
    """Pass-2 crop: around the main line with localisation jitter; LINE_H x LINE_W, letterboxed."""
    for _ in range(5):
        img, boxes = build_scene()
        img, boxes = geometric(img, boxes)
        main = [b for b in boxes if b[0] == CLS_LINE]
        if main:
            break
    else:
        return None
    _, x1, y1, x2, y2 = main[0]
    lw, lh = x2 - x1, y2 - y1
    mx1 = x1 - lw * random.uniform(0.0, 0.35)
    mx2 = x2 + lw * random.uniform(0.0, 0.35)
    my1 = y1 - lh * random.uniform(0.05, 0.9)
    my2 = y2 + lh * random.uniform(0.05, 0.9)
    S = img.shape[0]
    cx1, cy1, cx2, cy2 = int(max(0, mx1)), int(max(0, my1)), int(min(S, mx2)), int(min(S, my2))
    if cx2 - cx1 < 8 or cy2 - cy1 < 4:
        return None
    crop = img[cy1:cy2, cx1:cx2]
    boxes = [(c, a - cx1, b - cy1, d - cx1, e - cy1) for c, a, b, d, e in boxes]
    h, w = crop.shape[:2]
    k = min(LINE_H / h, LINE_W / w)
    nw, nh = max(1, int(round(w * k))), max(1, int(round(h * k)))
    rs = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
    out = np.full((LINE_H, LINE_W, 3), PAD_GREY, np.uint8)  # the app letterboxes with the same mid-grey
    ox, oy = 0, (LINE_H - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = rs
    boxes = [(c, a * k + ox, b * k + oy, d * k + ox, e * k + oy) for c, a, b, d, e in boxes]
    out = photometric(out, strength=0.7)
    return out, clip_boxes(boxes, LINE_W, LINE_H)


def draw_boxes(img, boxes):
    v = img.copy()
    for c, x1, y1, x2, y2 in boxes:
        col = (0, 0, 255) if c == CLS_LINE else (0, 255, 0) if c < 10 else (255, 0, 255)
        cv2.rectangle(v, (int(x1), int(y1)), (int(x2), int(y2)), col, 1)
        if c < 10:
            cv2.putText(v, str(c), (int(x1), int(y1) - 1), 0, 0.3, col, 1)
    return v


if __name__ == "__main__":
    paths.ensure_dirs()
    tiles = [draw_boxes(*scene_sample()) for _ in range(16)]
    cv2.imwrite(paths.REVIEW_S + "synth2_scene.jpg", np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, 16, 4)]))
    lines = []
    while len(lines) < 12:
        s = line_sample()
        if s:
            lines.append(draw_boxes(*s))
    cv2.imwrite(paths.REVIEW_S + "synth2_line.jpg", np.vstack(lines))
    print("wrote", paths.REVIEW_S)
