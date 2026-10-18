package com.almaham.meterocr

/**
 * Decodes the exported DigitNet outputs (peaks already NMS'd inside the graph) into detections in input pixels.
 * Layout: peaks [C,H,W], size [2,H,W], offs [2,H,W] flattened row-major (as ORT returns them).
 */
object PeakDecoder {
    fun decode(peaks: FloatArray, size: FloatArray, offs: FloatArray, classes: Int, h: Int, w: Int, thr: Float): List<Detection> {
        val out = ArrayList<Detection>()
        val plane = h * w
        for (c in 0 until classes) {
            val base = c * plane
            for (y in 0 until h) for (x in 0 until w) {
                val s = peaks[base + y * w + x]
                if (s <= thr) continue
                val i = y * w + x
                val bw = size[i]
                val bh = size[plane + i]
                val cx = (x + offs[i]) * MeterOcrConfig.OUTPUT_STRIDE
                val cy = (y + offs[plane + i]) * MeterOcrConfig.OUTPUT_STRIDE
                out.add(Detection(c, s, cx - bw / 2f, cy - bh / 2f, cx + bw / 2f, cy + bh / 2f))
            }
        }
        return out
    }
}
