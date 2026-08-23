package com.example.placascan.benchmark

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileWriter

data class BenchmarkResult(
    val plate: String,
    val method: String,
    val threshold: Float,
    val ocrOutput: String,
    val ocrConfidence: Float,
    val fullMatch: Boolean,
    val charAccuracy: Float
)

object CSVExporter {
    private const val TAG = "CSVExporter"

    fun exportResults(context: Context, results: List<BenchmarkResult>): File? {
        val fileName = "benchmark_results.csv"
        val file = File(context.getExternalFilesDir(null), fileName)

        try {
            val writer = FileWriter(file)
            writer.append("plate,method,threshold,ocr_output,ocr_confidence,full_match,char_accuracy\n")

            for (result in results) {
                writer.append(
                    "${result.plate},${result.method},${result.threshold},${result.ocrOutput}," +
                    "${result.ocrConfidence},${result.fullMatch},${result.charAccuracy}\n"
                )
            }
            writer.flush()
            writer.close()
            Log.d(TAG, "CSV exported successfully to: ${file.absolutePath}")
            return file
        } catch (e: Exception) {
            Log.e(TAG, "Error exporting CSV: ${e.message}", e)
            return null
        }
    }
}
