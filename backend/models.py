from django.db import models
from django.contrib.auth.models import User
import uuid


class PlateDetection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    original_image = models.ImageField(upload_to='uploads/')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('completed', 'Concluído'),
        ('error', 'Erro')
    ], default='pending')
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']


class DetectedPlate(models.Model):
    detection = models.ForeignKey(PlateDetection, on_delete=models.CASCADE, related_name='plates')
    plate_number = models.IntegerField()  # Número sequencial da placa na imagem
    bounding_box = models.JSONField()  # {x1, y1, x2, y2}
    yolo_confidence = models.FloatField()
    cropped_image = models.ImageField(upload_to='plates/cropped/')
    best_ocr_text = models.CharField(max_length=20, blank=True)
    best_ocr_confidence = models.FloatField(null=True, blank=True)
    ocr_results = models.JSONField(default=dict)  # Todos os resultados OCR
    created_at = models.DateTimeField(auto_now_add=True)