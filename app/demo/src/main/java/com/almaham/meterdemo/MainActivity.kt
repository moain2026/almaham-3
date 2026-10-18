package com.almaham.meterdemo

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.exifinterface.media.ExifInterface
import com.almaham.meterocr.MeterReader
import com.almaham.meterocr.ReadingLog
import com.almaham.meterocr.ReadingRecord
import com.almaham.meterocr.ReadingValidator
import com.almaham.meterocr.Source
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private enum class Screen { ENTRY, CAMERA, BATCH }

class MainActivity : ComponentActivity() {
    private lateinit var reader: MeterReader
    private lateinit var pipeline: CapturePipeline
    private lateinit var log: ReadingLog

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        reader = MeterReader(this)
        pipeline = CapturePipeline(reader)
        log = ReadingLog(File(getExternalFilesDir(null), "readings_log.csv"))
        setContent { CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) { App() } }
    }

    override fun onDestroy() {
        super.onDestroy()
        reader.close()
    }

    @Composable
    private fun App() {
        var screen by remember { mutableStateOf(Screen.ENTRY) }
        var state by remember { mutableStateOf(EntryState()) }
        var source by remember { mutableStateOf(Source.CAMERA) }
        var lastTotalMs by remember { mutableStateOf(0f) }
        var lastStatus by remember { mutableStateOf(com.almaham.meterocr.ReadingStatus.EMPTY) }
        var lastMinConf by remember { mutableStateOf(0f) }
        val scope = rememberCoroutineScope()
        val evidenceDir = remember { File(getExternalFilesDir(null), "evidence").apply { mkdirs() } }

        // Warm-up when the entry screen opens (brief §5: never at press time).
        LaunchedEffect(Unit) { withContext(Dispatchers.Default) { reader.warmUp() } }

        val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
            if (ok) screen = Screen.CAMERA
        }
        val gallery = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
            uri ?: return@rememberLauncherForActivityResult
            source = Source.GALLERY
            val shutter = SystemClock.elapsedRealtimeNanos()
            scope.launch(Dispatchers.Default) {
                val bmp = contentResolver.openInputStream(uri)!!.use { BitmapFactory.decodeStream(it) }
                val deg = contentResolver.openInputStream(uri)!!.use { s ->
                    when (ExifInterface(s).getAttributeInt(ExifInterface.TAG_ORIENTATION, 1)) {
                        ExifInterface.ORIENTATION_ROTATE_90 -> 90; ExifInterface.ORIENTATION_ROTATE_180 -> 180
                        ExifInterface.ORIENTATION_ROTATE_270 -> 270; else -> 0
                    }
                }
                val outcome = pipeline.readCrop(pipeline.upright(bmp, deg), shutter)
                val st = applyOutcome(outcome)
                withContext(Dispatchers.Main) { state = st; lastTotalMs = outcome.read.times.totalMs; lastStatus = outcome.read.reading.status; lastMinConf = outcome.read.reading.minConfidence }
                val (_, enc) = pipeline.saveEvidence(outcome.crop, evidenceDir, "gallery_${System.currentTimeMillis()}")
                withContext(Dispatchers.Main) { state = state.copy(evidenceBytes = enc.bytes.size) }
            }
        }

        when (screen) {
            Screen.ENTRY -> EntryScreen(
                state = state,
                onValueChange = { v -> state = state.copy(value = v, edited = state.autoRead && v != state.engineValue, warning = ReadingValidator.validate(v, DummyData.PREVIOUS)) },
                onCapture = {
                    source = Source.CAMERA
                    if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) screen = Screen.CAMERA
                    else cameraPermission.launch(Manifest.permission.CAMERA)
                },
                onGallery = { gallery.launch("image/*") },
                onSave = {
                    log.append(ReadingRecord(
                        timestampMs = System.currentTimeMillis(), engineValue = state.engineValue, savedValue = state.value,
                        edited = state.edited, confident = state.uncertainIndices.isEmpty() && state.engineValue.isNotEmpty(),
                        minConfidence = lastMinConf, status = lastStatus, totalMs = lastTotalMs,
                        captureToNumberMs = state.captureToNumberMs ?: 0f, evidenceBytes = state.evidenceBytes, source = source,
                    ))
                    state = EntryState(savedCount = state.savedCount + 1)
                },
                onBatchTest = { screen = Screen.BATCH },
            )
            Screen.CAMERA -> CameraScreen(
                onCaptured = { ev ->
                    // Called on the capture executor the instant the frame is available: close the camera first,
                    // then crop + read on a background thread, show the number, THEN compress & save evidence.
                    scope.launch(Dispatchers.Main) { screen = Screen.ENTRY }
                    scope.launch(Dispatchers.Default) {
                        val rotation = ev.image.imageInfo.rotationDegrees
                        val jpeg = pipeline.jpegBytes(ev.image)
                        ev.image.close()
                        val crop = pipeline.cropFromJpeg(jpeg, ev.rectInView, ev.viewW, ev.viewH, ev.scale, rotation)
                        val outcome = pipeline.readCrop(crop, ev.shutterNanos)
                        val st = applyOutcome(outcome)
                        withContext(Dispatchers.Main) { state = st; lastTotalMs = outcome.read.times.totalMs; lastStatus = outcome.read.reading.status; lastMinConf = outcome.read.reading.minConfidence }
                        val (_, enc) = pipeline.saveEvidence(outcome.crop, evidenceDir, "meter_${System.currentTimeMillis()}")
                        withContext(Dispatchers.Main) { state = state.copy(evidenceBytes = enc.bytes.size) }
                    }
                },
                onClose = { screen = Screen.ENTRY },
            )
            Screen.BATCH -> BatchScreen(reader) { screen = Screen.ENTRY }
        }
    }

    private fun applyOutcome(o: CaptureOutcome): EntryState {
        val value = o.read.voted.value
        val thumb = Bitmap.createScaledBitmap(o.crop, 240, (240f * o.crop.height / o.crop.width).toInt().coerceAtLeast(1), true)
        return EntryState(
            value = value, autoRead = true, edited = false, uncertainIndices = o.read.voted.uncertainIndices,
            thumbnail = thumb, evidenceBytes = 0, captureToNumberMs = o.captureToNumberMs, engineValue = value,
            warning = ReadingValidator.validate(value, DummyData.PREVIOUS),
        )
    }
}

@Composable
private fun BatchScreen(reader: MeterReader, onBack: () -> Unit) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val bench = remember { BatchBenchmark(ctx, reader) }
    var lines by remember { mutableStateOf(listOf("الصور تُقرأ من: ${bench.photosDir}", "ادفعها بـ: adb push photos/ ${bench.photosDir}")) }
    var running by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().background(Color(0xFF151410)).padding(16.dp)) {
        Text("الاختبار الجماعي — 49 صورة × (A مستطيل، B كاملة) × (DigitNet، ML Kit)", color = Color.White, fontSize = 16.sp)
        Button(enabled = !running, onClick = {
            running = true
            lines = listOf("بدأ…")
            scope.launch(Dispatchers.Default) {
                val rows = bench.run { done, total, r ->
                    val l = "$done/$total ${r.file} ${r.mode} ${r.engine}: ${r.value.ifEmpty { "—" }} (صح ${r.truth}) ${if (r.exact) "✓" else if (r.empty) "∅" else "✗"} ${"%.0f".format(r.totalMs)}ms"
                    scope.launch(Dispatchers.Main) { lines = (listOf(l) + lines).take(300) }
                }
                val s = bench.summary(rows).toString(2)
                withContext(Dispatchers.Main) { lines = listOf("انتهى. الملفات في ${bench.outDir}", s) + lines; running = false }
            }
        }, modifier = Modifier.padding(vertical = 8.dp)) { Text(if (running) "جاري التشغيل…" else "تشغيل") }
        TextButton(onClick = onBack) { Text("رجوع", color = Color(0xFFF2B233)) }
        Column(Modifier.verticalScroll(rememberScrollState())) {
            for (l in lines) Text(l, color = Color(0xFFCFCFCF), fontSize = 12.sp)
        }
    }
}
