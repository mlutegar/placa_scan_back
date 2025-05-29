from rest_framework import serializers
from .models import PlateDetection, DetectedPlate


class PlateDetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlateDetection
        fields = ['id', 'original_image', 'created_at', 'processed_at', 'status', 'error_message']
        read_only_fields = ['id', 'created_at', 'processed_at', 'status', 'error_message']


class DetectedPlateSerializer(serializers.ModelSerializer):
    cropped_image_url = serializers.SerializerMethodField()

    class Meta:
        model = DetectedPlate
        fields = [
            'id', 'plate_number', 'bounding_box', 'yolo_confidence',
            'cropped_image_url', 'best_ocr_text', 'best_ocr_confidence',
            'ocr_results', 'created_at'
        ]

    def get_cropped_image_url(self, obj):
        if obj.cropped_image:
            return obj.cropped_image.url
        return None