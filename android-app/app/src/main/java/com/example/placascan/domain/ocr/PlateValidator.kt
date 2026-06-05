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
        // Testa cada linha separadamente — OCR retorna várias linhas (ex: MERCOSUL, BRASIL, ABC1D23, BR)
        val lines = rawText.lines()
        for (line in lines) {
            val clean = line.replace("[^A-Z0-9]".toRegex(RegexOption.IGNORE_CASE), "").uppercase()
            when {
                clean.matches(regexMercosul) -> return ValidationResult(true, clean, PlateType.MERCOSUL)
                clean.matches(regexAntigo)   -> return ValidationResult(true, clean, PlateType.ANTIGA)
            }
        }
        val fullClean = rawText.replace("[^A-Z0-9]".toRegex(RegexOption.IGNORE_CASE), "").uppercase()
        return ValidationResult(false, fullClean, PlateType.INVALIDA)
    }
}
