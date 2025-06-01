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


class KnownPlate(models.Model):
    plate_number = models.CharField(max_length=20, unique=True, verbose_name="Número da Placa")
    is_regularized = models.BooleanField(default=True, verbose_name="Regularizada")
    details = models.TextField(blank=True, null=True, verbose_name="Detalhes Adicionais") # Opcional: para adicionar mais informações sobre a placa
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.plate_number} - {'Regularizada' if self.is_regularized else 'Não Regularizada'}"

    class Meta:
        verbose_name = "Placa Conhecida"
        verbose_name_plural = "Placas Conhecidas"
        ordering = ['plate_number']


class DetectedPlate(models.Model):
    detection = models.ForeignKey(PlateDetection, on_delete=models.CASCADE, related_name='plates')
    plate_number_detected = models.CharField(max_length=20, verbose_name="Número da Placa Detectada") # Antigo plate_number
    known_plate = models.ForeignKey(KnownPlate, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="Placa Conhecida Associada")
    bounding_box = models.JSONField()  # {x1, y1, x2, y2}
    yolo_confidence = models.FloatField()
    cropped_image = models.ImageField(upload_to='plates/cropped/')
    best_ocr_text = models.CharField(max_length=20, blank=True)
    best_ocr_confidence = models.FloatField(null=True, blank=True)
    ocr_results = models.JSONField(default=dict)  # Todos os resultados OCR
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def regularization_status(self):
        if self.known_plate:
            return "Regularizada" if self.known_plate.is_regularized else "Não Regularizada"
        return "Desconhecida"

    def __str__(self):
        return f"{self.plate_number_detected} - {self.regularization_status}"