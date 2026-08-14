package com.example.placascan.data.mqtt

import android.annotation.SuppressLint
import android.content.Context
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import com.hivemq.client.mqtt.MqttClient
import com.hivemq.client.mqtt.datatypes.MqttQos
import com.hivemq.client.mqtt.mqtt3.Mqtt3AsyncClient
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.CompletableFuture

/**
 * Publica detecções de placa no broker MQTT em modo fire-and-forget: nenhuma
 * falha de rede ou de broker se propaga para o fluxo de detecção/OCR.
 *
 * Publica UMA mensagem por placa reconhecida (nunca por frame), com QoS 1,
 * e loga no logcat (tag [TAG]) o tamanho do payload em bytes e a latência
 * entre o fim do reconhecimento e a confirmação (PUBACK) do broker.
 */
class MqttPublisher(private val context: Context) {

    companion object {
        private const val TAG = "MqttTelemetry"
    }

    @SuppressLint("HardwareIds")
    private val deviceId: String =
        Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"

    private val client: Mqtt3AsyncClient by lazy {
        MqttClient.builder()
            .useMqttVersion3()
            .identifier("placascan-$deviceId")
            .serverHost(MqttConfig.host(context))
            .serverPort(MqttConfig.port(context))
            .automaticReconnectWithDefaultConfig()
            .buildAsync()
    }

    /**
     * Monta o payload e publica. Chamado uma única vez por placa validada.
     *
     * @param plate placa validada (ex.: "ABC1B34")
     * @param fmt formato da placa ("mercosur" ou "antiga")
     * @param ocrConf menor confiança entre os caracteres (ML Kit); null = omitido
     * @param detConf confiança da detecção YOLO; null = omitido
     * @param recognitionEndMs SystemClock.elapsedRealtime() no fim do reconhecimento
     */
    fun publishDetection(
        plate: String,
        fmt: String,
        ocrConf: Float?,
        detConf: Float?,
        recognitionEndMs: Long
    ) {
        try {
            val json = JSONObject().apply {
                put("dev", deviceId)
                put("ts", isoUtcNow())
                put("plate", plate)
                if (ocrConf != null) put("conf", ocrConf.toDouble()) else
                    Log.w(TAG, "ML Kit não retornou confiança para $plate; campo 'conf' omitido")
                if (detConf != null) put("det_conf", detConf.toDouble())
                put("fmt", fmt)
            }
            val payload = json.toString().toByteArray(Charsets.UTF_8)
            val topic = MqttConfig.topic(context)
            Log.i(TAG, "Publicando em $topic: ${payload.size} bytes")

            ensureConnected()
                .thenCompose {
                    client.publishWith()
                        .topic(topic)
                        .qos(MqttQos.AT_LEAST_ONCE)
                        .payload(payload)
                        .send()
                }
                .whenComplete { _, error ->
                    if (error != null) {
                        Log.w(TAG, "Falha ao publicar (detecção não afetada): ${error.message}")
                    } else {
                        val latencyMs = SystemClock.elapsedRealtime() - recognitionEndMs
                        Log.i(
                            TAG,
                            "PUBACK recebido: payload=${payload.size} bytes, " +
                                "latência reconhecimento→PUBACK=${latencyMs} ms"
                        )
                    }
                }
        } catch (t: Throwable) {
            Log.w(TAG, "Erro no MQTT (detecção não afetada): ${t.message}")
        }
    }

    private fun ensureConnected(): CompletableFuture<*> =
        if (client.state.isConnected) {
            CompletableFuture.completedFuture(null)
        } else {
            // Se já houver conexão em andamento, o future falha e o publish é
            // descartado com log; a próxima detecção tenta de novo.
            client.connect()
        }

    private fun isoUtcNow(): String {
        val fmt = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
        fmt.timeZone = TimeZone.getTimeZone("UTC")
        return fmt.format(Date())
    }
}
