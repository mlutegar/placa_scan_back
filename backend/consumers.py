import json
import cv2
import base64
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
import threading
import time


class VideoStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cap = None
        self.streaming = False
        self.stream_thread = None
        self.loop = None  # Armazenar referência do loop principal

    async def connect(self):
        # Armazenar referência do loop de eventos atual
        self.loop = asyncio.get_event_loop()

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
                camera_id = data.get('camera_id', 0)
                await self.start_camera_stream(camera_id)
            elif command == 'stop_camera':
                await self.stop_camera_stream()

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Formato JSON inválido'
            }))

    async def start_camera_stream(self, camera_id=0):
        if self.streaming:
            await self.stop_camera_stream()

        # Lista de IDs de câmera para tentar
        camera_ids_to_try = [camera_id, 0, 1, 2, -1]  # -1 às vezes funciona

        self.cap = None
        working_cam_id = None

        for cam_id in camera_ids_to_try:
            print(f"Tentando câmera ID: {cam_id}")
            try:
                cap_test = cv2.VideoCapture(cam_id)

                # Tentar diferentes backends se disponível
                if not cap_test.isOpened():
                    cap_test.release()
                    # Tentar com backend específico (Windows)
                    cap_test = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)

                if cap_test.isOpened():
                    # Teste se consegue ler um frame
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
                'message': 'Não foi possível acessar nenhuma câmera. Verifique se há uma câmera conectada.'
            }))
            return

        # Configurar câmera (opcional - pode comentar se causar problemas)
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 15)  # FPS mais baixo para estabilizar
        except:
            pass  # Ignorar se não conseguir configurar

        self.streaming = True

        # Iniciar thread de streaming
        self.stream_thread = threading.Thread(target=self.camera_stream_loop, daemon=True)
        self.stream_thread.start()

        await self.send(text_data=json.dumps({
            'type': 'camera_started',
            'message': f'Câmera {working_cam_id} iniciada com sucesso'
        }))

    def camera_stream_loop(self):
        """Loop da câmera - APENAS captura e envia frames, sem processamento"""
        print("Iniciando loop da câmera...")

        while self.streaming and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    print("Não foi possível ler frame da câmera")
                    break

                # Redimensionar frame para performance
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    new_width = 640
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))

                # Converter para JPEG com qualidade média
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if not success:
                    continue

                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # Enviar frame usando o loop principal
                if self.loop and not self.loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        self.send_frame(frame_base64),
                        self.loop
                    )

                # Controlar FPS (~15 FPS)
                time.sleep(0.066)

            except Exception as e:
                print(f"Erro no loop da câmera: {e}")
                break

        print("Loop da câmera finalizado")

    async def send_frame(self, frame_base64):
        """Enviar frame via WebSocket"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'frame',
                'frame': frame_base64,
                'plates': [],  # Vazio por enquanto
                'timestamp': time.time()
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