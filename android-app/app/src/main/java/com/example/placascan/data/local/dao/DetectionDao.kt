package com.example.placascan.data.local.dao

import androidx.room.*
import com.example.placascan.data.local.entities.PlateDetectionEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface DetectionDao {

    @Query("SELECT * FROM plate_detections ORDER BY timestamp DESC")
    fun getAllDetections(): Flow<List<PlateDetectionEntity>>

    @Insert
    suspend fun insertDetection(detection: PlateDetectionEntity): Long

    @Query("DELETE FROM plate_detections")
    suspend fun clearAll()
}
