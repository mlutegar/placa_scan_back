package com.example.placascan.domain.detector

/**
 * Representa uma placa detectada pelo modelo YOLO com seus dados básicos.
 */
data class PlateDetection(
    val boundingBox: BoundingBox,
    val yoloConfidence: Float,
    val croppedBitmap: android.graphics.Bitmap
)

/**
 * Coordenadas da caixa delimitadora (bounding box) da placa na imagem original.
 * Espelha a lógica de {x1, y1, x2, y2} usada no plate_detector.py original.
 */
data class BoundingBox(
    val x1: Int,
    val y1: Int,
    val x2: Int,
    val y2: Int
) {
    val width: Int get() = x2 - x1
    val height: Int get() = y2 - y1
    val centerX: Float get() = (x1 + x2) / 2f
    val centerY: Float get() = (y1 + y2) / 2f
}
