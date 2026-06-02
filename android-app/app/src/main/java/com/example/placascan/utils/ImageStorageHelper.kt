package com.example.placascan.utils

import android.content.Context
import android.graphics.Bitmap
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

object ImageStorageHelper {

    fun saveBitmapToInternalStorage(context: Context, bitmap: Bitmap): String? {
        return try {
            // Cria a pasta "plates" dentro de filesDir se não existir
            val directory = File(context.filesDir, "plates")
            if (!directory.exists()) {
                directory.mkdirs()
            }

            // Gera um nome único para a imagem
            val fileName = "plate_${UUID.randomUUID()}.jpg"
            val file = File(directory, fileName)

            val outputStream = FileOutputStream(file)
            // Comprime a imagem como JPEG
            bitmap.compress(Bitmap.CompressFormat.JPEG, 90, outputStream)
            outputStream.flush()
            outputStream.close()

            file.absolutePath
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }
}
