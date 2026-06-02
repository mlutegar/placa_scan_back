package com.example.placascan.domain.ocr

import android.graphics.Bitmap
import org.opencv.android.Utils
import org.opencv.core.Mat
import org.opencv.core.Size
import org.opencv.imgproc.Imgproc

/**
 * Processador de imagem utilizando OpenCV para otimizar a imagem da placa
 * antes de enviá-la para o ML Kit OCR.
 */
class OpenCVImageProcessor {

    /**
     * Aplica uma série de filtros na imagem da placa para melhorar a precisão do OCR.
     */
    fun processPlateImage(bitmap: Bitmap): Bitmap {
        val mat = Mat()
        // Converte Bitmap para Mat (formato do OpenCV)
        Utils.bitmapToMat(bitmap, mat)

        // 1. Converter para escala de cinza
        val grayMat = Mat()
        Imgproc.cvtColor(mat, grayMat, Imgproc.COLOR_RGBA2GRAY)

        // 2. Filtro Bilateral (reduz ruído mantendo as bordas afiadas)
        val bilateralMat = Mat()
        Imgproc.bilateralFilter(grayMat, bilateralMat, 9, 75.0, 75.0)

        // 3. Adaptive Thresholding (destaca os caracteres com base na iluminação local)
        val threshMat = Mat()
        Imgproc.adaptiveThreshold(
            bilateralMat,
            threshMat,
            255.0,
            Imgproc.ADAPTIVE_THRESH_GAUSSIAN_C,
            Imgproc.THRESH_BINARY,
            11,
            2.0
        )

        // 4. Operação morfológica (Opcional, fechamento para preencher buracos nos caracteres)
        // val morphMat = Mat()
        // val kernel = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(3.0, 3.0))
        // Imgproc.morphologyEx(threshMat, morphMat, Imgproc.MORPH_CLOSE, kernel)

        // Converte de volta para Bitmap
        val resultBitmap = Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
        Utils.matToBitmap(threshMat, resultBitmap)

        // Limpa a memória nativa do OpenCV
        mat.release()
        grayMat.release()
        bilateralMat.release()
        threshMat.release()

        return resultBitmap
    }

    /**
     * Recorta a placa da imagem original baseado na bounding box do YOLO,
     * adicionando um padding opcional.
     */
    fun cropPlate(original: Bitmap, xMin: Float, yMin: Float, xMax: Float, yMax: Float, padding: Int = 10): Bitmap? {
        val width = original.width
        val height = original.height

        var left = (xMin.toInt() - padding).coerceAtLeast(0)
        var top = (yMin.toInt() - padding).coerceAtLeast(0)
        var right = (xMax.toInt() + padding).coerceAtMost(width)
        var bottom = (yMax.toInt() + padding).coerceAtMost(height)

        val cropWidth = right - left
        val cropHeight = bottom - top

        if (cropWidth <= 0 || cropHeight <= 0) return null

        return Bitmap.createBitmap(original, left, top, cropWidth, cropHeight)
    }
}
