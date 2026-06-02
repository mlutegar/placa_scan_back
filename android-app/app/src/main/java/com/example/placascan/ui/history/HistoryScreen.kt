package com.example.placascan.ui.history

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.placascan.PlacaScanApplication
import com.example.placascan.data.local.entities.PlateDetectionEntity
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun HistoryScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val application = context.applicationContext as PlacaScanApplication
    val detectionRepo = application.detectionRepository
    val coroutineScope = rememberCoroutineScope()

    val historyList by detectionRepo.getAllDetections().collectAsState(initial = emptyList())

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Histórico de Detecções",
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground
            )

            IconButton(onClick = { coroutineScope.launch { detectionRepo.clearHistory() } }) {
                Icon(imageVector = Icons.Default.Delete, contentDescription = "Limpar Histórico", tint = MaterialTheme.colorScheme.error)
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))

        if (historyList.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(text = "Nenhuma placa detectada ainda.", color = Color.Gray)
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(historyList) { detection ->
                    HistoryItem(detection)
                }
            }
        }
    }
}

@Composable
fun HistoryItem(detection: PlateDetectionEntity) {
    val formatter = SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault())
    val dateString = formatter.format(Date(detection.timestamp))

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Se tiver imagem salva
            if (detection.imagePath != null) {
                val bitmap = BitmapFactory.decodeFile(detection.imagePath)
                if (bitmap != null) {
                    Image(
                        bitmap = bitmap.asImageBitmap(),
                        contentDescription = "Placa Recortada",
                        modifier = Modifier
                            .size(80.dp, 40.dp)
                            .background(Color.Black)
                    )
                    Spacer(modifier = Modifier.width(16.dp))
                }
            }

            Column {
                Text(
                    text = detection.plateText,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = "${detection.plateType} • $dateString",
                    fontSize = 12.sp,
                    color = Color.Gray
                )
                
                if (detection.isKnown) {
                    Text(
                        text = "Conhecido: ${detection.ownerName}",
                        fontSize = 14.sp,
                        color = Color(0xFF4CAF50), // Verde
                        fontWeight = FontWeight.Medium
                    )
                } else {
                    Text(
                        text = "Desconhecido",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.error,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }
    }
}
