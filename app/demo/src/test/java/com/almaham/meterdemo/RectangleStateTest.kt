package com.almaham.meterdemo

import com.almaham.meterocr.MeterOcrConfig
import com.almaham.meterocr.NormRect
import org.junit.Assert.assertEquals
import org.junit.Test

class RectangleStateTest {
    private val eps = 1e-5f

    @Test
    fun default_isCentred_78pct_aspect125() {
        val r = RectangleState.default(1080f, 2400f)
        assertEquals(0.78f, r.width, eps)
        assertEquals(0.5f, (r.left + r.right) / 2, eps)
        assertEquals(0.5f, (r.top + r.bottom) / 2, eps)
        assertEquals(1.25f, (r.height * 2400f) / (r.width * 1080f), 1e-3f)
    }

    @Test
    fun move_isClampedInsideView() {
        val r = NormRect(0.1f, 0.1f, 0.5f, 0.5f)
        val m = RectangleState.apply(r, Handle.MOVE, 0.9f, -0.5f)
        assertEquals(NormRect(0.6f, 0f, 1f, 0.4f), m)
    }

    @Test
    fun resize_respectsMinimumSize() {
        val r = NormRect(0.1f, 0.1f, 0.5f, 0.5f)
        val m = RectangleState.apply(r, Handle.BR, -0.9f, -0.9f)
        assertEquals(MeterOcrConfig.RECT_MIN_SIZE_FRACTION, m.width, eps)
        assertEquals(MeterOcrConfig.RECT_MIN_SIZE_FRACTION, m.height, eps)
    }

    @Test
    fun resize_edgeOnly_changesOneSide() {
        val r = NormRect(0.1f, 0.1f, 0.5f, 0.5f)
        val m = RectangleState.apply(r, Handle.R, 0.2f, 0.3f)
        assertEquals(NormRect(0.1f, 0.1f, 0.7f, 0.5f), m)
    }

    @Test
    fun hitTest_cornersEdgesInsideOutside() {
        val r = NormRect(0.2f, 0.2f, 0.8f, 0.8f)
        val w = 1000f; val h = 1000f; val rad = 30f
        assertEquals(Handle.TL, RectangleState.hitTest(r, 205f, 210f, w, h, rad))
        assertEquals(Handle.BR, RectangleState.hitTest(r, 790f, 795f, w, h, rad))
        assertEquals(Handle.L, RectangleState.hitTest(r, 210f, 500f, w, h, rad))
        assertEquals(Handle.T, RectangleState.hitTest(r, 500f, 190f, w, h, rad))
        assertEquals(Handle.MOVE, RectangleState.hitTest(r, 500f, 500f, w, h, rad))
        assertEquals(Handle.NONE, RectangleState.hitTest(r, 50f, 50f, w, h, rad))
    }
}
