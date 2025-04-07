#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generatore di report HTML per Repolizer."""

import os
import json
from datetime import datetime
from jinja2 import Template
from typing import Dict, Any

# Import the category mapping from repolizer.py
try:
    from repolizer import CATEGORY_LABELS_MAPPING
except ImportError:
    # Fallback mapping if the import fails
    CATEGORY_LABELS_MAPPING = {
        "attivita_manutenzione": "Manutenzione",
        "community_collaborazione": "Collaborazione",
        "documentazione": "Documentazione",
        "popolarita_impatto": "Distribuzione",
        "qualita_codice": "Codice",
        "setup_usabilita": "Adozione",
        "sicurezza": "Sicurezza",
        "testing_cicd": "Integrazione"
    }

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
    
    # Map category names using CATEGORY_LABELS_MAPPING
    punteggi = {}
    dettagli = {}
    suggerimenti = {}
    
    # Map scores
    for categoria, punteggio in results.get('punteggi', {}).items():
        display_name = CATEGORY_LABELS_MAPPING.get(categoria, categoria)
        punteggi[display_name] = punteggio
    
    # Map details
    for categoria, dettaglio in results.get('dettagli', {}).items():
        display_name = CATEGORY_LABELS_MAPPING.get(categoria, categoria)
        dettagli[display_name] = dettaglio
    
    # Map suggestions
    for categoria, sugg in results.get('suggerimenti', {}).items():
        display_name = CATEGORY_LABELS_MAPPING.get(categoria, categoria)
        suggerimenti[display_name] = sugg
    
    # Ensure data is properly formatted for charts
    report_data = {
        'repo_name': repo_name,
        'repo_url': results.get('url', f'https://github.com/{repo_name}'),
        'data_analisi': results.get('data_analisi', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        'punteggi': punteggi,
        'dettagli': dettagli,
        'suggerimenti': suggerimenti,
        'punteggio_totale': results.get('punteggio_totale', 0),
        'category_mapping': CATEGORY_LABELS_MAPPING  # Pass mapping to template
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

def generate_html_report(report_data: Dict[str, Any]) -> str:
    """Genera un report HTML basato sui dati forniti.
    
    Args:
        report_data: Dizionario contenente i dati del report
        
    Returns:
        Contenuto HTML del report
    """
    # Calculate percentage for the total score
    report_data["punteggio_totale_percentuale"] = report_data.get("punteggio_totale", 0) * 10
    
    # Add timestamp formatting for the report
    if "data_analisi" in report_data:
        report_data["data_analisi_formatted"] = report_data["data_analisi"]
    
    # Process scores to ensure proper NA handling for the UI display
    for categoria, parametri in report_data.get("dettagli", {}).items():
        for nome_param, info in parametri.items():
            # Ensure score_is_na is set for all parameters
            if "score_is_na" not in info:
                info["score_is_na"] = info["punteggio"] is None
    
    # Load the template
    template_path = os.path.join(os.path.dirname(__file__), "templates", "report_template.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        return "<html><body><p>Template HTML non trovato. Assicurati che il file templates/report_template.html esista.</p></body></html>"
    
    # Replace variables in the template
    html_content = template
    html_content = html_content.replace("{{repo_name}}", report_data.get("nome_repository", "Repository"))
    html_content = html_content.replace("{{repo_url}}", report_data.get("url", "#"))
    html_content = html_content.replace("{{data_analisi}}", report_data.get("data_analisi_formatted", ""))
    html_content = html_content.replace("{{punteggio_totale}}", str(report_data.get("punteggio_totale", "N/A")))
    html_content = html_content.replace("{{report_data|tojson}}", json.dumps(report_data))
    
    return html_content