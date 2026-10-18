package com.almaham.meterocr

import android.graphics.Bitmap
import android.os.Build
import androidx.exifinterface.media.ExifInterface
import java.io.ByteArrayOutputStream
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import com.almaham.meterocr.MeterOcrConfig as C

/** Compressed evidence picture of the WHOLE meter (body + serial), 80–200 KB, written after the number is shown. */
object EvidenceImage {
    data class Encoded(val bytes: ByteArray, val quality: Int, val width: Int, val height: Int, val mime: String)

    /** Pure sizing rule: long edge -> EVIDENCE_LONG_EDGE_PX, never upscales. */
    fun targetSize(w: Int, h: Int, longEdge: Int = C.EVIDENCE_LONG_EDGE_PX): Pair<Int, Int> {
        val long = maxOf(w, h)
        if (long <= longEdge) return w to h
        val s = longEdge.toFloat() / long
        return maxOf(1, Math.round(w * s)) to maxOf(1, Math.round(h * s))
    }

    /**
     * Quality search: start at the main project's q82 and step down until the file is <= max bytes.
     * Below the minimum quality we accept whatever size results (never drop resolution below 1280: the serial
     * number must stay legible). Returns the byte array and the quality used.
     */
    fun encode(crop: Bitmap): Encoded {
        val (w, h) = targetSize(crop.width, crop.height)
        val scaled = if (w != crop.width || h != crop.height) Bitmap.createScaledBitmap(crop, w, h, true) else crop
        val format = if (Build.VERSION.SDK_INT >= 30) Bitmap.CompressFormat.WEBP_LOSSY else @Suppress("DEPRECATION") Bitmap.CompressFormat.WEBP
        var q = C.EVIDENCE_QUALITY_START
        var bytes = compress(scaled, format, q)
        while (bytes.size > C.EVIDENCE_TARGET_MAX_BYTES && q - C.EVIDENCE_QUALITY_STEP >= C.EVIDENCE_QUALITY_MIN) {
            q -= C.EVIDENCE_QUALITY_STEP
            bytes = compress(scaled, format, q)
        }
        if (scaled !== crop) scaled.recycle()
        return Encoded(bytes, q, w, h, "image/webp")
    }

    private fun compress(b: Bitmap, f: Bitmap.CompressFormat, q: Int): ByteArray =
        ByteArrayOutputStream(C.EVIDENCE_TARGET_MAX_BYTES).also { b.compress(f, q, it) }.toByteArray()

    /** Writes the file and basic EXIF (time + device, no location). WebP EXIF is supported by ExifInterface. */
    fun save(file: File, encoded: Encoded, capturedAt: Date = Date()) {
        file.writeBytes(encoded.bytes)
        runCatching {
            ExifInterface(file.absolutePath).apply {
                setAttribute(ExifInterface.TAG_DATETIME_ORIGINAL, SimpleDateFormat("yyyy:MM:dd HH:mm:ss", Locale.US).format(capturedAt))
                setAttribute(ExifInterface.TAG_MAKE, Build.MANUFACTURER)
                setAttribute(ExifInterface.TAG_MODEL, Build.MODEL)
                setAttribute(ExifInterface.TAG_SOFTWARE, "almaham-meter")
                saveAttributes()
            }
        }
    }
}
