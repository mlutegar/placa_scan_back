package com.example.placascan.data.mqtt

import android.content.Context

/**
 * Configuração do broker MQTT. Os valores padrão apontam para o broker público
 * de testes; podem ser sobrescritos via SharedPreferences ("mqtt_config"),
 * permitindo trocar de broker sem recompilar.
 */
object MqttConfig {

    const val DEFAULT_HOST = "test.mosquitto.org"
    const val DEFAULT_PORT = 1883
    const val DEFAULT_TOPIC = "ibmec/alpr/x7k2m9/detections"

    private const val PREFS_NAME = "mqtt_config"

    fun host(context: Context): String =
        prefs(context).getString("host", DEFAULT_HOST) ?: DEFAULT_HOST

    fun port(context: Context): Int =
        prefs(context).getInt("port", DEFAULT_PORT)

    fun topic(context: Context): String =
        prefs(context).getString("topic", DEFAULT_TOPIC) ?: DEFAULT_TOPIC

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
}
