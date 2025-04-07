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
    report_data = {
        'repo_name': results['nome_repository'],
        'repo_url': results['url'],
        'data_analisi': results['data_analisi'],
        'punteggi': results['punteggi'],
        'dettagli': results['dettagli'],
        'suggerimenti': results['suggerimenti'],
        'storico': results.get('storico', []),
        'punteggio_totale': round(sum(results['punteggi'].values()) / len(results['punteggi']), 2),
        'punteggio_totale_percentuale': round((sum(results['punteggi'].values()) / len(results['punteggi'])) * 10, 2)
    }
    
    # Genera l'HTML
    html_content = template.render(
        report_data=report_data,
        **report_data
    )
    
    # Se non è specificato un file di output, usa il nome del repository
    if not output_file:
        output_file = f"{results['nome_repository'].replace('/', '_')}_report.html"
    
    # Salva il report HTML
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_file