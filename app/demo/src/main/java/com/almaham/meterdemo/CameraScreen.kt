package com.almaham.meterdemo

import android.os.SystemClock
import android.view.MotionEvent
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.FocusMeteringAction
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FlashOff
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.ui.input.pointer.positionChange
import androidx.core.content.ContextCompat
import com.almaham.meterocr.MeterOcrConfig
import com.almaham.meterocr.NormRect
import com.almaham.meterocr.PreviewScale
import java.util.concurrent.Executor
import java.util.concurrent.Executors

/** Everything the pipeline needs from the moment of the press. */
data class ShutterEvent(
    val image: ImageProxy,
    val rectInView: NormRect,
    val viewW: Float,
    val viewH: Float,
    val scale: PreviewScale,
    val shutterNanos: Long,
    /** press -> ImageProxy delivered (ms). Answers "does the press capture instantly?" on a real phone. */
    val pressToFrameMs: Float = 0f,
    val zsl: Boolean = false,
    val zoom: Float = 1f,
)

private val Amber = Color(0xFFF2B233)

/**
 * In-app camera (brief §2.1–2.3): fixed-but-editable rectangle, pinch + 1x/2x/3x zoom, flash, tap-to-focus.
 * The press captures IMMEDIATELY (ZSL when supported, else MINIMIZE_LATENCY); there is no waiting UI and no
 * pre-capture check. The screen closes the instant the ImageProxy arrives; all processing happens elsewhere.
 */
@Composable
fun CameraScreen(onCaptured: (ShutterEvent) -> Unit, onClose: () -> Unit) {
    val ctx = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current
    val density = LocalDensity.current
    val executor: Executor = remember { Executors.newSingleThreadExecutor() }
    val mainExecutor = remember { ContextCompat.getMainExecutor(ctx) }
    var camera by remember { mutableStateOf<Camera?>(null) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var previewView by remember { mutableStateOf<PreviewView?>(null) }
    var torch by remember { mutableStateOf(false) }
    var zoom by remember { mutableFloatStateOf(1f) }
    var viewSize by remember { mutableStateOf(Size.Zero) }
    var rect by remember { mutableStateOf<NormRect?>(null) }
    var pressed by remember { mutableStateOf(false) }
    var zslOn by remember { mutableStateOf(false) }
    val handleRadiusPx = with(density) { MeterOcrConfig.RECT_HANDLE_TOUCH_RADIUS_DP.dp.toPx() }

    DisposableEffect(Unit) { onDispose { rect?.let { RectangleState.save(ctx, it) } } }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { c ->
                PreviewView(c).apply {
                    scaleType = PreviewView.ScaleType.FILL_CENTER
                    implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                    previewView = this
                    val future = ProcessCameraProvider.getInstance(c)
                    future.addListener({
                        val provider = future.get()
                        val preview = Preview.Builder().build().also { it.surfaceProvider = surfaceProvider }
                        val selector = CameraSelector.DEFAULT_BACK_CAMERA
                        val zsl = provider.getCameraInfo(selector).isZslSupported
                        zslOn = zsl
                        val capture = ImageCapture.Builder()
                            .setCaptureMode(if (zsl) ImageCapture.CAPTURE_MODE_ZERO_SHUTTER_LAG else ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                            .setResolutionSelector(ResolutionSelector.Builder()
                                .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY).build())
                            .setFlashMode(ImageCapture.FLASH_MODE_OFF)
                            .build()
                        provider.unbindAll()
                        camera = provider.bindToLifecycle(lifecycle, selector, preview, capture)
                        imageCapture = capture
                    }, mainExecutor)
                }
            },
        )

        // Rectangle + dim overlay + gestures (drag/resize). Pinch zoom is on the same layer.
        Canvas(
            Modifier.fillMaxSize()
                .pointerInput(Unit) {
                    detectTransformGestures(panZoomLock = true) { _, _, z, _ ->
                        if (z != 1f) {
                            val cam = camera ?: return@detectTransformGestures
                            val max = cam.cameraInfo.zoomState.value?.maxZoomRatio ?: 1f
                            zoom = (zoom * z).coerceIn(1f, max)
                            cam.cameraControl.setZoomRatio(zoom)
                        }
                    }
                }
                .pointerInput(Unit) {
                    awaitEachGesture {
                        val down = awaitFirstDown()
                        val r = rect ?: return@awaitEachGesture
                        val w = size.width.toFloat(); val h = size.height.toFloat()
                        val handle = RectangleState.hitTest(r, down.position.x, down.position.y, w, h, handleRadiusPx)
                        if (handle == Handle.NONE) {
                            // tap-to-focus outside the rectangle
                            val pv = previewView ?: return@awaitEachGesture
                            val pt = pv.meteringPointFactory.createPoint(down.position.x, down.position.y)
                            camera?.cameraControl?.startFocusAndMetering(FocusMeteringAction.Builder(pt).build())
                            return@awaitEachGesture
                        }
                        var moved = false
                        while (true) {
                            val ev = awaitPointerEvent()
                            val ch = ev.changes.firstOrNull { it.id == down.id } ?: break
                            if (!ch.pressed) break
                            val d = ch.positionChange()
                            if (d != Offset.Zero && ev.changes.size == 1) {
                                moved = true
                                rect = RectangleState.apply(rect ?: r, handle, d.x / w, d.y / h)
                                ch.consume()
                            }
                        }
                        if (!moved && handle == Handle.MOVE) {
                            val pv = previewView ?: return@awaitEachGesture
                            val pt = pv.meteringPointFactory.createPoint(down.position.x, down.position.y)
                            camera?.cameraControl?.startFocusAndMetering(FocusMeteringAction.Builder(pt).build())
                        }
                    }
                },
        ) {
            if (viewSize != size) {
                viewSize = size
                if (rect == null) rect = RectangleState.load(ctx, size.width, size.height)
            }
            val r = rect ?: return@Canvas
            val l = r.left * size.width; val t = r.top * size.height
            val rr = r.right * size.width; val b = r.bottom * size.height
            val dim = Color.Black.copy(alpha = 0.55f)
            drawRect(dim, Offset.Zero, Size(size.width, t))
            drawRect(dim, Offset(0f, b), Size(size.width, size.height - b))
            drawRect(dim, Offset(0f, t), Size(l, b - t))
            drawRect(dim, Offset(rr, t), Size(size.width - rr, b - t))
            drawRect(Amber, Offset(l, t), Size(rr - l, b - t), style = Stroke(3.dp.toPx()))
            val hr = 9.dp.toPx()
            for ((x, y) in listOf(l to t, rr to t, l to b, rr to b)) {
                drawCircle(Amber, hr, Offset(x, y)); drawCircle(Color.Black, hr * 0.45f, Offset(x, y))
            }
            val eh = 4.dp.toPx(); val el = 22.dp.toPx()
            drawRoundRect(Amber, Offset((l + rr) / 2 - el / 2, t - eh / 2), Size(el, eh), androidx.compose.ui.geometry.CornerRadius(eh))
            drawRoundRect(Amber, Offset((l + rr) / 2 - el / 2, b - eh / 2), Size(el, eh), androidx.compose.ui.geometry.CornerRadius(eh))
            drawRoundRect(Amber, Offset(l - eh / 2, (t + b) / 2 - el / 2), Size(eh, el), androidx.compose.ui.geometry.CornerRadius(eh))
            drawRoundRect(Amber, Offset(rr - eh / 2, (t + b) / 2 - el / 2), Size(eh, el), androidx.compose.ui.geometry.CornerRadius(eh))
        }

        // top bar
        Row(Modifier.fillMaxWidth().padding(top = 36.dp, start = 8.dp, end = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = {
                torch = !torch
                camera?.cameraControl?.enableTorch(torch)
            }) { Icon(if (torch) Icons.Default.FlashOn else Icons.Default.FlashOff, null, tint = Amber) }
            Spacer(Modifier.weight(1f))
            Text("صوّر العداد", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            IconButton(onClick = onClose) { Icon(Icons.Default.Close, null, tint = Color.White) }
        }
        Column(Modifier.fillMaxWidth().padding(top = 92.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("خلّ العداد كامل داخل المستطيل واضغط تصوير", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
            Text("تقدر تحرّك المستطيل وتكبّره من الزوايا", color = Color.White.copy(alpha = 0.75f), fontSize = 13.sp)
        }

        // bottom: zoom chips + shutter
        Column(Modifier.align(Alignment.BottomCenter).padding(bottom = 28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.clip(RoundedCornerShape(24.dp)).background(Color.Black.copy(alpha = 0.5f)).padding(4.dp)) {
                for (z in listOf(1f, 2f, 3f)) {
                    val selected = kotlin.math.abs(zoom - z) < 0.05f
                    Text(
                        "${z.toInt()}×", color = if (selected) Color.Black else Color.White, fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 4.dp)
                            .clip(CircleShape).background(if (selected) Color.White else Color.Transparent)
                            .clickable {
                                val cam = camera ?: return@clickable
                                val max = cam.cameraInfo.zoomState.value?.maxZoomRatio ?: 1f
                                zoom = z.coerceAtMost(max)
                                cam.cameraControl.setZoomRatio(zoom)
                            }.padding(horizontal = 14.dp, vertical = 8.dp),
                    )
                }
            }
            Spacer(Modifier.height(18.dp))
            Box(
                Modifier.size(78.dp).clip(CircleShape).background(Color.White.copy(alpha = if (pressed) 0.6f else 1f))
                    .clickable(enabled = !pressed) {
                        // The press is the capture. No checks, no waiting screen.
                        val capture = imageCapture ?: return@clickable
                        val r = rect ?: return@clickable
                        val size = viewSize
                        pressed = true
                        val shutterNanos = SystemClock.elapsedRealtimeNanos()
                        capture.takePicture(executor, object : ImageCapture.OnImageCapturedCallback() {
                            override fun onCaptureSuccess(image: ImageProxy) {
                                RectangleState.save(ctx, r)
                                val pressToFrame = (SystemClock.elapsedRealtimeNanos() - shutterNanos) / 1_000_000f
                                onCaptured(ShutterEvent(image, r, size.width, size.height, PreviewScale.FILL_CENTER, shutterNanos,
                                    pressToFrame, zslOn, zoom))
                            }

                            override fun onError(exception: ImageCaptureException) {
                                mainExecutor.execute { pressed = false }
                            }
                        })
                    },
                contentAlignment = Alignment.Center,
            ) { Box(Modifier.size(64.dp).clip(CircleShape).background(Color.White).padding(3.dp).clip(CircleShape).background(Color.Black).padding(2.dp).clip(CircleShape).background(Color.White)) }
        }
    }
}
