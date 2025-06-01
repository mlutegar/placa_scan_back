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
let detectedPlates = [];
let startTime = Date.now();

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

    socket.onopen = function(e) {
        updateStatus("✅ WebSocket conectado com sucesso!", 'success');
        startButton.disabled = false;
        reconnectAttempts = 0;
    };

    socket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('Erro ao processar mensagem:', e);
        }
    };

    socket.onclose = function(event) {
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

    socket.onerror = function(error) {
        updateStatus('📛 Erro no WebSocket', 'error');
        console.error('WebSocket error:', error);
    };
}

// Manipular mensagens WebSocket
function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'frame':
            // Atualizar vídeo
            videoFeed.src = 'data:image/jpeg;base64,' + data.frame;
            if (videoFeed.style.display === 'none') {
                videoFeed.style.display = 'block';
                loadingOverlay.style.display = 'none';
            }

            // Processar placas detectadas
            if (data.plates && data.plates.length > 0) {
                processDetectedPlates(data.plates);
            }
            break;

        case 'camera_started':
            updateStatus(`✅ ${data.message}`, 'success');
            startButton.disabled = true;
            stopButton.disabled = false;
            startTime = Date.now();
            detectedPlates = [];
            updateStatistics();
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

// Processar placas detectadas
function processDetectedPlates(plates) {
    plates.forEach(plate => {
        // Adicionar timestamp
        plate.timestamp = new Date().toLocaleTimeString();

        // Adicionar à lista se não for duplicata recente
        if (!isDuplicatePlate(plate)) {
            detectedPlates.unshift(plate);

            // Limitar a 50 placas na lista
            if (detectedPlates.length > 50) {
                detectedPlates = detectedPlates.slice(0, 50);
            }

            updatePlatesList();
            updateStatistics();
        }
    });
}

// Verificar placa duplicada
function isDuplicatePlate(newPlate) {
    const now = Date.now();
    return detectedPlates.some(plate => {
        const plateTTime = new Date(`1970/01/01 ${plate.timestamp}`).getTime();
        const timeDiff = now - plateTTime;

        return plate.text === newPlate.text && timeDiff < 3000; // 3 segundos
    });
}

// Atualizar lista de placas
function updatePlatesList() {
    if (detectedPlates.length === 0) {
        platesList.innerHTML = `  
            <div class="info-panel"> 
                <p>Nenhuma placa detectada ainda.</p> 
            </div>  
        `;
        return;
    }

    platesList.innerHTML = detectedPlates.map(plate => `  
        <div class="plate-item ${plate.is_valid ? '' : 'invalid'}">  
            <div class="plate-text">${plate.formatted_text || plate.text}</div>  
            <div class="confidence-bar"> 
                <div class="confidence-fill" style="width: ${plate.confidence}%"></div>  
            </div> 
            <div class="plate-details"> 
                <span class="plate-type ${plate.plate_type}">${plate.plate_type || 'desconhecido'}</span>  
                <span class="timestamp">${plate.timestamp}</span>  
            </div> 
            <div class="plate-details"> 
                <span>OCR: ${plate.confidence.toFixed(1)}%</span>  
                <span>YOLO: ${plate.yolo_confidence.toFixed(1)}%</span>  
            </div> 
        </div>  
    `).join('');
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
startButton.onclick = function() {
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

stopButton.onclick = function() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ command: 'stop_camera' }));
        updateStatus("⏹️ Parando câmera...");
    } else {
        updateStatus("❌ WebSocket não está conectado", 'error');
    }
};

detectionToggle.onclick = function() {
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

// Limpar recursos ao sair da página
window.addEventListener('beforeunload', function() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ command: 'stop_camera' }));
        socket.close();
    }
});