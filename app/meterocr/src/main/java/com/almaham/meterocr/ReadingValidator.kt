package com.almaham.meterocr

/** Colour-only validation (brief §2.5). It never blocks saving; it only tells the UI which tint to use. */
enum class Warning { NONE, BELOW_PREVIOUS, CONSUMPTION_TOO_HIGH }

object ReadingValidator {
    /**
     * @param current the value the field holds (engine output or the reader's edit), digits only or empty.
     * @param previous last approved reading.
     * @param maxConsumption adjustable ceiling for (current - previous).
     */
    fun validate(current: String, previous: Long, maxConsumption: Long = MeterOcrConfig.MAX_CONSUMPTION_KWH): Warning {
        val cur = current.toLongOrNull() ?: return Warning.NONE
        if (cur < previous) return Warning.BELOW_PREVIOUS
        if (cur - previous > maxConsumption) return Warning.CONSUMPTION_TOO_HIGH
        return Warning.NONE
    }
}
