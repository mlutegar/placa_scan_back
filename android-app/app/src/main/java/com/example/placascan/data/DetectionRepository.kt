package com.example.placascan.data

import com.example.placascan.data.local.dao.DetectionDao
import com.example.placascan.data.local.entities.PlateDetectionEntity
import kotlinx.coroutines.flow.Flow

class DetectionRepository(private val dao: DetectionDao) {

    fun getAllDetections(): Flow<List<PlateDetectionEntity>> {
        return dao.getAllDetections()
    }

    suspend fun insertDetection(detection: PlateDetectionEntity) {
        dao.insertDetection(detection)
    }

    suspend fun clearHistory() {
        dao.clearAll()
    }
}
