package com.almaham.meterocr

import org.junit.Assert.assertEquals
import org.junit.Test

class PeakDecoderTest {
    @Test
    fun decodesPeakIntoBoxInInputPixels() {
        val classes = 2; val h = 4; val w = 6
        val plane = h * w
        val peaks = FloatArray(classes * plane)
        val size = FloatArray(2 * plane)
        val offs = FloatArray(2 * plane)
        // class 1 peak at cell (y=2, x=3), offset (0.5, 0.25), box 20x40 px
        val i = 2 * w + 3
        peaks[plane + i] = 0.9f
        size[i] = 20f; size[plane + i] = 40f
        offs[i] = 0.5f; offs[plane + i] = 0.25f
        val d = PeakDecoder.decode(peaks, size, offs, classes, h, w, 0.3f)
        assertEquals(1, d.size)
        val det = d[0]
        assertEquals(1, det.cls)
        assertEquals(0.9f, det.score, 1e-6f)
        val cx = (3 + 0.5f) * MeterOcrConfig.OUTPUT_STRIDE
        val cy = (2 + 0.25f) * MeterOcrConfig.OUTPUT_STRIDE
        assertEquals(cx - 10f, det.x1, 1e-4f)
        assertEquals(cy - 20f, det.y1, 1e-4f)
        assertEquals(cx + 10f, det.x2, 1e-4f)
        assertEquals(cy + 20f, det.y2, 1e-4f)
    }

    @Test
    fun thresholdFiltersWeakPeaks() {
        val peaks = floatArrayOf(0.1f, 0.5f, 0.31f, 0.3f)
        val d = PeakDecoder.decode(peaks, FloatArray(8), FloatArray(8), 1, 2, 2, 0.3f)
        assertEquals(2, d.size)
    }
}
