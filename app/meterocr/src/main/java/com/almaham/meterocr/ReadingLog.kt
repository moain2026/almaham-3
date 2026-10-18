package com.almaham.meterocr

import android.os.Build
import java.io.File

/** Where the image came from (brief §2.8). */
enum class Source { CAMERA, GALLERY }

/** One row of the per-reading audit log (brief §2.8). Written as CSV, append-only, on the device. */
data class ReadingRecord(
    val timestampMs: Long,
    val engineValue: String,
    val savedValue: String,
    val edited: Boolean,
    val confident: Boolean,
    val minConfidence: Float,
    val status: ReadingStatus,
    val totalMs: Float,
    val captureToNumberMs: Float,
    val evidenceBytes: Int,
    val source: Source,
    val device: String = "${Build.MANUFACTURER} ${Build.MODEL} (API ${Build.VERSION.SDK_INT})",
) {
    fun toCsvRow(): String = listOf(
        timestampMs, engineValue, savedValue, edited, confident, "%.3f".format(minConfidence), status, "%.1f".format(totalMs),
        "%.1f".format(captureToNumberMs), evidenceBytes, source, device,
    ).joinToString(",") { v -> '"' + v.toString().replace("\"", "'") + '"' }

    companion object {
        const val HEADER = "timestamp_ms,engine_value,saved_value,edited,confident,min_confidence,status,engine_total_ms,capture_to_number_ms,evidence_bytes,source,device"
    }
}

class ReadingLog(private val file: File) {
    @Synchronized
    fun append(r: ReadingRecord) {
        if (!file.exists()) file.writeText(ReadingRecord.HEADER + "\n")
        file.appendText(r.toCsvRow() + "\n")
    }
}
