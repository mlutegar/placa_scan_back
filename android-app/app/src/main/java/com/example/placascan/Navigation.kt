package com.example.placascan

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import com.example.placascan.ui.camera.CameraScreen
import com.example.placascan.ui.history.HistoryScreen
import com.example.placascan.ui.knownplates.KnownPlatesScreen

/**
 * Navegação principal com barra de abas (Bottom Navigation).
 * Substitui as rotas e templates web (webcam, histórico, placas) do projeto Django.
 *
 * 3 abas:
 *  1. Câmera — detecção em tempo real (CameraX + YOLO + OCR)
 *  2. Histórico — lista de detecções salvas no Room
 *  3. Placas — CRUD de placas conhecidas no Room
 */
@Composable
fun MainNavigation() {
    var selectedTab by remember { mutableIntStateOf(0) }

    val tabs = listOf(
        BottomTab("Câmera", Icons.Default.CameraAlt),
        BottomTab("Histórico", Icons.Default.History),
        BottomTab("Placas", Icons.Default.DirectionsCar)
    )

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { index, tab ->
                    NavigationBarItem(
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                        selected = selectedTab == index,
                        onClick = { selectedTab = index }
                    )
                }
            }
        },
        modifier = Modifier.fillMaxSize()
    ) { innerPadding ->
        when (selectedTab) {
            0 -> CameraScreen()
            1 -> HistoryScreen(modifier = Modifier.padding(innerPadding))
            2 -> KnownPlatesScreen(modifier = Modifier.padding(innerPadding))
        }
    }
}

private data class BottomTab(val label: String, val icon: ImageVector)
