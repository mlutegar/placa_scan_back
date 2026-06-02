package com.example.placascan.ui.camera

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import com.example.placascan.domain.yolo.TFLitePlateDetector

/**
 * Overlay visual para desenhar as Bounding Boxes (caixas delimitadoras)
 * detectadas pelo YOLOv8 em tempo real sobre o feed da câmera.
 */
@Composable
fun GraphicOverlay(
    detections: List<TFLitePlateDetector.Detection>,
    modifier: Modifier = Modifier
) {
    Canvas(modifier = modifier.fillMaxSize()) {
        val canvasWidth = size.width
        val canvasHeight = size.height

        // Em uma implementação avançada, precisamos considerar a escala
        // entre a imagem original processada pelo modelo e o tamanho da tela.
        // O YOLO usa letterboxing 640x640, então temos que remapear.
        // Para simplificar na Versão 3, vamos assumir que as coordenadas 
        // já estão na escala da imagem original (bitmap) da câmera.

        for (detection in detections) {
            // As coordenadas de X e Y vêm da câmera (que pode ser 1080x1920, por exemplo).
            // Precisamos escalar para o tamanho da tela (canvasWidth x canvasHeight)
            // Assumindo câmera em modo retrato (1080x1920) mas a tela pode ter proporção diferente.
            // Aqui faremos um mapeamento direto considerando ScaleType FILL_CENTER.

            // FIXME: A escala real depende da proporção do PreviewView vs ImageProxy.
            // Usaremos mapeamento direto para simplificação.
            val boxWidth = detection.xMax - detection.xMin
            val boxHeight = detection.yMax - detection.yMin

            drawRect(
                color = Color.Green,
                topLeft = Offset(detection.xMin, detection.yMin),
                size = Size(boxWidth, boxHeight),
                style = Stroke(width = 8f) // Borda da caixa de 8px
            )
        }
    }
}
