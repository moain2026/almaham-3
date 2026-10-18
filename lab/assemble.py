"""Turn digit detections into ONE integer reading with honest per-digit confidence.

This is the reference implementation that the Kotlin `ReadingAssembler` mirrors line by line
(app/meterocr/src/main/java/.../ReadingAssembler.kt). Every threshold lives in CONFIG so both sides share values.

Input : detections (cls, score, x1, y1, x2, y2) from the reader net on a line crop. cls 0..9 digits, 10 = dot.
Output: Reading(text, digits=[Digit], status) where text is the INTEGER part only (decimals are never used, per
        the owner's rule), leading zeros kept in `text` and stripped in `value`.
Rules (all measurable, none heuristic-by-feel):
  1. Merge overlapping detections of different classes (IoU >= MERGE_IOU): keep the best, remember the runner-up
     as the digit's alternative -> margin-based uncertainty.
  2. Group digits into lines by vertical overlap of their boxes.
  3. Main line = the line whose digits are tallest (ties: more digits). The line crop is already centred on it.
  4. Decimal boundary = first dot whose centre lies between two digits, else the first digit whose height drops
     below SMALL_DIGIT_RATIO x median height of the digits before it (small decimals without a visible dot).
  5. Structure check on the integer digits: pitch must be regular (a gap > GAP_MISSING x median pitch means a digit
     was probably missed -> status MISSING_DIGIT, we do not guess).
  6. Per-digit confidence = peak score; a digit is `uncertain` when score < DIGIT_CONF_MIN or runner-up score
     >= ALT_RATIO x score. Reading is `confident` only if every digit is confident.
"""
from dataclasses import dataclass, field
from typing import List, Optional

CONFIG = {
    "MERGE_IOU": 0.45,            # same box, different class -> alternatives
    "LINE_OVERLAP": 0.4,          # vertical overlap ratio to be on the same line
    "HEIGHT_SIMILAR": 0.6,        # min height ratio for two digits to be on the same line
    "SMALL_DIGIT_RATIO": 0.65,    # a digit shorter than this x median -> decimal part (0.8 cut real 6-cell readings early)
    "INTEGER_CELLS_DEFAULT": 6,   # Yemeni LCD meters: 6 integer cells; with >=7 digits in a regular lattice, cells 7+ are decimals
    "GAP_MISSING": 1.75,          # a gap larger than this x median pitch -> a digit was missed
    "GAP_SPLIT": 2.6,             # a gap larger than this x median pitch -> a different number (e.g. unit text)
    "DIGIT_CONF_MIN": 0.45,       # below this a digit is uncertain
    "ALT_RATIO": 0.5,             # runner-up class at >= this x best score -> uncertain
    "MAX_INTEGER_DIGITS": 7,      # electricity meters: at most 7 integer digits
    "MIN_INTEGER_DIGITS": 1,
    "DOT_CLASS": 10,
    "SEG_AGREE_MIN": 6 / 7,       # a digit whose measured 7-segment pattern differs in >1 segment is uncertain
    "LATTICE_MIN_DIGITS": 3,      # digits needed to estimate the pitch lattice
    "LATTICE_FILL_TOL": 0.3,      # a gap of k*pitch (+-tol*pitch) with k>=2 means k-1 missing cells
}

CLS_LINE = 11  # synth2.CLS_LINE (duplicated to avoid importing the generator in the app-side reference)


@dataclass
class Digit:
    cls: int
    score: float
    x1: float
    y1: float
    x2: float
    y2: float
    alt_cls: int = -1
    alt_score: float = 0.0
    seg_agree: float = 1.0   # seven-segment pattern agreement with cls (segverify.py); 1.0 = all 7 segments match
    seg_cls: int = -1        # class suggested by the measured segment pattern

    @property
    def cx(self):
        return (self.x1 + self.x2) / 2

    @property
    def cy(self):
        return (self.y1 + self.y2) / 2

    @property
    def h(self):
        return self.y2 - self.y1

    @property
    def w(self):
        return self.x2 - self.x1

    @property
    def uncertain(self):
        return (self.score < CONFIG["DIGIT_CONF_MIN"] or self.alt_score >= CONFIG["ALT_RATIO"] * self.score
                or self.seg_agree < CONFIG["SEG_AGREE_MIN"])


@dataclass
class Reading:
    text: str = ""                 # integer digits as shown, e.g. "003155"
    status: str = "EMPTY"          # OK | EMPTY | MISSING_DIGIT | TOO_MANY_DIGITS
    digits: List[Digit] = field(default_factory=list)

    @property
    def value(self) -> str:
        return str(int(self.text)) if self.text.isdigit() else ""

    @property
    def confident(self) -> bool:
        return self.status == "OK" and bool(self.digits) and not any(d.uncertain for d in self.digits)

    @property
    def min_conf(self) -> float:
        return min((d.score for d in self.digits), default=0.0)


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def merge(dets) -> List[Digit]:
    """Cross-class NMS keeping the runner-up as alternative."""
    items = sorted((Digit(int(c), float(s), *b) for c, s, *b in dets), key=lambda d: -d.score)
    kept: List[Digit] = []
    for d in items:
        for k in kept:
            if iou((d.x1, d.y1, d.x2, d.y2), (k.x1, k.y1, k.x2, k.y2)) >= CONFIG["MERGE_IOU"]:
                if d.cls != k.cls and d.score > k.alt_score:
                    k.alt_cls, k.alt_score = d.cls, d.score
                break
        else:
            kept.append(d)
    return kept


def group_lines(digits: List[Digit]) -> List[List[Digit]]:
    lines: List[List[Digit]] = []
    for d in sorted(digits, key=lambda d: -d.h):
        for line in lines:
            ref = line[0]
            ov = max(0.0, min(d.y2, ref.y2) - max(d.y1, ref.y1)) / max(1e-6, min(d.h, ref.h))
            if ov >= CONFIG["LINE_OVERLAP"] and min(d.h, ref.h) / max(d.h, ref.h) >= CONFIG["HEIGHT_SIMILAR"]:
                line.append(d)
                break
        else:
            lines.append([d])
    for line in lines:
        line.sort(key=lambda d: d.cx)
    return lines


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def pick_main_line(lines: List[List[Digit]]) -> Optional[List[Digit]]:
    cand = [ln for ln in lines if any(d.cls < 10 for d in ln)]
    if not cand:
        return None
    return max(cand, key=lambda ln: (median([d.h for d in ln if d.cls < 10]), len(ln)))


def integer_part(line: List[Digit], dots: List[Digit]) -> List[Digit]:
    """Digits before the decimal boundary (dot between digits, or a height drop) and before a large gap."""
    ds = [d for d in line if d.cls < 10]
    if not ds:
        return []
    cut = len(ds)
    for dot in sorted(dots, key=lambda d: d.cx):
        if dot.cy < ds[0].cy - ds[0].h * 0.2:  # above the digit middle: not a decimal point
            continue
        for i in range(1, len(ds)):
            if ds[i - 1].cx < dot.cx < ds[i].cx:
                cut = min(cut, i)
                break
    # height drop (small decimals, dot missed)
    for i in range(1, len(ds)):
        ref = median([d.h for d in ds[:i]])
        if ds[i].h < CONFIG["SMALL_DIGIT_RATIO"] * ref:
            cut = min(cut, i)
            break
    # cell-count prior: on real meters the decimal digits are often the same height as the integers and the dot is
    # faint, so with >= INTEGER_CELLS_DEFAULT+1 digits in a regular lattice and no earlier cut, cut at the default.
    n0 = CONFIG["INTEGER_CELLS_DEFAULT"]
    if cut > n0 and len(ds) > n0:
        pitches = [ds[i + 1].cx - ds[i].cx for i in range(len(ds) - 1)]
        med = median(pitches)
        if med > 0 and all(abs(p - med) <= 0.35 * med for p in pitches):
            cut = n0
    ds = ds[:cut]
    # large gap: stop at the first gap that cannot be part of the same number
    if len(ds) >= 3:
        pitches = [ds[i + 1].cx - ds[i].cx for i in range(len(ds) - 1)]
        med = median(pitches)
        for i, p in enumerate(pitches):
            if p > CONFIG["GAP_SPLIT"] * med:
                ds = ds[:i + 1]
                break
    return ds


def missing_cells(ds: List[Digit]) -> List[tuple]:
    """Pitch-lattice gap analysis: returns boxes (x1,y1,x2,y2) of cells the lattice says exist between detected
    digits but no detection covered (a dropped digit). Empty list when the run is regular."""
    if len(ds) < CONFIG["LATTICE_MIN_DIGITS"]:
        return []
    pitches = [ds[i + 1].cx - ds[i].cx for i in range(len(ds) - 1)]
    pitch = median(pitches)
    if pitch <= 0:
        return []
    out = []
    for i, p in enumerate(pitches):
        k = round(p / pitch)
        if k >= 2 and abs(p - k * pitch) <= CONFIG["LATTICE_FILL_TOL"] * pitch * k:
            a, b = ds[i], ds[i + 1]
            w = (a.w + b.w) / 2
            for j in range(1, k):
                cx = a.cx + j * p / k
                y1 = a.y1 + (b.y1 - a.y1) * j / k
                y2 = a.y2 + (b.y2 - a.y2) * j / k
                out.append((cx - w / 2, y1, cx + w / 2, y2))
    return out


def structure_ok(ds: List[Digit]) -> bool:
    if len(ds) < 3:
        return True
    pitches = [ds[i + 1].cx - ds[i].cx for i in range(len(ds) - 1)]
    med = median(pitches)
    return all(p <= CONFIG["GAP_MISSING"] * med for p in pitches)


def assemble(dets, width: float, height: float) -> Reading:
    """dets: iterable of (cls, score, x1, y1, x2, y2) in crop pixels; width/height of the crop (for clipping)."""
    clipped = [(c, s, max(0, x1), max(0, y1), min(width, x2), min(height, y2)) for c, s, x1, y1, x2, y2 in dets
               if x2 > x1 and y2 > y1]
    merged = merge(clipped)
    digits = [d for d in merged if d.cls < 10]
    dots = [d for d in merged if d.cls == CONFIG["DOT_CLASS"]]
    main = pick_main_line(group_lines(digits))
    if not main:
        return Reading()
    ds = integer_part(main, dots)
    if len(ds) < CONFIG["MIN_INTEGER_DIGITS"]:
        return Reading()
    if len(ds) > CONFIG["MAX_INTEGER_DIGITS"]:
        return Reading(text="".join(str(d.cls) for d in ds), status="TOO_MANY_DIGITS", digits=ds)
    if not structure_ok(ds):
        return Reading(text="".join(str(d.cls) for d in ds), status="MISSING_DIGIT", digits=ds)
    return Reading(text="".join(str(d.cls) for d in ds), status="OK", digits=ds)


def truth_from_boxes(boxes, line_box) -> Optional[str]:
    """Ground truth integer text from synthetic labels: digits inside the line box, cut at the dot / height drop."""
    lx1, ly1, lx2, ly2 = line_box[1:5]
    inside = [b for b in boxes if b[0] != CLS_LINE and b[1] >= lx1 - 1 and b[3] <= lx2 + 1 and b[2] >= ly1 - 1 and b[4] <= ly2 + 1]
    digs = sorted([b for b in inside if b[0] < 10], key=lambda b: (b[1] + b[3]) / 2)
    dots = [b for b in inside if b[0] == CONFIG["DOT_CLASS"]]
    if not digs:
        return None
    cut = len(digs)
    for dot in dots:
        dcx = (dot[1] + dot[3]) / 2
        for i in range(1, len(digs)):
            if (digs[i - 1][1] + digs[i - 1][3]) / 2 < dcx < (digs[i][1] + digs[i][3]) / 2:
                cut = min(cut, i)
    h0 = digs[0][4] - digs[0][2]
    for i in range(1, len(digs)):
        if digs[i][4] - digs[i][2] < CONFIG["SMALL_DIGIT_RATIO"] * h0:
            cut = min(cut, i)
            break
    return "".join(str(int(b[0])) for b in digs[:cut])
