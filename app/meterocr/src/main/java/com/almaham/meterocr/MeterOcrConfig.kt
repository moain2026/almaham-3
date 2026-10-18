package com.almaham.meterocr

/**
 * Every threshold and constant of the engine lives here (brief §8: "all limits in one settings file").
 * Values mirror lab/assemble.py CONFIG and lab/det_model.py so Python and Kotlin stay in lock-step.
 */
object MeterOcrConfig {
    // ---- models (assets/models) ------------------------------------------------------------------
    const val LOCATOR_MODEL_ASSET = "models/line_locator.onnx"
    const val READER_MODEL_ASSET = "models/digit_reader.onnx"
    const val LOCATOR_INPUT = 256          // square, letterboxed rectangle crop
    const val READER_INPUT_H = 64
    const val READER_INPUT_W = 448
    const val OUTPUT_STRIDE = 4
    const val READER_CLASSES = 11          // '0'..'9' + decimal dot
    const val DOT_CLASS = 10
    const val ORT_INTRA_THREADS = 2

    // ---- locator -> line crop ----------------------------------------------------------------------
    const val LOCATOR_PEAK_MIN = 0.25f     // below this no line is found -> fall back to full-rectangle read
    const val LINE_PAD_X = 0.18f           // crop margin around the located line (fraction of line width)
    const val LINE_PAD_Y = 0.45f           // (fraction of line height)
    const val LINE_MIN_HEIGHT_PX = 6f      // smaller located lines are noise

    // ---- reader peaks --------------------------------------------------------------------------------
    const val READER_PEAK_MIN = 0.30f      // candidate digit threshold before assembly

    // ---- assembly (== lab/assemble.py CONFIG) -----------------------------------------------------------
    const val MERGE_IOU = 0.45f
    const val LINE_OVERLAP = 0.4f
    const val HEIGHT_SIMILAR = 0.6f
    const val SMALL_DIGIT_RATIO = 0.65f    // 0.8 cut real 6-cell readings early (bench §8)
    const val INTEGER_CELLS_DEFAULT = 6    // Yemeni LCD meters: 6 integer cells; cells 7+ in a regular lattice are decimals
    const val GAP_MISSING = 1.75f
    const val GAP_SPLIT = 2.6f
    const val DIGIT_CONF_MIN = 0.45f
    const val ALT_RATIO = 0.5f
    const val MAX_INTEGER_DIGITS = 7
    const val MIN_INTEGER_DIGITS = 1
    const val SEG_AGREE_MIN = 6f / 7f        // >1 segment mismatch with the measured 7-seg pattern -> uncertain
    const val LATTICE_MIN_DIGITS = 3
    const val LATTICE_FILL_TOL = 0.3f
    const val LATTICE_PEAK_MIN = 0.08f       // re-read threshold at lattice-predicted cells

    // ---- evidence image ---------------------------------------------------------------------------------
    const val EVIDENCE_LONG_EDGE_PX = 1280
    const val EVIDENCE_TARGET_MIN_BYTES = 80 * 1024
    const val EVIDENCE_TARGET_MAX_BYTES = 200 * 1024
    const val EVIDENCE_QUALITY_START = 82   // same as the main Kotlin project (WebP q82)
    const val EVIDENCE_QUALITY_MIN = 55
    const val EVIDENCE_QUALITY_STEP = 6

    // ---- business validation (colours only, never blocks saving) -------------------------------------------
    const val MAX_CONSUMPTION_KWH = 3000L   // orange when (current - previous) exceeds this; adjustable per utility

    // ---- camera rectangle defaults (fraction of preview) ------------------------------------------------------
    const val RECT_DEFAULT_WIDTH_FRACTION = 0.78f
    const val RECT_DEFAULT_ASPECT = 1.25f   // height / width
    const val RECT_MIN_SIZE_FRACTION = 0.2f
    const val RECT_MAX_SIZE_FRACTION = 1.0f
    const val RECT_HANDLE_TOUCH_RADIUS_DP = 28f
}
