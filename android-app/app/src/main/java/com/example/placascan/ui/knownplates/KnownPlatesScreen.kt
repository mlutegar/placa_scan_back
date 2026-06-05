package com.example.placascan.ui.knownplates

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.placascan.PlacaScanApplication
import com.example.placascan.data.local.entities.KnownPlateEntity
import kotlinx.coroutines.launch

@Composable
fun KnownPlatesScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val application = context.applicationContext as PlacaScanApplication
    val knownPlateRepo = application.knownPlateRepository
    val coroutineScope = rememberCoroutineScope()

    val knownPlates by knownPlateRepo.getAllKnownPlates().collectAsState(initial = emptyList())

    var showAddDialog by remember { mutableStateOf(false) }

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
                text = "Placas Cadastradas",
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground
            )

            IconButton(onClick = { showAddDialog = true }) {
                Icon(imageVector = Icons.Default.Add, contentDescription = "Adicionar Placa", tint = MaterialTheme.colorScheme.primary)
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))

        if (knownPlates.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(text = "Nenhuma placa cadastrada.", color = Color.Gray)
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(knownPlates) { plate ->
                    KnownPlateItem(plate, onDelete = {
                        coroutineScope.launch { knownPlateRepo.deleteKnownPlate(plate) }
                    })
                }
            }
        }
    }

    if (showAddDialog) {
        var plateInput by remember { mutableStateOf("") }
        var isRegularizedInput by remember { mutableStateOf(true) }

        AlertDialog(
            onDismissRequest = { showAddDialog = false },
            title = { Text("Cadastrar Placa") },
            text = {
                Column {
                    OutlinedTextField(
                        value = plateInput,
                        onValueChange = { plateInput = it.uppercase() },
                        label = { Text("Placa (Ex: ABC1234)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "Placa Regularizada",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Switch(
                            checked = isRegularizedInput,
                            onCheckedChange = { isRegularizedInput = it }
                        )
                    }
                }
            },
            confirmButton = {
                Button(onClick = {
                    if (plateInput.isNotBlank()) {
                        coroutineScope.launch {
                            knownPlateRepo.insertKnownPlate(
                                KnownPlateEntity(plateText = plateInput, isRegularized = isRegularizedInput)
                            )
                        }
                        showAddDialog = false
                    }
                }) {
                    Text("Salvar")
                }
            },
            dismissButton = {
                TextButton(onClick = { showAddDialog = false }) {
                    Text("Cancelar")
                }
            }
        )
    }
}

@Composable
fun KnownPlateItem(plate: KnownPlateEntity, onDelete: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = plate.plateText,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                val statusText = if (plate.isRegularized) "✅ Regularizada" else "❌ Não Regularizada"
                val statusColor = if (plate.isRegularized) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error
                Text(
                    text = statusText,
                    fontSize = 14.sp,
                    color = statusColor,
                    fontWeight = FontWeight.Medium
                )
            }
            
            IconButton(onClick = onDelete) {
                Icon(imageVector = Icons.Default.Delete, contentDescription = "Deletar", tint = MaterialTheme.colorScheme.error)
            }
        }
    }
}
