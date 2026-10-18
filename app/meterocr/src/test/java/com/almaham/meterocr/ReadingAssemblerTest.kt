package com.almaham.meterocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Same cases as lab/test_assemble.py so the Kotlin port is proven equivalent to the Python reference. */
class ReadingAssemblerTest {
    private fun box(cls: Int, x: Float, y: Float = 10f, w: Float = 20f, h: Float = 40f, score: Float = 0.9f) =
        Detection(cls, score, x, y, x + w, y + h)

    private fun digits(s: String, x0: Float = 10f, pitch: Float = 30f, score: Float = 0.9f) =
        s.mapIndexed { i, c -> box(c - '0', x0 + i * pitch, score = score) }

    @Test
    fun plainSixDigitsWithSmallDecimals() {
        val dets = digits("003155") + listOf(box(4, 200f, y = 30f, w = 10f, h = 20f), box(2, 215f, y = 30f, w = 10f, h = 20f))
        val r = ReadingAssembler.assemble(dets, 400f, 64f)
        assertEquals(ReadingStatus.OK, r.status)
        assertEquals("003155", r.text)
        assertEquals("3155", r.value)
        assertTrue(r.confident)
    }

    @Test
    fun dotSeparatesDecimalsOfEqualHeight() {
        val dets = digits("21") + listOf(Detection(10, 0.8f, 66f, 44f, 72f, 50f), box(4, 80f), box(8, 110f))
        val r = ReadingAssembler.assemble(dets, 400f, 64f)
        assertEquals("21", r.text)
    }

    @Test
    fun secondarySmallerLineIsIgnored() {
        val dets = digits("000538") + listOf(box(0, 20f, y = 55f, w = 8f, h = 14f), box(5, 32f, y = 55f, w = 8f, h = 14f))
        assertEquals("000538", ReadingAssembler.assemble(dets, 400f, 80f).text)
    }

    @Test
    fun missingDigitIsFlaggedNotGuessed() {
        val dets = digits("0067") + listOf(box(1, 10f + 5 * 30f), box(9, 10f + 6 * 30f))
        val r = ReadingAssembler.assemble(dets, 400f, 64f)
        assertEquals(ReadingStatus.MISSING_DIGIT, r.status)
        assertFalse(r.confident)
    }

    @Test
    fun alternativeClassMakesDigitUncertain() {
        val dets = digits("0024") + box(8, 10f + 3 * 30f, score = 0.6f)
        val r = ReadingAssembler.assemble(dets, 400f, 64f)
        assertEquals("0024", r.text)
        assertTrue(r.digits[3].uncertain)
        assertEquals(listOf(3), r.uncertainIndices)
        assertFalse(r.confident)
    }

    @Test
    fun lowScoreDigitIsUncertainButReadingReturned() {
        val dets = "0024".mapIndexed { i, c -> box(c - '0', 10f + i * 30f, score = if (i == 2) 0.3f else 0.9f) }
        val r = ReadingAssembler.assemble(dets, 400f, 64f)
        assertEquals("0024", r.text)
        assertTrue(r.digits[2].uncertain)
        assertFalse(r.confident)
    }

    @Test
    fun emptyWhenNoDigits() {
        assertEquals(ReadingStatus.EMPTY, ReadingAssembler.assemble(listOf(Detection(10, 0.9f, 1f, 1f, 5f, 5f)), 100f, 50f).status)
        assertEquals("", ReadingAssembler.assemble(emptyList(), 100f, 50f).value)
    }

    @Test
    fun tooManyDigits() {
        val dets = (0 until 9).map { box(1, 10f + it * 30f) }
        assertEquals(ReadingStatus.TOO_MANY_DIGITS, ReadingAssembler.assemble(dets, 400f, 64f).status)
    }

    @Test
    fun farAwayDigitsSplitOff() {
        val dets = digits("2887") + listOf(box(1, 330f), box(5, 360f))
        assertEquals("2887", ReadingAssembler.assemble(dets, 400f, 64f).text)
    }

    @Test
    fun allZerosReadsAsZero() {
        assertEquals("0", ReadingAssembler.assemble(digits("000000"), 400f, 64f).value)
    }

    @Test
    fun numberCleaner() {
        assertEquals("3155", NumberCleaner.stripLeadingZeros("003155"))
        assertEquals("0", NumberCleaner.stripLeadingZeros("0000"))
        assertEquals("", NumberCleaner.stripLeadingZeros(""))
        assertEquals("", NumberCleaner.stripLeadingZeros("12a"))
        assertEquals("31265", NumberCleaner.stripLeadingZeros("031265"))
    }

    @Test
    fun validatorColours() {
        assertEquals(Warning.NONE, ReadingValidator.validate("", 2259))
        assertEquals(Warning.NONE, ReadingValidator.validate("3155", 2259))
        assertEquals(Warning.BELOW_PREVIOUS, ReadingValidator.validate("2000", 2259))
        assertEquals(Warning.CONSUMPTION_TOO_HIGH, ReadingValidator.validate("9000", 2259, maxConsumption = 3000))
        assertEquals(Warning.NONE, ReadingValidator.validate("5259", 2259, maxConsumption = 3000))
    }
}

class LatticeAndSegmentTest {
    private fun box(cls: Int, x: Float, y: Float = 10f, w: Float = 20f, h: Float = 40f, score: Float = 0.9f) =
        Detection(cls, score, x, y, x + w, y + h)

    @Test
    fun latticePredictsTheMissingCell() {
        val dets = listOf(box(0, 10f), box(0, 40f), box(6, 70f), box(1, 130f), box(9, 160f))
        val r = ReadingAssembler.assemble(dets, 400f, 64f)
        assertEquals(ReadingStatus.MISSING_DIGIT, r.status)
        val cells = ReadingAssembler.missingCells(r.digits)
        assertEquals(1, cells.size)
        assertEquals(100f, cells[0][0], 1e-3f)
        assertEquals(120f, cells[0][2], 1e-3f)
    }

    @Test
    fun segmentPatternAgreement() {
        // perfect '8' ink (all segments on) agrees fully with 8 and disagrees with 0 on segment g
        val all = FloatArray(7) { 0.9f }
        assertEquals(1f, SegmentVerifier.agreement(all, 8), 1e-6f)
        assertEquals(6f / 7f, SegmentVerifier.agreement(all, 0), 1e-6f)
        // measured '0' (g off) -> best class 0
        val zero = floatArrayOf(0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.1f)
        assertEquals(0, SegmentVerifier.bestPatternClass(zero).first)
        // ghost segments: faint uniform ink stays OFF -> pattern of '1'
        val one = floatArrayOf(0.15f, 0.9f, 0.9f, 0.15f, 0.12f, 0.14f, 0.13f)
        assertEquals(1, SegmentVerifier.bestPatternClass(one).first)
    }

    @Test
    fun segmentDisagreementMakesDigitUncertain() {
        val d = Digit(8, 0.95f, 0f, 0f, 20f, 40f, segAgree = 5f / 7f)
        assertTrue(d.uncertain)
        assertFalse(d.copy(segAgree = 1f).uncertain)
    }
}
