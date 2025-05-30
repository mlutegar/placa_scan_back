import json
import cv2
import base64
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .services.plate_detector import PlateDetectorService
import numpy as np
import threading
import time


class VideoStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.detector_service = PlateDetectorService()
        self.cap = None
        self.streaming = False
        self.stream_thread = None
        self.frame_count = 0
        self.process_every_n_frames = 10  # Processar detecção a cada 10 frames

    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'status': 'connected',
            'message': 'WebSocket conectado com sucesso'
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
                camera_id = data.get('camera_id', 0)  # Permitir escolher câmera
                await self.start_camera_stream(camera_id)
            elif command == 'stop_camera':
                await self.stop_camera_stream()
            elif command == 'process_frame':
                frame_data = data.get('frame')
                await self.process_uploaded_frame(frame_data)
            elif command == 'change_detection_frequency':
                frequency = data.get('frequency', 10)
                self.process_every_n_frames = max(1, frequency)

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Formato JSON inválido'
            }))

    async def start_camera_stream(self, camera_id=0):
        if self.streaming:
            await self.stop_camera_stream()

        # Tentar diferentes IDs de câmera se não funcionar
        for cam_id in [camera_id, 0, 1, 2]:
            self.cap = cv2.VideoCapture(cam_id)
            if self.cap.isOpened():
                break
            self.cap.release()

        if not self.cap.isOpened():
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Não foi possível acessar a câmera'
            }))
            return

        # Configurar qualidade da câmera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.streaming = True
        self.frame_count = 0

        # Iniciar stream em thread separada para não bloquear
        self.stream_thread = threading.Thread(target=self.camera_stream_loop)
        self.stream_thread.start()

        await self.send(text_data=json.dumps({
            'type': 'camera_started',
            'message': f'Câmera {cam_id} iniciada com sucesso'
        }))

    def camera_stream_loop(self):
        """Loop principal da câmera executado em thread separada"""
        while self.streaming and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break

            try:
                # Redimensionar para performance (mantém proporção)
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))

                self.frame_count += 1
                plates_data = []

                # Processar detecção de placas periodicamente
                if self.frame_count % self.process_every_n_frames == 0:
                    plates_data = self.detect_plates_in_frame_sync(frame)

                # Desenhar bounding boxes se houver detecções
                if plates_data:
                    frame = self.draw_detections(frame, plates_data)

                # Converter frame para base64
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # Enviar frame via WebSocket (de forma assíncrona)
                asyncio.run_coroutine_threadsafe(
                    self.send_frame(frame_base64, plates_data),
                    asyncio.get_event_loop()
                )

                # Controlar FPS
                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                print(f"Erro no loop da câmera: {e}")
                break

    async def send_frame(self, frame_base64, plates_data):
        """Enviar frame via WebSocket"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'frame',
                'frame': frame_base64,
                'plates': plates_data,
                'timestamp': time.time(),
                'frame_count': self.frame_count
            }))
        except Exception as e:
            print(f"Erro ao enviar frame: {e}")

    def detect_plates_in_frame_sync(self, frame):
        """Versão síncrona da detecção de placas"""
        try:
            # Usar a imagem diretamente sem salvar arquivo temporário
            detected_plates = self.detector_service.detect_plates_from_array(frame)

            plates_data = []
            for plate_data in detected_plates:
                # OCR otimizado
                ocr_results = self.detector_service.process_plate_ocr_fast(
                    plate_data['cropped_image']
                )

                plates_data.append({
                    'plate_number': plate_data.get('plate_number', ''),
                    'bounding_box': plate_data.get('bounding_box', []),
                    'confidence': plate_data.get('confidence', 0.0),
                    'text': ocr_results.get('best_text', ''),
                    'text_confidence': ocr_results.get('best_confidence', 0.0)
                })

            return plates_data

        except Exception as e:
            print(f"Erro na detecção síncrona: {e}")
            return []

    def draw_detections(self, frame, plates_data):
        """Desenhar bounding boxes e texto nas detecções"""
        for plate in plates_data:
            bbox = plate.get('bounding_box', [])
            if len(bbox) == 4:
                x, y, w, h = bbox

                # Desenhar retângulo
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Desenhar texto
                text = plate.get('text', 'N/A')
                confidence = plate.get('text_confidence', 0)
                label = f"{text} ({confidence:.1f}%)"

                # Fundo para o texto
                (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x, y - text_height - 10), (x + text_width, y), (0, 255, 0), -1)

                # Texto
                cv2.putText(frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        return frame

    async def stop_camera_stream(self):
        """Parar stream da câmera"""
        self.streaming = False

        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2)

        if self.cap:
            self.cap.release()
            self.cap = None

        await self.send(text_data=json.dumps({
            'type': 'camera_stopped',
            'message': 'Câmera parada'
        }))

    async def process_uploaded_frame(self, frame_data):
        """Processar frame enviado via upload"""
        try:
            # Decodificar base64
            image_data = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Detectar placas
            plates_data = self.detect_plates_in_frame_sync(frame)

            # Desenhar detecções
            if plates_data:
                frame = self.draw_detections(frame, plates_data)

            # Retornar resultado
            _, buffer = cv2.imencode('.jpg', frame)
            result_base64 = base64.b64encode(buffer).decode('utf-8')

            await self.send(text_data=json.dumps({
                'type': 'processed_frame',
                'frame': result_base64,
                'plates': plates_data
            }))

        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Erro ao processar frame: {str(e)}'
            }))


# Método adicional que você precisa implementar no PlateDetectorService
def detect_plates_from_array(self, image_array):
    """
    Adicione este método ao seu PlateDetectorService para processar
    arrays numpy diretamente sem salvar arquivos temporários
    """
    pass