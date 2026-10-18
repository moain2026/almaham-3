"""Synthetic meter-face scenes for training the main-line localizer (heatmap segmentation).

Each scene: cluttered background -> one or more meter bodies -> LCD window -> main reading line (target)
+ distractors (serial numbers, barcodes, printed specs, Arabic handwriting, labels, secondary LCD lines,
neighbouring meters). Output: BGR image (SCENE x SCENE) and a float mask of the main-line box.
"""
import paths
import random
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import synth

SCENE = 256
FONTS_AR = [str(paths.FONTS / "Tajawal-Bold.ttf"),
            str(paths.FONTS / "IBMPlexSansArabic-Bold.ttf")]
FONT_LAT = str(paths.FONTS / "DejaVuSans-Bold.ttf")
AR_WORDS = ["محمد", "عبدالله", "احمد", "علي", "صالح", "ابراهيم", "حسن", "منزل", "عداد", "فاطمة", "سعيد", "ناصر"]
LAT_TEXT = ["Single Phase Static kWh Meter", "IEC62052-11", "IEC62053-21", "5(60)A 230V 50Hz", "MOE10027954",
            "No.2021-870011230", "1600imp/kWh", "SMART MT10-ALPHA", "TOMAS", "CRYSTAL", "Class 1.0", "DMC"]


def rand_color(lo=0, hi=255):
    return tuple(int(random.uniform(lo, hi)) for _ in range(3))


def background(size):
    bg = np.full((size, size, 3), rand_color(30, 200), np.uint8)
    for _ in range(random.randint(5, 40)):  # wires, blobs
        c = rand_color()
        if random.random() < 0.6:
            p = [(random.randint(0, size), random.randint(0, size)) for _ in range(3)]
            cv2.polylines(bg, [np.array(p)], False, c, random.randint(1, 6), cv2.LINE_AA)
        else:
            cv2.rectangle(bg, (random.randint(0, size), random.randint(0, size)),
                          (random.randint(0, size), random.randint(0, size)), c, -1)
    return cv2.GaussianBlur(bg, (0, 0), random.uniform(0.5, 3))


def pil_text(img, xy, text, font_path, size, color):
    pim = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pim)
    d.text(xy, text, font=ImageFont.truetype(font_path, max(6, int(size))), fill=color[::-1])
    return cv2.cvtColor(np.array(pim), cv2.COLOR_RGB2BGR)


def handwriting(img, x, y, w, h):
    """Arabic marker handwriting or numerals (strong distractor)."""
    txt = " ".join(random.sample(AR_WORDS, random.randint(1, 3)))
    if random.random() < 0.4:
        txt = str(random.randint(1, 9999))
    col = random.choice([(20, 20, 20), (120, 40, 20), (30, 30, 150)])
    img = pil_text(img, (x, y), txt, random.choice(FONTS_AR + [FONT_LAT]), h * random.uniform(0.5, 1.0), col)
    return img


def meter(img, mask, x0, y0, mw, mh, target):
    body = rand_color(150, 250) if random.random() < 0.6 else random.choice([(30, 200, 230), (60, 140, 60)])
    cv2.rectangle(img, (x0, y0), (x0 + mw, y0 + mh), body, -1)
    if random.random() < 0.5:  # blue band / label
        by = y0 + int(mh * random.uniform(0.35, 0.6))
        cv2.rectangle(img, (x0, by), (x0 + mw, by + int(mh * random.uniform(0.05, 0.2))), rand_color(80, 220), -1)
    # LCD window
    lw = int(mw * random.uniform(0.55, 0.85)); lh = int(lw * random.uniform(0.28, 0.55))
    lx = x0 + (mw - lw) // 2 + random.randint(-mw // 12, mw // 12); ly = y0 + int(mh * random.uniform(0.06, 0.3))
    line, _ = synth.render_line()
    # put the rendered line inside an LCD panel image
    bgc = tuple(int(v) for v in line[2, 2])
    panel = np.full((lh, lw, 3), bgc, np.uint8)
    lh2 = int(lh * random.uniform(0.45, 0.8)); lw2 = min(lw - 2, int(line.shape[1] * lh2 / line.shape[0]))
    lw2 = max(lw2, int(lw * 0.5)); lh2 = min(lh - 2, int(line.shape[0] * lw2 / line.shape[1]))
    ox = random.randint(0, max(0, lw - lw2)); oy = random.randint(0, max(0, lh - lh2))
    panel[oy:oy + lh2, ox:ox + lw2] = cv2.resize(line, (lw2, lh2))
    if random.random() < 0.4:  # secondary line under the main one
        sl, _ = synth.render_line(); sh = max(4, int(lh2 * 0.35))
        sy = oy + lh2
        if sy + sh < lh:
            panel[sy:sy + sh, ox:ox + min(lw - ox, int(sl.shape[1] * sh / sl.shape[0]))] = cv2.resize(
                sl, (min(lw - ox, int(sl.shape[1] * sh / sl.shape[0])), sh))
    cv2.rectangle(panel, (0, 0), (lw - 1, lh - 1), rand_color(0, 90), 2)
    H, W = img.shape[:2]
    xa, ya, xb, yb = max(0, lx), max(0, ly), min(W, lx + lw), min(H, ly + lh)
    if xb <= xa or yb <= ya:
        return img
    img[ya:yb, xa:xb] = panel[ya - ly:yb - ly, xa - lx:xb - lx]
    if target:
        # main line box: the line crop covers digits with small margins; tighten 8% horizontally
        tx0, ty0 = lx + ox + int(lw2 * 0.02), ly + oy + int(lh2 * 0.12)
        tx1, ty1 = lx + ox + int(lw2 * 0.98), ly + oy + int(lh2 * 0.88)
        mask[max(0, ty0):max(0, ty1), max(0, tx0):max(0, tx1)] = 1.0
    # printed text & barcode & serial
    for _ in range(random.randint(1, 5)):
        tx = x0 + random.randint(0, max(1, mw // 3)); ty = ly + lh + random.randint(0, max(1, mh - (ly - y0) - lh))
        img = pil_text(img, (tx, ty), random.choice(LAT_TEXT), FONT_LAT, mh * random.uniform(0.03, 0.07), (25, 25, 25))
    if random.random() < 0.5:
        bx = x0 + random.randint(0, mw // 3); byy = y0 + int(mh * random.uniform(0.65, 0.85))
        for i in range(random.randint(20, 50)):
            if random.random() < 0.6:
                cv2.line(img, (bx + i * 2, byy), (bx + i * 2, byy + mh // 14), (10, 10, 10), 1)
    for _ in range(random.randint(0, 3)):
        img = handwriting(img, x0 + random.randint(0, mw // 2), y0 + random.randint(0, mh), mw // 2, mh // 7)
    return img


def scene_augment(img):
    """Photometric degradations at scene scale (blur in pixels of the 256 scene, not line scale)."""
    f = img.astype(np.float32)
    h, w = f.shape[:2]
    gx = np.linspace(random.uniform(0.5, 1.2), random.uniform(0.5, 1.2), w)[None, :, None]
    gy = np.linspace(random.uniform(0.6, 1.2), random.uniform(0.6, 1.2), h)[:, None, None]
    f = f * gx * gy
    for _ in range(random.choices([0, 1, 2], [0.5, 0.35, 0.15])[0]):
        cx, cy, r = random.uniform(0, w), random.uniform(0, h), random.uniform(8, 60)
        yy, xx = np.mgrid[0:h, 0:w]
        f += np.exp(-(((xx - cx) / r) ** 2 + ((yy - cy) / r) ** 2))[..., None] * random.uniform(80, 230)
    f = np.clip(f, 0, 255).astype(np.uint8)
    s = random.choice([0, 0, 0.6, 1.0, 1.6])
    if s:
        f = cv2.GaussianBlur(f, (0, 0), s)
    if random.random() < 0.7:
        f = np.clip(f + np.random.normal(0, random.uniform(2, 12), f.shape), 0, 255).astype(np.uint8)
    if random.random() < 0.7:
        _, b = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, random.randint(30, 90)])
        f = cv2.imdecode(b, cv2.IMREAD_COLOR)
    return f


def scene():
    S = SCENE * 2
    img = background(S); mask = np.zeros((S, S), np.float32)
    layout = random.choices(["single", "panel"], [0.75, 0.25])[0]
    if layout == "single":
        mw = int(S * random.uniform(0.55, 0.95)); mh = int(mw * random.uniform(1.1, 1.5))
        x0 = random.randint(-mw // 10, S - mw + mw // 10); y0 = random.randint(-mh // 10, max(0, S - mh) + mh // 10)
        if random.random() < 0.4:  # neighbour meter (non-target)
            img = meter(img, mask, x0 + mw + 8, y0 + random.randint(-20, 20), mw, mh, False)
        img = meter(img, mask, x0, y0, mw, mh, True)
    else:
        cols, rows = random.randint(2, 4), random.randint(2, 3)
        mw = S // cols - 6; mh = int(mw * 1.2); t = (random.randrange(rows), random.randrange(cols))
        for r in range(rows):
            for c in range(cols):
                img = meter(img, mask, c * (mw + 6), r * (mh + 6), mw, mh, (r, c) == t)
        # panel: crop around target meter like the user's rectangle would
        cx, cy = t[1] * (mw + 6) + mw // 2, t[0] * (mh + 6) + mh // 2
        half = int(max(mw, mh) * random.uniform(0.55, 0.9))
        img = cv2.copyMakeBorder(img, half, half, half, half, cv2.BORDER_REFLECT)
        mask = cv2.copyMakeBorder(mask, half, half, half, half, cv2.BORDER_CONSTANT, value=0)
        img, mask = img[cy:cy + 2 * half, cx:cx + 2 * half], mask[cy:cy + 2 * half, cx:cx + 2 * half]
    # rotation/perspective of whole scene
    h, w = mask.shape
    ang = random.choice([0, 0, 0, random.uniform(-35, 35), random.uniform(-12, 12)])
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, random.uniform(0.9, 1.1))
    img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
    mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST)
    img = cv2.resize(img, (SCENE, SCENE), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(mask, (SCENE, SCENE), interpolation=cv2.INTER_NEAREST)
    img = scene_augment(img)
    return img, mask


if __name__ == "__main__":
    t = []
    for i in range(16):
        im, m = scene()
        ov = im.copy(); ov[m > 0.5] = (0.5 * ov[m > 0.5] + (0, 0, 127)).astype(np.uint8)
        t.append(ov)
    cv2.imwrite(paths.REVIEW_S + "scene.jpg", np.vstack([np.hstack(t[i:i + 8]) for i in (0, 8)]))
