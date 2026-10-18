"""Synthetic seven-segment meter-display line generator (training data only; no real test image is used).

Produces (gray_line_image, label) where label is the main reading text with an optional '.' followed by
decimal digits, e.g. "002231.69". Secondary lines, unit text, icons, ghost segments, glare, blur, noise,
JPEG artifacts and perspective are simulated so the recognizer learns to read only the main line.
"""
import paths
import random
import cv2
import numpy as np

SEG = {  # segments a b c d e f g
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}
ALL = "abcdefg"
LINE_H, LINE_W = 48, 320


def seg_polys(x, y, w, h, t, slant):
    """Return dict seg->polygon (float Nx2) for a digit cell with top-left (x,y)."""
    g = t * 0.12  # gap
    hh = h / 2
    def P(pts):
        return np.array([(px + slant * (h - py), py) for px, py in pts], np.float32) + (x, y)
    def hseg(yc):
        return P([(g + t / 2, yc), (g + t, yc - t / 2), (w - g - t, yc - t / 2), (w - g - t / 2, yc),
                  (w - g - t, yc + t / 2), (g + t, yc + t / 2)])
    def vseg(xc, y0, y1):
        return P([(xc, y0 + g + t / 2), (xc + t / 2, y0 + g + t), (xc + t / 2, y1 - g - t), (xc, y1 - g - t / 2),
                  (xc - t / 2, y1 - g - t), (xc - t / 2, y0 + g + t)])
    return {
        "a": hseg(t / 2), "g": hseg(hh), "d": hseg(h - t / 2),
        "f": vseg(t / 2, 0, hh), "b": vseg(w - t / 2, 0, hh),
        "e": vseg(t / 2, hh, h), "c": vseg(w - t / 2, hh, h),
    }


def draw_digit(canvas, ch, x, y, w, h, t, slant, fg, ghost, ghost_alpha, bevel):
    polys = seg_polys(x, y, w, h, t, slant)
    on = SEG.get(ch, "")
    for s in ALL:
        if s in on:
            col = fg
        elif ch != " " or random.random() < 0.6:
            col = ghost
            if ghost_alpha <= 0:
                continue
        else:
            continue
        p = polys[s]
        if bevel:
            cv2.fillPoly(canvas, [np.round(p * 4).astype(np.int32)], col, cv2.LINE_AA, shift=2)
        else:
            cv2.fillPoly(canvas, [np.round(p).astype(np.int32)], col)


def random_reading():
    style = random.choices(["six_dec2_big", "six_dec2_small", "eight_tinydot", "crystal", "six_dec1", "five_dec2"],
                           [0.25, 0.3, 0.12, 0.13, 0.1, 0.1])[0]
    if style == "crystal":
        n = random.choice([1, 2, 3, 4, 5])
        ip = str(random.randint(10 ** (n - 1) if n > 1 else 0, 10 ** n - 1))
        return style, ip, "%02d" % random.randint(0, 99)
    ndig = {"six_dec2_big": 6, "six_dec2_small": 6, "eight_tinydot": 6, "six_dec1": 6, "five_dec2": 5}[style]
    mag = random.choices([2, 3, 4, 5, 6], [0.08, 0.22, 0.45, 0.2, 0.05])[0]
    mag = min(mag, ndig)
    v = random.randint(0, 10 ** mag - 1)
    ip = str(v).zfill(ndig)
    dec = "%d" % random.randint(0, 9) if style == "six_dec1" else "%02d" % random.randint(0, 99)
    return style, ip, dec


def palette():
    kind = random.choices(["grey", "green", "blue", "white", "dark", "yellowish"], [0.25, 0.2, 0.2, 0.2, 0.08, 0.07])[0]
    bg = {"grey": (150, 165, 160), "green": (140, 175, 150), "blue": (210, 170, 120), "white": (225, 230, 225),
          "dark": (70, 80, 75), "yellowish": (120, 175, 185)}[kind]
    bg = tuple(int(np.clip(c + random.randint(-35, 35), 20, 250)) for c in bg)
    base = np.mean(bg)
    fg_l = random.uniform(10, 60) if base > 90 else random.uniform(5, 30)
    fg = tuple(int(np.clip(fg_l + random.randint(-15, 25), 0, 255)) for _ in range(3))
    contrast = random.uniform(0.25, 1.0)  # faint LCDs
    fg = tuple(int(b + (f - b) * contrast) for f, b in zip(fg, bg))
    ga = random.choices([0.0, random.uniform(0.04, 0.2), random.uniform(0.2, 0.45)], [0.35, 0.45, 0.2])[0]
    ghost = tuple(int(b + (f - b) * ga) for f, b in zip(fg, bg))
    return bg, fg, ghost, ga


def put_small_text(canvas, x, y, size, color):
    txt = random.choice(["kWh", "kwh", "KWH", "Hz", "A", "V", "kW", "Σ", "T1", "LAST", "DATE", "IMP"])
    cv2.putText(canvas, txt.replace("Σ", "E"), (int(x), int(y)), random.choice([0, 1, 2, 4]),
                size, color, max(1, int(size * 2)), cv2.LINE_AA)


def render_line():
    """Render a large display canvas and return (crop_bgr, label)."""
    style, ip, dec = random_reading()
    H = random.randint(70, 120)
    dh = H * random.uniform(0.5, 0.72)              # main digit height
    dw = dh * random.uniform(0.45, 0.62)
    t = dh * random.uniform(0.09, 0.17)
    slant = random.uniform(0.0, 0.14)
    pitch = dw * random.uniform(1.12, 1.35)
    bg, fg, ghost, ga = palette()
    W = int(pitch * 11 + H)
    canvas = np.full((H * 2, W, 3), bg, np.uint8)
    y0 = H * 0.5 + (H - dh) / 2 + random.uniform(-0.1, 0.1) * H
    x = H * 0.3 + random.uniform(0, pitch)
    bevel = random.random() < 0.8
    cells = list(ip)
    if style == "crystal":
        lead = random.randint(0, 6 - len(ip))
        cells = [" "] * lead + cells
    for ch in cells:
        draw_digit(canvas, ch, x, y0, dw, dh, t, slant, fg, ghost, ga, bevel)
        x += pitch
    label = ip
    dot_r = max(1.5, t * random.uniform(0.35, 0.6))
    small = style in ("six_dec2_small", "crystal") and random.random() < 0.85
    if style == "eight_tinydot":
        dot_r = max(1.0, t * random.uniform(0.15, 0.3))
    show_dot = random.random() < (0.93 if style != "eight_tinydot" else 0.75)
    if show_dot:
        cv2.circle(canvas, (int(x - pitch * 0.12), int(y0 + dh - dot_r)), int(round(dot_r)), fg, -1, cv2.LINE_AA)
        x += pitch * random.uniform(0.05, 0.25)
    sh = dh * (random.uniform(0.38, 0.6) if small else 1.0)
    sw, st_ = dw * sh / dh, t * sh / dh
    sp = pitch * sh / dh
    sy = y0 + dh - sh
    for ch in dec:
        draw_digit(canvas, ch, x, sy, sw, sh, st_, slant, fg, ghost, ga, bevel)
        x += sp
    label = ip + "." + dec
    right = x
    # decorations: unit text, icons, secondary small line
    if random.random() < 0.7:
        put_small_text(canvas, right + random.uniform(0, 8), y0 + random.uniform(0.2, 0.5) * dh,
                       dh / 75 * random.uniform(0.8, 1.4), fg)
    if random.random() < 0.4:
        put_small_text(canvas, H * 0.3, y0 - random.uniform(0.05, 0.25) * H, dh / 90, fg)
    if random.random() < 0.45:  # secondary smaller reading line (A, V, Hz...)
        sx = H * 0.3 + random.uniform(0, pitch * 3)
        s2 = dh * random.uniform(0.3, 0.5)
        yy = y0 + dh + random.uniform(0.08, 0.3) * H
        for ch in str(random.randint(0, 99999)):
            draw_digit(canvas, ch, sx, yy, s2 * 0.55, s2, s2 * 0.13, slant, fg, ghost, ga, bevel)
            sx += s2 * 0.7
    if random.random() < 0.3:
        cv2.rectangle(canvas, (int(right), int(y0 - 0.3 * H)), (int(right + dh * 0.5), int(y0 - 0.1 * H)), fg, 2)
    # crop around the main line with jitter (simulate localizer error)
    top = y0 - dh * random.uniform(0.05, 0.45)
    bot = y0 + dh + dh * random.uniform(0.05, 0.5)
    left = H * 0.3 - pitch * random.uniform(0.05, 0.6)
    rgt = right + pitch * random.uniform(0.1, 1.6)
    crop = canvas[int(max(0, top)):int(bot), int(max(0, left)):int(min(W, rgt))]
    return crop, label


def augment(img):
    h, w = img.shape[:2]
    f = img.astype(np.float32)
    # uneven illumination
    gx = np.linspace(random.uniform(0.6, 1.2), random.uniform(0.6, 1.2), w)[None, :, None]
    gy = np.linspace(random.uniform(0.75, 1.15), random.uniform(0.75, 1.15), h)[:, None, None]
    f = f * gx * gy
    # glare blobs
    for _ in range(random.choices([0, 1, 2], [0.5, 0.35, 0.15])[0]):
        cx, cy = random.uniform(0, w), random.uniform(0, h)
        r = random.uniform(0.1, 0.5) * h
        yy, xx = np.mgrid[0:h, 0:w]
        m = np.exp(-(((xx - cx) / (r * random.uniform(1, 3))) ** 2 + ((yy - cy) / r) ** 2))
        f += m[..., None] * random.uniform(60, 220)
    # scratches / streaks
    for _ in range(random.choices([0, 3, 10], [0.5, 0.3, 0.2])[0]):
        p1 = (random.randint(0, w), random.randint(0, h))
        p2 = (p1[0] + random.randint(-w // 2, w // 2), p1[1] + random.randint(-h, h))
        cv2.line(f, p1, p2, (random.uniform(150, 255),) * 3, 1, cv2.LINE_AA)
    # dust specks
    if random.random() < 0.4:
        for _ in range(random.randint(5, 60)):
            cv2.circle(f, (random.randint(0, w), random.randint(0, h)), random.randint(0, 2), (random.uniform(160, 255),) * 3, -1)
    f = np.clip(f, 0, 255).astype(np.uint8)
    # perspective / rotation
    if random.random() < 0.8:
        d = 0.08
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = src + np.float32([[random.uniform(-d, d) * w, random.uniform(-d, d) * h * 2] for _ in range(4)])
        M = cv2.getPerspectiveTransform(src, dst)
        f = cv2.warpPerspective(f, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    # blur
    k = random.choices([0, 1, 2, 3], [0.35, 0.3, 0.25, 0.1])[0]
    if k:
        if random.random() < 0.5:
            f = cv2.GaussianBlur(f, (0, 0), k * random.uniform(0.6, 1.4) * h / 60)
        else:
            L = max(3, int(k * 3 * h / 60)) | 1
            ker = np.zeros((L, L), np.float32); ker[L // 2, :] = 1
            ker = cv2.warpAffine(ker, cv2.getRotationMatrix2D((L / 2, L / 2), random.uniform(0, 180), 1), (L, L))
            f = cv2.filter2D(f, -1, ker / max(ker.sum(), 1e-6))
    # downscale-upscale (low resolution)
    if random.random() < 0.5:
        s = random.uniform(0.25, 0.7)
        f = cv2.resize(cv2.resize(f, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), (w, h))
    # noise
    if random.random() < 0.7:
        f = np.clip(f.astype(np.float32) + np.random.normal(0, random.uniform(2, 18), f.shape), 0, 255).astype(np.uint8)
    # jpeg
    if random.random() < 0.7:
        _, b = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, random.randint(25, 90)])
        f = cv2.imdecode(b, cv2.IMREAD_COLOR)
    if random.random() < 0.03:
        f = 255 - f
    return f


def sample():
    crop, label = render_line()
    return augment(crop), label


if __name__ == "__main__":
    tiles = []
    for i in range(40):
        im, lab = sample()
        im = cv2.resize(im, (LINE_W, LINE_H))
        cv2.putText(im, lab, (2, 12), 0, 0.4, (0, 0, 255), 1)
        tiles.append(im)
    cv2.imwrite(paths.REVIEW_S + "synth.jpg", np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, 40, 4)]))
