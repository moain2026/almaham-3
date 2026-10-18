package com.almaham.meterdemo

import android.graphics.Bitmap

/** Flavor `field`: no ML Kit in the product APK. The batch benchmark skips the mlkit rows. */
object MlKitBaselineFactory {
    fun create(): MlKitBaseline = object : MlKitBaseline {
        override val available = false
        override fun lines(b: Bitmap): List<String> = emptyList()
    }
}
