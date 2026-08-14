package com.example.placascan.domain.ocr

import com.google.mlkit.vision.text.Text

/**
 * Extrai a confiança do OCR para uma placa validada.
 *
 * A métrica é o MÍNIMO das confianças dos caracteres da placa: uma placa passa
 * num limiar t se e somente se todos os caracteres têm confiança >= t, o que
 * equivale a min >= t. A média mascararia um caractere ruim.
 */
object OcrConfidence {

    /**
     * Procura a linha do resultado do OCR cujo texto limpo corresponde à placa
     * validada e devolve a menor confiança entre seus caracteres.
     *
     * Fallbacks, nesta ordem: mínimo dos símbolos (por caractere) → mínimo dos
     * elementos da linha → confiança da linha. Retorna null se a placa não for
     * localizada no resultado — nesse caso o campo deve ser omitido do payload,
     * nunca estimado.
     */
    fun minCharConfidence(result: Text?, plate: String): Float? {
        result ?: return null
        for (block in result.textBlocks) {
            for (line in block.lines) {
                val clean = line.text.replace(Regex("[^A-Za-z0-9]"), "").uppercase()
                if (clean != plate) continue

                val symbols = line.elements
                    .flatMap { it.symbols }
                    .filter { it.text.length == 1 && it.text[0].isLetterOrDigit() }
                if (symbols.size == plate.length) {
                    return symbols.minOf { it.confidence }
                }
                if (line.elements.isNotEmpty()) {
                    return line.elements.minOf { it.confidence }
                }
                return line.confidence
            }
        }
        return null
    }
}
