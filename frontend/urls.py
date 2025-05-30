from django.urls import path
from . import views

urlpatterns = [
    path('', views.WebcamDetectorView.as_view(), name='webcam'),
    path('cameras/', views.CameraConfigView.as_view(), name='camera_config'),
    path('history/', views.DetectionHistoryView.as_view(), name='detection_history'),
]