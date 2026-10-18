"""Single source of truth for every filesystem path used by the lab scripts.

All paths are resolved relative to the repository root, so the lab runs identically in any
sandbox / workstation after `git clone`. Inputs that are NOT in git (customer photos, third-party
models, generated synthetic data) are configured via environment variables with sane defaults
under `data/` (git-ignored). See docs/runbooks/setup-environment.md.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAB = REPO / "lab"

# ---- versioned in git -------------------------------------------------------------------------
BENCH_DATA = REPO / "benchmark" / "data"
GROUND_TRUTH = BENCH_DATA / "ground_truth.csv"            # v2 = the only valid ground truth
METER_BOXES = BENCH_DATA / "meter_boxes.json"             # mode A rectangle (simulated user rect)
DISPLAY_BOXES = BENCH_DATA / "display_boxes.json"         # reference LCD boxes (evaluation only)
LINE_BOXES = BENCH_DATA / "line_boxes.json"               # reference main-line boxes (evaluation only)
ERP_LCD_BOXES = BENCH_DATA / "lcd_boxes_erp_detector.json"
RESULTS = REPO / "benchmark" / "results"
RESULTS_ENGINES = RESULTS / "engines"
RESULTS_RAW = RESULTS / "raw"
WEIGHTS = LAB / "weights"
LOGS = LAB / "logs"
FONTS = LAB / "assets" / "fonts"

# ---- NOT in git (env-configurable) -----------------------------------------------------------
DATA = Path(os.environ.get("METER_DATA_DIR", REPO / "data"))
PHOTOS = Path(os.environ.get("METER_PHOTOS_DIR", DATA / "photos"))        # the 49 test photos
MODELS = Path(os.environ.get("METER_MODELS_DIR", DATA / "models"))        # PP-OCR onnx (download_models.sh)
ERP_VISION = Path(os.environ.get("ERP_VISION_DIR", DATA / "erp_vision"))  # AGPL ERP models, lab baseline only
SYNTH = Path(os.environ.get("METER_SYNTH_DIR", DATA / "synth"))           # generated npz (gen_data.py)
REVIEW = Path(os.environ.get("METER_REVIEW_DIR", DATA / "review"))        # visual review sheets


def photo(name: str) -> str:
    """Absolute path (str, for cv2) of a test photo by filename, e.g. '23065.jpg'."""
    return str(PHOTOS / name)


def ensure_dirs() -> None:
    for d in (RESULTS_ENGINES, RESULTS_RAW, LOGS, REVIEW, SYNTH):
        d.mkdir(parents=True, exist_ok=True)


# String forms with trailing slash, for scripts that concatenate file names.
PHOTOS_S = str(PHOTOS) + "/"
MODELS_S = str(MODELS) + "/"
ERP_VISION_S = str(ERP_VISION) + "/"
REVIEW_S = str(REVIEW) + "/"
