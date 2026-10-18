package com.almaham.meterocr

import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/** Axis-aligned rectangle in normalised [0,1] coordinates of some frame (x = left→right, y = top→bottom). */
data class NormRect(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    val width get() = right - left
    val height get() = bottom - top
    fun clamped() = NormRect(left.coerceIn(0f, 1f), top.coerceIn(0f, 1f), right.coerceIn(0f, 1f), bottom.coerceIn(0f, 1f))
}

/** Integer pixel rectangle. */
data class PixelRect(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width get() = right - left
    val height get() = bottom - top
}

/** How PreviewView maps the camera buffer onto the view (androidx.camera.view.PreviewView.ScaleType). */
enum class PreviewScale { FILL_CENTER, FIT_CENTER }

/**
 * Pure functions that convert the reader's on-screen rectangle to a crop in the captured image.
 * No Android imports: fully unit-tested on the JVM (RectGeometryTest).
 *
 * Model (all in the *upright* frame the user sees):
 *  1. The sensor buffer is rotated by `rotationDegrees` (ImageProxy.imageInfo.rotationDegrees) to become upright.
 *  2. The upright buffer (uw x uh) is scaled onto the view (vw x vh) with FILL_CENTER (crop) or FIT_CENTER (letterbox).
 *  3. The rectangle is given in view pixels; we map it back to upright-buffer normalised coords, then to
 *     raw-buffer pixel coords by undoing the rotation.
 * Digital zoom does NOT change this mapping: CameraX applies zoom in the sensor pipeline, so the buffer the app
 * receives is already the zoomed field of view — exactly what the preview showed.
 */
object RectGeometry {

    /** Step 2 inverse: view-pixel rectangle -> normalised rectangle of the *upright* buffer. */
    fun viewToUpright(
        rectInView: NormRect, viewW: Float, viewH: Float,
        uprightW: Float, uprightH: Float, scale: PreviewScale,
    ): NormRect {
        require(viewW > 0 && viewH > 0 && uprightW > 0 && uprightH > 0) { "sizes must be positive" }
        val sx = viewW / uprightW
        val sy = viewH / uprightH
        val s = if (scale == PreviewScale.FILL_CENTER) max(sx, sy) else min(sx, sy)
        val shownW = uprightW * s          // size of the buffer as drawn in view pixels
        val shownH = uprightH * s
        val offX = (viewW - shownW) / 2f   // negative when the buffer is cropped (FILL), positive when letterboxed
        val offY = (viewH - shownH) / 2f
        fun mx(vx: Float) = (vx * viewW - offX) / shownW
        fun my(vy: Float) = (vy * viewH - offY) / shownH
        return NormRect(mx(rectInView.left), my(rectInView.top), mx(rectInView.right), my(rectInView.bottom)).clamped()
    }

    /**
     * Step 1 inverse: normalised rectangle in the upright frame -> normalised rectangle in the raw buffer.
     * rotationDegrees is the clockwise rotation that makes the raw buffer upright (0, 90, 180, 270).
     */
    fun uprightToRaw(r: NormRect, rotationDegrees: Int): NormRect = when (((rotationDegrees % 360) + 360) % 360) {
        0 -> r
        // upright = raw rotated 90° CW  =>  upright(x,y) = raw(y, 1-x)  =>  raw(x,y) = (upright.y, 1-upright.x)
        90 -> NormRect(r.top, 1f - r.right, r.bottom, 1f - r.left)
        180 -> NormRect(1f - r.right, 1f - r.bottom, 1f - r.left, 1f - r.top)
        270 -> NormRect(1f - r.bottom, r.left, 1f - r.top, r.right)
        else -> throw IllegalArgumentException("rotation must be a multiple of 90, got $rotationDegrees")
    }

    /** Normalised -> integer pixels, inclusive-exclusive, at least 1x1, inside the image. */
    fun toPixels(r: NormRect, imageW: Int, imageH: Int): PixelRect {
        val c = r.clamped()
        val l = (c.left * imageW).roundToInt().coerceIn(0, imageW - 1)
        val t = (c.top * imageH).roundToInt().coerceIn(0, imageH - 1)
        val rr = (c.right * imageW).roundToInt().coerceIn(l + 1, imageW)
        val b = (c.bottom * imageH).roundToInt().coerceIn(t + 1, imageH)
        return PixelRect(l, t, rr, b)
    }

    /** Full chain: view rectangle -> pixel crop of the raw captured buffer. */
    fun viewRectToRawCrop(
        rectInView: NormRect, viewW: Float, viewH: Float, scale: PreviewScale,
        rawW: Int, rawH: Int, rotationDegrees: Int,
    ): PixelRect {
        val rot = ((rotationDegrees % 360) + 360) % 360
        val swap = rot == 90 || rot == 270
        val uprightW = if (swap) rawH else rawW
        val uprightH = if (swap) rawW else rawH
        val upright = viewToUpright(rectInView, viewW, viewH, uprightW.toFloat(), uprightH.toFloat(), scale)
        return toPixels(uprightToRaw(upright, rot), rawW, rawH)
    }

    /** Letterbox parameters when fitting a (w x h) image into a (W x H) box: scale and top-left offset. */
    data class Letterbox(val scale: Float, val offsetX: Int, val offsetY: Int, val scaledW: Int, val scaledH: Int)

    fun letterbox(srcW: Int, srcH: Int, dstW: Int, dstH: Int, centreY: Boolean = true, centreX: Boolean = true): Letterbox {
        require(srcW > 0 && srcH > 0)
        val s = min(dstW.toFloat() / srcW, dstH.toFloat() / srcH)
        val sw = max(1, (srcW * s).roundToInt())
        val sh = max(1, (srcH * s).roundToInt())
        val ox = if (centreX) (dstW - sw) / 2 else 0
        val oy = if (centreY) (dstH - sh) / 2 else 0
        return Letterbox(s, ox, oy, sw, sh)
    }
}
