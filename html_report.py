#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generatore di report HTML per Repolizer."""

import os
import json
from datetime import datetime
from jinja2 import Template

def generate_html_report(results, output_file=None):
    """Genera un report HTML dai risultati dell'analisi.

    Args:
        results: Dizionario con i risultati dell'analisi
        output_file: Percorso del file di output HTML (opzionale)
    """
    # Carica il template HTML
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = Template(f.read())
    
    # Prepara i dati per il template
    repo_name = results.get('nome_repository', 'N/A')
    
    report_data = {
        'repo_name': repo_name,
        'repo_url': results.get('url', f'https://github.com/{repo_name}'),
        'data_analisi': results.get('data_analisi', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        'punteggi': results.get('punteggi', {}),
        'dettagli': results.get('dettagli', {}),
        'suggerimenti': results.get('suggerimenti', {}),
        'storico': results.get('storico', []),
        'punteggio_totale': results.get('punteggio_totale', 0)
    }
    
    # Assicurati che il punteggio totale sia un numero
    try:
        report_data['punteggio_totale'] = float(report_data['punteggio_totale'])
    except (ValueError, TypeError):
        report_data['punteggio_totale'] = 0
    
    # Calcola la percentuale per la visualizzazione della barra di progresso
    report_data['punteggio_totale_percentuale'] = report_data['punteggio_totale'] * 10
    
    # Genera l'HTML
    html_content = template.render(
        report_data=report_data,
        **report_data
    )
    
    # Se non è specificato un file di output, usa il nome del repository
    if not output_file:
        output_file = f"{repo_name.replace('/', '_')}_report.html"
    
    # Salva il report HTML
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_file