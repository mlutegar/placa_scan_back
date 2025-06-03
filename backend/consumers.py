import json
import cv2
import base64
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
import threading
import time
import numpy as np
# import tempfile # Não parece estar sendo usado, pode ser removido se não for necessário.

from backend.services.plate_detector import PlateDetectorService
import logging

logger = logging.getLogger(__name__)


class VideoStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cap = None
        self.streaming = False
        self.stream_thread = None
        self.loop = None

        self.plate_detector = None
        self.detection_enabled = True
        self.detection_interval = 5
        self.frame_count = 0
        self.last_detection_time = 0
        self.min_detection_interval = 2.0

        self.last_detected_plates = []
        self.detection_cache_duration = 5.0

        # ++ ADICIONAR: Configuração para URL do MJPEG (pode ser movida para settings.py se preferir) ++
        self.MJPEG_STREAM_URL = "http://admin:admin@172.16.1.143:8081/video"  # Exemplo de URL

    async def connect(self):
        self.loop = asyncio.get_event_loop()
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
        def init_detector():
            try:
                self.plate_detector = PlateDetectorService()
                logger.info("Detector de placas inicializado com sucesso")
                return True
            except Exception as e:
                logger.error(f"Erro ao inicializar detector: {e}")
                return False

        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, init_detector)

        if success:
            await self.send(text_data=json.dumps({
                'type': 'plate_detector_ready',
                'message': 'Detector de placas pronto'
            }))

    async def disconnect(self, close_code):
        await self.stop_camera_stream()  # Garante que o stream pare ao desconectar
        # A liberação do self.cap é feita em stop_camera_stream
        logger.info(f"WebSocket desconectado com código: {close_code}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            command = data.get('command')

            if command == 'start_camera':
                # ++ ADICIONAR: Obter source_type e outros parâmetros relevantes ++
                source_type = data.get('source_type', 'webcam')  # Padrão para webcam se não fornecido
                camera_id = data.get('camera_id', 0)  # Usado para webcam
                mjpeg_url = data.get('mjpeg_url',
                                     self.MJPEG_STREAM_URL)  # Usado para mjpeg, pode vir do front ou usar o default
                self.detection_enabled = data.get('detection_enabled', True)

                await self.start_camera_stream(source_type=source_type, camera_id=camera_id, mjpeg_url=mjpeg_url)

            elif command == 'stop_camera':
                await self.stop_camera_stream()
            elif command == 'toggle_detection':
                self.detection_enabled = data.get('enabled', True)
                await self.send(text_data=json.dumps({
                    'type': 'detection_toggled',
                    'enabled': self.detection_enabled
                }))

        except json.JSONDecodeError:
            await self.send_error_message('Formato JSON inválido')
        except Exception as e:
            logger.error(f"Erro ao processar comando: {e}")
            await self.send_error_message(f"Erro interno do servidor: {str(e)}")

    # ++ ALTERAR: start_camera_stream para lidar com source_type ++
    async def start_camera_stream(self, source_type='webcam', camera_id=0, mjpeg_url=None):
        if self.streaming:
            await self.stop_camera_stream()  # Para o stream anterior se houver

        self.cap = None
        stream_description = ""

        if source_type == 'webcam':
            stream_description = f"Webcam ID {camera_id}"
            camera_ids_to_try = [camera_id, 0, 1, 2, -1]  # Lógica original para encontrar webcam
            working_cam_id = None
            for cam_id_attempt in camera_ids_to_try:
                logger.info(f"Tentando webcam ID: {cam_id_attempt}")
                try:
                    cap_test = cv2.VideoCapture(cam_id_attempt)
                    if not cap_test.isOpened():  # Tentar com CAP_DSHOW se falhar
                        cap_test.release()
                        cap_test = cv2.VideoCapture(cam_id_attempt, cv2.CAP_DSHOW)

                    if cap_test.isOpened():
                        ret, frame = cap_test.read()
                        if ret and frame is not None:
                            self.cap = cap_test
                            working_cam_id = cam_id_attempt
                            stream_description = f"Webcam {working_cam_id}"
                            logger.info(f"Webcam {working_cam_id} funcionando!")
                            break
                        else:
                            cap_test.release()
                    else:
                        cap_test.release()
                except Exception as e:
                    logger.warning(f"Erro ao tentar webcam {cam_id_attempt}: {e}")
                    if cap_test: cap_test.release()  # Garante a liberação
                    continue

        elif source_type == 'mjpeg':
            target_mjpeg_url = mjpeg_url if mjpeg_url else self.MJPEG_STREAM_URL
            stream_description = f"MJPEG stream de {target_mjpeg_url}"
            logger.info(f"Tentando conectar ao MJPEG stream: {target_mjpeg_url}")
            try:
                self.cap = cv2.VideoCapture(target_mjpeg_url)
            except Exception as e:
                logger.error(f"Exceção ao tentar abrir MJPEG stream {target_mjpeg_url}: {e}")
                self.cap = None  # Garante que self.cap seja None em caso de falha na inicialização

        else:
            await self.send_error_message(f"Tipo de fonte de vídeo desconhecido: {source_type}")
            return

        if not self.cap or not self.cap.isOpened():
            error_message = f"Não foi possível acessar {stream_description}."
            if source_type == 'mjpeg':
                error_message += " Verifique o URL e as credenciais, se aplicável."
            await self.send_error_message(error_message)
            if self.cap: self.cap.release()  # Libera o recurso se foi parcialmente aberto
            self.cap = None
            return

        # Configurações da câmera (podem não se aplicar a todos os streams MJPEG)
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 15)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception as e:
            logger.warning(
                f"Aviso: Algumas configurações de câmera podem não ser aplicáveis ao stream {stream_description}: {e}")

        self.streaming = True
        self.frame_count = 0
        self.last_detection_time = 0

        self.stream_thread = threading.Thread(target=self.camera_stream_loop, daemon=True)
        self.stream_thread.start()

        await self.send(text_data=json.dumps({
            'type': 'camera_started',
            'message': f'Stream de {stream_description} iniciado com detecção de placas'
        }))

    def camera_stream_loop(self):
        logger.info("Iniciando loop do stream de vídeo com detecção de placas...")
        while self.streaming and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    logger.warning("Não foi possível ler frame do stream. Encerrando loop.")
                    asyncio.run_coroutine_threadsafe(
                        self.send_error_message("Perda de conexão com o stream de vídeo."),
                        self.loop
                    )
                    break

                self.frame_count += 1
                current_time = time.time()

                # Redimensionar frame
                height, width = frame.shape[:2]
                if width > 640:  # Manter a lógica de redimensionamento
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

                detected_plates_info = []
                should_detect = (
                        self.detection_enabled and
                        self.plate_detector is not None and
                        (self.frame_count % self.detection_interval == 0) and
                        (current_time - self.last_detection_time >= self.min_detection_interval)
                )

                if should_detect:
                    # logger.debug("Tentando detectar placas...")
                    time.sleep(0.05)  # Pequeno delay antes da detecção para não sobrecarregar CPU em alguns casos
                    detected_plates_info = self.detect_plates_in_frame(
                        frame.copy())  # Enviar cópia para evitar modificação do frame original
                    self.last_detection_time = current_time
                    # logger.debug(f"Placas detectadas nesta iteração: {len(detected_plates_info)}")

                display_frame = frame.copy()  # Trabalhar com uma cópia para desenhar
                if detected_plates_info:  # Usar o resultado da detecção mais recente
                    display_frame = self.draw_plate_detections(display_frame, detected_plates_info)

                success, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if not success:
                    logger.warning("Falha ao encodar frame para JPEG.")
                    continue

                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                if self.loop and not self.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self.send_frame_with_plates(frame_base64, detected_plates_info),
                        self.loop
                    )

                time.sleep(0.066)  # Controlar FPS (~15 FPS)

            except cv2.error as e:  # Erros específicos do OpenCV
                logger.error(f"Erro OpenCV no loop do stream: {e}. Tentando continuar...")
                time.sleep(1)  # Pausa antes de tentar o próximo frame
                continue  # Tenta continuar o loop se possível
            except Exception as e:
                logger.error(f"Erro inesperado no loop do stream: {e}")
                asyncio.run_coroutine_threadsafe(
                    self.send_error_message(f"Erro no processamento do stream: {str(e)}"),
                    self.loop
                )
                break  # Encerra o loop em caso de erro grave

        logger.info("Loop do stream de vídeo finalizado.")
        # Garante que o estado de streaming seja falso e notifique o cliente
        if self.streaming:  # Se o loop quebrou inesperadamente
            asyncio.run_coroutine_threadsafe(self.stop_camera_stream_logic(), self.loop)

    def detect_plates_in_frame(self, frame_to_detect):
        if self.plate_detector is None:
            return []
        try:
            # logger.debug("Chamando plate_detector.detect_plates_from_array")
            detected_plates_yolo = self.plate_detector.detect_plates_from_array(frame_to_detect)
            # logger.debug(f"Resultado YOLO: {len(detected_plates_yolo)} placas")

            plates_with_text_and_info = []
            for plate_info_yolo in detected_plates_yolo:
                try:
                    cropped_img = plate_info_yolo.get('cropped_image')
                    if cropped_img is None or cropped_img.size == 0:
                        # logger.warning("Imagem recortada inválida ou vazia.")
                        continue

                    ocr_result = self.plate_detector.process_plate_ocr_fast(cropped_img)
                    # logger.debug(f"Resultado OCR para uma placa: {ocr_result}")

                    if ocr_result and ocr_result.get('best_text'):
                        is_valid, formatted_text, plate_type = self.plate_detector.validate_plate_text(
                            ocr_result['best_text']
                        )

                        plate_data = {
                            'bounding_box': plate_info_yolo['bounding_box'],
                            'confidence': plate_info_yolo['confidence'],  # Confiança YOLO
                            'text': ocr_result['best_text'],
                            'formatted_text': formatted_text if is_valid else ocr_result['best_text'],
                            'ocr_confidence': ocr_result['best_confidence'],
                            'is_valid': is_valid,
                            'plate_type': plate_type if is_valid else 'unknown',
                            'timestamp': time.time()  # Timestamp da detecção
                        }
                        if not self.is_duplicate_detection(plate_data):
                            plates_with_text_and_info.append(plate_data)
                except Exception as e_ocr:
                    logger.error(f"Erro no processamento OCR de uma placa: {e_ocr}")
                    continue

            if plates_with_text_and_info:
                self.update_detection_cache(plates_with_text_and_info)
            # logger.debug(f"Total de placas processadas com OCR e sem duplicatas: {len(plates_with_text_and_info)}")
            return plates_with_text_and_info

        except Exception as e_detect:
            logger.error(f"Erro na detecção de placas (detect_plates_from_array): {e_detect}")
            time.sleep(0.2)  # Evitar loops rápidos de erro
            return []

    def is_duplicate_detection(self, new_plate):
        current_time = time.time()
        # Limpar cache de placas muito antigas primeiro (embora update_detection_cache já faça isso)
        self.last_detected_plates = [
            p for p in self.last_detected_plates
            if current_time - p['timestamp'] <= self.detection_cache_duration
        ]

        for cached_plate in self.last_detected_plates:
            # Não precisa checar timestamp aqui de novo, pois já foi filtrado

            # Verifica se o texto é o mesmo
            if (cached_plate['text'] == new_plate['text'] or
                    (cached_plate.get('formatted_text') and new_plate.get('formatted_text') and
                     cached_plate['formatted_text'] == new_plate['formatted_text'])):

                # Verifica proximidade das coordenadas (IoU ou distância do centro)
                # Simplificado para distância do centro por enquanto
                c_bbox = cached_plate['bounding_box']
                n_bbox = new_plate['bounding_box']

                center_c_x = (c_bbox['x1'] + c_bbox['x2']) / 2
                center_c_y = (c_bbox['y1'] + c_bbox['y2']) / 2
                center_n_x = (n_bbox['x1'] + n_bbox['x2']) / 2
                center_n_y = (n_bbox['y1'] + n_bbox['y2']) / 2

                distance = ((center_c_x - center_n_x) ** 2 + (center_c_y - center_n_y) ** 2) ** 0.5

                # Definir um limiar de distância. Isso pode precisar de ajuste.
                # Considere o tamanho da imagem e o tamanho típico das placas.
                # Para uma imagem de 640px de largura, 50px pode ser razoável.
                if distance < 50:  # pixels
                    # logger.debug(f"Detecção duplicada encontrada: {new_plate['text']} (Dist: {distance:.2f})")
                    return True
        return False

    def update_detection_cache(self, new_plates_data):
        current_time = time.time()
        # Remove old entries
        self.last_detected_plates = [
            p for p in self.last_detected_plates
            if current_time - p['timestamp'] <= self.detection_cache_duration
        ]
        # Add new ones, ensuring they have a timestamp
        for p_data in new_plates_data:
            if 'timestamp' not in p_data:
                p_data['timestamp'] = current_time  # Add timestamp if missing
        self.last_detected_plates.extend(new_plates_data)
        # logger.debug(f"Cache de detecção atualizado. Tamanho: {len(self.last_detected_plates)}")

    def draw_plate_detections(self, frame, detected_plates_info):
        for plate in detected_plates_info:
            bbox = plate['bounding_box']
            color = (0, 255, 0) if plate.get('is_valid', False) else (
            0, 0, 255)  # Verde para válida, Vermelho para inválida/desconhecida

            cv2.rectangle(frame, (bbox['x1'], bbox['y1']), (bbox['x2'], bbox['y2']), color, 2)

            text_to_display = plate.get('formatted_text', plate.get('text', 'N/A'))
            ocr_conf_text = f"OCR: {plate.get('ocr_confidence', 0) * 100:.1f}%" if plate.get(
                'ocr_confidence') is not None else "OCR: N/A"
            yolo_conf_text = f"YOLO: {plate.get('confidence', 0) * 100:.1f}%" if plate.get(
                'confidence') is not None else "YOLO: N/A"

            # Posição para o texto da placa (acima do bbox)
            (text_width, text_height), baseline = cv2.getTextSize(text_to_display, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (bbox['x1'], bbox['y1'] - text_height - baseline - 5),
                          (bbox['x1'] + text_width, bbox['y1'] - 5), color, -1)
            cv2.putText(frame, text_to_display, (bbox['x1'], bbox['y1'] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Posição para confianças (abaixo do bbox)
            cv2.putText(frame, ocr_conf_text, (bbox['x1'], bbox['y2'] + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            cv2.putText(frame, yolo_conf_text, (bbox['x1'], bbox['y2'] + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        return frame

    async def send_frame_with_plates(self, frame_base64, detected_plates_info):
        try:
            plates_payload = []
            for plate in detected_plates_info:
                plates_payload.append({
                    'text': plate.get('formatted_text', plate.get('text')),
                    'confidence': plate.get('ocr_confidence', 0.0),
                    # Enviar confiança do OCR como 'confidence' principal para UI
                    'yolo_confidence': plate.get('confidence', 0.0),  # Confiança da detecção YOLO
                    'is_valid': plate.get('is_valid', False),
                    'plate_type': plate.get('plate_type', 'unknown'),
                    'bounding_box': plate.get('bounding_box')
                })

            await self.send(text_data=json.dumps({
                'type': 'frame',
                'frame': frame_base64,
                'plates': plates_payload,
                'timestamp': time.time(),
                'detection_enabled': self.detection_enabled
            }))
        except Exception as e:
            logger.error(f"Erro ao enviar frame com placas: {e}")

    async def stop_camera_stream(self):
        """Função principal para parar o stream, chamada pelo receive ou disconnect."""
        if self.streaming or self.cap:  # Só executa se realmente precisa parar
            await self.stop_camera_stream_logic()

    async def stop_camera_stream_logic(self):
        """Lógica interna de parada do stream, para ser chamada de forma síncrona ou assíncrona."""
        logger.info("Parando stream de vídeo...")
        self.streaming = False  # Sinaliza para a thread do loop parar

        if self.stream_thread and self.stream_thread.is_alive():
            logger.debug("Aguardando thread do stream finalizar...")
            self.stream_thread.join(timeout=3)  # Espera a thread finalizar
            if self.stream_thread.is_alive():
                logger.warning("Thread do stream não finalizou no tempo esperado.")
        self.stream_thread = None

        if self.cap:
            logger.debug("Liberando captura de vídeo (cv2.VideoCapture)...")
            try:
                self.cap.release()
            except Exception as e:
                logger.error(f"Erro ao liberar self.cap: {e}")
            self.cap = None

        logger.info("Stream de vídeo parado e recursos liberados.")

        # Verifica se o websocket ainda está ativo antes de enviar a mensagem
        if self.channel_layer and self.channel_name:  # Garante que o consumidor ainda está "conectado"
            try:
                await self.send(text_data=json.dumps({
                    'type': 'camera_stopped',
                    'message': 'Stream parado e câmera liberada'
                }))
            except Exception as e:  # Exceção pode ocorrer se o cliente já desconectou
                logger.warning(f"Não foi possível enviar 'camera_stopped' ao cliente (pode já estar desconectado): {e}")
        else:
            logger.info("Consumidor não está mais ativo, não enviando 'camera_stopped'.")

    async def send_error_message(self, message):
        logger.error(f"Enviando erro para o cliente: {message}")
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': message
            }))
        except Exception as e:
            logger.warning(f"Não foi possível enviar mensagem de erro ao cliente (pode já estar desconectado): {e}")