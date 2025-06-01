from django.contrib import admin
from django.utils.html import format_html # Para exibir imagens
from .models import PlateDetection, DetectedPlate, KnownPlate

@admin.register(PlateDetection)
class PlateDetectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'display_original_image', 'status', 'created_at', 'processed_at')
    list_filter = ('status', 'created_at', 'processed_at', 'user')
    search_fields = ('id', 'user__username', 'error_message')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'processed_at', 'display_original_image_large') # Campos que não devem ser editáveis no detalhe

    def display_original_image(self, obj):
        if obj.original_image:
            return format_html('<img src="{}" width="100" height="auto" />', obj.original_image.url)
        return "Nenhuma imagem"
    display_original_image.short_description = "Imagem Original (Preview)"

    def display_original_image_large(self, obj):
        if obj.original_image:
            return format_html('<img src="{}" width="300" height="auto" />', obj.original_image.url)
        return "Nenhuma imagem"
    display_original_image_large.short_description = "Imagem Original"

    # Se você tiver muitos usuários, pode querer usar raw_id_fields
    # raw_id_fields = ('user',)

@admin.register(KnownPlate)
class KnownPlateAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'is_regularized', 'created_at', 'updated_at')
    list_filter = ('is_regularized', 'created_at', 'updated_at')
    search_fields = ('plate_number', 'details')
    ordering = ('plate_number',)

@admin.register(DetectedPlate)
class DetectedPlateAdmin(admin.ModelAdmin):
    list_display = (
        'plate_number_detected',
        'detection_link', # Link para a detecção pai
        'known_plate_link', # Link para a placa conhecida associada
        'regularization_status_display', # Mostrar o status de regularização
        'yolo_confidence',
        'best_ocr_text',
        'best_ocr_confidence',
        'display_cropped_image',
        'created_at'
    )
    list_filter = (
        'created_at',
        'yolo_confidence',
        'best_ocr_confidence',
        # Para filtrar por status de regularização, precisaremos de um filtro customizado
        # ou filtrar pelos campos 'known_plate__is_regularized' e 'known_plate__isnull'
        ('known_plate__is_regularized', admin.BooleanFieldListFilter), # Filtra placas conhecidas regularizadas/não regularizadas
        ('known_plate', admin.EmptyFieldListFilter), # Filtra se tem uma placa conhecida associada ou não
    )
    search_fields = (
        'plate_number_detected',
        'detection__id',
        'known_plate__plate_number',
        'best_ocr_text'
    )
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'display_cropped_image_large', 'ocr_results') # Campos que não devem ser editáveis no detalhe

    # Para melhorar a performance ao selecionar PlateDetection e KnownPlate
    raw_id_fields = ('detection', 'known_plate')

    def display_cropped_image(self, obj):
        if obj.cropped_image:
            return format_html('<img src="{}" width="100" height="auto" />', obj.cropped_image.url)
        return "Nenhuma imagem"
    display_cropped_image.short_description = "Imagem Recortada (Preview)"

    def display_cropped_image_large(self, obj):
        if obj.cropped_image:
            return format_html('<img src="{}" width="200" height="auto" />', obj.cropped_image.url)
        return "Nenhuma imagem"
    display_cropped_image_large.short_description = "Imagem Recortada"

    def regularization_status_display(self, obj):
        status = obj.regularization_status
        if status == "Regularizada":
            return format_html('<span style="color: green;">{}</span>', status)
        elif status == "Não Regularizada":
            return format_html('<span style="color: red;">{}</span>', status)
        return status
    regularization_status_display.short_description = "Status Regularização"
    regularization_status_display.admin_order_field = 'known_plate__is_regularized' # Permite ordenar por este campo

    def detection_link(self, obj):
        from django.urls import reverse
        link = reverse("admin:backend_platedetection_change", args=[obj.detection.id])
        return format_html('<a href="{}">{}</a>', link, obj.detection.id)
    detection_link.short_description = "Detecção ID"
    detection_link.admin_order_field = 'detection'

    def known_plate_link(self, obj):
        if obj.known_plate:
            from django.urls import reverse
            link = reverse("admin:backend_knownplate_change", args=[obj.known_plate.id])
            return format_html('<a href="{}">{}</a>', link, obj.known_plate.plate_number)
        return "-"
    known_plate_link.short_description = "Placa Conhecida"
    known_plate_link.admin_order_field = 'known_plate'