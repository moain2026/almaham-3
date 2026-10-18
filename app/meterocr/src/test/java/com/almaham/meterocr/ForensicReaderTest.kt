package com.almaham.meterocr

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.io.DataInputStream

/**
 * Kotlin ForensicReader == Python lab/forensic_reader.py on 5 fixed line crops (raw ARGB fixtures written by
 * lab/make_forensic_fixtures.py together with the Python output in expected.txt). Code-equivalence only.
 */
class ForensicReaderTest {
    private val dir = File(javaClass.classLoader!!.getResource("forensic/expected.txt")!!.toURI()).parentFile

    private fun load(name: String): Triple<IntArray, Int, Int> {
        DataInputStream(File(dir, name).inputStream().buffered()).use { s ->
            val w = s.readInt(); val h = s.readInt()
            return Triple(IntArray(w * h) { s.readInt() }, w, h)
        }
    }

    @Test
    fun matchesPythonReferenceOnFiveCrops() {
        val lines = File(dir, "expected.txt").readLines().filter { it.isNotBlank() }
        assertEquals(5, lines.size)
        for (line in lines) {
            val (name, text, status, digits) = line.split("|")
            val (px, w, h) = load(name)
            val r = ForensicReader.readLine(px, w, h)
            assertEquals("$name text", text, r.text)
            assertEquals("$name status", status, r.status)
            val exp = if (digits.isEmpty()) emptyList() else digits.split(";")
            assertEquals("$name digit count", exp.size, r.digits.size)
            exp.zip(r.digits).forEachIndexed { i, (e, d) ->
                val (cls, conf, box, seg) = e.split(":")
                assertEquals("$name[$i] cls", cls.toInt(), d.cls)
                assertEquals("$name[$i] conf", conf.toDouble(), d.conf, 1e-6)
                assertArrayEquals("$name[$i] box", box.split(",").map { it.toDouble() }.toDoubleArray(), d.box, 1e-5)
                assertEquals("$name[$i] segments", seg, d.segments.joinToString(""))
            }
        }
    }

    @Test
    fun emptyOnBlankImage() {
        val r = ForensicReader.readLine(IntArray(200 * 60) { 0xFFE0E0E0.toInt() }, 200, 60)
        assertEquals("EMPTY", r.status)
        assertEquals("", r.value)
    }

    @Test
    fun otsuSplitsTwoLevels() {
        val u8 = IntArray(100) { if (it < 50) 20 else 200 }
        val t = ForensicReader.otsu(u8)
        assert(t in 20 until 200)
    }

    @Test
    fun percentileMatchesNumpyLinear() {
        assertEquals(22.5, ForensicReader.percentile(listOf(10.0, 20.0, 15.0, 30.0), 75.0), 1e-9)
        assertEquals(15.0, ForensicReader.median(listOf(30.0, 10.0, 15.0)), 1e-9)
    }
}
