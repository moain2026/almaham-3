package com.almaham.meterdemo

import android.graphics.Bitmap
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

/** Flavor `bench`: real ML Kit text recognition (bundled model). */
object MlKitBaselineFactory {
    fun create(): MlKitBaseline = object : MlKitBaseline {
        private val client = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        override val available = true
        override fun lines(b: Bitmap): List<String> {
            val text = runCatching { Tasks.await(client.process(InputImage.fromBitmap(b, 0))) }.getOrNull() ?: return emptyList()
            return text.textBlocks.flatMap { it.lines }.map { it.text }
        }
    }
}
