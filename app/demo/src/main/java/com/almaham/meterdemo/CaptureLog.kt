package com.almaham.meterdemo

import android.os.Build
import java.io.File

/**
 * Per-capture timing/geometry log for the real-phone test (docs/phone-test-<device>.md):
 * (a) press -> frame delivered, (b) press -> number on screen, (c) evidence size, (d) rect-check image name.
 * Append-only CSV in <external files>/captures_log.csv; pull with `adb pull`.
 */
data class CaptureRecord(
    val name: String,
    val pressToFrameMs: Float,
    val captureToNumberMs: Float,
    val engineMs: Float,
    val value: String,
    val status: String,
    val evidenceBytes: Int,
    val rawW: Int,
    val rawH: Int,
    val rotation: Int,
    val cropW: Int,
    val cropH: Int,
    val zsl: Boolean,
    val zoom: Float,
    val rectCheck: String,
    val device: String = "${Build.MANUFACTURER} ${Build.MODEL} (API ${Build.VERSION.SDK_INT})",
) {
    fun csv(): String = listOf(
        name, "%.1f".format(pressToFrameMs), "%.1f".format(captureToNumberMs), "%.1f".format(engineMs), value, status,
        evidenceBytes, rawW, rawH, rotation, cropW, cropH, zsl, "%.2f".format(zoom), rectCheck, device,
    ).joinToString(",") { '"' + it.toString().replace("\"", "'") + '"' }

    companion object {
        const val HEADER = "name,press_to_frame_ms,capture_to_number_ms,engine_ms,value,status,evidence_bytes," +
            "raw_w,raw_h,rotation,crop_w,crop_h,zsl,zoom,rect_check,device"
    }
}

class CaptureLog(private val file: File) {
    @Synchronized
    fun append(r: CaptureRecord) {
        if (!file.exists()) file.writeText(CaptureRecord.HEADER + "\n")
        file.appendText(r.csv() + "\n")
    }
}
