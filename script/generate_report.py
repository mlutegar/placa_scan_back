import os
import django
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import io
import pandas as pd
from pathlib import Path

# Configura o ambiente Django
# ESTA LINHA DEVE SER EXECUTADA DENTRO DO SEU AMBIENTE DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'projeto_veicular_back.settings')
django.setup()

from backend.models import DetectedPlate, KnownPlate

def create_bar_chart(data, title, filename, save_path=None):
    """Cria um gráfico de barras, salva como imagem e retorna um buffer de memória."""
    labels = [item[0] for item in data]
    values = [item[1] for item in data]

    plt.figure(figsize=(10, 6))
    plt.bar(labels, values, color='skyblue')
    plt.xlabel('Combinação/Método')
    plt.ylabel('Porcentagem de Acerto (%)')
    plt.title(title)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Salva o gráfico no caminho especificado, se fornecido
    if save_path:
        plt.savefig(save_path, format='png')
        print(f"Gráfico salvo em: {save_path}")

    # Salva o gráfico em um buffer de memória para o PDF
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

def generate_ocr_accuracy_report(output_pdf_filename="relatorio_ocr_acuracia.pdf",
                                  graphs_dir="graphs", data_dir="data"):
    """
    Gera um relatório de porcentagem de acerto para cada combinação de método e threshold dos resultados OCR,
    exporta para um arquivo PDF com gráficos, e salva gráficos e tabelas de resultados em pastas específicas.
    """
    # Criar diretórios se não existirem
    Path(graphs_dir).mkdir(parents=True, exist_ok=True)
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    total_detections_with_known_plate = 0
    combination_metrics = defaultdict(lambda: {'correct': 0, 'total': 0})
    method_metrics = defaultdict(lambda: {'correct': 0, 'total': 0})

    for detected_plate in DetectedPlate.objects.all():
        if detected_plate.known_plate and detected_plate.known_plate.plate_number:
            total_detections_with_known_plate += 1
            correct_plate = detected_plate.known_plate.plate_number.strip().upper()

            for ocr_result in detected_plate.ocr_results:
                method = ocr_result.get('method')
                threshold = ocr_result.get('threshold')
                ocr_text = ocr_result.get('text')

                if method and ocr_text is not None:
                    normalized_ocr_text = ocr_text.strip().upper()

                    # Métricas por combinação (método + threshold)
                    combination_key = f"{method}_threshold_{threshold}"
                    combination_metrics[combination_key]['total'] += 1
                    if normalized_ocr_text == correct_plate:
                        combination_metrics[combination_key]['correct'] += 1

                    # Métricas por método (ignora o threshold para esta contagem)
                    method_metrics[method]['total'] += 1
                    if normalized_ocr_text == correct_plate:
                        method_metrics[method]['correct'] += 1

    # Preparar dados para o PDF e para as tabelas/gráficos
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<h1>Relatório de Acerto de OCR</h1>", styles['h1']))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph(f"Total de detecções com placas conhecidas: <b>{total_detections_with_known_plate}</b>", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # --- Relatório de Acerto por Combinação ---
    story.append(Paragraph("<h2>Relatório de Acerto por Combinação (Método + Threshold)</h2>", styles['h2']))
    story.append(Spacer(1, 0.1 * inch))

    combination_data_for_chart = []
    combination_data_for_table = []

    sorted_combinations = sorted(combination_metrics.items(), key=lambda item: item[0])
    for combo, metrics in sorted_combinations:
        accuracy = (metrics['correct'] / metrics['total'] * 100) if metrics['total'] > 0 else 0
        story.append(Paragraph(f"<b>Combinação:</b> {combo}", styles['Normal']))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Acertos: {metrics['correct']}", styles['Normal']))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Total de OCRs para esta combinação: {metrics['total']}", styles['Normal']))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Porcentagem de Acerto: {accuracy:.2f}%", styles['Normal']))
        story.append(Spacer(1, 0.1 * inch))
        combination_data_for_chart.append((combo, accuracy))
        combination_data_for_table.append({'Combinação': combo, 'Acertos': metrics['correct'], 'Total': metrics['total'], 'Porcentagem de Acerto': accuracy})

    # Gerar e salvar gráfico de acurácia por combinação
    if combination_data_for_chart:
        chart_path_combo = Path(graphs_dir) / "combination_accuracy.png"
        chart_buffer_combo = create_bar_chart(combination_data_for_chart, "Porcentagem de Acerto por Combinação", "combination_accuracy.png", save_path=chart_path_combo)
        story.append(ReportLabImage(chart_buffer_combo, width=6 * inch, height=4 * inch))
        story.append(Spacer(1, 0.2 * inch))

    # Salvar tabela de acurácia por combinação
    if combination_data_for_table:
        df_combinations = pd.DataFrame(combination_data_for_table)
        table_path_combo = Path(data_dir) / "combination_accuracy.csv"
        df_combinations.to_csv(table_path_combo, index=False)
        print(f"Tabela de combinações salva em: {table_path_combo}")

    # --- Relatório de Acerto por Método ---
    story.append(Paragraph("<h2>Relatório de Acerto por Método</h2>", styles['h2']))
    story.append(Spacer(1, 0.1 * inch))

    method_data_for_chart = []
    method_data_for_table = []

    sorted_methods = sorted(method_metrics.items(), key=lambda item: item[0])
    for method, metrics in sorted_methods:
        accuracy = (metrics['correct'] / metrics['total'] * 100) if metrics['total'] > 0 else 0
        story.append(Paragraph(f"<b>Método:</b> {method}", styles['Normal']))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Acertos: {metrics['correct']}", styles['Normal']))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Total de OCRs para este método: {metrics['total']}", styles['Normal']))
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Porcentagem de Acerto: {accuracy:.2f}%", styles['Normal']))
        story.append(Spacer(1, 0.1 * inch))
        method_data_for_chart.append((method, accuracy))
        method_data_for_table.append({'Método': method, 'Acertos': metrics['correct'], 'Total': metrics['total'], 'Porcentagem de Acerto': accuracy})

    # Gerar e salvar gráfico de acurácia por método
    if method_data_for_chart:
        chart_path_method = Path(graphs_dir) / "method_accuracy.png"
        chart_buffer_method = create_bar_chart(method_data_for_chart, "Porcentagem de Acerto por Método", "method_accuracy.png", save_path=chart_path_method)
        story.append(ReportLabImage(chart_buffer_method, width=6 * inch, height=4 * inch))
        story.append(Spacer(1, 0.2 * inch))

    # Salvar tabela de acurácia por método
    if method_data_for_table:
        df_methods = pd.DataFrame(method_data_for_table)
        table_path_method = Path(data_dir) / "method_accuracy.csv"
        df_methods.to_csv(table_path_method, index=False)
        print(f"Tabela de métodos salva em: {table_path_method}")

    # --- Resumo Final ---
    best_method = None
    max_method_accuracy = -1
    for method, metrics in method_metrics.items():
        accuracy = (metrics['correct'] / metrics['total'] * 100) if metrics['total'] > 0 else 0
        if accuracy > max_method_accuracy:
            max_method_accuracy = accuracy
            best_method = method

    if best_method:
        story.append(Paragraph(f"<h3>O método com maior porcentagem de acerto é: <b>{best_method}</b> com <b>{max_method_accuracy:.2f}%</b> de acerto.</h3>", styles['h3']))
    else:
        story.append(Paragraph("<h3>Não foi possível determinar o melhor método.</h3>", styles['h3']))
    story.append(Spacer(1, 0.1 * inch))

    best_combination = None
    max_combination_accuracy = -1
    for combo, metrics in combination_metrics.items():
        accuracy = (metrics['correct'] / metrics['total'] * 100) if metrics['total'] > 0 else 0
        if accuracy > max_combination_accuracy:
            max_combination_accuracy = accuracy
            best_combination = combo

    if best_combination:
        story.append(Paragraph(f"<h3>A combinação (método + threshold) com maior porcentagem de acerto é: <b>{best_combination}</b> com <b>{max_combination_accuracy:.2f}%</b> de acerto.</h3>", styles['h3']))
    else:
        story.append(Paragraph("<h3>Não foi possível determinar a melhor combinação.</h3>", styles['h3']))

    # Gerar o PDF
    doc = SimpleDocTemplate(output_pdf_filename, pagesize=letter)
    doc.build(story)
    print(f"\nRelatório PDF gerado com sucesso em: {output_pdf_filename}")

if __name__ == '__main__':
    generate_ocr_accuracy_report()