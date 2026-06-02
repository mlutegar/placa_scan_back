package com.example.placascan

import android.app.Application
import androidx.room.Room
import com.example.placascan.data.DetectionRepository
import com.example.placascan.data.KnownPlateRepository
import com.example.placascan.data.local.AppDatabase

class PlacaScanApplication : Application() {
    
    lateinit var database: AppDatabase
        private set
        
    lateinit var detectionRepository: DetectionRepository
        private set
        
    lateinit var knownPlateRepository: KnownPlateRepository
        private set

    override fun onCreate() {
        super.onCreate()
        
        database = Room.databaseBuilder(
            applicationContext,
            AppDatabase::class.java,
            "placascan-db"
        ).build()
        
        detectionRepository = DetectionRepository(database.detectionDao())
        knownPlateRepository = KnownPlateRepository(database.knownPlateDao())
    }
}
