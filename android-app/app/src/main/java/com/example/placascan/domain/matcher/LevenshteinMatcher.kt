package com.example.placascan.domain.matcher

/**
 * Implementação de busca aproximada (fuzzy matching) por distância de edição (Levenshtein).
 *
 * Substitui a biblioteca thefuzz (Python) que usava fuzz.ratio() para comparar placas.
 * Migrado da lógica de views.py (linhas 91-120) e do fluxo process_frame (linhas 280-326).
 *
 * O limiar padrão de similaridade é 60% (equivalente a SIMILARITY_THRESHOLD = 60 no Python).
 */
object LevenshteinMatcher {

    /**
     * Calcula a similaridade entre duas strings no intervalo [0, 100].
     * Equivalente ao fuzz.ratio() da biblioteca thefuzz em Python.
     *
     * @param s1 Primeira string (ex: texto OCR da placa)
     * @param s2 Segunda string (ex: placa conhecida no banco)
     * @return Score de similaridade de 0 a 100
     */
    fun ratio(s1: String, s2: String): Int {
        if (s1.isEmpty() && s2.isEmpty()) return 100
        if (s1.isEmpty() || s2.isEmpty()) return 0

        val distance = levenshteinDistance(s1, s2)
        val maxLen = maxOf(s1.length, s2.length)
        return ((1.0 - distance.toDouble() / maxLen) * 100).toInt()
    }

    /**
     * Encontra a melhor correspondência em uma lista de strings candidatas.
     *
     * @param query Texto a ser buscado (ex: placa lida pelo OCR)
     * @param candidates Lista de strings candidatas (ex: placas conhecidas)
     * @param threshold Limiar mínimo de similaridade (0-100), padrão 60
     * @return Par (índice da melhor correspondência, score), ou null se nenhuma atingir o limiar
     */
    fun bestMatch(
        query: String,
        candidates: List<String>,
        threshold: Int = 60
    ): Pair<Int, Int>? {
        var bestIndex = -1
        var bestScore = 0

        candidates.forEachIndexed { index, candidate ->
            val score = ratio(query, candidate)
            if (score > bestScore) {
                bestScore = score
                bestIndex = index
            }
        }

        return if (bestIndex >= 0 && bestScore >= threshold) {
            Pair(bestIndex, bestScore)
        } else {
            null
        }
    }

    /**
     * Calcula a distância de edição de Levenshtein entre duas strings.
     * Algoritmo clássico de programação dinâmica (DP).
     */
    private fun levenshteinDistance(s1: String, s2: String): Int {
        val m = s1.length
        val n = s2.length
        val dp = Array(m + 1) { IntArray(n + 1) }

        for (i in 0..m) dp[i][0] = i
        for (j in 0..n) dp[0][j] = j

        for (i in 1..m) {
            for (j in 1..n) {
                dp[i][j] = if (s1[i - 1] == s2[j - 1]) {
                    dp[i - 1][j - 1]
                } else {
                    1 + minOf(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
                }
            }
        }
        return dp[m][n]
    }
}
