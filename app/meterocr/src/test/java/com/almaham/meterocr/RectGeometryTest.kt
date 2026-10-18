package com.almaham.meterocr

import org.junit.Assert.assertEquals
import org.junit.Test

class RectGeometryTest {
    private val eps = 1e-4f

    private fun assertRect(exp: NormRect, got: NormRect) {
        assertEquals(exp.left, got.left, eps)
        assertEquals(exp.top, got.top, eps)
        assertEquals(exp.right, got.right, eps)
        assertEquals(exp.bottom, got.bottom, eps)
    }

    // ---- view -> upright ----------------------------------------------------------------------------
    @Test
    fun fitCenter_sameAspect_isIdentity() {
        val r = NormRect(0.1f, 0.2f, 0.9f, 0.8f)
        assertRect(r, RectGeometry.viewToUpright(r, 1080f, 1920f, 1080f, 1920f, PreviewScale.FIT_CENTER))
        assertRect(r, RectGeometry.viewToUpright(r, 1080f, 1920f, 1080f, 1920f, PreviewScale.FILL_CENTER))
    }

    @Test
    fun fillCenter_tallerView_cropsBufferTopAndBottom() {
        // 4:3 upright buffer (1080x1440) shown FILL_CENTER on a 1080x2400 view: scale = 2400/1440 = 1.6667,
        // shown width = 1800 -> 360px cropped each side horizontally. View x in [0,1] maps to buffer x in [0.2,0.8].
        val r = NormRect(0f, 0f, 1f, 1f)
        val got = RectGeometry.viewToUpright(r, 1080f, 2400f, 1080f, 1440f, PreviewScale.FILL_CENTER)
        assertRect(NormRect(0.2f, 0f, 0.8f, 1f), got)
    }

    @Test
    fun fitCenter_tallerView_letterboxes() {
        // same buffer FIT_CENTER: scale = 1, shown 1080x1440 centred vertically with 480px bars.
        val r = NormRect(0f, 480f / 2400f, 1f, 1920f / 2400f)
        val got = RectGeometry.viewToUpright(r, 1080f, 2400f, 1080f, 1440f, PreviewScale.FIT_CENTER)
        assertRect(NormRect(0f, 0f, 1f, 1f), got)
    }

    @Test
    fun fillCenter_centredRectangle_staysCentred() {
        val r = NormRect(0.11f, 0.3f, 0.89f, 0.7f)
        val got = RectGeometry.viewToUpright(r, 1080f, 2400f, 1080f, 1440f, PreviewScale.FILL_CENTER)
        assertEquals(0.5f, (got.left + got.right) / 2f, eps)
        assertEquals(0.5f, (got.top + got.bottom) / 2f, eps)
        assertEquals(0.78f * 0.6f, got.width, eps)   // 60% of the buffer width is visible
    }

    // ---- upright -> raw (rotation) ----------------------------------------------------------------------
    @Test
    fun rotation0_identity() {
        val r = NormRect(0.1f, 0.2f, 0.4f, 0.7f)
        assertRect(r, RectGeometry.uprightToRaw(r, 0))
    }

    @Test
    fun rotation90_portraitPhone_landscapeSensor() {
        // Typical phone: sensor buffer is landscape, rotationDegrees = 90. A rectangle at the TOP-LEFT of the
        // upright view sits at the TOP-RIGHT of the raw buffer.
        val topLeft = NormRect(0f, 0f, 0.2f, 0.1f)
        assertRect(NormRect(0f, 0.8f, 0.1f, 1f), RectGeometry.uprightToRaw(topLeft, 90))
    }

    @Test
    fun rotation180() {
        val r = NormRect(0f, 0f, 0.2f, 0.1f)
        assertRect(NormRect(0.8f, 0.9f, 1f, 1f), RectGeometry.uprightToRaw(r, 180))
    }

    @Test
    fun rotation270() {
        val r = NormRect(0f, 0f, 0.2f, 0.1f)
        assertRect(NormRect(0.9f, 0f, 1f, 0.2f), RectGeometry.uprightToRaw(r, 270))
    }

    @Test
    fun rotationNegativeAndOver360_normalised() {
        val r = NormRect(0.1f, 0.2f, 0.3f, 0.5f)
        assertRect(RectGeometry.uprightToRaw(r, 90), RectGeometry.uprightToRaw(r, -270))
        assertRect(RectGeometry.uprightToRaw(r, 90), RectGeometry.uprightToRaw(r, 450))
    }

    @Test
    fun rotations_areInvertible_viaFourApplications() {
        val r = NormRect(0.12f, 0.33f, 0.58f, 0.91f)
        var x = r
        repeat(4) { x = RectGeometry.uprightToRaw(x, 90) }
        assertRect(r, x)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rotationNotMultipleOf90_rejected() {
        RectGeometry.uprightToRaw(NormRect(0f, 0f, 1f, 1f), 45)
    }

    // ---- pixels ------------------------------------------------------------------------------------------
    @Test
    fun toPixels_roundsAndClampsInsideImage() {
        val p = RectGeometry.toPixels(NormRect(-0.1f, 0.5f, 1.2f, 0.75f), 4000, 3000)
        assertEquals(PixelRect(0, 1500, 4000, 2250), p)
    }

    @Test
    fun toPixels_neverEmpty() {
        val p = RectGeometry.toPixels(NormRect(0.5f, 0.5f, 0.5f, 0.5f), 100, 100)
        assertEquals(1, p.width)
        assertEquals(1, p.height)
    }

    // ---- full chain --------------------------------------------------------------------------------------
    @Test
    fun fullChain_portrait_fillCenter_rotation90() {
        // Sensor 4000x3000 (landscape), rotation 90 => upright 3000x4000 (3:4). View 1080x2400 (9:20) FILL_CENTER:
        // scale = 2400/4000 = 0.6, shown width = 1800, offX = -360. Rectangle covering the whole view =>
        // upright x in [0.2, 0.8], y in [0, 1] => raw: x in [0,1], y in [0.2, 0.8] => pixels (0,600)-(4000,2400).
        val p = RectGeometry.viewRectToRawCrop(NormRect(0f, 0f, 1f, 1f), 1080f, 2400f, PreviewScale.FILL_CENTER, 4000, 3000, 90)
        assertEquals(PixelRect(0, 600, 4000, 2400), p)
    }

    @Test
    fun fullChain_defaultRectangle_rotation90_isCentredInRaw() {
        val w = MeterOcrConfig.RECT_DEFAULT_WIDTH_FRACTION
        val hPx = w * 1080f * MeterOcrConfig.RECT_DEFAULT_ASPECT
        val r = NormRect((1 - w) / 2, (2400f - hPx) / 2 / 2400f, (1 + w) / 2, (2400f + hPx) / 2 / 2400f)
        val p = RectGeometry.viewRectToRawCrop(r, 1080f, 2400f, PreviewScale.FILL_CENTER, 4000, 3000, 90)
        assertEquals(2000f, (p.left + p.right) / 2f, 1f)
        assertEquals(1500f, (p.top + p.bottom) / 2f, 1f)
        // aspect in raw space is transposed: raw width (= upright height) / raw height (= upright width) == 1.25
        assertEquals(1.25f, p.width.toFloat() / p.height, 0.01f)
    }

    @Test
    fun fullChain_rotation270_mirrorsRotation90() {
        val r = NormRect(0f, 0f, 0.5f, 0.5f)
        val p90 = RectGeometry.viewRectToRawCrop(r, 1080f, 1440f, PreviewScale.FIT_CENTER, 1440, 1080, 90)
        val p270 = RectGeometry.viewRectToRawCrop(r, 1080f, 1440f, PreviewScale.FIT_CENTER, 1440, 1080, 270)
        assertEquals(PixelRect(0, 540, 720, 1080), p90)
        assertEquals(PixelRect(720, 0, 1440, 540), p270)
    }

    @Test
    fun letterbox_wideLineIntoReaderInput() {
        val lb = RectGeometry.letterbox(900, 150, 448, 64)
        assertEquals(384, lb.scaledW)
        assertEquals(64, lb.scaledH)
        assertEquals(0, lb.offsetY)
        assertEquals(32, lb.offsetX)
    }

    @Test
    fun letterbox_tallCropIntoSquare() {
        val lb = RectGeometry.letterbox(1000, 1250, 256, 256)
        assertEquals(256, lb.scaledH)
        assertEquals(205, lb.scaledW)
        assertEquals(25, lb.offsetX)
    }
}
