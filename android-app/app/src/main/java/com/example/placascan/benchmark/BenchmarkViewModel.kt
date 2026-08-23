package com.example.placascan.benchmark

import android.content.Context
import android.graphics.BitmapFactory
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class BenchmarkViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(BenchmarkUiState())
    val uiState: StateFlow<BenchmarkUiState> = _uiState.asStateFlow()

    private val thresholds = listOf(0.0f, 0.2f, 0.4f, 0.6f, 0.8f)

    fun runBenchmark(context: Context) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRunning = true, progress = 0f, statusMessage = "Iniciando benchmark...")
            
            val results = mutableListOf<BenchmarkResult>()
            
            withContext(Dispatchers.Default) {
                try {
                    val assets = context.assets
                    val testPlatesDir = "test_plates"
                    val files = assets.list(testPlatesDir) ?: emptyArray()
                    
                    val imageFiles = files.filter { 
                        it.endsWith(".jpg", ignoreCase = true) || 
                        it.endsWith(".jpeg", ignoreCase = true) || 
                        it.endsWith(".png", ignoreCase = true) 
                    }

                    if (imageFiles.isEmpty()) {
                        _uiState.value = _uiState.value.copy(
                            isRunning = false,
                            statusMessage = "Nenhuma imagem encontrada em assets/test_plates/"
                        )
                        return@withContext
                    }

                    val totalIterations = imageFiles.size * PreprocessingEngine.METHODS.size * thresholds.size
                    var currentIteration = 0

                    for ((imageIndex, filename) in imageFiles.withIndex()) {
                        val nameWithoutExt = filename.substringBeforeLast(".")
                        val groundTruth = nameWithoutExt.substringBefore("_").uppercase()
                        
                        val inputStream = assets.open("$testPlatesDir/$filename")
                        val bitmap = BitmapFactory.decodeStream(inputStream)
                        inputStream.close()

                        if (bitmap == null) continue

                        for (method in PreprocessingEngine.METHODS) {
                            val processedBitmap = PreprocessingEngine.applyMethod(bitmap, method)
                            
                            val ocrResult = OCREngine.processImage(processedBitmap)
                            
                            for (threshold in thresholds) {
                                currentIteration++
                                
                                val finalOutput = if (ocrResult.confidence >= threshold) ocrResult.cleanedText else ""
                                val isMatch = AccuracyCalculator.isFullMatch(finalOutput, groundTruth)
                                val accuracy = AccuracyCalculator.calculateCharAccuracy(finalOutput, groundTruth)
                                
                                results.add(
                                    BenchmarkResult(
                                        plate = groundTruth,
                                        method = method,
                                        threshold = threshold,
                                        ocrOutput = finalOutput,
                                        ocrConfidence = ocrResult.confidence,
                                        fullMatch = isMatch,
                                        charAccuracy = accuracy
                                    )
                                )

                                _uiState.value = _uiState.value.copy(
                                    progress = currentIteration.toFloat() / totalIterations,
                                    statusMessage = "Processando imagem ${imageIndex + 1}/${imageFiles.size} | Método: $method | Threshold: $threshold"
                                )
                            }
                        }
                    }

                    val savedFile = CSVExporter.exportResults(context, results)
                    
                    if (savedFile != null) {
                        _uiState.value = _uiState.value.copy(
                            isRunning = false,
                            progress = 1.0f,
                            statusMessage = "Benchmark concluído! CSV salvo em:\n${savedFile.absolutePath}",
                            csvPath = savedFile.absolutePath
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isRunning = false,
                            statusMessage = "Erro ao salvar CSV."
                        )
                    }

                } catch (e: Exception) {
                    _uiState.value = _uiState.value.copy(
                        isRunning = false,
                        statusMessage = "Erro no benchmark: ${e.message}"
                    )
                }
            }
        }
    }
}

data class BenchmarkUiState(
    val isRunning: Boolean = false,
    val progress: Float = 0f,
    val statusMessage: String = "Pronto para iniciar",
    val csvPath: String? = null
)
