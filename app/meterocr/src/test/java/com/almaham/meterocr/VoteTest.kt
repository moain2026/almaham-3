package com.almaham.meterocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoteTest {
    private fun neural(s: String, conf: Float = 0.9f) = Reading(s, ReadingStatus.OK,
        s.mapIndexed { i, c -> Digit(c - '0', conf, i * 30f, 0f, i * 30f + 20f, 40f) })

    private fun forensic(s: String, conf: Double = 0.95) = ForensicReader.Result(s,
        s.map { ForensicReader.Digit(it - '0', conf, doubleArrayOf(0.0, 0.0, 1.0, 1.0), IntArray(7)) }, "OK", 1.0)

    @Test fun agreementIsConfident() {
        val v = Vote.vote(neural("003155"), forensic("003155"))
        assertEquals("3155", v.value); assertTrue(v.confident); assertTrue(v.digits.all { it.src == "both" })
    }

    @Test fun disagreementWithOneHighEngineTakesIt() {
        val v = Vote.vote(neural("003185", 0.5f), forensic("003155", 0.95))
        assertEquals("3155", v.value); assertTrue(v.confident)
    }

    @Test fun disagreementBothHighIsUncertainNotWrongConfident() {
        val v = Vote.vote(neural("003185", 0.95f), forensic("003155", 0.95))
        assertFalse(v.confident); assertEquals(listOf(4), v.uncertainIndices)
    }

    @Test fun singleEngineKeepsOwnConfidence() {
        assertTrue(Vote.vote(neural("0024", 0.9f), null).confident)
        assertFalse(Vote.vote(neural("0024", 0.5f), null).confident)
        assertEquals("", Vote.vote(Reading(), null).value)
    }

    @Test fun lengthMismatchTakesTheAllHighEngine() {
        val v = Vote.vote(neural("06719", 0.6f), forensic("006719", 0.95))
        assertEquals("6719", v.value); assertEquals("LEN_FORENSIC", v.status)
    }
}
