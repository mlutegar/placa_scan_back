import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def char_position_accuracy(df):
    pos_matches = {i: 0 for i in range(7)}
    pos_totals = {i: 0 for i in range(7)}
    
    for _, row in df.iterrows():
        gt = str(row['plate'])
        ocr = str(row['ocr_output']) if pd.notna(row['ocr_output']) else ""
        
        for i in range(min(len(gt), 7)):
            pos_totals[i] += 1
            if i < len(ocr) and ocr[i] == gt[i]:
                pos_matches[i] += 1
                
    accuracies = {i: (pos_matches[i] / pos_totals[i]) * 100 if pos_totals[i] > 0 else 0 for i in range(7)}
    return accuracies

def run_analysis():
    # 1. Load Data
    df = pd.read_csv('benchmark_results.csv')
    
    # 2. Calculate Metrics
    # Acurácia full-plate por método (Melhor Threshold)
    method_thresh_acc = df.groupby(['method', 'threshold'])['full_match'].mean() * 100
    method_best_acc = method_thresh_acc.groupby('method').max().sort_values(ascending=False)
    
    # Top 10 combinations
    top_10 = method_thresh_acc.sort_values(ascending=False).head(10)
    
    # Acurácia por Threshold (Geral)
    thresh_acc = df.groupby('threshold')['full_match'].mean() * 100
    
    # Acurácia por posição de caractere
    pos_acc = char_position_accuracy(df)
    
    # 3. Generate Charts
    # Gráfico 1: Acurácia por Método (Best Threshold)
    plt.figure(figsize=(10, 6))
    method_best_acc.plot(kind='bar', color='skyblue', edgecolor='black')
    plt.title('Melhor Acurácia Full-Plate por Método (ML Kit On-Device)')
    plt.ylabel('Acurácia (%)')
    plt.xlabel('Método de Pré-processamento')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('accuracy_by_method.pdf')
    plt.close()
    
    # Gráfico 2: Impacto do Threshold
    plt.figure(figsize=(8, 5))
    thresh_acc.plot(kind='line', marker='o', color='purple', linewidth=2)
    plt.title('Impacto do Limiar de Confiança (Threshold)')
    plt.ylabel('Acurácia (%)')
    plt.xlabel('Threshold')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig('accuracy_by_threshold.pdf')
    plt.close()
    
    # Gráfico 3: Posição do Caractere
    plt.figure(figsize=(8, 5))
    positions = list(pos_acc.keys())
    accs = list(pos_acc.values())
    plt.bar(positions, accs, color='lightgreen', edgecolor='black')
    plt.title('Acurácia por Posição do Caractere')
    plt.ylabel('Acurácia (%)')
    plt.xlabel('Posição (Index)')
    for i, v in enumerate(accs):
        plt.text(i, v + 1, f"{v:.1f}%", ha='center')
    plt.tight_layout()
    plt.savefig('accuracy_by_position.pdf')
    plt.close()
    
    # 4. Generate LaTeX Tables
    with open('tables.tex', 'w') as f:
        f.write("% Tabela 1: Comparativo CBIC (Tesseract) vs WVC2026 (ML Kit)\n")
        f.write("\\begin{table}[h]\n\\centering\n")
        f.write("\\caption{Comparativo de Acurácia: Tesseract OCR (Desktop) vs ML Kit (On-Device)}\n")
        f.write("\\label{tab:comparative}\n")
        f.write("\\begin{tabular}{|l|c|c|}\n\\hline\n")
        f.write("\\textbf{Métrica} & \\textbf{Tesseract (CBIC2025)} & \\textbf{ML Kit (WVC2026)} \\\\ \\hline\n")
        f.write(f"Melhor Método (Full-Plate) & Resized2x (66.7\\%) & {method_best_acc.index[0].capitalize()} ({method_best_acc.iloc[0]:.1f}\\%) \\\\\n")
        f.write(f"Inverted (Full-Plate) & 11.8\\% & {method_best_acc.get('inverted', 0):.1f}\\% \\\\\n")
        f.write(f"Posição 0 (1º char) & 40.5\\% & {pos_acc[0]:.1f}\\% \\\\\n")
        f.write(f"Posição 6 (Último char) & 20.6\\% & {pos_acc[6]:.1f}\\% \\\\\n")
        
        # Overall character accuracy vs Tesseract (26.8%)
        overall_char_acc = df['char_accuracy'].mean() * 100
        overall_full_acc = df['full_match'].mean() * 100
        
        f.write(f"Acurácia Geral Caractere & 26.8\\% & {overall_char_acc:.1f}\\% \\\\\n")
        f.write(f"Acurácia Geral Placa & 3.1\\% & {overall_full_acc:.1f}\\% \\\\ \\hline\n")
        f.write("\\end{tabular}\n\\end{table}\n\n")
        
        f.write("% Tabela 2: Top 10 Combinações (ML Kit)\n")
        f.write("\\begin{table}[h]\n\\centering\n")
        f.write("\\caption{Top 10 Combinações de Pré-processamento e Threshold (ML Kit)}\n")
        f.write("\\label{tab:top10}\n")
        f.write("\\begin{tabular}{|l|c|c|}\n\\hline\n")
        f.write("\\textbf{Método} & \\textbf{Threshold} & \\textbf{Acurácia Full-Plate (\\%)} \\\\ \\hline\n")
        for (method, thresh), acc in top_10.items():
            f.write(f"{method.capitalize()} & {thresh} & {acc:.1f}\\% \\\\\n")
        f.write("\\hline\n\\end{tabular}\n\\end{table}\n")
        
    print("Análise concluída. Arquivos gerados:")
    print("- accuracy_by_method.pdf")
    print("- accuracy_by_threshold.pdf")
    print("- accuracy_by_position.pdf")
    print("- tables.tex")

if __name__ == '__main__':
    run_analysis()
