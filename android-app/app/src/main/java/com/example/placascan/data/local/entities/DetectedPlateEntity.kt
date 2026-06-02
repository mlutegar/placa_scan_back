package com.example.placascan.data.local.entities

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Entidade Room equivalente ao model DetectedPlate do Django (backend/models.py).
 *
 * Representa uma placa individual encontrada em uma sessão de detecção.
 * Campos mapeados:
 *   - detection            → detectionId (FK → PlateDetectionEntity, CASCADE delete)
 *   - plate_number_detected → plateNumberDetected (texto bruto do OCR)
 *   - known_plate          → knownPlateId (FK → KnownPlateEntity, SET NULL)
 *   - bounding_box {x1..}  → x1, y1, x2, y2 (campos achatados em vez de JSON)
 *   - yolo_confidence      → yoloConfidence
 *   - cropped_image        → croppedImagePath (caminho local no filesDir)
 *   - best_ocr_text        → bestOcrText
 *   - best_ocr_confidence  → bestOcrConfidence
 *   - created_at           → createdAt
 *
 * Propriedade regularizationStatus equivale ao @property Django de DetectedPlate.
 */
@Entity(
    tableName = "detected_plates",
    foreignKeys = [
        ForeignKey(
            entity = PlateDetectionEntity::class,
            parentColumns = ["id"],
            childColumns = ["detectionId"],
            onDelete = ForeignKey.CASCADE
        ),
        ForeignKey(
            entity = KnownPlateEntity::class,
            parentColumns = ["id"],
            childColumns = ["knownPlateId"],
            onDelete = ForeignKey.SET_NULL
        )
    ],
    indices = [
        Index("detectionId"),
        Index("knownPlateId")
    ]
)
data class DetectedPlateEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Int = 0,
    val detectionId: String,
    val plateNumberDetected: String,
    val knownPlateId: Int? = null,
    val similarityScore: Int? = null,   // Score do LevenshteinMatcher (0-100)
    val isRegularized: Boolean? = null, // Cache do status para exibição rápida
    // Bounding box achatado (x1, y1, x2, y2) em vez de JSONField do Django
    val x1: Int,
    val y1: Int,
    val x2: Int,
    val y2: Int,
    val yoloConfidence: Float,
    val croppedImagePath: String,
    val bestOcrText: String,
    val bestOcrConfidence: Float? = null,
    val plateType: String = "unknown",  // "old" | "mercosul" | "unknown"
    val createdAt: Long = System.currentTimeMillis()
) {
    /**
     * Equivalente ao @property regularization_status do Django.
     */
    val regularizationStatus: String
        get() = when (isRegularized) {
            true  -> "Regularizada"
            false -> "Não Regularizada"
            null  -> "Desconhecida"
        }
}
