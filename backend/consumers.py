import json
import cv2
import base64
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
import threading
import time
import numpy as np
import tempfile

from backend.services.plate_detector import PlateDetectorService
import logging

logger = logging.getLogger(__name__)


class VideoStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cap = None
        self.streaming = False
        self.stream_thread = None
        self.loop = None  # Armazenar referência do loop principal

        # Configurações de detecção de placas
        self.plate_detector = None
        self.detection_enabled = True
        self.detection_interval = 5  # Detectar a cada 5 frames (para performance)
        self.frame_count = 0
        self.last_detection_time = 0
        self.min_detection_interval = 2.0  # Mínimo 2 segundos entre detecções

        # Cache para evitar detecções repetidas
        self.last_detected_plates = []
        self.detection_cache_duration = 5.0  # segundos

    async def connect(self):
        # Armazenar referência do loop de eventos atual
        self.loop = asyncio.get_event_loop()

        # Inicializar detector de placas em thread separada
        try:
            await self.initialize_plate_detector()
        except Exception as e:
            logger.error(f"Erro ao inicializar detector de placas: {e}")

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'message': 'WebSocket conectado com sucesso',
            'plate_detection': self.plate_detector is not None
        }))

    async def initialize_plate_detector(self):
        """Inicializa o detector de placas em uma thread separada"""

        def init_detector():
            try:
                self.plate_detector = PlateDetectorService()
                logger.info("Detector de placas inicializado com sucesso")
                return True
            except Exception as e:
                logger.error(f"Erro ao inicializar detector: {e}")
                return False

        # Executar inicialização em thread separada para não bloquear
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, init_detector)

        if success:
            await self.send(text_data=json.dumps({
                'type': 'plate_detector_ready',
                'message': 'Detector de placas pronto'
            }))

    async def disconnect(self, close_code):
        await self.stop_camera_stream()
        if self.cap:
            self.cap.release()
        self.streaming = False

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            command = data.get('command')

            if command == 'start_camera':
                camera_id = data.get('camera_id', 0)
                self.detection_enabled = data.get('detection_enabled', True)
                await self.start_camera_stream(camera_id)
            elif command == 'stop_camera':
                await self.stop_camera_stream()
            elif command == 'toggle_detection':
                self.detection_enabled = data.get('enabled', True)
                await self.send(text_data=json.dumps({
                    'type': 'detection_toggled',
                    'enabled': self.detection_enabled
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Formato JSON inválido'
            }))

    async def start_camera_stream(self, camera_id=0):
        if self.streaming:
            await self.stop_camera_stream()

            # Lista de IDs de câmera para tentar
        camera_ids_to_try = [camera_id, 0, 1, 2, -1]

        self.cap = None
        working_cam_id = None

        for cam_id in camera_ids_to_try:
            print(f"Tentando câmera ID: {cam_id}")
            try:
                cap_test = cv2.VideoCapture(cam_id)

                if not cap_test.isOpened():
                    cap_test.release()
                    cap_test = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)

                if cap_test.isOpened():
                    ret, frame = cap_test.read()
                    if ret and frame is not None:
                        self.cap = cap_test
                        working_cam_id = cam_id
                        print(f"Câmera {cam_id} funcionando!")
                        break
                    else:
                        cap_test.release()
                else:
                    cap_test.release()

            except Exception as e:
                print(f"Erro ao tentar câmera {cam_id}: {e}")
                continue

        if not self.cap or not self.cap.isOpened():
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Não foi possível acessar nenhuma câmera.'
            }))
            return

            # Configurar câmera para melhor performance
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 15)
            # Configurações adicionais para performance
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduzir buffer
        except:
            pass

        self.streaming = True
        self.frame_count = 0
        self.last_detection_time = 0

        # Iniciar thread de streaming
        self.stream_thread = threading.Thread(target=self.camera_stream_loop, daemon=True)
        self.stream_thread.start()

        await self.send(text_data=json.dumps({
            'type': 'camera_started',
            'message': f'Câmera {working_cam_id} iniciada com detecção de placas'
        }))

    def camera_stream_loop(self):
        """Loop otimizado da câmera com detecção de placas integrada"""
        print("Iniciando loop da câmera com detecção de placas...")

        while self.streaming and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    print("Não foi possível ler frame da câmera")
                    break

                self.frame_count += 1
                current_time = time.time()

                # Redimensionar frame para performance
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))

                detected_plates = []

                # Detectar placas com intervalo controlado
                should_detect = (
                        self.detection_enabled and
                        self.plate_detector is not None and
                        (self.frame_count % self.detection_interval == 0) and
                        (current_time - self.last_detection_time >= self.min_detection_interval)
                )

                if should_detect:
                    time.sleep(0.05)  # Pequeno delay antes da detecção
                    detected_plates = self.detect_plates_in_frame(frame.copy())
                    self.last_detection_time = current_time

                # Desenhar bounding boxes das placas detectadas
                display_frame = frame.copy()
                if detected_plates:
                    display_frame = self.draw_plate_detections(display_frame, detected_plates)

                # Converter para JPEG
                success, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if not success:
                    continue

                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # Enviar frame com dados de placas
                if self.loop and not self.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self.send_frame_with_plates(frame_base64, detected_plates),
                        self.loop
                    )

                    # Controlar FPS (~15 FPS)
                time.sleep(0.066)

            except Exception as e:
                print(f"Erro no loop da câmera: {e}")
                break

        print("Loop da câmera finalizado")

    def detect_plates_in_frame(self, frame):
        """Detecta placas no frame atual"""
        try:
            # Usar a versão otimizada de detecção
            detected_plates = self.plate_detector.detect_plates_from_array(frame)

            # Processar OCR apenas se houver placas detectadas
            plates_with_text = []
            for plate_info in detected_plates:
                try:
                    # OCR rápido na imagem recortada
                    ocr_result = self.plate_detector.process_plate_ocr_fast(plate_info['cropped_image'])

                    # Validar texto da placa
                    if ocr_result['best_text']:
                        is_valid, formatted_text, plate_type = self.plate_detector.validate_plate_text(
                            ocr_result['best_text'])

                        plate_data = {
                            'bounding_box': plate_info['bounding_box'],
                            'confidence': plate_info['confidence'],
                            'text': ocr_result['best_text'],
                            'formatted_text': formatted_text if is_valid else ocr_result['best_text'],
                            'ocr_confidence': ocr_result['best_confidence'],
                            'is_valid': is_valid,
                            'plate_type': plate_type if is_valid else 'unknown',
                            'timestamp': time.time()
                        }

                        # Verificar se não é uma detecção repetida recente
                        if not self.is_duplicate_detection(plate_data):
                            plates_with_text.append(plate_data)

                except Exception as e:
                    logger.error(f"Erro no OCR da placa: {e}")
                    continue

            # Atualizar cache de detecções
            if plates_with_text:
                self.update_detection_cache(plates_with_text)

            return plates_with_text

        except Exception as e:
            logger.error(f"Erro na detecção de placas do array: {e}")
            # Aumentar delay para evitar processamento muito rápido
            time.sleep(0.2)
            return []

    def is_duplicate_detection(self, new_plate):
        """Verifica se a placa já foi detectada recentemente"""
        current_time = time.time()

        for cached_plate in self.last_detected_plates:
            # Remover detecções antigas do cache
            if current_time - cached_plate['timestamp'] > self.detection_cache_duration:
                continue

            # Verificar similaridade do texto
            if (cached_plate['text'] == new_plate['text'] or
                    cached_plate['formatted_text'] == new_plate['formatted_text']):

                # Verificar proximidade das coordenadas
                bbox1 = cached_plate['bounding_box']
                bbox2 = new_plate['bounding_box']

                # Calcular distância entre centros dos bounding boxes
                center1_x = (bbox1['x1'] + bbox1['x2']) / 2
                center1_y = (bbox1['y1'] + bbox1['y2']) / 2
                center2_x = (bbox2['x1'] + bbox2['x2']) / 2
                center2_y = (bbox2['y1'] + bbox2['y2']) / 2

                distance = ((center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2) ** 0.5

                # Se a distância for pequena, considerar duplicata
                if distance < 50:  # pixels
                    return True

        return False

    def update_detection_cache(self, new_plates):
        """Atualiza o cache de detecções"""
        current_time = time.time()

        # Remover detecções antigas
        self.last_detected_plates = [
            plate for plate in self.last_detected_plates
            if current_time - plate['timestamp'] <= self.detection_cache_duration
        ]

        # Adicionar novas detecções
        self.last_detected_plates.extend(new_plates)

    def draw_plate_detections(self, frame, detected_plates):
        """Desenha bounding boxes e texto das placas detectadas"""
        for plate in detected_plates:
            bbox = plate['bounding_box']

            # Cor baseada na validade da placa
            color = (0, 255, 0) if plate['is_valid'] else (0, 165, 255)  # Verde para válida, laranja para inválida

            # Desenhar retângulo
            cv2.rectangle(frame, (bbox['x1'], bbox['y1']), (bbox['x2'], bbox['y2']), color, 2)

            # Texto da placa
            text = plate['formatted_text'] if plate['is_valid'] else plate['text']
            confidence_text = f"{plate['ocr_confidence']:.1f}%"

            # Fundo para o texto
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame, (bbox['x1'], bbox['y1'] - 30),
                          (bbox['x1'] + text_size[0] + 10, bbox['y1']), color, -1)

            # Texto da placa
            cv2.putText(frame, text, (bbox['x1'] + 5, bbox['y1'] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Confiança
            cv2.putText(frame, confidence_text, (bbox['x1'], bbox['y2'] + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        return frame

    async def send_frame_with_plates(self, frame_base64, detected_plates):
        """Enviar frame com dados de placas via WebSocket"""
        try:
            # Preparar dados das placas para envio
            plates_data = []
            for plate in detected_plates:
                plates_data.append({
                    'text': plate['formatted_text'],
                    'confidence': plate['ocr_confidence'],
                    'yolo_confidence': plate['confidence'],
                    'is_valid': plate['is_valid'],
                    'plate_type': plate['plate_type'],
                    'bounding_box': plate['bounding_box']
                })

            await self.send(text_data=json.dumps({
                'type': 'frame',
                'frame': frame_base64,
                'plates': plates_data,
                'timestamp': time.time(),
                'detection_enabled': self.detection_enabled
            }))
        except Exception as e:
            print(f"Erro ao enviar frame: {e}")

    async def stop_camera_stream(self):
        """Parar stream da câmera"""
        print("Parando câmera...")
        self.streaming = False

        # Aguardar thread finalizar
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=3)

            # Liberar câmera
        if self.cap:
            self.cap.release()
            self.cap = None

        await self.send(text_data=json.dumps({
            'type': 'camera_stopped',
            'message': 'Câmera parada'
        }))