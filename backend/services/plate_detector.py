import cv2
import numpy as np
import os
import json
import logging
from typing import List, Dict, Tuple, Optional
from ultralytics import YOLO
import easyocr
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from io import BytesIO
import uuid

logger = logging.getLogger(__name__)


class PlateDetectorService:
    def __init__(self):
        self.model = None
        self.reader = None
        self._initialize_models()

    def _initialize_models(self):
        """Inicializa os modelos YOLO e EasyOCR"""
        try:
            # Inicializar YOLO
            logger.info("Carregando modelo YOLO...")
            self.model = YOLO(settings.YOLO_MODEL_PATH)
            logger.info("✓ Modelo YOLO carregado com sucesso")

            # Inicializar EasyOCR
            logger.info("Inicializando EasyOCR...")
            self.reader = easyocr.Reader(settings.EASYOCR_LANGUAGES)
            logger.info("✓ EasyOCR inicializado com sucesso")

        except Exception as e:
            logger.error(f"Erro ao inicializar modelos: {e}")
            raise

    def detect_plates(self, image_path: str) -> List[Dict]:
        """
        Detecta placas em uma imagem usando YOLO

        Args:
            image_path: Caminho para a imagem

        Returns:
            Lista de dicionários com informações das placas detectadas
        """
        # Carregar imagem
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Não foi possível carregar a imagem: {image_path}")

        # Executar detecção YOLO
        results = self.model(image)

        detected_plates = []

        for result_idx, result in enumerate(results):
            boxes = result.boxes

            if len(boxes) == 0:
                continue

            for plate_idx, box in enumerate(boxes):
                try:
                    # Extrair coordenadas
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    confidence = float(box.conf[0])

                    # Adicionar padding
                    padding = 5
                    y1_pad = max(0, y1 - padding)
                    y2_pad = min(image.shape[0], y2 + padding)
                    x1_pad = max(0, x1 - padding)
                    x2_pad = min(image.shape[1], x2 + padding)

                    # Cortar placa
                    cropped_plate = image[y1_pad:y2_pad, x1_pad:x2_pad].copy()

                    if cropped_plate.size == 0:
                        continue

                    detected_plates.append({
                        'plate_number': len(detected_plates) + 1,
                        'bounding_box': {
                            'x1': int(x1), 'y1': int(y1),
                            'x2': int(x2), 'y2': int(y2)
                        },
                        'confidence': confidence,
                        'cropped_image': cropped_plate
                    })

                except Exception as e:
                    logger.error(f"Erro ao processar placa {plate_idx}: {e}")
                    continue

        return detected_plates

    def preprocess_images(self, image: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """
        Aplica diferentes técnicas de pré-processamento na imagem

        Args:
            image: Imagem original

        Returns:
            Lista de tuplas (descrição, imagem_processada)
        """
        processed_images = []

        # Original
        processed_images.append(("Original", image))

        # Escala de cinza
        gray_plate = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        processed_images.append(("Grayscale", gray_plate))

        # Limiarização Otsu
        _, otsu_thresh = cv2.threshold(gray_plate, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(("Otsu", otsu_thresh))

        # Limiarização adaptativa
        adaptive_thresh = cv2.adaptiveThreshold(
            gray_plate, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        processed_images.append(("Adaptive", adaptive_thresh))

        # Filtro bilateral
        bilateral = cv2.bilateralFilter(gray_plate, 11, 17, 17)
        processed_images.append(("Bilateral", bilateral))

        # Nitidez
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(gray_plate, -1, kernel)
        processed_images.append(("Sharpened", sharpened))

        # Redimensionado 2x
        height, width = gray_plate.shape
        resized2x = cv2.resize(gray_plate, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
        processed_images.append(("Resized2x", resized2x))

        # Invertido
        inverted = cv2.bitwise_not(gray_plate)
        processed_images.append(("Inverted", inverted))

        return processed_images

    def run_ocr_with_thresholds(self, image: np.ndarray, thresholds: List[float] = None) -> Tuple[Dict, List]:
        """
        Executa OCR com diferentes limiares de confiança

        Args:
            image: Imagem para OCR
            thresholds: Lista de limiares de confiança

        Returns:
            Tupla (resultados_por_limiar, resultados_brutos)
        """
        if thresholds is None:
            thresholds = settings.CONFIDENCE_THRESHOLDS

        # Resultados brutos do EasyOCR
        raw_results = self.reader.readtext(image)

        threshold_results = {}

        for threshold in thresholds:
            # Filtrar por score de confiança
            filtered_results = [res for res in raw_results if res[2] >= threshold]

            if filtered_results:
                texts = []
                for bbox, text, score in filtered_results:
                    # Limpar texto (apenas alfanuméricos)
                    clean_text = ''.join(c for c in text if c.isalnum())
                    if clean_text:
                        texts.append((clean_text, score))

                if texts:
                    # Ordenar por confiança
                    texts.sort(key=lambda x: x[1], reverse=True)
                    combined_text = ''.join([t[0] for t in texts])

                    threshold_results[threshold] = {
                        'combined_text': combined_text,
                        'text_details': texts,
                        'raw_detections': filtered_results
                    }

        return threshold_results, raw_results

    def process_plate_ocr(self, cropped_plate: np.ndarray) -> Dict:
        """
        Processa OCR em uma placa cortada

        Args:
            cropped_plate: Imagem da placa cortada

        Returns:
            Dicionário com resultados do OCR
        """
        # Aplicar pré-processamento
        processed_images = self.preprocess_images(cropped_plate)

        all_results = []

        for desc, img in processed_images:
            try:
                threshold_results, raw_results = self.run_ocr_with_thresholds(img)

                for threshold, results in threshold_results.items():
                    combined_text = results['combined_text']
                    text_details = results['text_details']

                    all_results.append({
                        'method': desc,
                        'threshold': threshold,
                        'text': combined_text,
                        'details': text_details
                    })

            except Exception as e:
                logger.error(f"Erro no OCR com método {desc}: {e}")
                continue

        # Encontrar melhor resultado
        best_text = ""
        best_confidence = 0.0

        for result in all_results:
            if result['details']:
                avg_confidence = sum(conf for _, conf in result['details']) / len(result['details'])
                text_length = len(result['text'])

                # Priorizar texto mais longo ou maior confiança
                if (text_length > len(best_text)) or \
                        (text_length == len(best_text) and avg_confidence > best_confidence):
                    best_text = result['text']
                    best_confidence = avg_confidence

        return {
            'best_text': best_text,
            'best_confidence': best_confidence,
            'all_results': all_results
        }

    def save_cropped_plate(self, cropped_plate: np.ndarray, filename: str) -> str:
        """
        Salva uma imagem de placa cortada

        Args:
            cropped_plate: Imagem da placa
            filename: Nome do arquivo

        Returns:
            Caminho do arquivo salvo
        """
        # Converter para bytes
        is_success, buffer = cv2.imencode(".jpg", cropped_plate)
        if not is_success:
            raise ValueError("Erro ao codificar imagem")

        # Criar arquivo Django
        image_file = ContentFile(buffer.tobytes(), name=filename)

        return image_file