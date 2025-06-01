from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'detections', views.PlateDetectionViewSet)
router.register(r'detected-plates', views.DetectedPlateViewSet)

urlpatterns = [] + router.urls