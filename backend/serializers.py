from rest_framework import serializers
from .models import PlateDetection, DetectedPlate


class PlateDetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlateDetection
        fields = ['id', 'original_image', 'created_at', 'processed_at', 'status', 'error_message']
        read_only_fields = ['id', 'created_at', 'processed_at', 'status', 'error_message']


class DetectedPlateSerializer(serializers.ModelSerializer):
    # Adiciona o timestamp da detecção pai para cada placa
    detection_created_at = serializers.DateTimeField(source='detection.created_at', read_only=True, allow_null=True)

    # Adiciona a URL completa para a imagem da placa cortada
    cropped_image_url = serializers.SerializerMethodField()

    # Exemplo de como você poderia adicionar informações de placas conhecidas
    # is_known = serializers.SerializerMethodField()
    # plate_type = serializers.CharField(source='known_plate_info.vehicle_type', read_only=True, allow_null=True) # Se tiver um related_name 'known_plate_info'

    class Meta:
        model = DetectedPlate
        fields = [
            'id',
            'detection',  # ID da PlateDetection à qual esta placa pertence
            'detection_created_at',
            'plate_number_detected',
            'bounding_box',
            'yolo_confidence',
            'cropped_image_url',  # Use esta em vez de 'cropped_image' no frontend
            'best_ocr_text',
            'best_ocr_confidence',
            'ocr_results',
            # 'is_known',
            # 'plate_type',
            # Adicione outros campos que seu modelo DetectedPlate possa ter e que sejam úteis na UI
        ]

    def get_cropped_image_url(self, obj):
        request = self.context.get('request')
        if obj.cropped_image and hasattr(obj.cropped_image, 'url'):
            if request:  # Se o contexto da requisição estiver disponível, construa URL absoluta
                return request.build_absolute_uri(obj.cropped_image.url)
            return obj.cropped_image.url  # Caso contrário, apenas a URL relativa
        return None

    # def get_is_known(self, obj):
    #     # Exemplo: verificar se existe uma KnownPlate associada
    #     # return KnownPlate.objects.filter(plate_number=obj.best_ocr_text).exists()
    #     # ou se você tem um relacionamento direto:
    #     # return hasattr(obj, 'known_plate_info') and obj.known_plate_info is not None
    #     return False # Placeholder