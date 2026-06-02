package com.example.placascan.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "plate_detections")
data class PlateDetectionEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Int = 0,
    val plateText: String,
    val plateType: String,
    val imagePath: String?,
    val isKnown: Boolean,
    val ownerName: String?,
    val timestamp: Long
)
