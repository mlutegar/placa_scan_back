import uuid

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files import File
from thefuzz import fuzz
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
                # 'detected_plates_yolo' é uma lista de dicts do serviço, cada um com:
                # 'cropped_image' (np.array), 'bounding_box', 'confidence'
                detected_plates_yolo = detector_service.detect_plates(image_path)

                if not detected_plates_yolo:
                    detection.status = 'completed'
                    detection.processed_at = timezone.now()
                    detection.save()
                    return Response({
                        'id': detection.id,
                        'message': 'Nenhuma placa detectada na imagem',
                        'plates': []
                    })

                processed_plates_response_data = []  # Renomeado para clareza

                for plate_data_from_yolo in detected_plates_yolo:
                    # Executar OCR (o método process_plate_ocr é mais completo que o process_plate_ocr_fast)
                    ocr_results = detector_service.process_plate_ocr(
                        plate_data_from_yolo['cropped_image']  # Passar o array numpy da imagem da placa cortada
                    )
                    plate_text_from_ocr = ocr_results.get('best_text', '').strip().upper()

                    known_plate_association = None  # Para armazenar a KnownPlate se uma correspondência for encontrada
                    current_highest_similarity = 0  # Para registrar a similaridade da associação

                    # Só tenta a busca por similaridade se o OCR retornou algum texto
                    if plate_text_from_ocr:
                        # Validar e formatar o texto da placa para a consulta
                        _, query_plate_text, _ = detector_service.validate_plate_text(plate_text_from_ocr)

                        if query_plate_text:
                            SIMILARITY_THRESHOLD = 50
                            all_known_plates_qs = KnownPlate.objects.all()
                            best_match_for_this_ocr = None

                            for db_plate in all_known_plates_qs:
                                score = fuzz.ratio(query_plate_text, db_plate.plate_number)
                                if score > current_highest_similarity:
                                    current_highest_similarity = score
                                    best_match_for_this_ocr = db_plate

                            if best_match_for_this_ocr and current_highest_similarity >= SIMILARITY_THRESHOLD:
                                known_plate_association = best_match_for_this_ocr
                                logger.info(
                                    f"Para PlateDetection ID {detection.id}: Placa OCR '{plate_text_from_ocr}' (processada como '{query_plate_text}') "
                                    f"será associada à KnownPlate '{known_plate_association.plate_number}' "
                                    f"(similaridade: {current_highest_similarity}%)."
                                )
                            else:
                                if best_match_for_this_ocr:  # Match encontrado, mas abaixo do limiar
                                    logger.info(
                                        f"Para PlateDetection ID {detection.id}: Placa OCR '{plate_text_from_ocr}' (processada como '{query_plate_text}'). "
                                        f"Melhor correspondência KnownPlate: '{best_match_for_this_ocr.plate_number}' (similaridade: {current_highest_similarity}%). "
                                        f"Não atingiu o limiar de {SIMILARITY_THRESHOLD}%. Será salva sem associação explícita."
                                    )
                                else:  # Nenhum match ou similaridade 0
                                    logger.info(
                                        f"Para PlateDetection ID {detection.id}: Nenhuma KnownPlate similar encontrada "
                                        f"para OCR '{plate_text_from_ocr}' (processada como '{query_plate_text}'). Será salva sem associação explícita."
                                    )
                            # --- FIM DA LÓGICA DE BUSCA POR SIMILARIDADE ---

                    # Salvar imagem cortada (como antes)
                    filename = f"plate_{detection.id}_{uuid.uuid4().hex[:8]}.jpg"
                    cropped_file_django_field = detector_service.save_cropped_plate(
                        plate_data_from_yolo['cropped_image'], filename
                    )

                    # Criar registro da placa detectada.
                    # 'known_plate' será preenchido com 'known_plate_association' (que pode ser None).
                    detected_plate_object = DetectedPlate.objects.create(
                        detection=detection,
                        plate_number_detected=plate_text_from_ocr,
                        known_plate=known_plate_association,  # Associação aqui (pode ser None)
                        bounding_box=plate_data_from_yolo['bounding_box'],
                        yolo_confidence=plate_data_from_yolo['confidence'],
                        cropped_image=cropped_file_django_field,
                        best_ocr_text=ocr_results.get('best_text', ''),
                        best_ocr_confidence=ocr_results.get('best_confidence'),
                        ocr_results=ocr_results.get('all_results', {})  # Usar .get para evitar KeyError
                    )

                    processed_plates_response_data.append({
                        'id': detected_plate_object.id,
                        'plate_number_detected': detected_plate_object.plate_number_detected,
                        # Adicionar informação sobre a placa conhecida associada e a similaridade
                        'known_plate_associated_number': known_plate_association.plate_number if known_plate_association else None,
                        'association_similarity_score': current_highest_similarity if known_plate_association else None,
                        # Score da associação feita
                        'is_regularized_status': known_plate_association.is_regularized if known_plate_association else None,
                        'bounding_box': detected_plate_object.bounding_box,
                        'yolo_confidence': detected_plate_object.yolo_confidence,
                        'cropped_image_url': request.build_absolute_uri(
                            detected_plate_object.cropped_image.url) if detected_plate_object.cropped_image else None,
                        'best_ocr_text': detected_plate_object.best_ocr_text,  # Pode ser igual a plate_number_detected
                        'best_ocr_confidence': detected_plate_object.best_ocr_confidence
                    })

                # Atualizar status da detecção principal
                detection.status = 'completed'
                detection.processed_at = timezone.now()
                detection.save()

                return Response({
                    'id': detection.id,
                    'message': f'{len(processed_plates_response_data)} placa(s) detectada(s) e processada(s) com sucesso na imagem.',
                    'plates': processed_plates_response_data
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Erro ao processar detecção {detection.id}: {e}", exc_info=True)  # Adicionado exc_info
                detection.status = 'error'
                detection.error_message = str(e)
                detection.processed_at = timezone.now()  # Marcar processed_at mesmo em erro
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
        Processa um frame único. Detecta placas, realiza OCR,
        e salva a detecção no banco de dados APENAS SE a placa OCRizada for conhecida.
        """
        temp_path = None  # Para garantir que temp_path seja definido para o bloco finally/except
        detection_instance_for_frame = None  # Para rastrear a instância de PlateDetection do frame

        try:
            if 'frame' not in request.FILES:
                return Response({'error': 'Frame obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

            frame_file = request.FILES['frame']

            # Salvar temporariamente o frame para processamento
            # É importante usar um método seguro para criar arquivos temporários
            # e garantir que o diretório exista e seja gravável.
            # O código original usa /tmp/, que pode não ser ideal para todas as plataformas.
            # Considere usar o módulo `tempfile` do Python para maior portabilidade.
            # Exemplo simplificado mantendo a lógica original de /tmp/:
            temp_dir = '/tmp'
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)  # Garante que o diretório exista
            temp_frame_filename = f'frame_{uuid.uuid4().hex}.jpg'
            temp_path = os.path.join(temp_dir, temp_frame_filename)

            with open(temp_path, 'wb+') as destination:
                for chunk in frame_file.chunks():
                    destination.write(chunk)

            detector_service = PlateDetectorService()

            # Detectar placas no frame salvo.
            # `detect_plates` retorna uma lista de dicts, cada um com 'cropped_image' (np.array),
            # 'bounding_box', e 'confidence'.
            detected_plates_from_yolo = detector_service.detect_plates(temp_path)

            saved_plates_output_info = []  # Informações das placas salvas para a resposta

            if not detected_plates_from_yolo:
                os.remove(temp_path)
                return Response({
                    'detection_id': None,
                    'message': 'Nenhuma placa detectada no frame.',
                    'saved_plates': [],
                    'frame_processed': True
                }, status=status.HTTP_200_OK)

            for plate_data_yolo in detected_plates_from_yolo:
                cropped_image_np = plate_data_yolo['cropped_image']
                ocr_results = detector_service.process_plate_ocr_fast(cropped_image_np)
                plate_text_from_ocr = ocr_results.get('best_text', '').strip().upper()

                if not plate_text_from_ocr:
                    continue

                    # Validar e formatar o texto da placa para consulta (como antes)
                _, query_plate_text, _ = detector_service.validate_plate_text(plate_text_from_ocr)

                # Se após a validação/limpeza, o texto da placa estiver vazio, pule.
                if not query_plate_text:
                    print(f"Texto da placa OCR '{plate_text_from_ocr}' resultou em query vazia após validação.")
                    continue

                # --- INÍCIO DA ALTERAÇÃO: Lógica de Busca por Similaridade ---
                known_plate_instance = None

                # Defina um limiar de similaridade (0-100).
                # Este valor é crucial e pode precisar de ajuste experimental.
                # Um valor mais alto significa uma correspondência mais estrita.
                SIMILARITY_THRESHOLD = 60  # Exemplo: 85% de similaridade mínima

                # Busca todas as placas conhecidas.
                # ATENÇÃO: Se você tiver MUITAS placas conhecidas, buscar todas (`.all()`)
                # e iterar pode ser ineficiente. Considere estratégias de pré-filtragem
                # se a performance se tornar um problema.
                # Ex: KnownPlate.objects.filter(plate_number__startswith=query_plate_text[0])
                # ou usar funcionalidades de busca por similaridade do próprio banco de dados (ex: pg_trgm para PostgreSQL).
                all_known_plates_qs = KnownPlate.objects.all()

                best_match_found = None
                highest_similarity_score = 0

                for db_plate in all_known_plates_qs:
                    # Calcula a similaridade entre o texto do OCR (query_plate_text)
                    # e o número da placa no banco de dados (db_plate.plate_number).
                    # fuzz.ratio() é uma boa escolha geral para similaridade de strings.
                    current_similarity_score = fuzz.ratio(query_plate_text, db_plate.plate_number)

                    if current_similarity_score > highest_similarity_score:
                        highest_similarity_score = current_similarity_score
                        best_match_found = db_plate

                # Verifica se o melhor match encontrado atinge o limiar de similaridade
                if best_match_found and highest_similarity_score >= SIMILARITY_THRESHOLD:
                    known_plate_instance = best_match_found
                    print(
                        f"Placa OCR '{plate_text_from_ocr}' (processada como '{query_plate_text}') "
                        f"correspondeu à placa conhecida '{known_plate_instance.plate_number}' "
                        f"com similaridade de {highest_similarity_score}% (limiar: {SIMILARITY_THRESHOLD}%)."
                    )
                else:
                    # Log se um match foi encontrado mas estava abaixo do limiar, ou nenhum match.
                    if best_match_found:
                        print(
                            f"Placa OCR '{plate_text_from_ocr}' (processada como '{query_plate_text}'). "
                            f"Melhor correspondência: '{best_match_found.plate_number}' (similaridade: {highest_similarity_score}%). "
                            f"Não atingiu o limiar de {SIMILARITY_THRESHOLD}%. Não será salva."
                        )
                    else:  # Nenhuma placa no DB para comparar ou todas tiveram score 0
                        print(
                            f"Nenhuma placa conhecida no banco de dados para comparar ou nenhuma similaridade significativa encontrada "
                            f"para OCR '{plate_text_from_ocr}' (processada como '{query_plate_text}')."
                        )
                    # known_plate_instance permanece None, a placa não será salva.
                # --- FIM DA ALTERAÇÃO: Lógica de Busca por Similaridade ---

                if not known_plate_instance:
                    # Se nenhuma placa conhecida suficientemente similar foi encontrada,
                    # pule para a próxima placa detectada pelo YOLO.
                    continue

                    # Se known_plate_instance FOI encontrado (por similaridade):
                # O restante do código para criar PlateDetection (se necessário),
                # salvar a imagem cortada, e criar o objeto DetectedPlate continua aqui,
                # exatamente como na sua implementação anterior que esperava uma correspondência exata.
                # Exemplo:
                if detection_instance_for_frame is None:
                    frame_file.seek(0)
                    detection_instance_for_frame = PlateDetection.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        original_image=frame_file,
                        status='processing'
                    )

                cropped_image_filename = f"plate_{detection_instance_for_frame.id}_{uuid.uuid4().hex[:8]}.jpg"
                django_cropped_image_file = detector_service.save_cropped_plate(
                    cropped_image_np,
                    cropped_image_filename
                )

                detected_plate_obj = DetectedPlate.objects.create(
                    detection=detection_instance_for_frame,
                    plate_number_detected=plate_text_from_ocr,
                    known_plate=known_plate_instance,  # <- Aqui usa a placa encontrada por similaridade
                    bounding_box=plate_data_yolo['bounding_box'],
                    yolo_confidence=plate_data_yolo['confidence'],
                    cropped_image=django_cropped_image_file,
                    best_ocr_text=ocr_results.get('best_text', ''),
                    best_ocr_confidence=ocr_results.get('best_confidence'),
                    ocr_results={'fast_ocr_result': ocr_results}
                )

                saved_plates_output_info.append({
                    'detected_plate_id': detected_plate_obj.id,
                    'plate_number_ocr': detected_plate_obj.plate_number_detected,
                    'known_plate_db_number': known_plate_instance.plate_number,
                    'similarity_score': highest_similarity_score,  # Adicionar score para informação
                    'is_regularized': known_plate_instance.is_regularized,
                    'bounding_box_yolo': detected_plate_obj.bounding_box,
                    'cropped_image_url': request.build_absolute_uri(
                        detected_plate_obj.cropped_image.url) if detected_plate_obj.cropped_image else None,
                    'ocr_confidence': detected_plate_obj.best_ocr_confidence
                })

            # Finalizar o status do PlateDetection se ele foi criado e placas foram salvas
            if detection_instance_for_frame and saved_plates_output_info:
                detection_instance_for_frame.status = 'completed'
                detection_instance_for_frame.processed_at = timezone.now()
                detection_instance_for_frame.save()

                os.remove(temp_path)  # Remover arquivo temporário
                return Response({
                    'detection_id': detection_instance_for_frame.id,
                    'message': f'{len(saved_plates_output_info)} placa(s) conhecida(s) detectada(s) e salva(s) com sucesso.',
                    'saved_plates': saved_plates_output_info,
                    'frame_processed': True
                }, status=status.HTTP_201_CREATED)  # 201 CREATED pois novos recursos foram criados

            # Se chegou aqui, ou nenhuma placa foi detectada pelo YOLO,
            # ou placas foram detectadas mas nenhuma era conhecida.
            # Em ambos os casos, nenhum PlateDetection foi criado ou nenhuma DetectedPlate foi salva.
            os.remove(temp_path)  # Remover arquivo temporário
            message = 'Nenhuma placa detectada no frame.'
            if detected_plates_from_yolo:  # Se YOLO detectou algo, mas nada era conhecido
                message = 'Placas foram detectadas no frame, mas nenhuma delas é conhecida no banco de dados e, portanto, não foram salvas.'

            return Response({
                'detection_id': None,
                'message': message,
                'saved_plates': [],
                'frame_processed': True
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Erro geral no processamento do frame: {e}", exc_info=True)

            # Se uma instância de PlateDetection foi criada antes do erro, atualize seu status
            if detection_instance_for_frame and PlateDetection.objects.filter(
                    id=detection_instance_for_frame.id).exists():
                detection_instance_for_frame.status = 'error'
                detection_instance_for_frame.error_message = str(e)
                detection_instance_for_frame.processed_at = timezone.now()
                detection_instance_for_frame.save()

            return Response({'error': f'Erro interno no servidor ao processar o frame: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # Garantir que o arquivo temporário seja removido em caso de erro também, se ele existir
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e_rm:
                    logger.error(f"Erro ao tentar remover arquivo temporário {temp_path} no bloco finally: {e_rm}")

    @action(detail=False, methods=['get'])
    def list_detections(self, request):
        """Lista todas as detecções com paginação"""
        detections = PlateDetection.objects.all().order_by('-created_at')
        serializer = self.get_serializer(detections, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        detection = get_object_or_404(PlateDetection, pk=pk)

        if 'status' in request.data:
            detection.status = request.data['status']
        if 'processed_at' in request.data:
            detection.processed_at = timezone.now()

        detection.save()
        return Response(PlateDetectionSerializer(detection).data)


class DetectedPlateViewSet(viewsets.ModelViewSet):
    queryset = DetectedPlate.objects.select_related('detection').all().order_by('-detection__created_at', '-id')
    serializer_class = DetectedPlateSerializer

    def create(self, request, *args, **kwargs):
        """Criar nova placa detectada"""
        return super().create(request, *args, **kwargs)