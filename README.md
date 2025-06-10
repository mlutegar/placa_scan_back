# PlacaScan: Sistema Web de Reconhecimento de Placas

[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![Django REST Framework](https://img.shields.io/badge/DRF-3.14-red.svg)](https://www.django-rest-framework.org/)
[![WebSockets](https://img.shields.io/badge/WebSockets-Django_Channels-blue.svg)](https://channels.readthedocs.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-yellow.svg)](https://github.com/ultralytics/ultralytics)

https://www.canva.com/design/DAGp968ZEDE/Ysf2rYL_f00USe7ULTsD3w/edit?utm_content=DAGp968ZEDE&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton

## Visão Geral

Sistema web completo para detecção e reconhecimento de placas veiculares, desenvolvido com **Django REST Framework** e **WebSockets** para processamento em tempo real. O sistema oferece uma interface web moderna para upload de imagens, stream de vídeo ao vivo e gerenciamento de banco de dados de placas conhecidas.

## Arquitetura do Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Serviços      │
│   (HTML/CSS/JS) │◄──►│   (Django/DRF)  │◄──►│   (YOLO/OCR)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
    WebSockets              REST API              PlateDetector
    (Tempo Real)           (CRUD/Upload)           Service
```

### Componentes Principais

#### Backend (Django)
- **API REST** para upload e processamento de imagens
- **WebSockets** para streaming de vídeo em tempo real
- **Sistema de detecção** com YOLO v8 e OCR (Tesseract/EasyOCR)
- **Banco de dados** PostgreSQL para persistência
- **Matching inteligente** com algoritmo de similaridade (fuzzy matching)

#### Frontend
- **Interface responsiva** HTML5/CSS3/JavaScript
- **Upload de imagens** com drag & drop
- **Stream ao vivo** de webcam/MJPEG
- **Dashboard** com estatísticas em tempo real
- **Visualização** de bounding boxes e confiança

## Estrutura do Banco de Dados

### Modelos Django

```python
# Detecção principal
class PlateDetection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    original_image = models.ImageField(upload_to='uploads/')
    status = models.CharField(choices=['pending', 'processing', 'completed', 'error'])
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

# Placas conhecidas (base de dados)
class KnownPlate(models.Model):
    plate_number = models.CharField(max_length=20, unique=True)
    is_regularized = models.BooleanField(default=True)
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

# Placas detectadas
class DetectedPlate(models.Model):
    detection = models.ForeignKey(PlateDetection, on_delete=models.CASCADE)
    plate_number_detected = models.CharField(max_length=20)
    known_plate = models.ForeignKey(KnownPlate, on_delete=models.SET_NULL)
    bounding_box = models.JSONField()  # {x1, y1, x2, y2}
    yolo_confidence = models.FloatField()
    cropped_image = models.ImageField(upload_to='plates/cropped/')
    best_ocr_text = models.CharField(max_length=20)
    best_ocr_confidence = models.FloatField()
    ocr_results = models.JSONField(default=dict)
```

### Relacionamentos
- `PlateDetection` 1:N `DetectedPlate` (uma imagem pode ter múltiplas placas)
- `KnownPlate` 1:N `DetectedPlate` (relacionamento por similaridade fuzzy)
- `User` 1:N `PlateDetection` (rastreamento por usuário)

## API REST Endpoints

### Upload e Processamento
```http
POST /api/detections/detect_plates/
Content-Type: multipart/form-data

{
  "original_image": <file>
}
```

**Resposta:**
```json
{
  "id": "uuid-detection-id",
  "message": "2 placa(s) detectada(s) e processada(s)",
  "plates": [
    {
      "id": "plate-id",
      "plate_number_detected": "ABC1234",
      "known_plate_associated_number": "ABC1234",
      "association_similarity_score": 95.0,
      "is_regularized_status": true,
      "yolo_confidence": 0.87,
      "best_ocr_confidence": 0.92,
      "cropped_image_url": "/media/plates/cropped/..."
    }
  ]
}
```

### Processamento de Frame (Tempo Real)
```http
POST /api/detections/process_frame/
Content-Type: multipart/form-data

{
  "frame": <frame_data>
}
```

### Listagem de Detecções
```http
GET /api/detections/
```

### Resultados Detalhados
```http
GET /api/detections/{detection_id}/get_results/
```

## WebSocket para Streaming

### Conectar ao WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/video/');
```

### Comandos Suportados

#### Iniciar Webcam
```javascript
ws.send(JSON.stringify({
    'command': 'start_camera',
    'source_type': 'webcam',
    'camera_id': 0,
    'detection_enabled': true
}));
```

#### Iniciar Stream MJPEG
```javascript
ws.send(JSON.stringify({
    'command': 'start_camera',
    'source_type': 'mjpeg',
    'mjpeg_url': 'http://admin:admin@192.168.1.100:8081/video',
    'detection_enabled': true
}));
```

#### Alternar Detecção
```javascript
ws.send(JSON.stringify({
    'command': 'toggle_detection',
    'enabled': false
}));
```

### Mensagens Recebidas

#### Frame com Detecções
```javascript
{
    "type": "frame",
    "frame": "base64_encoded_image",
    "plates": [
        {
            "text": "ABC1234",
            "confidence": 0.92,
            "yolo_confidence": 0.87,
            "is_valid": true,
            "plate_type": "old",
            "bounding_box": {"x1": 100, "y1": 50, "x2": 200, "y2": 100}
        }
    ],
    "timestamp": 1640995200.0,
    "detection_enabled": true
}
```

## Serviço de Detecção

### PlateDetectorService

O serviço principal que integra YOLO e OCR:

```python
class PlateDetectorService:
    def __init__(self):
        self.model = YOLO(settings.YOLO_MODEL_PATH)
        self.reader = easyocr.Reader(settings.EASYOCR_LANGUAGES)
    
    def detect_plates_from_array(self, image_array):
        """Detecta placas diretamente de array numpy"""
        results = self.model(image_array)
        # Processa resultados YOLO...
    
    def process_plate_ocr_fast(self, cropped_image):
        """OCR otimizado para tempo real"""
        # Pré-processamento + Tesseract/EasyOCR
    
    def validate_plate_text(self, text):
        """Valida padrões brasileiros (antigo/Mercosul)"""
        # Regex para ABC1234 e ABC1D23
```

### Técnicas de Pré-processamento

O sistema implementa múltiplas técnicas para otimizar OCR:

- **Grayscale**: Conversão para escala de cinza
- **Otsu Thresholding**: Binarização automática
- **Adaptive Thresholding**: Para condições variáveis de luz
- **Bilateral Filter**: Redução de ruído preservando bordas
- **Sharpening**: Aumento de nitidez
- **Resizing 2x**: Aumento de resolução para textos pequenos
- **Inversion**: Inversão de cores para contraste

### Algoritmo de Matching

Sistema de correspondência fuzzy para placas conhecidas:

```python
from thefuzz import fuzz

def find_known_plate(detected_text):
    SIMILARITY_THRESHOLD = 60  # 60% mínimo
    best_match = None
    highest_score = 0
    
    for known_plate in KnownPlate.objects.all():
        score = fuzz.ratio(detected_text, known_plate.plate_number)
        if score > highest_score and score >= SIMILARITY_THRESHOLD:
            highest_score = score
            best_match = known_plate
    
    return best_match, highest_score
```

## Interface Web

### Funcionalidades

#### Dashboard Principal
- **Status do sistema** em tempo real
- **Controles de stream** (webcam/MJPEG)
- **Toggle de detecção** on/off
- **Lista de placas detectadas** com timestamps
- **Estatísticas** (total, válidas, confiança média, taxa/min)

#### Stream de Vídeo
- **Feed em tempo real** com overlay de detecções
- **Bounding boxes** coloridos (verde=válida, vermelho=inválida)
- **Informações de confiança** YOLO e OCR
- **Controles de qualidade** e filtros

#### Upload de Imagens
- **Drag & drop** ou seleção de arquivos
- **Preview** da imagem original
- **Resultados detalhados** com crops das placas
- **Download** de imagens processadas

### Tecnologias Frontend

```html
<!-- HTML5 moderno -->
<input type="file" accept="image/*" multiple>
<canvas id="videoCanvas"></canvas>
<div class="detection-overlay"></div>

<!-- CSS3 com Grid/Flexbox -->
.video-container {
    display: grid;
    grid-template: "video controls" / 2fr 1fr;
    gap: 20px;
}

.plate-item {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 8px;
    padding: 15px;
}

<!-- JavaScript ES6+ -->
class WebSocketManager {
    constructor(url) {
        this.ws = new WebSocket(url);
        this.setupEventHandlers();
    }
    
    sendCommand(command, data) {
        this.ws.send(JSON.stringify({command, ...data}));
    }
}
```

## Performance e Otimizações

### Backend
- **Processamento assíncrono** com Django Channels
- **Cache de detecções** para evitar duplicatas
- **Batch processing** para múltiplas placas
- **Thread pools** para operações CPU-intensivas

### Frontend
- **Debouncing** de eventos de UI
- **Lazy loading** de imagens
- **WebSocket reconnection** automática
- **Progressive enhancement** para diferentes navegadores

### Banco de Dados
- **Índices otimizados** em campos de busca
- **Particionamento** por data para grandes volumes
- **Connection pooling** para alta concorrência

## Configuração e Deploy

### Variáveis de Ambiente
```python
# settings.py
YOLO_MODEL_PATH = 'models/yolo-plate-detection.pt'
EASYOCR_LANGUAGES = ['en']
CONFIDENCE_THRESHOLDS = [0.0, 0.2, 0.4, 0.6, 0.8]

# Tesseract
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# WebSocket
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {"hosts": [('127.0.0.1', 6379)]},
    },
}
```

### Instalação
```bash
# 1. Clonar repositório
git clone [repo-url]
cd placascan-web

# 2. Ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.\.venv\Scripts\activate  # Windows

# 3. Dependências
pip install -r requirements.txt

# 4. Banco de dados
python manage.py migrate
python manage.py createsuperuser

# 5. Modelos de IA
# Baixar modelo YOLO treinado para models/

# 6. Executar
python manage.py runserver
```

### Docker Deploy
```dockerfile
FROM python:3.10

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Instalar Tesseract
RUN apt-get update && apt-get install -y tesseract-ocr

COPY . .
EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## Monitoramento e Logs

### Métricas Coletadas
- **Taxa de detecção** (placas/minuto)
- **Precisão do OCR** por método de pré-processamento
- **Latência** do pipeline completo
- **Uso de recursos** (CPU/GPU/Memória)
- **Erros** e exceções por componente

### Logs Estruturados
```python
logger.info(
    f"Placa detectada: OCR '{ocr_text}' → "
    f"KnownPlate '{known_plate.plate_number}' "
    f"(similaridade: {similarity_score}%)"
)
```

## Testes

### Cobertura de Testes
- **API Endpoints**: Upload, processamento, WebSocket
- **Modelos Django**: Validação de dados, relacionamentos
- **Serviços**: Detecção YOLO, OCR, matching fuzzy
- **Frontend**: Interações JavaScript, WebSocket

### Testes de Performance
- **Load testing** com múltiplos usuários simultâneos
- **Stress testing** do pipeline de detecção
- **Memory profiling** para vazamentos
- **Benchmark** de diferentes resoluções de vídeo

## Roadmap Técnico

### Próximas Funcionalidades
- [ ] **API GraphQL** para queries flexíveis
- [ ] **Autenticação JWT** e autorização baseada em roles
- [ ] **Exportação de dados** em múltiplos formatos
- [ ] **Dashboards analíticos** com métricas avançadas
- [ ] **Integração com câmeras IP** (RTSP/ONVIF)
- [ ] **Deploy em Kubernetes** com scaling automático

### Melhorias de Performance
- [ ] **GPU acceleration** para YOLO e OCR
- [ ] **Caching distribuído** com Redis Cluster
- [ ] **CDN** para servir imagens processadas
- [ ] **Background workers** com Celery
- [ ] **Database sharding** para escala massiva

## Contribuição

Este sistema serve como base para implementações de LPR em produção, oferecendo:

- **Arquitetura escalável** com separação clara de responsabilidades
- **APIs RESTful** para integração com sistemas existentes
- **Interface moderna** para operadores humanos
- **Flexibilidade** para diferentes fontes de vídeo
- **Extensibilidade** para novos algoritmos de detecção

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.
