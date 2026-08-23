package com.example.placascan.benchmark

import android.graphics.Bitmap
import org.opencv.android.Utils
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.Size
import org.opencv.imgproc.Imgproc

object PreprocessingEngine {

    val METHODS = listOf(
        "original", "grayscale", "inverted", "adaptive", 
        "bilateral", "otsu", "resized2x", "sharpened"
    )

    fun applyMethod(bitmap: Bitmap, method: String): Bitmap {
        val mat = Mat()
        Utils.bitmapToMat(bitmap, mat)
        
        val dst = Mat()
        
        when (method) {
            "original" -> {
                mat.copyTo(dst)
            }
            "grayscale" -> {
                Imgproc.cvtColor(mat, dst, Imgproc.COLOR_BGR2GRAY)
            }
            "inverted" -> {
                val gray = Mat()
                Imgproc.cvtColor(mat, gray, Imgproc.COLOR_BGR2GRAY)
                Core.bitwise_not(gray, dst)
            }
            "adaptive" -> {
                val gray = Mat()
                Imgproc.cvtColor(mat, gray, Imgproc.COLOR_BGR2GRAY)
                Imgproc.adaptiveThreshold(
                    gray, dst, 255.0,
                    Imgproc.ADAPTIVE_THRESH_MEAN_C, Imgproc.THRESH_BINARY, 11, 2.0
                )
            }
            "bilateral" -> {
                val rgb = Mat()
                Imgproc.cvtColor(mat, rgb, Imgproc.COLOR_RGBA2RGB)
                Imgproc.bilateralFilter(rgb, dst, 9, 75.0, 75.0)
            }
            "otsu" -> {
                val gray = Mat()
                Imgproc.cvtColor(mat, gray, Imgproc.COLOR_BGR2GRAY)
                Imgproc.threshold(
                    gray, dst, 0.0, 255.0,
                    Imgproc.THRESH_BINARY + Imgproc.THRESH_OTSU
                )
            }
            "resized2x" -> {
                Imgproc.resize(
                    mat, dst, Size(mat.width() * 2.0, mat.height() * 2.0),
                    0.0, 0.0, Imgproc.INTER_CUBIC
                )
            }
            "sharpened" -> {
                val kernel = Mat(3, 3, CvType.CV_32F)
                kernel.put(0, 0, 0.0, -1.0, 0.0, -1.0, 5.0, -1.0, 0.0, -1.0, 0.0)
                Imgproc.filter2D(mat, dst, -1, kernel)
            }
            else -> {
                mat.copyTo(dst)
            }
        }
        
        val outBitmap = Bitmap.createBitmap(dst.cols(), dst.rows(), Bitmap.Config.ARGB_8888)
        try {
            Utils.matToBitmap(dst, outBitmap)
        } catch (e: Exception) {
            if (dst.channels() == 1) {
                val rgba = Mat()
                Imgproc.cvtColor(dst, rgba, Imgproc.COLOR_GRAY2RGBA)
                Utils.matToBitmap(rgba, outBitmap)
            } else if (dst.channels() == 3) {
                val rgba = Mat()
                Imgproc.cvtColor(dst, rgba, Imgproc.COLOR_RGB2RGBA)
                Utils.matToBitmap(rgba, outBitmap)
            } else {
                mat.copyTo(dst)
                Utils.matToBitmap(dst, outBitmap)
            }
        }
        
        return outBitmap
    }
}
