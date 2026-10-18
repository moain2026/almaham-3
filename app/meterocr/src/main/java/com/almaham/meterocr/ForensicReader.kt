package com.almaham.meterocr

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/**
 * Forensic (deterministic, no-ML) seven-segment line reader — Kotlin port of lab/forensic_reader.py
 * (contract docs/agent-contract.md §2). Owner: agent B. No OpenCV: plain array operations only.
 *
 * Input: a line crop as ARGB pixels (Bitmap.getPixels order), any size. Output: integer part only (decimals are never
 * read), one entry per digit with class, honest confidence, box in crop pixels and the measured a..g segment pattern.
 * Every constant and every arithmetic step mirrors the Python reference so results match on the same pixels
 * (verified by ForensicReaderTest on 5 fixed crops).
 */
object ForensicReader {
    const val WORK_H = 96
    private const val BG_K_FRAC = 0.45
    private val SHEARS = DoubleArray(29) { (-350 + 25 * it) / 1000.0 }
    const val INT_DIGITS = 6
    private const val H_TOL = 0.15
    private const val ONE_W = 0.45
    private const val MAX_PIECE_W_TO_H = 1.6
    private const val MIN_PIECE_AREA_FRAC = 0.002
    private const val THR_MIN = 0.2
    private const val THR_MAX = 0.6
    private const val SPREAD_MIN = 0.3
    private const val CONF_ONE = 0.9
    const val CONF_HIGH = 0.95
    const val CONF_LOW_CAP = 0.79
    const val MIN_LEN_HIGH = 5
    private val VARIANTS = arrayOf("max", "gray", "green")
    private const val SEG_ORDER = "abcdefg"
    private val PATTERNS: List<Pair<Int, String>> = listOf(
        0 to "abcdef", 1 to "bc", 2 to "abdeg", 3 to "abcdg", 4 to "bcfg", 5 to "acdfg", 6 to "acdefg", 7 to "abc",
        8 to "abcdefg", 9 to "abcdfg", 7 to "abcf", 9 to "abcfg", 6 to "cdefg",
    )
    private val PAT_BITS: List<Pair<Int, IntArray>> = PATTERNS.map { (c, p) -> c to IntArray(7) { if (p.contains(SEG_ORDER[it])) 1 else 0 } }
    private val WIN: Array<DoubleArray> = arrayOf( // a..g: x0, y0, x1, y1 as fractions of the digit box
        doubleArrayOf(0.25, 0.00, 0.75, 0.16), doubleArrayOf(0.70, 0.15, 1.00, 0.42), doubleArrayOf(0.70, 0.58, 1.00, 0.85),
        doubleArrayOf(0.25, 0.84, 0.75, 1.00), doubleArrayOf(0.00, 0.58, 0.30, 0.85), doubleArrayOf(0.00, 0.15, 0.30, 0.42),
        doubleArrayOf(0.25, 0.42, 0.75, 0.58),
    )

    data class Digit(val cls: Int, val conf: Double, val box: DoubleArray, val segments: IntArray)
    data class Result(val text: String, val digits: List<Digit>, val status: String, val ms: Double) {
        /** Integer value without leading zeros ("" if nothing was read). */
        val value: String get() = if (text.isEmpty()) "" else text.trimStart('0').ifEmpty { "0" }
    }

    // ------------------------------------------------------------------ portable primitives
    /** Plain 2-D array of doubles (row-major). */
    class Plane(val w: Int, val h: Int, val v: DoubleArray = DoubleArray(w * h)) {
        operator fun get(x: Int, y: Int) = v[y * w + x]
        operator fun set(x: Int, y: Int, value: Double) { v[y * w + x] = value }
    }

    /** Binary mask (0/1) row-major. */
    class Mask(val w: Int, val h: Int, val v: IntArray = IntArray(w * h)) {
        operator fun get(x: Int, y: Int) = v[y * w + x]
        operator fun set(x: Int, y: Int, value: Int) { v[y * w + x] = value }
    }

    fun resizeBox(src: Plane, outW: Int, outH: Int): Plane {
        val h = src.h; val w = src.w
        val ii = DoubleArray((h + 1) * (w + 1))
        for (y in 0 until h) {
            var row = 0.0
            for (x in 0 until w) {
                row += src[x, y]
                ii[(y + 1) * (w + 1) + x + 1] = ii[y * (w + 1) + x + 1] + row
            }
        }
        val out = Plane(outW, outH)
        for (i in 0 until outH) {
            val y0 = i * h / outH; val y1 = max((i + 1) * h / outH, y0 + 1)
            for (j in 0 until outW) {
                val x0 = j * w / outW; val x1 = max((j + 1) * w / outW, x0 + 1)
                val s = ii[y1 * (w + 1) + x1] - ii[y0 * (w + 1) + x1] - ii[y1 * (w + 1) + x0] + ii[y0 * (w + 1) + x0]
                out[j, i] = s / ((y1 - y0) * (x1 - x0))
            }
        }
        return out
    }

    private fun filter1d(a: Plane, k: Int, vertical: Boolean, isMax: Boolean): Plane {
        val r = k / 2
        val out = Plane(a.w, a.h)
        for (y in 0 until a.h) for (x in 0 until a.w) {
            var best = if (isMax) Double.NEGATIVE_INFINITY else Double.POSITIVE_INFINITY
            if (vertical) {
                for (yy in max(0, y - r) until min(a.h, y + r + 1)) { val q = a[x, yy]; best = if (isMax) max(best, q) else min(best, q) }
            } else {
                for (xx in max(0, x - r) until min(a.w, x + r + 1)) { val q = a[xx, y]; best = if (isMax) max(best, q) else min(best, q) }
            }
            out[x, y] = best
        }
        return out
    }

    /** Morphological closing with a k x k square, window clipped at the border (same as the Python reference). */
    fun closeRect(a: Plane, k: Int): Plane {
        val d = filter1d(filter1d(a, k, vertical = true, isMax = true), k, vertical = false, isMax = true)
        return filter1d(filter1d(d, k, vertical = true, isMax = false), k, vertical = false, isMax = false)
    }

    fun otsu(u8: IntArray): Int {
        val hist = DoubleArray(256)
        for (p in u8) hist[p] += 1.0
        val total = u8.size.toDouble()
        var sumAll = 0.0
        for (t in 0 until 256) sumAll += t * hist[t]
        var w0 = 0.0; var s0 = 0.0; var best = -1.0; var thr = 0
        for (t in 0 until 256) {
            w0 += hist[t]
            if (w0 == 0.0) continue
            val w1 = total - w0
            if (w1 == 0.0) break
            s0 += t * hist[t]
            val m0 = s0 / w0; val m1 = (sumAll - s0) / w1
            val v = w0 * w1 * (m0 - m1) * (m0 - m1)
            if (v > best) { best = v; thr = t }
        }
        return thr
    }

    /** 8-connected components in scan order of first pixel: (x, y, w, h, area) + label image (1-based). */
    fun components(m: Mask): Pair<List<IntArray>, IntArray> {
        val lab = IntArray(m.w * m.h)
        val out = ArrayList<IntArray>()
        val stack = IntArray(m.w * m.h)
        for (y in 0 until m.h) for (x in 0 until m.w) {
            if (m[x, y] == 0 || lab[y * m.w + x] != 0) continue
            val n = out.size + 1
            var sp = 0
            stack[sp++] = y * m.w + x
            lab[y * m.w + x] = n
            var x0 = x; var x1 = x; var y0 = y; var y1 = y; var area = 0
            while (sp > 0) {
                val p = stack[--sp]
                val cy = p / m.w; val cx = p % m.w
                area++
                x0 = min(x0, cx); x1 = max(x1, cx); y0 = min(y0, cy); y1 = max(y1, cy)
                for (dy in -1..1) for (dx in -1..1) {
                    val ny = cy + dy; val nx = cx + dx
                    if (ny in 0 until m.h && nx in 0 until m.w && m[nx, ny] != 0 && lab[ny * m.w + nx] == 0) {
                        lab[ny * m.w + nx] = n
                        stack[sp++] = ny * m.w + nx
                    }
                }
            }
            out.add(intArrayOf(x0, y0, x1 - x0 + 1, y1 - y0 + 1, area))
        }
        return out to lab
    }

    /** Nearest-neighbour shear: out[y, x] = m[y, floor(x - k*(y - h/2) + 0.5)]. */
    fun shear(m: Mask, k: Double): Mask {
        val out = Mask(m.w, m.h)
        for (y in 0 until m.h) {
            val off = k * (y - m.h / 2.0)
            for (x in 0 until m.w) {
                val src = floor(x - off + 0.5).toInt()
                if (src in 0 until m.w) out[x, y] = m[src, y]
            }
        }
        return out
    }

    // ------------------------------------------------------------------ pipeline
    fun channel(argb: IntArray, w: Int, h: Int, variant: String): Plane {
        val p = Plane(w, h)
        for (i in argb.indices) {
            val c = argb[i]
            val r = (c shr 16) and 0xFF; val g = (c shr 8) and 0xFF; val b = c and 0xFF
            p.v[i] = when (variant) {
                "max" -> max(max(b, g), r)
                "gray" -> (299 * r + 587 * g + 114 * b) / 1000
                else -> g
            }.toDouble()
        }
        return p
    }

    fun inkMask(lumFull: Plane): Mask {
        val outW = max(1, lumFull.w * WORK_H / lumFull.h)
        val lum = resizeBox(lumFull, outW, WORK_H)
        val k = max(3, (WORK_H * BG_K_FRAC).toInt()) or 1
        val bg = closeRect(lum, k)
        val dark = DoubleArray(lum.v.size) { max(0.0, bg.v[it] - lum.v[it]) }
        var lo = Double.POSITIVE_INFINITY; var hi = Double.NEGATIVE_INFINITY
        for (d in dark) { lo = min(lo, d); hi = max(hi, d) }
        val u8 = IntArray(dark.size) { if (hi <= lo) 0 else floor((dark[it] - lo) * 255.0 / (hi - lo)).toInt() }
        val t = otsu(u8)
        return Mask(outW, WORK_H, IntArray(u8.size) { if (u8[it] > t) 1 else 0 })
    }

    fun clean(m: Mask): Mask {
        val h = m.h; val w = m.w
        val (comps, lab) = components(m)
        val keep = IntArray(comps.size + 1)
        comps.forEachIndexed { idx, c ->
            val (x, y, bw, bh, area) = c.toList()
            val touches = x == 0 || y == 0 || x + bw >= w || y + bh >= h
            val frameLike = touches && (bw > 0.6 * h || bh > 0.95 * h || area < 0.2 * bw * bh || bw < 0.12 * bh)
            val thinLine = bw > MAX_PIECE_W_TO_H * h * 0.5 && area < 0.25 * bw * bh
            keep[idx + 1] = if (!frameLike && !thinLine && area >= MIN_PIECE_AREA_FRAC * h * h) 1 else 0
        }
        return Mask(w, h, IntArray(lab.size) { keep[lab[it]] })
    }

    /** argmax over SHEARS of n*sum(col^2) - (sum col)^2 (exact integer variance x n^2). */
    fun deskew(m: Mask): Pair<Mask, Double> {
        var best = -1L; var bk = 0.0; var bm = m
        for (k in SHEARS) {
            val s = shear(m, k)
            var sum = 0L; var sq = 0L
            for (x in 0 until s.w) {
                var c = 0L
                for (y in 0 until s.h) c += s[x, y]
                sum += c; sq += c * c
            }
            val v = s.w * sq - sum * sum
            if (v > best) { best = v; bk = k; bm = s }
        }
        return bm to bk
    }

    private fun group(pieces: List<IntArray>): List<IntArray> {
        val sorted = pieces.sortedWith(compareBy<IntArray>({ it[0] }, { it[1] }, { it[2] }, { it[3] }))
        val groups = ArrayList<IntArray>()
        for (p in sorted) {
            val (x, y, w, h) = p.toList()
            val last = groups.lastOrNull()
            if (last != null && x < last[2] - 1) {
                groups[groups.size - 1] = intArrayOf(min(last[0], x), min(last[1], y), max(last[2], x + w), max(last[3], y + h))
            } else groups.add(intArrayOf(x, y, x + w, y + h))
        }
        return groups.map { intArrayOf(it[0], it[1], it[2] - it[0], it[3] - it[1]) }
    }

    fun median(v: List<Double>): Double {
        val s = v.sorted(); val n = s.size
        return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2.0
    }

    fun percentile(v: List<Double>, q: Double): Double {
        val s = v.sorted()
        val pos = (s.size - 1) * q / 100.0
        val lo = pos.toInt(); val hi = min(lo + 1, s.size - 1)
        return s[lo] + (s[hi] - s[lo]) * (pos - lo)
    }

    private fun refHeight(boxes: List<IntArray>, H: Int): Double? {
        val hs = boxes.map { it[3] }.filter { it >= 0.25 * H }
        if (hs.isEmpty()) return null
        val votes = hs.map { h -> hs.count { o -> abs(o - h) <= H_TOL * h } to h }
        val top = votes.maxOf { it.first }
        return median(votes.filter { it.first == top }.map { it.second.toDouble() })
    }

    private fun mainBoxes(m: Mask): List<IntArray> {
        val H = m.h
        val pieces = components(m).first.filter { it[4] >= 4 }.map { intArrayOf(it[0], it[1], it[2], it[3]) }
        var boxes = group(pieces)
        var ref = refHeight(boxes, H) ?: return emptyList()
        if (boxes.any { it[3] > (1 + 2 * H_TOL) * ref }) {
            boxes = group(pieces.filter { it[3] <= (1 + 2 * H_TOL) * ref && it[2] <= 2.5 * ref })
            ref = refHeight(boxes, H) ?: ref
        }
        val main = ArrayList<IntArray>()
        var started = false
        for (b in boxes) {
            val (x, _, w, h) = b.toList()
            if (abs(h - ref) <= H_TOL * ref && !(x <= 1 && w < ONE_W * ref * 0.3)) { main.add(b); started = true }
            else if (started && h > 0.2 * ref && h < (1 - H_TOL) * ref) break
        }
        if (main.isEmpty()) return emptyList()
        val wide = main.map { it[2].toDouble() }.filter { it > ONE_W * ref * 0.55 }.ifEmpty { listOf(main[0][2].toDouble()) }
        val wmed = median(wide)
        val runs = ArrayList<MutableList<IntArray>>()
        var cur = mutableListOf(main[0])
        for (i in 1 until main.size) {
            val a = main[i - 1]; val b = main[i]
            if (b[0] - (a[0] + a[2]) > 1.6 * wmed) { runs.add(cur); cur = mutableListOf(b) } else cur.add(b)
        }
        runs.add(cur)
        var best = runs[0]
        for (r in runs) if (r.size > best.size) best = r   // first longest, like Python max()
        return best.take(INT_DIGITS)
    }

    private fun segValues(m: Mask, box: IntArray, typicalW: Double): DoubleArray {
        var x = box[0].toDouble(); val y = box[1].toDouble(); var bw = box[2].toDouble(); val bh = box[3].toDouble()
        if (bw < ONE_W * typicalW) { x = x + bw - typicalW; bw = typicalW }
        return DoubleArray(7) { s ->
            val (a, b, c, d) = WIN[s].toList()
            val x0 = (x + a * bw).toInt(); val x1 = (x + c * bw).toInt()
            val y0 = (y + b * bh).toInt(); val y1 = (y + d * bh).toInt()
            val xs = max(0, x0); val xe = min(m.w, max(x0 + 1, x1))
            val ys = max(0, y0); val ye = min(m.h, max(y0 + 1, y1))
            if (ye > ys && xe > xs) {
                var sum = 0
                for (yy in ys until ye) for (xx in xs until xe) sum += m[xx, yy]
                sum.toDouble() / ((ye - ys) * (xe - xs))
            } else 0.0
        }
    }

    /** returns (thr, mean low, mean high). */
    private fun twoCluster(vals: List<Double>): DoubleArray {
        val v = vals.sorted()
        var best = -1.0; var thr = v.sum() / v.size
        for (i in 1 until v.size) {
            var sl = 0.0; for (j in 0 until i) sl += v[j]
            var sh = 0.0; for (j in i until v.size) sh += v[j]
            val ml = sl / i; val mh = sh / (v.size - i)
            val d = mh - ml
            val sc = (i * (v.size - i)).toDouble() * (d * d)   // Python: len(lo)*len(hi)*(mh-ml)**2
            if (sc > best) { best = sc; thr = (v[i - 1] + v[i]) / 2 }
        }
        val lo = v.filter { it <= thr }; val hi = v.filter { it > thr }
        return doubleArrayOf(thr, if (lo.isNotEmpty()) lo.sum() / lo.size else 0.0, if (hi.isNotEmpty()) hi.sum() / hi.size else 1.0)
    }

    private data class Cls(val cls: Int, val conf: Double, val bits: IntArray)

    private fun classify(seg: DoubleArray, thr: Double, spread: Double): Cls {
        val soft = DoubleArray(7) { min(1.0, max(0.0, (seg[it] - thr) / spread + 0.5)) }
        val dists = PAT_BITS.map { (c, bits) ->
            var d = 0.0
            for (i in 0 until 7) d += abs(bits[i] - soft[i])
            d to c
        }.sortedBy { it.first }   // stable, like Python's list.sort
        val (bestD, bestC) = dists[0]
        val secondD = dists.drop(1).first { it.second != bestC }.first
        return Cls(bestC, min(1.0, (secondD - bestD) / 2.0), IntArray(7) { if (soft[it] >= 0.5) 1 else 0 })
    }

    private class Exam(val cls: Int, val conf: Double, val box: DoubleArray, val bits: IntArray)

    private fun readVariant(argb: IntArray, w: Int, h: Int, variant: String): List<Exam> {
        val (mask, k) = deskew(clean(inkMask(channel(argb, w, h, variant))))
        val boxes = mainBoxes(mask)
        if (boxes.isEmpty()) return emptyList()
        val typicalW = percentile(boxes.map { it[2].toDouble() }, 75.0)
        val segs = boxes.map { if (it[2] < ONE_W * typicalW) null else segValues(mask, it, typicalW) }
        val vals = segs.filterNotNull().flatMap { it.toList() }
        val tc = if (vals.isNotEmpty()) twoCluster(vals) else doubleArrayOf(0.4, 0.0, 1.0)
        val thr = min(max(tc[0], THR_MIN), THR_MAX)
        val spread = max(tc[2] - tc[1], SPREAD_MIN)
        val s = h.toDouble() / WORK_H
        return boxes.zip(segs).map { (b, sg) ->
            val (x, y, bw, bh) = b.toList()
            val dx = k * (y + bh / 2.0 - WORK_H / 2.0)
            val box = doubleArrayOf((x + dx) * s, y * s, (x + bw + dx) * s, (y + bh) * s)
            if (sg == null) Exam(1, CONF_ONE, box, intArrayOf(0, 1, 1, 0, 0, 0, 0))
            else classify(sg, thr, spread).let { Exam(it.cls, it.conf, box, it.bits) }
        }
    }

    /** Reads a line crop given as ARGB pixels (Bitmap.getPixels order), width [w], height [h]. */
    fun readLine(argb: IntArray, w: Int, h: Int): Result {
        val t0 = System.nanoTime()
        val exams = VARIANTS.map { readVariant(argb, w, h, it) }
        val texts = exams.map { e -> e.joinToString("") { it.cls.toString() } }
        val ms = { (System.nanoTime() - t0) / 1e6 }
        val nonEmpty = texts.filter { it.isNotEmpty() }
        if (nonEmpty.isEmpty()) return Result("", emptyList(), "EMPTY", ms())
        // most-agreed text; ties -> earliest variant (max(RGB) first), same as the Python reference
        val win = nonEmpty.maxWith(compareBy<String>({ t -> texts.count { it == t } }, { t -> -texts.indexOf(t) }))
        val base = exams[texts.indexOf(win)]
        val sameLen = exams.filter { it.size == base.size }
        val digits = base.mapIndexed { i, d ->
            val nAgree = sameLen.count { it[i].cls == d.cls }
            val p = if (nAgree == VARIANTS.size && base.size >= MIN_LEN_HIGH && !(i == 0 && d.cls != 0)) CONF_HIGH
            else min(CONF_LOW_CAP, d.conf * nAgree / VARIANTS.size)
            Digit(d.cls, p, d.box, d.bits)
        }
        val unanimous = texts.count { it == win } == VARIANTS.size
        val status = when {
            unanimous && digits.all { it.conf >= 0.8 } -> "OK"
            base.size < MIN_LEN_HIGH -> "MISSING_DIGIT"
            else -> "UNSURE"
        }
        return Result(win, digits, status, ms())
    }
}
