package com.example.placascan.benchmark

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.google.android.gms.tasks.Task
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

suspend fun <T> Task<T>.await(): T = suspendCoroutine { continuation ->
    addOnSuccessListener { result ->
        continuation.resume(result)
    }
    addOnFailureListener { exception ->
        continuation.resumeWithException(exception)
    }
}

data class OCRResult(
    val cleanedText: String,
    val confidence: Float
)

object OCREngine {

    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

    suspend fun processImage(bitmap: Bitmap): OCRResult {
        val inputImage = InputImage.fromBitmap(bitmap, 0)
        
        return try {
            val result: Text = recognizer.process(inputImage).await()
            val rawText = result.text
            val cleaned = rawText.replace(Regex("[^A-Za-z0-9]"), "").uppercase()
            
            var bestConfidence = 1.0f
            
            for (block in result.textBlocks) {
                for (line in block.lines) {
                    val lineCleaned = line.text.replace(Regex("[^A-Za-z0-9]"), "").uppercase()
                    if (lineCleaned == cleaned) {
                        try {
                            val confMethod = line::class.java.getMethod("getConfidence")
                            val conf = confMethod.invoke(line) as Float
                            bestConfidence = conf
                        } catch (e: Exception) {
                            // No confidence property found
                        }
                    }
                }
            }

            OCRResult(cleanedText = cleaned, confidence = bestConfidence)
        } catch (e: Exception) {
            OCRResult(cleanedText = "", confidence = 0f)
        }
    }
}
