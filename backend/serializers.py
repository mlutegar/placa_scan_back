from rest_framework import serializers
from .models import PlateDetection, DetectedPlate, KnownPlate # Adicione KnownPlate se for usar diretamente

class PlateDetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlateDetection
        fields = ['id', 'original_image', 'created_at', 'processed_at', 'status', 'error_message']
        read_only_fields = ['id', 'created_at', 'processed_at', 'status', 'error_message']


class DetectedPlateSerializer(serializers.ModelSerializer):
    detection_created_at = serializers.DateTimeField(source='detection.created_at', read_only=True, allow_null=True)
    cropped_image_url = serializers.SerializerMethodField()

    # Campos para informações da KnownPlate associada
    known_plate_number = serializers.CharField(source='known_plate.plate_number', read_only=True, allow_null=True)
    known_plate_is_regularized = serializers.BooleanField(source='known_plate.is_regularized', read_only=True, allow_null=True)
    # Alternativamente, usando SerializerMethodField para mais controle ou se precisar de lógica customizada:
    # known_plate_number = serializers.SerializerMethodField()
    # known_plate_is_regularized = serializers.SerializerMethodField()

    class Meta:
        model = DetectedPlate
        fields = [
            'id',
            'detection',
            'detection_created_at',
            'plate_number_detected',
            'bounding_box',
            'yolo_confidence',
            'cropped_image_url',
            'best_ocr_text',
            'best_ocr_confidence',
            'ocr_results',
            'known_plate', # ID da KnownPlate associada (opcional, pode remover se não quiser expor o ID direto)
            'known_plate_number', # Novo campo
            'known_plate_is_regularized' # Novo campo
        ]

    def get_cropped_image_url(self, obj):
        request = self.context.get('request')
        if obj.cropped_image and hasattr(obj.cropped_image, 'url'):
            if request:
                return request.build_absolute_uri(obj.cropped_image.url)
            return obj.cropped_image.url
        return None

    # Se você optou por SerializerMethodField, descomente e implemente estes métodos:
    # def get_known_plate_number(self, obj):
    #     if obj.known_plate:
    #         return obj.known_plate.plate_number
    #     return None
    #
    # def get_known_plate_is_regularized(self, obj):
    #     if obj.known_plate:
    #         return obj.known_plate.is_regularized
    #     return None