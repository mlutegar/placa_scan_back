// Elementos DOM
const videoFeed = document.getElementById('videoFeed');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');
// ++ ADICIONAR: Referências para os novos botões e elementos de UI ++
const useWebcamButton = document.getElementById('useWebcamButton');
const useMjpegButton = document.getElementById('useMjpegButton');
const mjpegUrlGroup = document.getElementById('mjpegUrlGroup'); // Descomente se adicionou o input de URL
const webcamIdGroup = document.getElementById('webcamIdGroup');
// const mjpegUrlInput = document.getElementById('mjpegUrl'); // Descomente se adicionou o input de URL
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

console.log("Script webcam.js carregado.");
console.log("Elemento useWebcamButton:", useWebcamButton);
console.log("Elemento useMjpegButton:", useMjpegButton);
console.log("Elemento webcamIdGroup:", webcamIdGroup);


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

// ++ ADICIONAR: Variável para controlar a fonte de vídeo atual ++
let currentVideoSource = 'webcam'; // 'webcam' ou 'mjpeg'

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
        startButton.disabled = false; // Habilitar o botão de iniciar após a conexão
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

// ++ ADICIONAR: Função para atualizar a UI de seleção de fonte ++
function updateSourceSelectionUI() {
    if (currentVideoSource === 'webcam') {
        useWebcamButton.classList.add('active');
        useMjpegButton.classList.remove('active');
        if (webcamIdGroup) webcamIdGroup.style.display = 'block';
        // if (mjpegUrlGroup) mjpegUrlGroup.style.display = 'none'; // Descomente se usar input de URL MJPEG
    } else { // mjpeg
        useWebcamButton.classList.remove('active');
        useMjpegButton.classList.add('active');
        if (webcamIdGroup) webcamIdGroup.style.display = 'none';
        // if (mjpegUrlGroup) mjpegUrlGroup.style.display = 'block'; // Descomente se usar input de URL MJPEG
    }
}


// Função para converter base64 para Blob
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

// Função para obter o cookie CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Função para enviar o frame ao backend para salvamento
async function saveFrameToServer(frameBase64) {
    if (isSavingFrame) {
        return;
    }
    const now = Date.now();
    if (now - lastSaveTime < SAVE_FRAME_INTERVAL) {
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
            videoFeed.src = 'data:image/jpeg;base64,' + data.frame;
            if (videoFeed.style.display === 'none') {
                videoFeed.style.display = 'block';
                loadingOverlay.style.display = 'none';
            }
            if (detectionEnabled && data.frame && data.plates && data.plates.length > 0) {
                saveFrameToServer(data.frame);
            }
            break;
        case 'camera_started': // ++ ALTERAR: Mensagem mais genérica ++
            updateStatus(`✅ ${data.message}`, 'success');
            startButton.disabled = true;
            stopButton.disabled = false;
            // ++ ADICIONAR: Desabilitar botões de seleção de fonte enquanto o stream está ativo ++
            useWebcamButton.disabled = true;
            useMjpegButton.disabled = true;
            startTime = Date.now();
            detectedPlates = [];
            updatePlatesList();
            updateStatistics();
            lastSaveTime = 0;
            break;
        case 'camera_stopped': // ++ ALTERAR: Mensagem mais genérica ++
            updateStatus(`⏹️ ${data.message}`);
            startButton.disabled = false;
            stopButton.disabled = true;
            // ++ ADICIONAR: Habilitar botões de seleção de fonte quando o stream parar ++
            useWebcamButton.disabled = false;
            useMjpegButton.disabled = false;
            videoFeed.style.display = 'none';
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Stream parado'; // ++ ALTERAR ++
            clearPlatesList();
            break;
        case 'error':
            updateStatus(`❌ ${data.message}`, 'error');
            // ++ ALTERAR: Habilitar startButton e botões de seleção em caso de erro ao iniciar ++
            startButton.disabled = false;
            useWebcamButton.disabled = false;
            useMjpegButton.disabled = false;
            stopButton.disabled = true;
            loadingOverlay.style.display = 'flex';
            loadingText.textContent = 'Erro ao iniciar';
            videoFeed.style.display = 'none';
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


// Buscar placas do banco de dados
async function fetchPlatesFromDB() {
    updateStatus("🔄 Carregando placas do banco de dados...", 'info');
    try {
        const response = await fetch('/api/detected-plates/');
        if (!response.ok) {
            let errorMsg = `Erro HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.error || JSON.stringify(errorData);
            } catch (e) { /* ignore parsing error */ }
            throw new Error(errorMsg);
        }
        const platesFromDB = await response.json();

        detectedPlates = platesFromDB.map(plate => {
            const knownNum = plate.known_plate_number;
            const detectedNum = plate.plate_number_detected || plate.best_ocr_text;
            let htmlFormattedPlateText;
            let simplePlateText;

            if (knownNum) {
                htmlFormattedPlateText = `<div><span class="plate-label">Placa Conhecida:</span> ${knownNum}</div>`;
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
                text: simplePlateText,
                formatted_text: htmlFormattedPlateText,
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
                known_plate_is_regularized: plate.known_plate_is_regularized
            };
        });

        updatePlatesList();
        updateStatistics();
        updateStatus(`✅ ${detectedPlates.length} placas carregadas do banco.`, 'success');

    } catch (error) {
        console.error('Erro ao buscar placas do banco de dados:', error);
        updateStatus(`⚠️ Erro ao carregar placas: ${error.message}`, 'error');
    }
}

// Atualizar lista de placas
function updatePlatesList() {
    if (detectedPlates.length === 0) {
        platesList.innerHTML = `
            <div class="info-panel">
                <p>Nenhuma placa salva no banco de dados.</p>
                <p>Inicie o stream para detectar e salvar novas placas.</p> </div>
        `;
        return;
    }

    platesList.innerHTML = detectedPlates.map(plate => {
        let regularizationDisplayHtml;
        if (typeof plate.known_plate_is_regularized === 'boolean') {
            if (plate.known_plate_is_regularized) {
                regularizationDisplayHtml = `<span class="plate-status regularizada">✅ Regularizada</span>`;
            } else {
                regularizationDisplayHtml = `<span class="plate-status nao-regularizada">❌ Não Regularizada</span>`;
            }
        } else {
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
            <p>Inicie o stream para começar a detecção.</p> </div>
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

// ++ ADICIONAR: Listeners para os botões de seleção de fonte ++
if (useWebcamButton) {
    useWebcamButton.onclick = function () {
        currentVideoSource = 'webcam';
        updateSourceSelectionUI();
    };
}

if (useMjpegButton) {
    useMjpegButton.onclick = function () {
        currentVideoSource = 'mjpeg';
        updateSourceSelectionUI();
    };
}


startButton.onclick = function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
        const message = {
            command: 'start_camera',
            source_type: currentVideoSource, // ++ ADICIONAR: Enviar tipo de fonte ++
            detection_enabled: detectionEnabled
        };

        if (currentVideoSource === 'webcam') {
            message.camera_id = parseInt(cameraIdInput.value, 10);
        } else if (currentVideoSource === 'mjpeg') {
            // Se o URL do MJPEG for configurável pelo usuário e não fixo no backend:
            // const mjpegStreamUrl = mjpegUrlInput.value;
            // if (!mjpegStreamUrl) {
            //     updateStatus("❌ URL do MJPEG não fornecida.", 'error');
            //     return;
            // }
            // message.mjpeg_url = mjpegStreamUrl;
            // Por enquanto, o URL do MJPEG é fixo no backend, então não precisamos enviar.
            // O backend saberá qual URL usar quando source_type for 'mjpeg'.
        }

        socket.send(JSON.stringify(message));
        updateStatus(`📹 Tentando iniciar stream (${currentVideoSource})...`); // ++ ALTERAR ++
        loadingText.textContent = 'Iniciando stream...'; // ++ ALTERAR ++
        loadingOverlay.style.display = 'flex';
        // ++ ADICIONAR: Desabilitar botões de seleção de fonte ao iniciar ++
        useWebcamButton.disabled = true;
        useMjpegButton.disabled = true;

    } else {
        updateStatus("❌ WebSocket não está conectado", 'error');
    }
};

stopButton.onclick = function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ command: 'stop_camera' }));
        updateStatus("⏹️ Parando stream..."); // ++ ALTERAR ++
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
updateSourceSelectionUI(); // ++ ADICIONAR: Chamar para definir o estado inicial da UI de seleção ++

// Limpar recursos ao sair da página
window.addEventListener('beforeunload', function () {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ command: 'stop_camera' }));
        socket.close();
    }
});