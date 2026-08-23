# Projeto LPR Android — Benchmark de Pré-processamento

## Contexto do projeto

App Android nativo de reconhecimento de placas brasileiras (LPR) que roda **100% offline**.
Faz parte de uma pesquisa acadêmica. Já temos um paper publicado (CBIC2025) que comparou
8 métodos de pré-processamento usando Tesseract OCR no desktop. Agora estamos escrevendo
um segundo paper (WVC2026) que valida o pipeline **on-device** usando ML Kit no Android.

A tarefa principal é: rodar as mesmas 65 imagens de placa pelos mesmos 8 métodos de
pré-processamento, mas agora com ML Kit Text Recognition como motor de OCR, e coletar
os resultados num CSV para comparar com os dados do Tesseract do paper anterior.

## Stack do app

- **Linguagem:** Kotlin
- **UI:** Jetpack Compose (MVVM)
- **Câmera:** CameraX
- **Processamento de imagem:** OpenCV Android SDK
- **Detecção de placa:** YOLOv8 exportado para TensorFlow Lite
- **OCR:** ML Kit Text Recognition (bundled/offline)
- **Banco local:** Room (SQLite)
- **Min API:** 24 (Android 7.0)

## O que precisa ser implementado

### 1. Pasta de imagens de teste

As 65 imagens de placa (já cropadas/detectadas pelo YOLO) devem ficar em:
```
app/src/main/assets/test_plates/
```

Cada imagem é nomeada com o ground truth da placa como nome do arquivo.
Exemplos: `ABC1D23.jpg`, `XYZ4567.png`, `DEF2G45.jpg`

O nome do arquivo (sem extensão) = texto correto da placa (ground truth).
Formatos aceitos: .jpg, .jpeg, .png

### 2. Módulo de Benchmark (BenchmarkActivity ou BenchmarkScreen)

Criar uma tela acessível na UI (pode ser um botão na tela principal) que executa
o benchmark completo automaticamente.

#### Fluxo:

1. Listar todas as imagens em `assets/test_plates/`
2. Para cada imagem:
   - Decodificar o bitmap
   - Extrair ground truth do nome do arquivo (sem extensão, uppercase)
   - Para cada método de pré-processamento (8 métodos):
     - Para cada threshold (0.0, 0.2, 0.4, 0.6, 0.8):
       - Aplicar o pré-processamento via OpenCV
       - Rodar ML Kit Text Recognition no bitmap processado
       - Limpar output do OCR (só alfanumérico, uppercase)
       - Calcular full_match (boolean: output == ground_truth)
       - Calcular char_accuracy (float: caracteres corretos / total de caracteres do ground truth)
       - Salvar resultado na lista
3. Exportar todos os resultados como CSV

#### Total esperado: 65 imagens × 8 métodos × 5 thresholds = 2.600 tentativas de OCR

### 3. Os 8 métodos de pré-processamento

Todos usam OpenCV Android. O parâmetro `threshold` é o confidence threshold
do OCR (filtro pós-OCR), NÃO um parâmetro do pré-processamento em si.
O threshold filtra resultados: se a confiança do OCR for menor que o threshold,
o resultado é descartado (retorna string vazia).

```
1. original    → sem modificação, usa a imagem como está
2. grayscale   → Imgproc.cvtColor(mat, gray, Imgproc.COLOR_BGR2GRAY)
3. inverted    → grayscale + Core.bitwise_not(gray, inv)
4. adaptive    → grayscale + Imgproc.adaptiveThreshold(gray, dst, 255.0,
                  Imgproc.ADAPTIVE_THRESH_MEAN_C, Imgproc.THRESH_BINARY, 11, 2.0)
5. bilateral   → Imgproc.bilateralFilter(mat, dst, 9, 75.0, 75.0)
6. otsu        → grayscale + Imgproc.threshold(gray, dst, 0.0, 255.0,
                  Imgproc.THRESH_BINARY + Imgproc.THRESH_OTSU)
7. resized2x   → Imgproc.resize(mat, dst, Size(mat.width()*2.0, mat.height()*2.0),
                  0.0, 0.0, Imgproc.INTER_CUBIC)
8. sharpened   → kernel de sharpening via Imgproc.filter2D
                  kernel: [0, -1, 0, -1, 5, -1, 0, -1, 0]
```

### 4. ML Kit OCR

Usar ML Kit Text Recognition com o modelo bundled (offline).
Dependência: `com.google.mlkit:text-recognition:16.0.0` (ou versão mais recente)

```kotlin
val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
val inputImage = InputImage.fromBitmap(bitmap, 0)

recognizer.process(inputImage)
    .addOnSuccessListener { result ->
        val rawText = result.text
        // Limpar: só alfanumérico, uppercase
        val cleaned = rawText.replace(Regex("[^A-Za-z0-9]"), "").uppercase()
        // Se ML Kit retorna confidence por bloco/linha, usar para filtrar pelo threshold
    }
```

**Sobre confidence do ML Kit:**
ML Kit Text Recognition v2 retorna confidence por TextBlock e TextLine.
Se disponível, usar a confidence da linha que contém o texto da placa.
Se a confidence < threshold configurado, descartar o resultado (retornar "").
Se confidence não estiver disponível na versão usada, aplicar threshold = 0.0
para todos (sem filtro) e documentar isso.

### 5. Cálculo de acurácia

```kotlin
fun calculateCharAccuracy(ocrOutput: String, groundTruth: String): Float {
    if (groundTruth.isEmpty()) return 0f
    var matches = 0
    for (i in 0 until minOf(ocrOutput.length, groundTruth.length)) {
        if (ocrOutput[i] == groundTruth[i]) matches++
    }
    return matches.toFloat() / groundTruth.length.toFloat()
}

fun isFullMatch(ocrOutput: String, groundTruth: String): Boolean {
    return ocrOutput.equals(groundTruth, ignoreCase = true)
}
```

### 6. Formato do CSV de saída

Salvar em: `getExternalFilesDir(null)/benchmark_results.csv`

Colunas:
```
plate,method,threshold,ocr_output,ocr_confidence,full_match,char_accuracy
ABC1D23,inverted,0.4,ABC1D23,0.92,true,1.0
XYZ4567,grayscale,0.2,XYZ4S67,0.71,false,0.857
```

### 7. UI do Benchmark

- Botão "Rodar Benchmark" na tela principal ou tela separada
- Progress bar mostrando: "Processando imagem X/65 | Método: inverted | Threshold: 0.4"
- Ao terminar: mostrar resumo (total processado, acurácia média, melhor método)
- Botão "Exportar CSV" ou exportar automaticamente ao terminar
- Lançar o processamento em coroutine (Dispatchers.Default) para não travar a UI

## Restrições

- **NÃO** usar internet. Tudo offline.
- **NÃO** usar Tesseract. Apenas ML Kit Text Recognition.
- **NÃO** incluir a etapa de detecção YOLO no benchmark. As imagens já estão cropadas.
  O benchmark testa apenas: pré-processamento → OCR → comparação.
- Manter compatibilidade com API 24+.
- Tratar erros graciosamente (imagem corrompida, OCR falha, etc). Logar erro e continuar.

## Estrutura esperada de arquivos novos

```
app/src/main/
├── assets/
│   └── test_plates/          ← 65 imagens de placa (eu coloco manualmente)
├── java/.../
│   ├── benchmark/
│   │   ├── BenchmarkActivity.kt (ou BenchmarkScreen.kt se Compose)
│   │   ├── BenchmarkViewModel.kt
│   │   ├── PreprocessingEngine.kt    ← os 8 métodos
│   │   ├── OCREngine.kt             ← wrapper do ML Kit
│   │   ├── AccuracyCalculator.kt    ← char_accuracy + full_match
│   │   └── CSVExporter.kt           ← salvar resultados
```

## Comandos úteis

- Build: `./gradlew assembleDebug`
- Rodar testes: `./gradlew test`
- Instalar no emulador: `./gradlew installDebug`
