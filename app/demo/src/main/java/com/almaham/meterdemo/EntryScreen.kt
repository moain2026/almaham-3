package com.almaham.meterdemo

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.almaham.meterocr.Warning

private val Bg = Color(0xFF151410)
private val Card = Color(0xFF1F1D18)
private val Amber = Color(0xFFF2B233)
private val Green = Color(0xFF58D68D)
private val Red = Color(0xFFE74C3C)
private val Orange = Color(0xFFF39C12)
private val Muted = Color(0xFF9A978F)

/** Dummy subscriber data (brief §7.2: entry screen with fake data, no ERP). */
object DummyData {
    const val SUBSCRIBER = "حليمه ابراهيم عبدالله رجب"
    const val METER_NO = "870010055"
    const val PREVIOUS = 2259L
}

/** State of the entry screen after a capture. */
data class EntryState(
    val value: String = "",
    val autoRead: Boolean = false,
    val edited: Boolean = false,
    val uncertainIndices: List<Int> = emptyList(),
    val thumbnail: Bitmap? = null,
    val evidenceBytes: Int = 0,
    val captureToNumberMs: Float? = null,
    val engineValue: String = "",
    val warning: Warning = Warning.NONE,
    val savedCount: Int = 0,
)

/** Colours only the uncertain digits (brief §2.5: "the digit the engine is unsure of colours itself"). */
private class UncertainDigitsTransformation(private val indices: Set<Int>) : VisualTransformation {
    override fun filter(text: androidx.compose.ui.text.AnnotatedString): TransformedText {
        val styled = buildAnnotatedString {
            text.text.forEachIndexed { i, ch ->
                if (i in indices) withStyle(SpanStyle(color = Orange, background = Orange.copy(alpha = 0.18f))) { append(ch) } else append(ch)
            }
        }
        return TransformedText(styled, OffsetMapping.Identity)
    }
}

@Composable
fun EntryScreen(
    state: EntryState,
    onValueChange: (String) -> Unit,
    onCapture: () -> Unit,
    onGallery: () -> Unit,
    onSave: () -> Unit,
    onBatchTest: () -> Unit,
) {
    val fieldColor = when (state.warning) {
        Warning.BELOW_PREVIOUS -> Red
        Warning.CONSUMPTION_TOO_HIGH -> Orange
        Warning.NONE -> if (state.autoRead) Amber else Muted
    }
    Column(Modifier.fillMaxSize().background(Bg).verticalScroll(rememberScrollState()).padding(16.dp)) {
        Spacer(Modifier.height(24.dp))
        Text("إدخال القراءة", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
        Text("${DummyData.SUBSCRIBER} · عداد ${DummyData.METER_NO}", color = Muted, fontSize = 13.sp, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
        Spacer(Modifier.height(20.dp))

        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card).padding(16.dp)) {
            Text("القراءة السابقة: ${DummyData.PREVIOUS}", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = state.value,
                onValueChange = { v -> if (v.length <= 8 && v.all { it.isDigit() }) onValueChange(v) },
                singleLine = true,
                textStyle = androidx.compose.ui.text.TextStyle(color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.End),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                visualTransformation = UncertainDigitsTransformation(if (state.edited) emptySet() else state.uncertainIndices.toSet()),
                placeholder = { Text("القراءة الحالية", color = Muted) },
                leadingIcon = if (state.autoRead && !state.edited) ({
                    Text("قراءة تلقائية", color = Green, fontSize = 12.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.clip(RoundedCornerShape(12.dp)).background(Green.copy(alpha = 0.15f)).padding(horizontal = 10.dp, vertical = 6.dp))
                }) else null,
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = fieldColor, unfocusedBorderColor = fieldColor, cursorColor = Amber),
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth(),
            )
            val hint = when (state.warning) {
                Warning.BELOW_PREVIOUS -> "تنبيه: الرقم أصغر من القراءة السابقة"
                Warning.CONSUMPTION_TOO_HIGH -> "تنبيه: الاستهلاك أكبر من الحد المعتاد"
                Warning.NONE -> if (state.autoRead && state.value.isEmpty()) "ما قدر المحرك يقرأ الرقم، اكتبه بيدك" else "تأكد من الرقم، وإذا غلط اضغط عليه وعدّله"
            }
            Text(hint, color = if (state.warning == Warning.NONE) Muted else fieldColor, fontSize = 12.sp, modifier = Modifier.padding(top = 6.dp))
            state.captureToNumberMs?.let {
                Text("من الضغطة إلى الرقم: ${"%.0f".format(it)} ms", color = Muted, fontSize = 11.sp)
            }
        }

        Spacer(Modifier.height(14.dp))
        Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Card).padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(92.dp).clip(RoundedCornerShape(10.dp)).border(2.dp, if (state.thumbnail != null) Green else Muted, RoundedCornerShape(10.dp)).background(Color.Black)) {
                    state.thumbnail?.let { Image(it.asImageBitmap(), null, Modifier.fillMaxSize()) }
                }
                Spacer(Modifier.width(14.dp))
                Column {
                    Text("صورة العداد", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                    Text(
                        if (state.thumbnail != null) (if (state.evidenceBytes > 0) "تم الالتقاط، ${state.evidenceBytes / 1024} كيلوبايت" else "تم الالتقاط، جاري الحفظ…") else "لم يتم التصوير بعد",
                        color = if (state.thumbnail != null) Green else Muted, fontSize = 13.sp,
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onCapture, modifier = Modifier.weight(1.4f), shape = RoundedCornerShape(24.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Amber)) {
                    Text(if (state.thumbnail != null) "إعادة التصوير" else "تصوير العداد", fontWeight = FontWeight.Bold)
                }
                OutlinedButton(onClick = onGallery, modifier = Modifier.weight(1f), shape = RoundedCornerShape(24.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Muted)) { Text("من الاستديو") }
            }
        }

        Spacer(Modifier.height(24.dp))
        Button(onClick = onSave, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Amber, contentColor = Color.Black)) {
            Text("حفظ والتالي", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        if (state.savedCount > 0) Text("تم الحفظ (${state.savedCount}) — السجل في readings_log.csv", color = Green, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = onBatchTest, modifier = Modifier.fillMaxWidth()) { Text("وضع الاختبار الجماعي (49 صورة)", color = Muted) }
    }
}
