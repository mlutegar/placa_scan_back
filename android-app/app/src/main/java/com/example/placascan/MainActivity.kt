package com.example.placascan

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.example.placascan.theme.PlacaScanTheme

class MainActivity : ComponentActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    
    if (org.opencv.android.OpenCVLoader.initDebug()) {
        android.util.Log.d("OpenCV", "OpenCV initialized successfully")
    } else {
        android.util.Log.e("OpenCV", "OpenCV initialization failed")
    }

    enableEdgeToEdge()
    setContent {
      PlacaScanTheme { Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { MainNavigation() } }
    }
  }
}
