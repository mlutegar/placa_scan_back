package com.example.placascan.ui.camera

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Camera
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.placascan.domain.ocr.MLKitTextRecognizer
import com.example.placascan.domain.yolo.TFLitePlateDetector
import kotlinx.coroutines.launch
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer

@Composable
fun CameraScreen() {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var recognizedText by remember { mutableStateOf("") }
    var isProcessing by remember { mutableStateOf(false) }
    
    // Lista de detecções para o overlay
    var detections by remember { mutableStateOf(emptyList<TFLitePlateDetector.Detection>()) }

    val mlKitTextRecognizer = remember { MLKitTextRecognizer() }
    val plateDetector = remember { TFLitePlateDetector(context) }
    val openCVProcessor = remember { com.example.placascan.domain.ocr.OpenCVImageProcessor() }

    val application = context.applicationContext as com.example.placascan.PlacaScanApplication
    val detectionRepo = application.detectionRepository
    val knownPlateRepo = application.knownPlateRepository

    DisposableEffect(Unit) {
        onDispose { plateDetector.close() }
    }

    fun takePicture() {
        val capture = imageCapture ?: return
        isProcessing = true
        recognizedText = "Processando..."

        val bestDetection = detections.maxByOrNull { it.confidence }

        capture.takePicture(
            ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val fullBitmap = imageProxyToBitmap(image)
                    image.close()

                    coroutineScope.launch {
                        var finalBitmap = fullBitmap
                        var croppedPlateBitmap: Bitmap? = null
                        
                        if (bestDetection != null) {
                            val w = fullBitmap.width.toFloat()
                            val h = fullBitmap.height.toFloat()
                            
                            val xMin = bestDetection.relXMin * w
                            val yMin = bestDetection.relYMin * h
                            val xMax = bestDetection.relXMax * w
                            val yMax = bestDetection.relYMax * h
                            
                            val cropped = openCVProcessor.cropPlate(fullBitmap, xMin, yMin, xMax, yMax, padding = 15)
                            if (cropped != null) {
                                croppedPlateBitmap = cropped
                                finalBitmap = openCVProcessor.processPlateImage(cropped)
                            }
                        }

                        val text = mlKitTextRecognizer.recognizeText(finalBitmap)
                        val validation = com.example.placascan.domain.ocr.PlateValidator.validate(text)
                        
                        if (validation.isValid) {
                            // Verifica se é uma placa conhecida (Fuzzy Matcher)
                            val knownPlates = knownPlateRepo.getKnownPlatesList()
                            val plateTexts = knownPlates.map { it.plateText }
                            val bestMatchPair = com.example.placascan.domain.matcher.LevenshteinMatcher.bestMatch(validation.plate, plateTexts)
                            
                            val bestMatchEntity = if (bestMatchPair != null) knownPlates[bestMatchPair.first] else null
                            val isKnown = bestMatchEntity != null
                            val statusText = if (isKnown) "✅ ${bestMatchEntity?.ownerName}" else "⚠️ Desconhecido"
                            
                            recognizedText = "${validation.plate} - $statusText"

                            // Salva imagem no armazenamento
                            var imagePath: String? = null
                            if (croppedPlateBitmap != null) {
                                imagePath = com.example.placascan.utils.ImageStorageHelper.saveBitmapToInternalStorage(context, croppedPlateBitmap)
                            }

                            // Salva no banco de dados (Histórico)
                            val entity = com.example.placascan.data.local.entities.PlateDetectionEntity(
                                plateText = validation.plate,
                                plateType = validation.type.name,
                                imagePath = imagePath,
                                isKnown = isKnown,
                                ownerName = bestMatchEntity?.ownerName,
                                timestamp = System.currentTimeMillis()
                            )
                            detectionRepo.insertDetection(entity)

                        } else {
                            recognizedText = if (text.isBlank()) "Nenhuma placa lida" else "Inválido: $text"
                        }
                        
                        isProcessing = false
                    }
                }

                override fun onError(exception: ImageCaptureException) {
                    Log.e("CameraScreen", "Erro ao capturar imagem: ${exception.message}", exception)
                    recognizedText = "Erro na captura"
                    isProcessing = false
                }
            }
        )
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        if (hasCameraPermission) {
            CameraPreview(
                modifier = Modifier.fillMaxSize(),
                onImageCaptureReady = { capture -> imageCapture = capture },
                onFrameAnalyzed = { bitmap ->
                    // Analisar o frame com o YOLOv8
                    detections = plateDetector.detect(bitmap, confidenceThreshold = 0.5f)
                }
            )
            
            // Desenhar bounding boxes por cima
            GraphicOverlay(detections = detections)

            // Overlay de informações no topo
            Column(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 24.dp, start = 16.dp, end = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color.Black.copy(alpha = 0.6f)
                    )
                ) {
                    Text(
                        text = if (detections.isNotEmpty()) "✅ Placa Detectada!" else "🔍 Aponte para uma placa",
                        color = if (detections.isNotEmpty()) Color.Green else Color.White,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                    )
                }

                if (recognizedText.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    ) {
                        Text(
                            text = recognizedText,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 24.dp, vertical = 12.dp)
                        )
                    }
                }
            }

            // Botão de captura manual
            FloatingActionButton(
                onClick = { if (!isProcessing) takePicture() },
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 48.dp)
                    .size(72.dp),
                shape = CircleShape,
                containerColor = if (isProcessing) Color.Gray else MaterialTheme.colorScheme.primary
            ) {
                Icon(
                    imageVector = Icons.Default.Camera,
                    contentDescription = "Capturar placa",
                    tint = Color.White,
                    modifier = Modifier.size(32.dp)
                )
            }

        } else {
            // Estado de permissão negada
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Text(text = "📷", fontSize = 64.sp)
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "Permissão de Câmera Necessária",
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "O PlacaScan precisa da câmera para detectar placas veiculares.",
                    color = Color.White.copy(alpha = 0.7f),
                    fontSize = 14.sp
                )
                Spacer(modifier = Modifier.height(24.dp))
                Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                    Text("Conceder Permissão")
                }
            }
        }
    }
}

@Composable
fun CameraPreview(
    modifier: Modifier = Modifier,
    onImageCaptureReady: (ImageCapture) -> Unit,
    onFrameAnalyzed: (Bitmap) -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val previewView = remember { PreviewView(context) }
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()
    }

    LaunchedEffect(Unit) {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()

            val preview = Preview.Builder().build().also {
                it.surfaceProvider = previewView.surfaceProvider
            }

            val imageAnalysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                .build()
                
            imageAnalysis.setAnalyzer(ContextCompat.getMainExecutor(context)) { imageProxy ->
                val bitmap = imageProxyToBitmapYUV(imageProxy)
                onFrameAnalyzed(bitmap)
                imageProxy.close()
            }

            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageCapture,
                    imageAnalysis
                )
                onImageCaptureReady(imageCapture)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }, ContextCompat.getMainExecutor(context))
    }

    AndroidView(
        factory = { previewView },
        modifier = modifier
    )
}

/**
 * Converte um ImageProxy (JPEG nativo do ImageCapture) para Bitmap.
 */
private fun imageProxyToBitmap(image: ImageProxy): Bitmap {
    val buffer: ByteBuffer = image.planes[0].buffer
    val bytes = ByteArray(buffer.capacity())
    buffer.get(bytes)
    return BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
}

/**
 * Converte um ImageProxy (YUV_420_888 do ImageAnalysis) para Bitmap.
 */
private fun imageProxyToBitmapYUV(image: ImageProxy): Bitmap {
    val yBuffer = image.planes[0].buffer // Y
    val uBuffer = image.planes[1].buffer // U
    val vBuffer = image.planes[2].buffer // V

    val ySize = yBuffer.remaining()
    val uSize = uBuffer.remaining()
    val vSize = vBuffer.remaining()

    val nv21 = ByteArray(ySize + uSize + vSize)

    yBuffer.get(nv21, 0, ySize)
    vBuffer.get(nv21, ySize, vSize)
    uBuffer.get(nv21, ySize + vSize, uSize)

    val yuvImage = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
    val out = ByteArrayOutputStream()
    yuvImage.compressToJpeg(Rect(0, 0, yuvImage.width, yuvImage.height), 100, out)
    val imageBytes = out.toByteArray()
    
    return BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
}
