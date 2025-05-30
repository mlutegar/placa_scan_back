from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json


class WebcamDetectorView(View):
    """View para a página do detector de placas com webcam"""

    def get(self, request):
        context = {
            'title': 'Detector de Placas - Webcam',
            'page_description': 'Sistema de reconhecimento de placas em tempo real'
        }
        return render(request, 'detector/webcam.html', context)


# API views opcionais para funcionalidades extras
@method_decorator(csrf_exempt, name='dispatch')
class CameraConfigView(View):
    """API para configurações da câmera"""

    def get(self, request):
        """Retorna as câmeras disponíveis no sistema"""
        import cv2

        available_cameras = []
        for i in range(5):  # Testa até 5 câmeras
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Obter informações da câmera
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))

                available_cameras.append({
                    'id': i,
                    'name': f'Câmera {i}',
                    'resolution': f'{width}x{height}',
                    'fps': fps
                })
                cap.release()

        return JsonResponse({
            'cameras': available_cameras,
            'total': len(available_cameras)
        })

    def post(self, request):
        """Salva configurações da câmera"""
        try:
            data = json.loads(request.body)
            # Aqui você pode salvar as configurações no banco de dados
            # ou em um arquivo de configuração

            return JsonResponse({
                'success': True,
                'message': 'Configurações salvas com sucesso'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class DetectionHistoryView(View):
    """API para histórico de detecções"""

    def get(self, request):
        """Retorna histórico de detecções (implementar com seu modelo)"""
        # Exemplo - substitua pela sua lógica de banco de dados

        # from .models import PlateDetection
        # detections = PlateDetection.objects.all().order_by('-created_at')[:50]

        sample_detections = [
            {
                'id': 1,
                'plate_text': 'ABC-1234',
                'confidence': 95.5,
                'timestamp': '2024-01-15T10:30:00Z',
                'camera_id': 0,
                'plate_type': 'old'
            },
            # ... mais detecções
        ]

        return JsonResponse({
            'detections': sample_detections,
            'total': len(sample_detections)
        })