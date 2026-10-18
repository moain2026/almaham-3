"""Ground-truth loader shared by lab scripts (schema v2: benchmark/data/ground_truth.csv + meter_boxes.json).

v1 (archived in benchmark/data/archive/ground_truth_v1.csv) had columns readable/uncertain=yes|no and an
inline meter_box_norm; it contained 3 wrong readings (23106, 23109, 23113) and is NOT used anymore.
"""
import csv
import json
from dataclasses import dataclass

import paths

PHOTOS = paths.PHOTOS_S


@dataclass(frozen=True)
class Item:
    name: str
    reading: str          # cleaned integer reading ("" if unreadable)
    display_text: str     # full text on the LCD incl. leading zeros/decimals
    readable: bool
    uncertain: bool
    box: tuple            # mode-A meter rectangle, normalized x1,y1,x2,y2
    meter_type: str
    difficulty: str       # clear | hard | unreadable


def load():
    boxes = json.load(open(paths.METER_BOXES))
    out = []
    for r in csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")):
        out.append(Item(r["filename"], r["reading"], r["display_text"], r["difficulty"] != "unreadable",
                        r["uncertain"] == "1", tuple(boxes[r["filename"]]), r["meter_type"], r["difficulty"]))
    return out


def crop_box(img, box):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    return img[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)]
