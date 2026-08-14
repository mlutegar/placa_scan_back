package com.example.placascan.domain.ocr

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine

/**
 * Serviço de OCR offline usando o Google ML Kit Text Recognition.
 *
 * Migrado da funcionalidade original que usava Tesseract/EasyOCR no Django.
 * Operação 100% offline no Android, não requer Google Play Services se
 * usando o artefato 'com.google.mlkit:text-recognition' em vez da versão play-services.
 */
class MLKitTextRecognizer {

    // Instancia o reconhecedor configurado para textos com alfabeto latino
    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

    /**
     * Processa a imagem e extrai o texto lido.
     *
     * @param bitmap Imagem (idealmente já recortada na placa) a ser processada
     * @return O texto bruto identificado na imagem, ou uma string vazia se falhar/nada for lido
     */
    suspend fun recognizeText(bitmap: Bitmap): String = suspendCoroutine { continuation ->
        try {
            val image = InputImage.fromBitmap(bitmap, 0)
            recognizer.process(image)
                .addOnSuccessListener { result ->
                    continuation.resume(result.text)
                }
                .addOnFailureListener { e ->
                    e.printStackTrace()
                    continuation.resume("")
                }
        } catch (e: Exception) {
            e.printStackTrace()
            continuation.resume("")
        }
    }

    /**
     * Mesmo reconhecimento de [recognizeText], mas retorna o resultado estruturado
     * do ML Kit (blocos/linhas/elementos/símbolos com confiança), ou null se falhar.
     * O texto bruto equivalente é `result.text`.
     */
    suspend fun recognizeDetailed(bitmap: Bitmap): Text? = suspendCoroutine { continuation ->
        try {
            val image = InputImage.fromBitmap(bitmap, 0)
            recognizer.process(image)
                .addOnSuccessListener { result ->
                    continuation.resume(result)
                }
                .addOnFailureListener { e ->
                    e.printStackTrace()
                    continuation.resume(null)
                }
        } catch (e: Exception) {
            e.printStackTrace()
            continuation.resume(null)
        }
    }
}
