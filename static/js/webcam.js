// Elementos DOM
const videoFeed = document.getElementById('videoFeed');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');
const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const cameraIdInput = document.getElementById('cameraId');
const statusPanel = document.getElementById('statusPanel');
const statusText = document.getElementById('statusText');
const detectionToggle = document.getElementById('detectionToggle');
const platesList = document.getElementById('platesList');

// Elementos de estatísticas
const totalPlatesEl = document.getElementById('totalPlates');
const validPlatesEl = document.getElementById('validPlates');
const avgConfidenceEl = document.getElementById('avgConfidence');
const detectionRateEl = document.getElementById('detectionRate');

// Configurações WebSocket
const socketUrl = `ws://${window.location.hostname}:8000/ws/video-stream/`;
let socket;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// Variáveis de controle
let detectionEnabled = true;
let detectedPlates = []; // Mantém as placas para exibição na UI
let startTime = Date.now();
let isSavingFrame = false; // Flag para controlar o envio de frames para salvamento
const SAVE_FRAME_INTERVAL = 5000; // Salvar no máximo um frame a cada 5 segundos
let lastSaveTime = 0;

// Atualizar status
function updateStatus(message, type = 'info') {
    statusText.textContent = message;
    statusPanel.className = `status-panel ${type}`;
    console.log(`[${type.toUpperCase()}] ${message}`);
}

// Conectar WebSocket
function connectWebSocket() {
    updateStatus("Conectando ao WebSocket...");
    loadingText.textContent = "Conectando...";

    socket = new WebSocket(socketUrl);

    socket.onopen = function (e) {
        updateStatus("✅ WebSocket conectado com sucesso!", 'success');
        startButton.disabled = false;
        reconnectAttempts = 0;
    };

    socket.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('Erro ao processar mensagem:', e);
        }
    };

    socket.onclose = function (event) {
        startButton.disabled = true;
        stopButton.disabled = true;
        videoFeed.style.display = 'none';
        loadingOverlay.style.display = 'flex';

        if (event.wasClean) {
            updateStatus(`🔌 Conexão fechada (código: ${event.code})`);
            loadingText.textContent = 'Desconectado';
        } else {
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                updateStatus(`❌ Conexão perdida. Tentativa ${reconnectAttempts}/${maxReconnectAttempts} em 3s...`, 'error');
                loadingText.textContent = 'Reconectando...';
                setTimeout(connectWebSocket, 3000);
            } else {
                updateStatus('❌ Não foi possível reconectar. Recarregue a página.', 'error');
                loadingText.textContent = 'Erro de conexão';
            }
        }
    };

    socket.onerror = function (error) {
        updateStatus('📛 Erro no WebSocket', 'error');
        console.error('WebSocket error:', error);
    };
}

// ++ ADICIONAR: Função para converter base64 para Blob ++
function base64ToBlob(base64, contentType = '', sliceSize = 512) {
    const byteCharacters = atob(base64);
    const byteArrays = [];

    for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
        const slice = byteCharacters.slice(offset, offset + sliceSize);
        const byteNumbers = new Array(slice.length);
        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }

    return new Blob(byteArrays, {type: contentType});
}

// ++ ADICIONAR: Função para obter o cookie CSRF ++
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// ++ ADICIONAR: Função para enviar o frame ao backend para salvamento ++
async function saveFrameToServer(frameBase64) {
    if (isSavingFrame) {
        // console.log("Salvamento de frame já em progresso.");
        return;
    }
    const now = Date.now();
    if (now - lastSaveTime < SAVE_FRAME_INTERVAL) {
        // console.log("Intervalo mínimo entre salvamentos não atingido.");
        return;
    }

    isSavingFrame = true;
    lastSaveTime = now;
    updateStatus("📡 Enviando frame para salvamento...", 'info');

    try {
        const imageBlob = base64ToBlob(frameBase64, 'image/jpeg');
        const formData = new FormData();
        const timestamp = new Date().toISOString();
        formData.append('original_image', imageBlob, `frame_${timestamp}.jpg`);

        const csrfToken = getCookie('csrftoken');

        const response = await fetch('/api/detections/detect_plates/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                // 'Content-Type': 'multipart/form-data' é definido automaticamente pelo navegador para FormData
            },
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            console.log('Frame salvo com sucesso. Detecção ID:', result.id, 'Placas:', result.plates);
            updateStatus(`🖼️ Frame salvo (ID: ${result.id}), ${result.plates ? result.plates.length : 0} placa(s) processada(s).`, 'success');

            fetchPlatesFromDB();
        } else {
            const errorData = await response.json();
            console.error('Erro ao salvar frame:', response.status, errorData);
            updateStatus(`⚠️ Erro ao salvar frame: ${errorData.error || response.statusText}`, 'error');
        }
    } catch (error) {
        console.error('Erro na requisição fetch para salvar frame:', error);
        updateStatus(`📛 Erro de rede ao salvar frame.`, 'error');
    } finally {
        isSavingFrame = false;
    }
}

// Manipular mensagens WebSocket
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'frame':
            // Atualizar vídeo
            videoFeed.src = 'data:image/jpeg;base64,' + data.frame;
            if (videoFeed.style.display === 'none') {
                videoFeed.style.display = 'block';
                loadingOverlay.style.display = 'none';
            }

            if (detectionEnabled && data.frame && data.plates && data.plates.length > 0) {
                // Poderia haver uma lógica mais sofisticada aqui para decidir
                // quais frames salvar (ex: apenas se uma nova placa única aparecer,
                // ou com base na confiança, etc.)
                // Por ora, tentaremos salvar se houver placas.
                // A função saveFrameToServer() já tem um controle de taxa.
                saveFrameToServer(data.frame);
            }
            break;

        case 'camera_started':
            updateStatus(`✅ ${data.message}`, 'success');
            startButton.disabled = true;
            stopButton.disabled = false;
            startTime = Date.now();
            detectedPlates = []; // Limpa placas da UI
            updatePlatesList(); // Atualiza UI
            updateStatistics();
            lastSaveTime = 0; // Resetar o tempo do último salvamento
            break;

        case 'camera_stopped':
            updateStatus(`⏹️ ${data.message}`);
            startButton.disabled = false;
            stopButton.disabled = true;
            videoFeed.style.display = 'none';
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Câmera parada';
            clearPlatesList();
            break;

        case 'error':
            updateStatus(`❌ ${data.message}`, 'error');
            startButton.disabled = false;
            stopButton.disabled = true;
            break;

        case 'connection':
            updateStatus(`🔗 ${data.message}`, 'success');
            break;

        case 'plate_detector_ready':
            updateStatus(`🤖 ${data.message}`, 'success');
            break;

        case 'detection_toggled':
            detectionEnabled = data.enabled;
            updateDetectionToggle();
            break;
    }
}


// ++ NOVA FUNÇÃO: Buscar placas do banco de dados ++
async function fetchPlatesFromDB() {
    updateStatus("🔄 Carregando placas do banco de dados...", 'info');
    try {
        const response = await fetch('/api/detected-plates/'); // Endpoint criado na Parte 1
        if (!response.ok) {
            let errorMsg = `Erro HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.error || JSON.stringify(errorData);
            } catch (e) { /* ignore parsing error */
            }
            throw new Error(errorMsg);
        }
        const platesFromDB = await response.json();

        // Mapear os dados do backend para o formato que updatePlatesList espera
        detectedPlates = platesFromDB.map(plate => {
            const knownNum = plate.known_plate_number;
            // Prioriza plate_number_detected, depois best_ocr_text como a placa detectada.
            const detectedNum = plate.plate_number_detected || plate.best_ocr_text;

            let htmlFormattedPlateText;
            let simplePlateText; // Para uso em atributos 'alt' ou contextos não-HTML

            if (knownNum) {
                htmlFormattedPlateText = `<div><span class="plate-label">Placa Conhecida:</span> ${knownNum}</div>`;
                // Sempre mostrar a detectada se a conhecida estiver presente, para clareza.
                htmlFormattedPlateText += `<div><span class="plate-label">Placa Detectada:</span> ${detectedNum || "N/A"}</div>`;

                simplePlateText = `${knownNum}`;
                if (detectedNum && knownNum !== detectedNum) {
                    simplePlateText += ` (Detectada: ${detectedNum})`;
                } else if (!detectedNum) {
                    simplePlateText += ` (Detectada: N/A)`;
                }
            } else {
                htmlFormattedPlateText = `<div><span class="plate-label">Placa Detectada:</span> ${detectedNum || "N/A"}</div>`;
                simplePlateText = detectedNum || "N/A";
            }

            const isValid = !!plate.known_plate;

            return {
                id: plate.id,
                text: simplePlateText, // Texto simples para 'alt' e outros.
                formatted_text: htmlFormattedPlateText, // HTML formatado para exibição principal.
                confidence: plate.best_ocr_confidence !== null && plate.best_ocr_confidence !== undefined
                    ? plate.best_ocr_confidence * 100
                    : 0,
                yolo_confidence: plate.yolo_confidence !== null && plate.yolo_confidence !== undefined
                    ? plate.yolo_confidence * 100
                    : 0,
                timestamp: plate.detection_created_at
                    ? new Date(plate.detection_created_at).toLocaleString()
                    : 'N/A',
                is_valid: isValid,
                cropped_image_url: plate.cropped_image_url,
                raw_timestamp: plate.detection_created_at,
                known_plate_is_regularized: plate.known_plate_is_regularized // Mantém da alteração anterior
            };
        });

        updatePlatesList();
        updateStatistics(); // As estatísticas também devem se basear nas placas do banco
        updateStatus(`✅ ${detectedPlates.length} placas carregadas do banco.`, 'success');

    } catch (error) {
        console.error('Erro ao buscar placas do banco de dados:', error);
        updateStatus(`⚠️ Erro ao carregar placas: ${error.message}`, 'error');
        // Opcional: limpar a lista se o carregamento falhar
        // detectedPlates = [];
        // updatePlatesList();
        // updateStatistics();
    }
}

// Atualizar lista de placas
function updatePlatesList() {
    if (detectedPlates.length === 0) {
        platesList.innerHTML = `
            <div class="info-panel">
                <p>Nenhuma placa salva no banco de dados.</p>
                <p>Inicie a câmera para detectar e salvar novas placas.</p>
            </div>
        `;
        return;
    }

    platesList.innerHTML = detectedPlates.map(plate => {
        let regularizationDisplayHtml;
        // Verifica se a propriedade known_plate_is_regularized existe e é um booleano
        if (typeof plate.known_plate_is_regularized === 'boolean') {
            if (plate.known_plate_is_regularized) {
                regularizationDisplayHtml = `<span class="plate-status regularizada">✅ Regularizada</span>`;
            } else {
                regularizationDisplayHtml = `<span class="plate-status nao-regularizada">❌ Não Regularizada</span>`;
            }
        } else {
            // Caso a placa não seja conhecida ou o status de regularização não esteja disponível
            regularizationDisplayHtml = `<span class="plate-status status-desconhecido">❔ Status Desconhecido</span>`;
        }

        return `
        <div class="plate-item ${plate.is_valid ? '' : 'invalid'}">
            ${plate.cropped_image_url ? `
                <div class="plate-image-container">
                    <img src="${plate.cropped_image_url}" alt="Placa ${plate.text}" class="plate-thumbnail">
                </div>
            ` : ''}
            <div class="plate-info-details">
                <div class="plate-text">${plate.formatted_text || plate.text}</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${plate.confidence.toFixed(1)}%"></div>
                </div>
                <div class="plate-details">
                    ${regularizationDisplayHtml}
                    <span class="timestamp">${plate.timestamp}</span>
                </div>
                <div class="plate-details">
                    <span>OCR: ${plate.confidence.toFixed(1)}%</span>
                    <span>YOLO: ${plate.yolo_confidence.toFixed(1)}%</span>
                </div>
            </div>
        </div>`;
    }).join('');
}

// Limpar lista de placas
function clearPlatesList() {
    platesList.innerHTML = `  
        <div class="info-panel"> 
            <p>Nenhuma placa detectada ainda.</p> 
            <p>Inicie a câmera para começar a detecção.</p> 
        </div>  
    `;
}

// Atualizar estatísticas
function updateStatistics() {
    const total = detectedPlates.length;
    const valid = detectedPlates.filter(p => p.is_valid).length;
    const avgConf = total > 0 ?
        detectedPlates.reduce((sum, p) => sum + p.confidence, 0) / total : 0;

    const timeElapsed = (Date.now() - startTime) / 60000; // minutos
    const rate = timeElapsed > 0 ? (total / timeElapsed).toFixed(1) : 0;

    totalPlatesEl.textContent = total;
    validPlatesEl.textContent = valid;
    avgConfidenceEl.textContent = `${avgConf.toFixed(1)}%`;
    detectionRateEl.textContent = `${rate}/min`;
}

// Atualizar toggle de detecção
function updateDetectionToggle() {
    if (detectionEnabled) {
        detectionToggle.classList.add('active');
    } else {
        detectionToggle.classList.remove('active');
    }
}

// Event Listeners
startButton.onclick = function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
        const camId = parseInt(cameraIdInput.value, 10);
        const message = {
            command: 'start_camera',
            camera_id: camId,
            detection_enabled: detectionEnabled
        };
        socket.send(JSON.stringify(message));
        updateStatus(`📹 Tentando iniciar câmera ${camId}...`);
        loadingText.textContent = 'Iniciando câmera...';
        loadingOverlay.style.display = 'flex';
    } else {
        updateStatus("❌ WebSocket não está conectado", 'error');
    }
};

stopButton.onclick = function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({command: 'stop_camera'}));
        updateStatus("⏹️ Parando câmera...");
    } else {
        updateStatus("❌ WebSocket não está conectado", 'error');
    }
};

detectionToggle.onclick = function () {
    detectionEnabled = !detectionEnabled;
    updateDetectionToggle();

    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            command: 'toggle_detection',
            enabled: detectionEnabled
        }));
    }
};

// Inicializar
connectWebSocket();
updateDetectionToggle();
fetchPlatesFromDB();

// Limpar recursos ao sair da página
window.addEventListener('beforeunload', function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({command: 'stop_camera'}));
        socket.close();
    }
});