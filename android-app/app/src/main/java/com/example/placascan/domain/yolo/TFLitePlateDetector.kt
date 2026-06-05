package com.example.placascan.domain.yolo

import android.content.Context
import android.graphics.Bitmap
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel
import kotlin.math.max

/**
 * Detector de placas offline usando YOLOv8 no formato TFLite.
 */
class TFLitePlateDetector(context: Context) {

    private var interpreter: Interpreter? = null
    
    // Configurações do modelo YOLOv8n
    private val inputSize = 640 // YOLOv8 padronizado para 640x640
    private val numElements = 5 // cx, cy, w, h, class_score (pois temos apenas 1 classe: 'placa')
    private val numAnchors = 8400 // Total de caixas delimitadoras inferidas
    
    init {
        try {
            val modelBuffer = loadModelFile(context, "placa-veicular-model.tflite")
            val options = Interpreter.Options().apply {
                setNumThreads(4)
            }
            interpreter = Interpreter(modelBuffer, options)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun loadModelFile(context: Context, modelName: String): ByteBuffer {
        val assetFileDescriptor = context.assets.openFd(modelName)
        val fileInputStream = FileInputStream(assetFileDescriptor.fileDescriptor)
        val fileChannel = fileInputStream.channel
        val startOffset = assetFileDescriptor.startOffset
        val declaredLength = assetFileDescriptor.declaredLength
        return fileChannel.map(FileChannel.MapMode.READ_ONLY, startOffset, declaredLength)
    }

    /**
     * Classe para representar uma detecção (caixa delimitadora e pontuação de confiança).
     */
    data class Detection(
        val xMin: Float,
        val yMin: Float,
        val xMax: Float,
        val yMax: Float,
        val confidence: Float,
        val relXMin: Float = 0f,
        val relYMin: Float = 0f,
        val relXMax: Float = 0f,
        val relYMax: Float = 0f
    )

    /**
     * Processa a imagem da câmera e retorna as detecções de placas.
     * @param bitmap O frame da câmera
     * @param confidenceThreshold Limiar mínimo de confiança para aceitar a detecção
     * @return Lista de detecções
     */
    fun detect(bitmap: Bitmap, confidenceThreshold: Float = 0.5f): List<Detection> {
        if (interpreter == null) return emptyList()

        // 1. Pré-processamento: Redimensionar e converter para ByteBuffer
        val resizedBitmap = Bitmap.createScaledBitmap(bitmap, inputSize, inputSize, true)
        val inputBuffer = convertBitmapToByteBuffer(resizedBitmap)

        // 2. Output Tensor Shape: [1, 5, 8400]
        val outputBuffer = Array(1) { Array(numElements) { FloatArray(numAnchors) } }

        // 3. Inferência
        interpreter?.run(inputBuffer, outputBuffer)

        // 4. Pós-processamento (Decodificação e NMS)
        return postProcess(outputBuffer[0], confidenceThreshold, bitmap.width, bitmap.height)
    }

    private fun convertBitmapToByteBuffer(bitmap: Bitmap): ByteBuffer {
        // 1 (batch) * 640 (h) * 640 (w) * 3 (canais) * 4 (bytes por float)
        val byteBuffer = ByteBuffer.allocateDirect(4 * 1 * inputSize * inputSize * 3)
        byteBuffer.order(ByteOrder.nativeOrder())

        val intValues = IntArray(inputSize * inputSize)
        bitmap.getPixels(intValues, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)

        var pixel = 0
        for (i in 0 until inputSize) {
            for (j in 0 until inputSize) {
                val value = intValues[pixel++]
                // YOLOv8 usa normalização / 255.0
                byteBuffer.putFloat(((value shr 16) and 0xFF) / 255.0f) // R
                byteBuffer.putFloat(((value shr 8) and 0xFF) / 255.0f)  // G
                byteBuffer.putFloat((value and 0xFF) / 255.0f)         // B
            }
        }
        return byteBuffer
    }

    private fun postProcess(
        output: Array<FloatArray>,
        confidenceThreshold: Float,
        originalWidth: Int,
        originalHeight: Int
    ): List<Detection> {
        val detections = mutableListOf<Detection>()

        for (i in 0 until numAnchors) {
            val confidence = output[4][i]
            if (confidence > confidenceThreshold) {
                val cx = output[0][i]
                val cy = output[1][i]
                val w = output[2][i]
                val h = output[3][i]

                // Modelo retorna coordenadas normalizadas (0-1), converter para pixels da imagem original
                val xMin = (cx - w / 2) * originalWidth
                val yMin = (cy - h / 2) * originalHeight
                val xMax = (cx + w / 2) * originalWidth
                val yMax = (cy + h / 2) * originalHeight

                detections.add(
                    Detection(
                        xMin, yMin, xMax, yMax, confidence,
                        relXMin = cx - w / 2,
                        relYMin = cy - h / 2,
                        relXMax = cx + w / 2,
                        relYMax = cy + h / 2
                    )
                )
            }
        }

        return nonMaximumSuppression(detections, iouThreshold = 0.45f)
    }

    /**
     * Aplica Non-Maximum Suppression (NMS) para remover caixas sobrepostas duplicadas.
     */
    private fun nonMaximumSuppression(boxes: List<Detection>, iouThreshold: Float): List<Detection> {
        if (boxes.isEmpty()) return emptyList()

        val sortedBoxes = boxes.sortedByDescending { it.confidence }.toMutableList()
        val selectedBoxes = mutableListOf<Detection>()

        while (sortedBoxes.isNotEmpty()) {
            val bestBox = sortedBoxes.removeAt(0)
            selectedBoxes.add(bestBox)

            sortedBoxes.removeAll { box ->
                calculateIoU(bestBox, box) > iouThreshold
            }
        }
        return selectedBoxes
    }

    private fun calculateIoU(box1: Detection, box2: Detection): Float {
        val xA = max(box1.xMin, box2.xMin)
        val yA = max(box1.yMin, box2.yMin)
        val xB = kotlin.math.min(box1.xMax, box2.xMax)
        val yB = kotlin.math.min(box1.yMax, box2.yMax)

        val intersectionArea = max(0f, xB - xA) * max(0f, yB - yA)

        val box1Area = (box1.xMax - box1.xMin) * (box1.yMax - box1.yMin)
        val box2Area = (box2.xMax - box2.xMin) * (box2.yMax - box2.yMin)

        val unionArea = box1Area + box2Area - intersectionArea

        return if (unionArea > 0) intersectionArea / unionArea else 0f
    }

    fun close() {
        interpreter?.close()
        interpreter = null
    }
}
