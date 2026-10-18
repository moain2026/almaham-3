package com.almaham.meterdemo

import android.graphics.Bitmap

/**
 * Optional baseline OCR used only by the batch benchmark (brief §6.a).
 * Flavor `bench` = Google ML Kit (src/bench); flavor `field` = not available (src/field) so the field APK carries
 * no ML Kit code or native libraries (~18 MB saved, docs/apk-size-report.md).
 */
interface MlKitBaseline {
    val available: Boolean
    /** Recognised text lines, top to bottom. Empty when unavailable or nothing found. */
    fun lines(b: Bitmap): List<String>
}
