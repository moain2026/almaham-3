package com.almaham.meterdemo

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.os.Build
import android.os.SystemClock
import androidx.exifinterface.media.ExifInterface
import com.almaham.meterocr.EvidenceImage
import com.almaham.meterocr.MeterReader
import com.almaham.meterocr.NormRect
import com.almaham.meterocr.NumberCleaner
import com.almaham.meterocr.ReadingStatus
import com.almaham.meterocr.RectGeometry
import com.almaham.meterocr.Vote
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import org.json.JSONObject
import java.io.File

/** One ground-truth row (benchmark/data/ground_truth.csv, shipped as an asset). */
data class TruthRow(val file: String, val reading: String, val type: String, val difficulty: String, val uncertain: Boolean)

data class BenchRow(
    val file: String, val mode: String, val engine: String, val truth: String, val value: String, val status: String,
    val confident: Boolean, val minConf: Float, val locMs: Float, val readMs: Float, val totalMs: Float, val evidenceBytes: Int,
) {
    val readable get() = truth.isNotEmpty()
    val exact get() = readable && value == truth
    val empty get() = value.isEmpty()
    val wrongConfident get() = readable && !empty && value != truth && confident
    fun csv() = listOf(file, mode, engine, truth, value, status, confident, "%.3f".format(minConf), "%.1f".format(locMs),
        "%.1f".format(readMs), "%.1f".format(totalMs), evidenceBytes).joinToString(",")

    companion object {
        const val HEADER = "file,mode,engine,truth,value,status,confident,min_conf,locate_ms,read_ms,total_ms,evidence_bytes"
    }
}

/**
 * Batch test mode (brief §7.2): the 49 photos in mode A (meter rectangle from meter_boxes.json) and mode B
 * (full photo), for our engine and for ML Kit as the baseline. Photos are read from
 * <external files dir>/photos/ (pushed with adb, never bundled). Output: bench_<device>.csv + bench_summary.json.
 */
class BatchBenchmark(private val ctx: Context, private val reader: MeterReader) {
    private val mlkit = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    val photosDir: File = File(ctx.getExternalFilesDir(null), "photos")
    val outDir: File = ctx.getExternalFilesDir(null)!!

    fun loadTruth(): List<TruthRow> = ctx.assets.open("bench/ground_truth.csv").bufferedReader().readLines().drop(1)
        .filter { it.isNotBlank() }.map { line ->
            val c = line.split(",")
            TruthRow(c[0], c[1].trim(), c[3], c[4], c[5] == "1")
        }

    fun loadBoxes(): Map<String, NormRect> {
        val j = JSONObject(ctx.assets.open("bench/meter_boxes.json").bufferedReader().readText())
        return j.keys().asSequence().filter { !it.startsWith("_") }.associateWith { k ->
            val a = j.getJSONArray(k)
            NormRect(a.getDouble(0).toFloat(), a.getDouble(1).toFloat(), a.getDouble(2).toFloat(), a.getDouble(3).toFloat())
        }
    }

    /** Decodes an upright photo (EXIF orientation applied), full resolution. */
    fun loadUpright(f: File): Bitmap {
        val b = BitmapFactory.decodeFile(f.absolutePath)
        val o = ExifInterface(f.absolutePath).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
        val deg = when (o) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
        if (deg == 0f) return b
        val r = Bitmap.createBitmap(b, 0, 0, b.width, b.height, Matrix().apply { postRotate(deg) }, true)
        b.recycle()
        return r
    }

    fun crop(b: Bitmap, r: NormRect): Bitmap {
        val p = RectGeometry.toPixels(r, b.width, b.height)
        return Bitmap.createBitmap(b, p.left, p.top, p.width, p.height)
    }

    /** ML Kit baseline: longest run of digits (with optional dot) in the recognised text, integer part, cleaned. */
    private fun mlkitRead(b: Bitmap): Triple<String, Float, Float> {
        val t0 = SystemClock.elapsedRealtimeNanos()
        val text = runCatching { Tasks.await(mlkit.process(InputImage.fromBitmap(b, 0))) }.getOrNull()
        val ms = (SystemClock.elapsedRealtimeNanos() - t0) / 1_000_000f
        val raw = text?.textBlocks?.flatMap { it.lines }?.map { it.text } ?: emptyList()
        val cands = raw.flatMap { Regex("\\d{2,8}(?:[.,]\\d{1,2})?").findAll(it).map { m -> m.value }.toList() }
        val best = cands.maxByOrNull { it.substringBefore('.').substringBefore(',').length } ?: ""
        val integer = best.substringBefore('.').substringBefore(',')
        return Triple(NumberCleaner.stripLeadingZeros(integer), 1f, ms)
    }

    /** Runs everything; [progress] is called with (done, total, lastRow). Returns the rows. */
    fun run(progress: (Int, Int, BenchRow) -> Unit): List<BenchRow> {
        val truth = loadTruth()
        val boxes = loadBoxes()
        val rows = ArrayList<BenchRow>()
        val total = truth.size * 6
        var done = 0
        synchronized(reader) { reader.warmUp() }
        for (t in truth) {
            val f = File(photosDir, t.file)
            if (!f.exists()) continue
            // an unreadable file (e.g. pushed with wrong owner) must not crash the whole batch run
            val full = runCatching { loadUpright(f) }.getOrNull() ?: continue
            val a = crop(full, boxes[t.file] ?: NormRect(0f, 0f, 1f, 1f))
            for ((mode, bmp) in listOf("A" to a, "B" to full)) {
                val t0 = SystemClock.elapsedRealtimeNanos()
                val r = synchronized(reader) { reader.read(bmp) }
                val tot = (SystemClock.elapsedRealtimeNanos() - t0) / 1_000_000f
                val ev = if (mode == "A") EvidenceImage.encode(bmp).bytes.size else 0
                val row = BenchRow(t.file, mode, "digitnet", t.reading, r.reading.value, r.reading.status.name, r.reading.confident,
                    r.reading.minConfidence, r.times.locatorPrepMs + r.times.locatorMs, r.times.linePrepMs + r.times.readerMs, tot, ev)
                rows.add(row); progress(++done, total, row)
                val fv = r.forensic?.text?.let { NumberCleaner.stripLeadingZeros(it) } ?: ""
                rows.add(BenchRow(t.file, mode, "forensic", t.reading, fv, r.forensic?.status ?: "NO_LINE",
                    r.forensic?.digits?.all { it.conf >= Vote.HIGH } == true, r.forensic?.digits?.minOfOrNull { it.conf.toFloat() } ?: 0f,
                    0f, r.times.forensicMs, r.times.forensicMs, 0))
                val vrow = BenchRow(t.file, mode, "vote", t.reading, r.voted.value, r.voted.status, r.voted.confident,
                    r.voted.digits.minOfOrNull { it.conf } ?: 0f, 0f, 0f, tot, 0)
                rows.add(vrow); progress(++done, total, vrow)
                r.readerInput.recycle()
                val (mv, mc, mms) = mlkitRead(bmp)
                val mrow = BenchRow(t.file, mode, "mlkit", t.reading, mv, if (mv.isEmpty()) ReadingStatus.EMPTY.name else "OK", mv.isNotEmpty(), mc, 0f, mms, mms, 0)
                rows.add(mrow); progress(++done, total, mrow)
            }
            a.recycle(); full.recycle()
        }
        write(rows)
        return rows
    }

    private fun write(rows: List<BenchRow>) {
        val dev = "${Build.MANUFACTURER}_${Build.MODEL}".replace(Regex("[^A-Za-z0-9_]"), "_")
        File(outDir, "bench_$dev.csv").writeText(BenchRow.HEADER + "\n" + rows.joinToString("\n") { it.csv() } + "\n")
        File(outDir, "bench_summary_$dev.json").writeText(summary(rows).toString(2))
    }

    fun summary(rows: List<BenchRow>): JSONObject {
        val out = JSONObject()
        out.put("device", "${Build.MANUFACTURER} ${Build.MODEL} API ${Build.VERSION.SDK_INT}")
        for ((key, group) in rows.groupBy { it.engine + "_" + it.mode }) {
            val readable = group.filter { it.readable }
            val times = group.map { it.totalMs }.sorted()
            val o = JSONObject()
            o.put("n_readable", readable.size)
            o.put("exact", readable.count { it.exact })
            o.put("empty", readable.count { it.empty })
            o.put("wrong", readable.count { !it.empty && !it.exact })
            o.put("wrong_confident", readable.count { it.wrongConfident })
            o.put("unreadable_rejected", group.filter { !it.readable }.count { it.empty })
            o.put("p50_ms", times.getOrNull(times.size / 2) ?: 0f)
            o.put("p95_ms", times.getOrNull((times.size * 0.95).toInt().coerceAtMost(times.size - 1)) ?: 0f)
            o.put("max_ms", times.lastOrNull() ?: 0f)
            val ev = group.map { it.evidenceBytes }.filter { it > 0 }
            if (ev.isNotEmpty()) { o.put("evidence_min_kb", ev.min() / 1024); o.put("evidence_max_kb", ev.max() / 1024) }
            out.put(key, o)
        }
        return out
    }
}
