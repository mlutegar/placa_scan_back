import cv2
import numpy as np
import pytesseract
from PIL import Image
import logging
from typing import List, Dict, Tuple
from ultralytics import YOLO
import easyocr
from django.conf import settings
from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


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

    def process_plate_ocr_fast(self, cropped_plate: np.ndarray) -> Dict:
        """
        Versão rápida do OCR - apenas grayscale + melhor threshold
        """
        try:
            # Apenas processamento básico para velocidade
            gray_plate = cv2.cvtColor(cropped_plate, cv2.COLOR_BGR2GRAY)

            # OCR direto
            raw_results = self.reader.readtext(gray_plate)

            best_text = ""
            best_confidence = 0.0

            for bbox, text, score in raw_results:
                if score > 0.3:  # Threshold mínimo
                    clean_text = ''.join(c for c in text if c.isalnum())
                    if len(clean_text) > len(best_text) or score > best_confidence:
                        best_text = clean_text
                        best_confidence = score

            return {
                'best_text': best_text,
                'best_confidence': best_confidence
            }

        except Exception as e:
            return {'best_text': '', 'best_confidence': 0.0}

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

    def detect_plates_from_array(self, image_array):
        """
        Detecta placas diretamente de um array numpy sem salvar arquivo temporário
        Args:
            image_array: Array numpy da imagem (formato BGR do OpenCV)
        Returns:
            Lista de dicionários com informações das placas detectadas
        """
        try:
            # Executar detecção YOLO diretamente no array
            results = self.model(image_array)

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
                        y2_pad = min(image_array.shape[0], y2 + padding)
                        x1_pad = max(0, x1 - padding)
                        x2_pad = min(image_array.shape[1], x2 + padding)

                        # Cortar placa
                        cropped_plate = image_array[y1_pad:y2_pad, x1_pad:x2_pad].copy()

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

        except Exception as e:
            logger.error(f"Erro na detecção de placas do array: {e}")
            return []

    def process_plate_ocr_fast(self, cropped_image):
        """
        Versão otimizada do OCR para processamento em tempo real

        Args:
            cropped_image: Imagem recortada da placa

        Returns:
            Dicionário com o melhor texto e confiança
        """
        try:
            # Converter de BGR para RGB se necessário
            if len(cropped_image.shape) == 3:
                rgb_image = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = cropped_image

            # Pré-processamento para melhorar OCR
            processed_image = self.preprocess_for_ocr(rgb_image)

            # Configuração do Tesseract para placas brasileiras
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

            # Executar OCR
            text = pytesseract.image_to_string(
                Image.fromarray(processed_image),
                config=custom_config
            ).strip()

            # Calcular confiança (implementação simplificada)
            confidence_data = pytesseract.image_to_data(
                Image.fromarray(processed_image),
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )

            # Calcular confiança média
            confidences = [int(conf) for conf in confidence_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            return {
                'best_text': text,
                'best_confidence': avg_confidence
            }

        except Exception as e:
            print(f"Erro no OCR rápido: {e}")
            return {
                'best_text': '',
                'best_confidence': 0.0
            }

    def preprocess_for_ocr(self, image):
        """
        Pré-processamento da imagem para melhorar o OCR

        Args:
            image: Imagem RGB

        Returns:
            Imagem pré-processada
        """
        try:
            # Converter para escala de cinza
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image

            # Redimensionar se muito pequena
            height, width = gray.shape
            if width < 200:
                scale_factor = 200 / width
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

            # Aplicar filtro bilateral para reduzir ruído mantendo bordas
            gray = cv2.bilateralFilter(gray, 9, 75, 75)

            # Aplicar threshold adaptativo
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            # Operações morfológicas para limpar a imagem
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            return thresh

        except Exception as e:
            print(f"Erro no pré-processamento: {e}")
            return image

    def validate_plate_text(self, text):
        """
        Valida se o texto detectado segue o padrão de placas brasileiras

        Args:
            text: Texto detectado pelo OCR

        Returns:
            Tuple (is_valid, formatted_text, plate_type)
        """
        import re

        # Remover espaços e caracteres especiais
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())

        # Padrão antigo: ABC1234
        old_pattern = r'^[A-Z]{3}[0-9]{4}$'

        # Padrão Mercosul: ABC1D23
        mercosul_pattern = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'

        if re.match(old_pattern, clean_text):
            formatted = f"{clean_text[:3]}-{clean_text[3:]}"
            return True, formatted, "old"
        elif re.match(mercosul_pattern, clean_text):
            formatted = f"{clean_text[:3]}{clean_text[3]}{clean_text[4]}{clean_text[5:]}"
            return True, formatted, "mercosul"
        else:
            return False, clean_text, "unknown"