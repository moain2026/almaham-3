package com.almaham.meterocr

/** One voted digit. [src]: both | neural | forensic | conflict. */
data class VotedDigit(val cls: Int, val conf: Float, val uncertain: Boolean, val src: String)

data class VotedReading(val text: String, val digits: List<VotedDigit>, val status: String) {
    val value: String get() = NumberCleaner.stripLeadingZeros(text)
    val confident: Boolean get() = digits.isNotEmpty() && digits.none { it.uncertain }
    val uncertainIndices: List<Int> get() = digits.withIndex().filter { it.value.uncertain }.map { it.index }
}

/**
 * Per-digit vote between DigitNet (neural) and ForensicReader (deterministic). Mirrors lab/vote.py exactly:
 * right-aligned positions; agreement -> keep; one engine only -> keep with its own confidence; disagreement ->
 * the one with conf >= HIGH if exactly one is high, else keep the higher but mark uncertain.
 */
object Vote {
    const val HIGH = 0.8f

    private fun neuralDigits(r: Reading): List<Pair<Int, Float>> = r.digits.map { d ->
        val honest = d.segAgree >= MeterOcrConfig.SEG_AGREE_MIN && d.altScore < MeterOcrConfig.ALT_RATIO * d.score
        d.cls to minOf(d.score, 1f) * (if (honest) 1f else 0.5f)
    }

    private fun forensicDigits(f: ForensicReader.Result?): List<Pair<Int, Float>> =
        f?.digits?.map { it.cls to it.conf.toFloat() } ?: emptyList()

    fun vote(neural: Reading, forensic: ForensicReader.Result?): VotedReading {
        val a = neuralDigits(neural)
        val b = forensicDigits(forensic)
        if (a.isEmpty() && b.isEmpty()) return VotedReading("", emptyList(), "EMPTY")
        if (a.isEmpty() || b.isEmpty()) {
            val src = if (a.isNotEmpty()) "neural" else "forensic"
            return finish((a.ifEmpty { b }).map { (c, p) -> VotedDigit(c, p, p < HIGH, src) }, "SINGLE")
        }
        if (a.size != b.size) {
            val aHigh = a.all { it.second >= HIGH }
            val bHigh = b.all { it.second >= HIGH }
            if (aHigh && !bHigh) return finish(a.map { (c, p) -> VotedDigit(c, p, false, "neural") }, "LEN_NEURAL")
            if (bHigh && !aHigh) return finish(b.map { (c, p) -> VotedDigit(c, p, false, "forensic") }, "LEN_FORENSIC")
        }
        val n = maxOf(a.size, b.size)
        val ra = List<Pair<Int, Float>?>(n - a.size) { null } + a
        val rb = List<Pair<Int, Float>?>(n - b.size) { null } + b
        val ds = ArrayList<VotedDigit>()
        for (i in 0 until n) {
            val x = ra[i]; val y = rb[i]
            when {
                x == null || y == null -> { val (c, p) = x ?: y!!; ds.add(VotedDigit(c, p, true, if (x != null) "neural" else "forensic")) }
                x.first == y.first -> ds.add(VotedDigit(x.first, maxOf(x.second, y.second), false, "both"))
                else -> {
                    val xa = x.second >= HIGH; val yb = y.second >= HIGH
                    when {
                        xa && !yb -> ds.add(VotedDigit(x.first, x.second, false, "neural"))
                        yb && !xa -> ds.add(VotedDigit(y.first, y.second, false, "forensic"))
                        else -> { val best = if (x.second >= y.second) x else y; ds.add(VotedDigit(best.first, best.second, true, "conflict")) }
                    }
                }
            }
        }
        return finish(ds, "VOTE")
    }

    private fun finish(ds: List<VotedDigit>, status: String) = VotedReading(ds.joinToString("") { it.cls.toString() }, ds, status)
}
