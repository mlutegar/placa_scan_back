package com.example.placascan.data

import com.example.placascan.data.local.dao.KnownPlateDao
import com.example.placascan.data.local.entities.KnownPlateEntity
import kotlinx.coroutines.flow.Flow

class KnownPlateRepository(private val dao: KnownPlateDao) {

    fun getAllKnownPlates(): Flow<List<KnownPlateEntity>> {
        return dao.getAllKnownPlates()
    }
    
    suspend fun getKnownPlatesList(): List<KnownPlateEntity> {
        return dao.getKnownPlatesList()
    }

    suspend fun insertKnownPlate(plate: KnownPlateEntity) {
        dao.insertKnownPlate(plate)
    }

    suspend fun deleteKnownPlate(plate: KnownPlateEntity) {
        dao.deleteKnownPlate(plate)
    }
}
