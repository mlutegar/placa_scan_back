package com.example.placascan.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "known_plates")
data class KnownPlateEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Int = 0,
    val plateText: String,
    val ownerName: String
)
