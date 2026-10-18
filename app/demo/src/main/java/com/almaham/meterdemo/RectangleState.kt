package com.almaham.meterdemo

import android.content.Context
import com.almaham.meterocr.MeterOcrConfig
import com.almaham.meterocr.NormRect

/** Which part of the rectangle a touch grabbed. */
enum class Handle { NONE, MOVE, TL, TR, BL, BR, L, R, T, B }

/**
 * Pure rectangle editing logic (drag / resize with min-max clamps) in normalised view coordinates,
 * plus persistence of the last rectangle (brief §2.2: the app remembers the last position).
 */
object RectangleState {
    private const val PREFS = "meter_rect"

    fun default(viewW: Float, viewH: Float): NormRect {
        val w = MeterOcrConfig.RECT_DEFAULT_WIDTH_FRACTION
        val hPx = w * viewW * MeterOcrConfig.RECT_DEFAULT_ASPECT
        val h = (hPx / viewH).coerceAtMost(MeterOcrConfig.RECT_MAX_SIZE_FRACTION)
        return NormRect((1 - w) / 2, (1 - h) / 2, (1 + w) / 2, (1 + h) / 2)
    }

    fun load(ctx: Context, viewW: Float, viewH: Float): NormRect {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!p.contains("l")) return default(viewW, viewH)
        return NormRect(p.getFloat("l", 0f), p.getFloat("t", 0f), p.getFloat("r", 1f), p.getFloat("b", 1f)).clamped()
    }

    fun save(ctx: Context, r: NormRect) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putFloat("l", r.left).putFloat("t", r.top).putFloat("r", r.right).putFloat("b", r.bottom).apply()
    }

    /** Hit test in view pixels. */
    fun hitTest(r: NormRect, x: Float, y: Float, viewW: Float, viewH: Float, radiusPx: Float): Handle {
        val l = r.left * viewW; val t = r.top * viewH; val rr = r.right * viewW; val b = r.bottom * viewH
        fun near(px: Float, py: Float) = Math.hypot((x - px).toDouble(), (y - py).toDouble()) <= radiusPx
        return when {
            near(l, t) -> Handle.TL
            near(rr, t) -> Handle.TR
            near(l, b) -> Handle.BL
            near(rr, b) -> Handle.BR
            Math.abs(x - l) <= radiusPx && y in t..b -> Handle.L
            Math.abs(x - rr) <= radiusPx && y in t..b -> Handle.R
            Math.abs(y - t) <= radiusPx && x in l..rr -> Handle.T
            Math.abs(y - b) <= radiusPx && x in l..rr -> Handle.B
            x in l..rr && y in t..b -> Handle.MOVE
            else -> Handle.NONE
        }
    }

    /** Apply a drag delta (normalised units) to the grabbed handle, keeping size within limits and inside the view. */
    fun apply(r: NormRect, h: Handle, dx: Float, dy: Float): NormRect {
        val minW = MeterOcrConfig.RECT_MIN_SIZE_FRACTION
        val minH = MeterOcrConfig.RECT_MIN_SIZE_FRACTION
        var l = r.left; var t = r.top; var rr = r.right; var b = r.bottom
        when (h) {
            Handle.MOVE -> {
                val ddx = dx.coerceIn(-l, 1f - rr)
                val ddy = dy.coerceIn(-t, 1f - b)
                return NormRect(l + ddx, t + ddy, rr + ddx, b + ddy)
            }
            Handle.TL -> { l += dx; t += dy }
            Handle.TR -> { rr += dx; t += dy }
            Handle.BL -> { l += dx; b += dy }
            Handle.BR -> { rr += dx; b += dy }
            Handle.L -> l += dx
            Handle.R -> rr += dx
            Handle.T -> t += dy
            Handle.B -> b += dy
            Handle.NONE -> return r
        }
        // Moving edges are clamped against the fixed opposite edge, then everything stays inside [0,1].
        val movesLeft = h == Handle.TL || h == Handle.BL || h == Handle.L
        val movesTop = h == Handle.TL || h == Handle.TR || h == Handle.T
        if (movesLeft) l = l.coerceIn(0f, maxOf(0f, rr - minW)) else rr = rr.coerceIn(minOf(1f, l + minW), 1f)
        if (movesTop) t = t.coerceIn(0f, maxOf(0f, b - minH)) else b = b.coerceIn(minOf(1f, t + minH), 1f)
        return NormRect(l, t, rr, b)
    }
}
