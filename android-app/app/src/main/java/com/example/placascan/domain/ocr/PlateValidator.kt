package com.example.placascan.domain.ocr

/**
 * Validador de formato de placas brasileiras.
 */
object PlateValidator {
    
    // Padrão antigo: 3 letras e 4 números (ex: ABC1234)
    private val regexAntigo = "^[A-Z]{3}[0-9]{4}$".toRegex()
    
    // Padrão Mercosul: 3 letras, 1 número, 1 letra, 2 números (ex: ABC1D23)
    private val regexMercosul = "^[A-Z]{3}[0-9][A-Z][0-9]{2}$".toRegex()

    enum class PlateType {
        ANTIGA,
        MERCOSUL,
        INVALIDA
    }

    data class ValidationResult(
        val isValid: Boolean,
        val plate: String,
        val type: PlateType
    )

    /**
     * Limpa o texto bruto extraído pelo OCR e verifica se corresponde a uma placa válida.
     */
    fun validate(rawText: String): ValidationResult {
        // Limpa espaços, traços e converte para maiúsculo
        val cleanText = rawText.replace("[^A-Z0-9]".toRegex(RegexOption.IGNORE_CASE), "").uppercase()

        // Ajustes comuns de OCR (ex: '0' lido como 'O', '1' lido como 'I')
        // Em um sistema real mais robusto, aplicaríamos isso apenas nas posições onde sabemos
        // que deve haver número ou letra.
        
        return when {
            cleanText.matches(regexMercosul) -> ValidationResult(true, cleanText, PlateType.MERCOSUL)
            cleanText.matches(regexAntigo) -> ValidationResult(true, cleanText, PlateType.ANTIGA)
            else -> ValidationResult(false, cleanText, PlateType.INVALIDA)
        }
    }
}
