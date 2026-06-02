package com.example.placascan.domain.validator

import java.util.regex.Pattern

/**
 * Valida e formata textos de placas veiculares brasileiras.
 *
 * Migrado diretamente da função validate_plate_text() em:
 * backend/services/plate_detector.py (linhas 453-481)
 *
 * Padrões suportados:
 * - Antigo: ABC-1234 → regex: ^[A-Z]{3}[0-9]{4}$
 * - Mercosul: ABC1D23 → regex: ^[A-Z]{3}[0-9][A-Z][0-9]{2}$
 */
object PlateValidator {

    private val OLD_PATTERN = Pattern.compile("^[A-Z]{3}[0-9]{4}$")
    private val MERCOSUL_PATTERN = Pattern.compile("^[A-Z]{3}[0-9][A-Z][0-9]{2}$")

    enum class PlateType { OLD, MERCOSUL, UNKNOWN }

    data class ValidationResult(
        val isValid: Boolean,
        val cleanText: String,
        val formattedText: String,
        val plateType: PlateType
    )

    /**
     * Valida se o texto lido pelo OCR corresponde a uma placa brasileira válida.
     *
     * @param rawText Texto bruto do OCR
     * @return ValidationResult com status, texto limpo, formatado e tipo de placa
     */
    fun validate(rawText: String): ValidationResult {
        // Remove espaços e caracteres não alfanuméricos, converte para maiúsculas
        // Equivalente ao: re.sub(r'[^A-Z0-9]', '', text.upper()) do Python
        val cleanText = rawText.uppercase().replace(Regex("[^A-Z0-9]"), "")

        return when {
            OLD_PATTERN.matcher(cleanText).matches() -> {
                // Formato: ABC-1234
                val formatted = "${cleanText.substring(0, 3)}-${cleanText.substring(3)}"
                ValidationResult(true, cleanText, formatted, PlateType.OLD)
            }
            MERCOSUL_PATTERN.matcher(cleanText).matches() -> {
                // Formato: ABC1D23 (sem traço no padrão Mercosul)
                ValidationResult(true, cleanText, cleanText, PlateType.MERCOSUL)
            }
            else -> {
                ValidationResult(false, cleanText, cleanText, PlateType.UNKNOWN)
            }
        }
    }
}
