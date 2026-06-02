package com.example.placascan.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.example.placascan.data.local.dao.DetectionDao
import com.example.placascan.data.local.dao.KnownPlateDao
import com.example.placascan.data.local.entities.KnownPlateEntity
import com.example.placascan.data.local.entities.PlateDetectionEntity

/**
 * Banco de dados Room do PlacaScan.
 */
@Database(
    entities = [
        KnownPlateEntity::class,
        PlateDetectionEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun knownPlateDao(): KnownPlateDao
    abstract fun detectionDao(): DetectionDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "placascan.db"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
