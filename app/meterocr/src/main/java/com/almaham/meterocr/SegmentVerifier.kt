package com.almaham.meterocr

import android.graphics.Bitmap

/**
 * Seven-segment consistency verifier (no learning). Mirrors lab/segverify.py.
 * Measures the ink of the 7 segment zones inside a predicted digit box and compares the ON/OFF pattern with the
 * predicted class. Catches 0↔8, 6↔8, 9↔8, 5↔6, 3↔9, 1↔7 confusions that a CNN scores confidently on ghosted LCDs.
 */
object SegmentVerifier {
    private const val ALL = "abcdefg"
    private val SEG = mapOf(0 to "abcdef", 1 to "bc", 2 to "abged", 3 to "abgcd", 4 to "fgbc", 5 to "afgcd", 6 to "afgedc",
        7 to "abc", 8 to "abcdefg", 9 to "abcdfg")
    private val PATTERN: Map<Int, BooleanArray> = SEG.mapValues { (_, on) -> BooleanArray(7) { on.contains(ALL[it]) } }
    private const val NARROW_RATIO = 0.55f
    private const val MIN_SIZE = 8
    private const val T = 0.22f
    private const val M = 0.5f
    // zones as (x0,y0,x1,y1) fractions, order a,b,c,d,e,f,g
    private val ZONES = arrayOf(
        floatArrayOf(0.2f, 0f, 0.8f, T), floatArrayOf(1 - T, 0.12f, 1f, M - 0.08f), floatArrayOf(1 - T, M + 0.08f, 1f, 1 - 0.12f),
        floatArrayOf(0.2f, 1 - T, 0.8f, 1f), floatArrayOf(0f, M + 0.08f, T, 1 - 0.12f), floatArrayOf(0f, 0.12f, T, M - 0.08f),
        floatArrayOf(0.2f, M - T / 2, 0.8f, M + T / 2),
    )

    /** Grayscale (0..255) plane of a bitmap, row-major. */
    fun gray(b: Bitmap): IntArray {
        val px = IntArray(b.width * b.height)
        b.getPixels(px, 0, b.width, 0, 0, b.width, b.height)
        return IntArray(px.size) { i -> val p = px[i]; (((p shr 16) and 0xFF) * 299 + ((p shr 8) and 0xFF) * 587 + (p and 0xFF) * 114) / 1000 }
    }

    /** Ink per segment in [0,1], or null when the box is too small to measure. */
    fun segmentInk(g: IntArray, imgW: Int, imgH: Int, bx1: Float, by1: Float, bx2: Float, by2: Float): FloatArray? {
        var x1 = maxOf(0, bx1.toInt()); val y1 = maxOf(0, by1.toInt()); val x2 = minOf(imgW, bx2.toInt()); val y2 = minOf(imgH, by2.toInt())
        var w = x2 - x1; val h = y2 - y1
        if (w < 3 || h < MIN_SIZE) return null
        if (w.toFloat() / h < NARROW_RATIO) { x1 = maxOf(0, x2 - Math.round(h * 0.6f)); w = x2 - x1 }
        // Otsu threshold on the cell
        val hist = IntArray(256); var sum = 0L; var n = 0
        for (y in y1 until y2) for (x in x1 until x2) { val v = g[y * imgW + x]; hist[v]++; sum += v; n++ }
        if (n == 0) return null
        val invert = sum / n < 100
        var sumB = 0L; var wB = 0; var best = 0.0; var thr = 128
        for (t in 0 until 256) {
            wB += hist[t]; if (wB == 0) continue
            val wF = n - wB; if (wF == 0) break
            sumB += t.toLong() * hist[t]
            val mB = sumB.toDouble() / wB; val mF = (sum - sumB).toDouble() / wF
            val v = wB.toDouble() * wF * (mB - mF) * (mB - mF)
            if (v > best) { best = v; thr = t }
        }
        val ink = FloatArray(7)
        for (s in 0 until 7) {
            val z = ZONES[s]
            val zx0 = x1 + (z[0] * w).toInt(); val zy0 = y1 + (z[1] * h).toInt()
            val zx1 = maxOf(zx0 + 1, x1 + (z[2] * w).toInt()); val zy1 = maxOf(zy0 + 1, y1 + (z[3] * h).toInt())
            var dark = 0; var cnt = 0
            for (y in zy0 until minOf(zy1, y2)) for (x in zx0 until minOf(zx1, x2)) {
                var v = g[y * imgW + x]; if (invert) v = 255 - v
                if (v < thr) dark++; cnt++
            }
            ink[s] = if (cnt == 0) 0f else dark.toFloat() / cnt
        }
        return ink
    }

    fun onPattern(ink: FloatArray): BooleanArray {
        val lo = ink.min(); val hi = ink.max()
        return if (hi - lo < 0.15f) BooleanArray(7) { ink[it] > 0.5f } else BooleanArray(7) { ink[it] > (lo + hi) / 2 }
    }

    fun agreement(ink: FloatArray, cls: Int): Float {
        val p = onPattern(ink); val ref = PATTERN[cls] ?: return 1f
        return (0 until 7).count { p[it] == ref[it] } / 7f
    }

    fun bestPatternClass(ink: FloatArray): Pair<Int, Float> {
        val p = onPattern(ink)
        return PATTERN.entries.map { (c, ref) -> c to (0 until 7).count { p[it] == ref[it] } / 7f }.maxBy { it.second }
    }

    /** Returns digits annotated with segment agreement (does not change the class). */
    fun verify(g: IntArray, imgW: Int, imgH: Int, digits: List<Digit>): List<Digit> = digits.map { d ->
        val ink = segmentInk(g, imgW, imgH, d.x1, d.y1, d.x2, d.y2) ?: return@map d
        d.copy(segAgree = agreement(ink, d.cls), segCls = bestPatternClass(ink).first)
    }
}
