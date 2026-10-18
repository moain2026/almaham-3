package com.almaham.meterocr

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.os.SystemClock
import java.nio.FloatBuffer
import com.almaham.meterocr.MeterOcrConfig as C

/** Wall-clock milliseconds of each stage, measured with SystemClock.elapsedRealtimeNanos. */
data class StageTimes(
    val locatorPrepMs: Float, val locatorMs: Float, val linePrepMs: Float, val readerMs: Float, val assembleMs: Float,
    val forensicMs: Float = 0f,
) {
    val totalMs get() = locatorPrepMs + locatorMs + linePrepMs + readerMs + assembleMs + forensicMs
}

/** Result of one read on one rectangle crop. */
data class ReadResult(
    /** Neural (DigitNet) reading with per-digit confidence. */
    val reading: Reading,
    /** Deterministic ForensicReader result on the tight located line (null when no line was located). */
    val forensic: ForensicReader.Result?,
    /** Final per-digit vote of both engines — this is what the entry field shows. */
    val voted: VotedReading,
    /** Located main line in crop pixels (null when the locator found nothing and the whole crop was read). */
    val lineRect: RectF?,
    val lineScore: Float,
    val times: StageTimes,
    /** The 64x448 tensor image actually fed to the reader (debug / evidence of what was read). */
    val readerInput: Bitmap,
)

/**
 * Two-pass on-device reader: (1) locate the main reading line inside the rectangle crop at 256x256,
 * (2) read digits on a 64x448 crop of that line, (3) assemble + clean.
 * Thread-safe for one call at a time; create once per process and call [warmUp] when the entry screen opens.
 */
class MeterReader(context: Context) : AutoCloseable {
    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val locator: OrtSession
    private val reader: OrtSession
    private val locBuf = FloatBuffer.allocate(C.LOCATOR_INPUT * C.LOCATOR_INPUT * 3)
    private val readBuf = FloatBuffer.allocate(C.READER_INPUT_H * C.READER_INPUT_W * 3)
    private val locPixels = IntArray(C.LOCATOR_INPUT * C.LOCATOR_INPUT)
    private val readPixels = IntArray(C.READER_INPUT_H * C.READER_INPUT_W)

    init {
        val opts = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(C.ORT_INTRA_THREADS)
            setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        }
        locator = env.createSession(context.assets.open(C.LOCATOR_MODEL_ASSET).readBytes(), opts)
        reader = env.createSession(context.assets.open(C.READER_MODEL_ASSET).readBytes(), opts)
    }

    /** Runs both nets once on blank input so the first real capture pays no graph-initialisation cost. */
    fun warmUp() {
        val blank = Bitmap.createBitmap(64, 80, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.GRAY) }
        read(blank)
        blank.recycle()
    }

    /**
     * @param crop the reader's rectangle crop, upright, any size.
     *
     * Synchronized: the input buffers (locBuf/readBuf) are reused across calls, so two threads
     * (e.g. warm-up on the entry screen + batch benchmark) must never run the engine concurrently
     * (observed as BufferUnderflowException — see docs/phone-test-emulator_x86_64_api30.md).
     */
    @Synchronized
    fun read(crop: Bitmap): ReadResult {
        val t0 = SystemClock.elapsedRealtimeNanos()
        val lb = RectGeometry.letterbox(crop.width, crop.height, C.LOCATOR_INPUT, C.LOCATOR_INPUT)
        val locIn = letterboxed(crop, C.LOCATOR_INPUT, C.LOCATOR_INPUT, lb, Rect(0, 0, crop.width, crop.height))
        fillNhwc(locIn, locPixels, locBuf)
        val t1 = SystemClock.elapsedRealtimeNanos()
        val (locPeaks, locSize, locOffs) = run(locator, locBuf, C.LOCATOR_INPUT, C.LOCATOR_INPUT)
        val hl = C.LOCATOR_INPUT / C.OUTPUT_STRIDE
        val lines = PeakDecoder.decode(locPeaks, locSize, locOffs, 1, hl, hl, C.LOCATOR_PEAK_MIN)
        val t2 = SystemClock.elapsedRealtimeNanos()
        val best = lines.filter { it.y2 - it.y1 >= C.LINE_MIN_HEIGHT_PX }.maxByOrNull { it.score }
        // map the located line from locator-input pixels back to crop pixels
        val lineRect = best?.let {
            RectF((it.x1 - lb.offsetX) / lb.scale, (it.y1 - lb.offsetY) / lb.scale, (it.x2 - lb.offsetX) / lb.scale, (it.y2 - lb.offsetY) / lb.scale)
        }
        val src = if (lineRect != null) padded(lineRect, crop.width, crop.height) else Rect(0, 0, crop.width, crop.height)
        val lb2 = RectGeometry.letterbox(src.width(), src.height(), C.READER_INPUT_W, C.READER_INPUT_H, centreX = false)
        val readIn = letterboxed(crop, C.READER_INPUT_W, C.READER_INPUT_H, lb2, src)
        fillNhwc(readIn, readPixels, readBuf)
        val t3 = SystemClock.elapsedRealtimeNanos()
        val (peaks, size, offs) = run(reader, readBuf, C.READER_INPUT_H, C.READER_INPUT_W)
        val dets = PeakDecoder.decode(peaks, size, offs, C.READER_CLASSES, C.READER_INPUT_H / C.OUTPUT_STRIDE,
            C.READER_INPUT_W / C.OUTPUT_STRIDE, C.READER_PEAK_MIN)
        val t4 = SystemClock.elapsedRealtimeNanos()
        var reading = ReadingAssembler.assemble(dets, C.READER_INPUT_W.toFloat(), C.READER_INPUT_H.toFloat())
        if (reading.status == ReadingStatus.MISSING_DIGIT) {
            val extra = latticeReread(peaks, reading.digits)
            if (extra.isNotEmpty()) reading = ReadingAssembler.assemble(dets + extra, C.READER_INPUT_W.toFloat(), C.READER_INPUT_H.toFloat())
        }
        val verified = SegmentVerifier.verify(SegmentVerifier.gray(readIn), readIn.width, readIn.height, reading.digits)
        reading = reading.copy(digits = verified)
        val t5 = SystemClock.elapsedRealtimeNanos()
        // Second engine: deterministic reader on the TIGHT located line (it is sensitive to padding; measured in
        // docs/benchmark_report.md §7). Skipped when no line was located.
        val forensic = lineRect?.let { r ->
            val tight = Rect(r.left.toInt().coerceIn(0, crop.width - 1), r.top.toInt().coerceIn(0, crop.height - 1),
                r.right.toInt().coerceIn(1, crop.width), r.bottom.toInt().coerceIn(1, crop.height))
            if (tight.width() < 8 || tight.height() < 6) null else {
                val px = IntArray(tight.width() * tight.height())
                crop.getPixels(px, 0, tight.width(), tight.left, tight.top, tight.width(), tight.height())
                ForensicReader.readLine(px, tight.width(), tight.height())
            }
        }
        val voted = Vote.vote(reading, forensic)
        val t6 = SystemClock.elapsedRealtimeNanos()
        locIn.recycle()
        fun ms(a: Long, b: Long) = (b - a) / 1_000_000f
        return ReadResult(reading, forensic, voted, lineRect, best?.score ?: 0f,
            StageTimes(ms(t0, t1), ms(t1, t2), ms(t2, t3), ms(t3, t4), ms(t4, t5), ms(t5, t6)), readIn)
    }

    /** For every cell the pitch lattice predicts, take the strongest digit class in the raw heat-map (3x3 window). */
    private fun latticeReread(peaks: FloatArray, digits: List<Digit>): List<Detection> {
        val hw = C.READER_INPUT_W / C.OUTPUT_STRIDE
        val hh = C.READER_INPUT_H / C.OUTPUT_STRIDE
        val plane = hw * hh
        val out = ArrayList<Detection>()
        for (cell in ReadingAssembler.missingCells(digits)) {
            val cx = ((cell[0] + cell[2]) / 2 / C.OUTPUT_STRIDE).toInt()
            val cy = ((cell[1] + cell[3]) / 2 / C.OUTPUT_STRIDE).toInt()
            var best = C.LATTICE_PEAK_MIN; var bestCls = -1
            for (c in 0 until 10) for (y in maxOf(0, cy - 1)..minOf(hh - 1, cy + 1)) for (x in maxOf(0, cx - 1)..minOf(hw - 1, cx + 1)) {
                val v = peaks[c * plane + y * hw + x]
                if (v > best) { best = v; bestCls = c }
            }
            if (bestCls >= 0) out.add(Detection(bestCls, best, cell[0], cell[1], cell[2], cell[3]))
        }
        return out
    }

    private fun padded(r: RectF, w: Int, h: Int): Rect {
        val px = r.width() * C.LINE_PAD_X
        val py = r.height() * C.LINE_PAD_Y
        return Rect((r.left - px).toInt().coerceIn(0, w - 1), (r.top - py).toInt().coerceIn(0, h - 1),
            (r.right + px).toInt().coerceIn(1, w), (r.bottom + py).toInt().coerceIn(1, h)).also {
            if (it.width() < 1) it.right = it.left + 1
            if (it.height() < 1) it.bottom = it.top + 1
        }
    }

    /** Draws [src] of [bmp] into a dstW x dstH bitmap using the letterbox placement; border = mid grey. */
    private fun letterboxed(bmp: Bitmap, dstW: Int, dstH: Int, lb: RectGeometry.Letterbox, src: Rect): Bitmap {
        val out = Bitmap.createBitmap(dstW, dstH, Bitmap.Config.ARGB_8888)
        out.eraseColor(Color.rgb(128, 128, 128))
        val c = Canvas(out)
        val dst = Rect(lb.offsetX, lb.offsetY, lb.offsetX + lb.scaledW, lb.offsetY + lb.scaledH)
        c.drawBitmap(bmp, src, dst, Paint(Paint.FILTER_BITMAP_FLAG))
        return out
    }

    /** ARGB bitmap -> NHWC float RGB 0..255 (normalisation is inside the ONNX graph). */
    private fun fillNhwc(bmp: Bitmap, px: IntArray, buf: FloatBuffer) {
        bmp.getPixels(px, 0, bmp.width, 0, 0, bmp.width, bmp.height)
        buf.clear()
        for (p in px) {
            buf.put(((p shr 16) and 0xFF).toFloat())
            buf.put(((p shr 8) and 0xFF).toFloat())
            buf.put((p and 0xFF).toFloat())
        }
        buf.rewind()
    }

    private fun run(session: OrtSession, buf: FloatBuffer, h: Int, w: Int): Triple<FloatArray, FloatArray, FloatArray> {
        OnnxTensor.createTensor(env, buf, longArrayOf(1, h.toLong(), w.toLong(), 3)).use { input ->
            session.run(mapOf(session.inputNames.first() to input)).use { out ->
                val peaks = (out[0].value as Array<Array<Array<FloatArray>>>)[0]
                val size = (out[1].value as Array<Array<Array<FloatArray>>>)[0]
                val offs = (out[2].value as Array<Array<Array<FloatArray>>>)[0]
                return Triple(flatten(peaks), flatten(size), flatten(offs))
            }
        }
    }

    private fun flatten(a: Array<Array<FloatArray>>): FloatArray {
        val c = a.size
        val h = a[0].size
        val w = a[0][0].size
        val out = FloatArray(c * h * w)
        var i = 0
        for (ci in 0 until c) for (y in 0 until h) {
            System.arraycopy(a[ci][y], 0, out, i, w)
            i += w
        }
        return out
    }

    @Synchronized
    override fun close() {
        locator.close()
        reader.close()
    }
}
