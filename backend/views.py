import uuid

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
import os
import logging

from .models import PlateDetection, DetectedPlate, KnownPlate
from .serializers import PlateDetectionSerializer, DetectedPlateSerializer
from .services.plate_detector import PlateDetectorService

logger = logging.getLogger(__name__)


class PlateDetectionViewSet(viewsets.ModelViewSet):
    queryset = PlateDetection.objects.all()
    serializer_class = PlateDetectionSerializer
    parser_classes = [MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @action(detail=False, methods=['post'])
    def detect_plates(self, request):
        """
        Endpoint para detectar placas em uma imagem
        """
        try:
            print(f"Request data: {request.data}")
            print(f"Request files: {request.FILES}")
            # Validar arquivo
            if 'original_image' not in request.FILES:
                print("Erro: Campo 'image' não encontrado")
                return Response(
                    {'error': 'Arquivo de imagem é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            detector_service = PlateDetectorService()

            image_file = request.FILES['original_image']

            # Criar registro de detecção
            detection = PlateDetection.objects.create(
                user=request.user if request.user.is_authenticated else None,
                original_image=image_file,
                status='processing'
            )

            try:
                # Processar imagem
                image_path = detection.original_image.path
                detected_plates = detector_service.detect_plates(image_path)

                if not detected_plates:
                    detection.status = 'completed'
                    detection.processed_at = timezone.now()
                    detection.save()

                    return Response({
                        'id': detection.id,
                        'message': 'Nenhuma placa detectada na imagem',
                        'plates': []
                    })

                # Processar cada placa detectada
                plates_data = []

                for plate_data in detected_plates:
                    # Executar OCR
                    ocr_results = detector_service.process_plate_ocr(
                        plate_data['cropped_image']
                    )

                    # Salvar imagem cortada
                    filename = f"plate_{detection.id}_{uuid.uuid4().hex[:8]}.jpg"
                    cropped_file = detector_service.save_cropped_plate(
                        plate_data['cropped_image'], filename
                    )

                    # Criar registro da placa
                    detected_plate = DetectedPlate.objects.create(
                        detection=detection,
                        plate_number_detected=ocr_results['best_text'],  # Usar o resultado do OCR
                        bounding_box=plate_data['bounding_box'],
                        yolo_confidence=plate_data['confidence'],
                        cropped_image=cropped_file,
                        best_ocr_text=ocr_results['best_text'],
                        best_ocr_confidence=ocr_results['best_confidence'],
                        ocr_results=ocr_results['all_results']
                    )

                    plates_data.append({
                        'id': detected_plate.id,
                        'plate_number_detected': detected_plate.plate_number_detected,
                        'bounding_box': detected_plate.bounding_box,
                        'yolo_confidence': detected_plate.yolo_confidence,
                        'cropped_image_url': detected_plate.cropped_image.url,
                        'best_ocr_text': detected_plate.best_ocr_text,
                        'best_ocr_confidence': detected_plate.best_ocr_confidence
                    })

                # Atualizar status
                detection.status = 'completed'
                detection.processed_at = timezone.now()
                detection.save()

                return Response({
                    'id': detection.id,
                    'message': f'{len(plates_data)} placa(s) detectada(s) com sucesso',
                    'plates': plates_data
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erro ao processar detecção {detection.id}: {e}")
                detection.status = 'error'
                detection.error_message = str(e)
                detection.save()

                return Response(
                    {'error': f'Erro ao processar imagem: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"Erro geral na detecção: {e}")
            return Response(
                {'error': f'Erro interno: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def get_results(self, request, pk=None):
        """
        Obtém resultados detalhados de uma detecção
        """
        detection = get_object_or_404(PlateDetection, pk=pk)

        # Verificar permissão (se necessário)
        if detection.user and detection.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Sem permissão para acessar esta detecção'},
                status=status.HTTP_403_FORBIDDEN
            )

        plates = DetectedPlate.objects.filter(detection=detection)
        plates_data = DetectedPlateSerializer(plates, many=True).data

        return Response({
            'detection': PlateDetectionSerializer(detection).data,
            'plates': plates_data
        })

    @action(detail=False, methods=['post'])
    def process_frame(self, request):
        """
        Processa um frame único do stream de vídeo
        """
        try:
            if 'frame' not in request.FILES:
                return Response({'error': 'Frame obrigatório'}, status=400)

            frame_file = request.FILES['frame']

            # Salvar temporariamente
            temp_path = f'/tmp/frame_{uuid.uuid4()}.jpg'
            with open(temp_path, 'wb+') as destination:
                for chunk in frame_file.chunks():
                    destination.write(chunk)

            # Detectar placas
            detector_service = PlateDetectorService()
            detected_plates = detector_service.detect_plates(temp_path)

            # OCR rápido
            plates_data = []
            for plate_data in detected_plates:
                ocr_results = detector_service.process_plate_ocr_fast(
                    plate_data['cropped_image']
                )

                plates_data.append({
                    'bounding_box': plate_data['bounding_box'],
                    'confidence': plate_data['confidence'],
                    'text': ocr_results['best_text'],
                    'text_confidence': ocr_results['best_confidence']
                })

            # Limpar arquivo temporário
            os.remove(temp_path)

            return Response({
                'plates': plates_data,
                'frame_processed': True
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def list_detections(self, request):
        """Lista todas as detecções com paginação"""
        detections = PlateDetection.objects.all().order_by('-created_at')
        serializer = self.get_serializer(detections, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Atualiza status de uma detecção"""
        detection = get_object_or_404(PlateDetection, pk=pk)

        if 'status' in request.data:
            detection.status = request.data['status']
        if 'processed_at' in request.data:
            detection.processed_at = timezone.now()

        detection.save()
        return Response(PlateDetectionSerializer(detection).data)


class DetectedPlateViewSet(viewsets.ModelViewSet):
    queryset = DetectedPlate.objects.all()
    serializer_class = DetectedPlateSerializer

    def create(self, request, *args, **kwargs):
        """Criar nova placa detectada"""
        return super().create(request, *args, **kwargs)