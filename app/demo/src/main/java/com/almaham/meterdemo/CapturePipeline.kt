package com.almaham.meterdemo

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapRegionDecoder
import android.graphics.Matrix
import android.graphics.Rect
import android.os.SystemClock
import androidx.camera.core.ImageProxy
import com.almaham.meterocr.EvidenceImage
import com.almaham.meterocr.MeterReader
import com.almaham.meterocr.NormRect
import com.almaham.meterocr.PixelRect
import com.almaham.meterocr.PreviewScale
import com.almaham.meterocr.ReadResult
import com.almaham.meterocr.RectGeometry
import java.io.File
import java.nio.ByteBuffer

/** What the entry screen receives: number first (fast path), evidence file second (slow path). */
data class CaptureOutcome(
    val read: ReadResult,
    val crop: Bitmap,
    val captureToNumberMs: Float,
)

/**
 * Everything that happens after the shutter press, on a background thread, in memory:
 * JPEG bytes -> decode only the rectangle region -> upright -> read -> (caller shows number) -> encode evidence.
 * The full-resolution image is never written to disk.
 */
class CapturePipeline(private val reader: MeterReader) {

    /** Decode just the user's rectangle out of the JPEG (BitmapRegionDecoder: no full-frame decode). */
    fun cropFromJpeg(jpeg: ByteArray, rectInView: NormRect, viewW: Float, viewH: Float, scale: PreviewScale, rotationDegrees: Int): Bitmap {
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size, opts)
        val rawW = opts.outWidth
        val rawH = opts.outHeight
        val px: PixelRect = RectGeometry.viewRectToRawCrop(rectInView, viewW, viewH, scale, rawW, rawH, rotationDegrees)
        val decoder = BitmapRegionDecoder.newInstance(jpeg, 0, jpeg.size, false)
        val region = decoder.decodeRegion(Rect(px.left, px.top, px.right, px.bottom), BitmapFactory.Options().apply {
            inPreferredConfig = Bitmap.Config.ARGB_8888
        })
        decoder.recycle()
        return upright(region, rotationDegrees)
    }

    fun upright(b: Bitmap, rotationDegrees: Int): Bitmap {
        val rot = ((rotationDegrees % 360) + 360) % 360
        if (rot == 0) return b
        val m = Matrix().apply { postRotate(rot.toFloat()) }
        val r = Bitmap.createBitmap(b, 0, 0, b.width, b.height, m, true)
        if (r !== b) b.recycle()
        return r
    }

    /** JPEG bytes from an ImageCapture ImageProxy (format JPEG, single plane). */
    fun jpegBytes(image: ImageProxy): ByteArray {
        val buf: ByteBuffer = image.planes[0].buffer
        val arr = ByteArray(buf.remaining())
        buf.get(arr)
        return arr
    }

    /** Fast path: crop + read. [shutterNanos] = SystemClock.elapsedRealtimeNanos() at the moment of the press. */
    fun readCrop(crop: Bitmap, shutterNanos: Long): CaptureOutcome {
        val read = reader.read(crop)
        val toNumber = (SystemClock.elapsedRealtimeNanos() - shutterNanos) / 1_000_000f
        return CaptureOutcome(read, crop, toNumber)
    }

    /** Slow path, called AFTER the number was shown: evidence file 80–200 KB with the whole meter. */
    fun saveEvidence(crop: Bitmap, dir: File, name: String): Pair<File, EvidenceImage.Encoded> {
        val enc = EvidenceImage.encode(crop)
        val f = File(dir, "$name.webp")
        EvidenceImage.save(f, enc)
        return f to enc
    }
}
