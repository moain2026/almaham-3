"""Main-reading-line boxes derived from display boxes with per-image vertical band (eval only)."""
import paths
import json
d = json.load(open(paths.DISPLAY_BOXES))
BAND = {"23070.jpg": (0.0, 0.6), "23076.jpg": (0.0, 0.62), "23094.jpg": (0.0, 0.62), "23098.jpg": (0.0, 0.62),
        "23100.jpg": (0.05, 0.62), "23089.jpg": (0.0, 0.8), "23091.jpg": (0.0, 0.75),
        "23074.jpg": (0.25, 1.0), "23085.jpg": (0.25, 1.0), "23081.jpg": (0.2, 1.0), "23092.jpg": (0.25, 1.0),
        "23088.jpg": (0.25, 0.95), "23086.jpg": (0.2, 1.0), "23080.jpg": (0.25, 1.0), "23067.jpg": (0.2, 1.0),
        "23073.jpg": (0.2, 1.0), "23079.jpg": (0.15, 1.0)}
out = {}
for k, (x1, y1, x2, y2) in d.items():
    a, b = BAND.get(k, (0.0, 1.0)); h = y2 - y1
    out[k] = [x1, round(y1 + a * h, 4), x2, round(y1 + b * h, 4)]
json.dump(out, open(paths.LINE_BOXES, "w"), indent=0)
