package com.example.placascan.data.local.dao

import androidx.room.*
import com.example.placascan.data.local.entities.KnownPlateEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface KnownPlateDao {

    @Query("SELECT * FROM known_plates ORDER BY plateText ASC")
    fun getAllKnownPlates(): Flow<List<KnownPlateEntity>>

    @Query("SELECT * FROM known_plates ORDER BY plateText ASC")
    suspend fun getKnownPlatesList(): List<KnownPlateEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertKnownPlate(plate: KnownPlateEntity): Long

    @Delete
    suspend fun deleteKnownPlate(plate: KnownPlateEntity)
}
