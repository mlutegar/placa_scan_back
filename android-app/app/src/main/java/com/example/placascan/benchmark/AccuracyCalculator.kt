package com.example.placascan.benchmark

import kotlin.math.min

object AccuracyCalculator {

    fun calculateCharAccuracy(ocrOutput: String, groundTruth: String): Float {
        if (groundTruth.isEmpty()) return 0f
        var matches = 0
        for (i in 0 until min(ocrOutput.length, groundTruth.length)) {
            if (ocrOutput[i] == groundTruth[i]) matches++
        }
        return matches.toFloat() / groundTruth.length.toFloat()
    }

    fun isFullMatch(ocrOutput: String, groundTruth: String): Boolean {
        return ocrOutput.equals(groundTruth, ignoreCase = true)
    }
}
