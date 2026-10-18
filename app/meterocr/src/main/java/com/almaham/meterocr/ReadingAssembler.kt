package com.almaham.meterocr

import com.almaham.meterocr.MeterOcrConfig as C

/** One detection from the digit reader net, in line-crop pixels. cls 0..9 = digit, 10 = decimal dot. */
data class Detection(val cls: Int, val score: Float, val x1: Float, val y1: Float, val x2: Float, val y2: Float)

/** A digit kept after merging, with its best competing class (for honest uncertainty). */
data class Digit(
    val cls: Int, val score: Float, val x1: Float, val y1: Float, val x2: Float, val y2: Float,
    val altCls: Int = -1, val altScore: Float = 0f,
    /** Seven-segment pattern agreement with [cls] from SegmentVerifier; 1.0 = all 7 segments match. */
    val segAgree: Float = 1f, val segCls: Int = -1,
) {
    val cx get() = (x1 + x2) / 2f
    val cy get() = (y1 + y2) / 2f
    val h get() = y2 - y1
    val w get() = x2 - x1
    val uncertain get() = score < C.DIGIT_CONF_MIN || altScore >= C.ALT_RATIO * score || segAgree < C.SEG_AGREE_MIN
}

enum class ReadingStatus { OK, EMPTY, MISSING_DIGIT, TOO_MANY_DIGITS }

/** Integer reading as displayed (leading zeros kept in [text]); decimals are never part of it. */
data class Reading(val text: String = "", val status: ReadingStatus = ReadingStatus.EMPTY, val digits: List<Digit> = emptyList()) {
    /** Cleaned value: leading zeros removed ("003155" -> "3155", "000000" -> "0"); empty when nothing was read. */
    val value: String get() = NumberCleaner.stripLeadingZeros(text)
    val confident: Boolean get() = status == ReadingStatus.OK && digits.isNotEmpty() && digits.none { it.uncertain }
    val minConfidence: Float get() = digits.minOfOrNull { it.score } ?: 0f
    /** Indices (into [text]) of digits the engine is unsure about: the UI colours exactly these. */
    val uncertainIndices: List<Int> get() = digits.withIndex().filter { it.value.uncertain }.map { it.index }
}

/**
 * Detections -> one integer reading. Mirrors lab/assemble.py line by line; both are covered by the same test cases.
 */
object ReadingAssembler {

    fun iou(a: Digit, b: Digit): Float {
        val iw = maxOf(0f, minOf(a.x2, b.x2) - maxOf(a.x1, b.x1))
        val ih = maxOf(0f, minOf(a.y2, b.y2) - maxOf(a.y1, b.y1))
        val inter = iw * ih
        val ua = a.w * a.h + b.w * b.h - inter
        return if (ua > 0f) inter / ua else 0f
    }

    /** Cross-class NMS that keeps the runner-up class of each box. */
    fun merge(dets: List<Detection>): List<Digit> {
        val kept = ArrayList<Digit>()
        for (d in dets.sortedByDescending { it.score }) {
            val cand = Digit(d.cls, d.score, d.x1, d.y1, d.x2, d.y2)
            val i = kept.indexOfFirst { iou(it, cand) >= C.MERGE_IOU }
            if (i < 0) kept.add(cand)
            else {
                val k = kept[i]
                if (d.cls != k.cls && d.score > k.altScore) kept[i] = k.copy(altCls = d.cls, altScore = d.score)
            }
        }
        return kept
    }

    fun groupLines(digits: List<Digit>): List<List<Digit>> {
        val lines = ArrayList<MutableList<Digit>>()
        for (d in digits.sortedByDescending { it.h }) {
            val line = lines.firstOrNull { ln ->
                val ref = ln[0]
                val ov = maxOf(0f, minOf(d.y2, ref.y2) - maxOf(d.y1, ref.y1)) / maxOf(1e-6f, minOf(d.h, ref.h))
                ov >= C.LINE_OVERLAP && minOf(d.h, ref.h) / maxOf(d.h, ref.h) >= C.HEIGHT_SIMILAR
            }
            if (line != null) line.add(d) else lines.add(mutableListOf(d))
        }
        return lines.map { it.sortedBy { d -> d.cx } }
    }

    fun median(v: List<Float>): Float {
        val s = v.sorted()
        val n = s.size
        return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2f
    }

    fun pickMainLine(lines: List<List<Digit>>): List<Digit>? =
        lines.filter { ln -> ln.any { it.cls < 10 } }
            .maxWithOrNull(compareBy<List<Digit>>({ median(it.filter { d -> d.cls < 10 }.map { d -> d.h }) }, { it.size }))

    fun integerPart(line: List<Digit>, dots: List<Digit>): List<Digit> {
        var ds = line.filter { it.cls < 10 }
        if (ds.isEmpty()) return ds
        var cut = ds.size
        for (dot in dots.sortedBy { it.cx }) {
            if (dot.cy < ds[0].cy - ds[0].h * 0.2f) continue
            for (i in 1 until ds.size) {
                if (ds[i - 1].cx < dot.cx && dot.cx < ds[i].cx) { cut = minOf(cut, i); break }
            }
        }
        for (i in 1 until ds.size) {
            val ref = median(ds.subList(0, i).map { it.h })
            if (ds[i].h < C.SMALL_DIGIT_RATIO * ref) { cut = minOf(cut, i); break }
        }
        ds = ds.subList(0, cut)
        if (ds.size >= 3) {
            val pitches = (0 until ds.size - 1).map { ds[it + 1].cx - ds[it].cx }
            val med = median(pitches)
            val split = pitches.indexOfFirst { it > C.GAP_SPLIT * med }
            if (split >= 0) ds = ds.subList(0, split + 1)
        }
        return ds
    }

    /** Pitch-lattice gap analysis: cells the regular pitch predicts between detected digits but nothing covered. */
    fun missingCells(ds: List<Digit>): List<FloatArray> {
        if (ds.size < C.LATTICE_MIN_DIGITS) return emptyList()
        val pitches = (0 until ds.size - 1).map { ds[it + 1].cx - ds[it].cx }
        val pitch = median(pitches)
        if (pitch <= 0f) return emptyList()
        val out = ArrayList<FloatArray>()
        for ((i, p) in pitches.withIndex()) {
            val k = Math.round(p / pitch)
            if (k >= 2 && Math.abs(p - k * pitch) <= C.LATTICE_FILL_TOL * pitch * k) {
                val a = ds[i]; val b = ds[i + 1]; val w = (a.w + b.w) / 2f
                for (j in 1 until k) {
                    val cx = a.cx + j * p / k
                    val y1 = a.y1 + (b.y1 - a.y1) * j / k; val y2 = a.y2 + (b.y2 - a.y2) * j / k
                    out.add(floatArrayOf(cx - w / 2, y1, cx + w / 2, y2))
                }
            }
        }
        return out
    }

    fun structureOk(ds: List<Digit>): Boolean {
        if (ds.size < 3) return true
        val pitches = (0 until ds.size - 1).map { ds[it + 1].cx - ds[it].cx }
        val med = median(pitches)
        return pitches.all { it <= C.GAP_MISSING * med }
    }

    fun assemble(dets: List<Detection>, width: Float, height: Float): Reading {
        val clipped = dets.filter { it.x2 > it.x1 && it.y2 > it.y1 }
            .map { it.copy(x1 = maxOf(0f, it.x1), y1 = maxOf(0f, it.y1), x2 = minOf(width, it.x2), y2 = minOf(height, it.y2)) }
        val merged = merge(clipped)
        val digits = merged.filter { it.cls < 10 }
        val dots = merged.filter { it.cls == C.DOT_CLASS }
        val main = pickMainLine(groupLines(digits)) ?: return Reading()
        val ds = integerPart(main, dots)
        if (ds.size < C.MIN_INTEGER_DIGITS) return Reading()
        val text = ds.joinToString("") { it.cls.toString() }
        if (ds.size > C.MAX_INTEGER_DIGITS) return Reading(text, ReadingStatus.TOO_MANY_DIGITS, ds)
        if (!structureOk(ds)) return Reading(text, ReadingStatus.MISSING_DIGIT, ds)
        return Reading(text, ReadingStatus.OK, ds)
    }
}

/** Number cleaning (brief §2.6): leading zeros and decimals are dropped; everything else is ignored upstream. */
object NumberCleaner {
    fun stripLeadingZeros(text: String): String {
        if (text.isEmpty() || !text.all { it.isDigit() }) return ""
        val t = text.trimStart('0')
        return if (t.isEmpty()) "0" else t
    }
}
