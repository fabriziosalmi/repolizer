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
        
    Returns:
        str: Il contenuto HTML generato
    """
    # Carica il template HTML
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = Template(f.read())
    except (FileNotFoundError, IOError):
        print(f"Errore: Template non trovato in {template_path}")
        # Fallback to basic template if not found
        template = Template("<html><body><h1>Report</h1><pre>{{ results|tojson(indent=4) }}</pre></body></html>")
    
    # Prepara i dati per il template
    repo_name = results.get('nome_repository', 'N/A')
    
    # Ensure data is properly formatted for charts
    report_data = {
        'repo_name': repo_name,
        'repo_url': results.get('url', f'https://github.com/{repo_name}'),
        'data_analisi': results.get('data_analisi', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        'punteggi': results.get('punteggi', {}),
        'dettagli': results.get('dettagli', {}),
        'suggerimenti': results.get('suggerimenti', {}),
        'punteggio_totale': results.get('punteggio_totale', 0)
    }
    
    # Process historical data to ensure it's in the right format
    storico = results.get('storico', [])
    if isinstance(storico, list):
        # Make sure each item in storico has proper data_analisi and punteggio_totale fields
        processed_storico = []
        for entry in storico:
            if isinstance(entry, dict):
                processed_entry = {
                    'data_analisi': entry.get('data_analisi', 'N/A'),
                    'punteggio_totale': float(entry.get('punteggio_totale', 0)),
                    'punteggi': entry.get('punteggi', {})
                }
                processed_storico.append(processed_entry)
        report_data['storico'] = processed_storico
    else:
        report_data['storico'] = []
    
    # Assicurati che il punteggio totale sia un numero
    try:
        report_data['punteggio_totale'] = float(report_data['punteggio_totale'])
    except (ValueError, TypeError):
        report_data['punteggio_totale'] = 0
    
    # Calcola la percentuale per la visualizzazione della barra di progresso
    report_data['punteggio_totale_percentuale'] = report_data['punteggio_totale'] * 10
    
    # Genera l'HTML
    try:
        html_content = template.render(
            report_data=report_data,
            **report_data
        )
    except Exception as e:
        print(f"Errore nella generazione del report HTML: {e}")
        html_content = f"<html><body><h1>Errore nella generazione del report</h1><p>{str(e)}</p></body></html>"
    
    # Se è specificato un file di output, salva il report
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"Report HTML salvato in: {output_file}")
        except Exception as e:
            print(f"Errore nel salvataggio del report HTML: {e}")
            
    return html_content