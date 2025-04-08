#!/usr/bin/env python3

import os
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import unittest

# Import the module to test
from html_report import generate_html_report, CATEGORY_LABELS_MAPPING

@pytest.fixture
def sample_results():
    """Fixture to provide sample results for testing."""
    return {
        "nome_repository": "test/repo",
        "url": "https://github.com/test/repo",
        "data_analisi": "2023-01-01 12:00:00",
        "punteggi": {
            "manutenzione": 8.5,
            "collaborazione": 7.0,
            "documentazione": 9.0,
            "distribuzione": 6.5,
            "codice": 7.5,
            "adozione": 8.0,
            "sicurezza": 9.5,
            "integrazione": 7.0
        },
        "dettagli": {
            "manutenzione": {
                "data_ultimo_commit": {"valore": "10 giorni fa", "punteggio": 9.0, "peso": 1, "descrizione": "Data dell'ultimo commit", "conta_punteggio": True, "score_is_na": False},
                "frequenza_commit": {"valore": "0.5 commit/giorno", "punteggio": 7.0, "peso": 1, "descrizione": "Frequenza dei commit", "conta_punteggio": True, "score_is_na": False}
            },
            "codice": {
                "complessita_media": {"valore": "Media complessità", "punteggio": 8.0, "peso": 1, "descrizione": "Complessità media del codice", "conta_punteggio": True, "score_is_na": False}
            }
        },
        "suggerimenti": {
            "manutenzione": ["Aumenta la frequenza dei commit."],
            "codice": ["Migliora la complessità del codice."]
        },
        "punteggio_totale": 7.5,
        "storico": [
            {"data_analisi": "2022-12-01 12:00:00", "punteggio_totale": 7.0, "punteggi": {"manutenzione": 7.0, "codice": 7.0}},
            {"data_analisi": "2022-11-01 12:00:00", "punteggio_totale": 6.5, "punteggi": {"manutenzione": 6.0, "codice": 6.0}}
        ]
    }

def test_generate_html_report_basic(sample_results):
    """Test basic HTML report generation."""
    html_content = generate_html_report(sample_results)
    assert "<html>" in html_content
    assert "<head>" in html_content
    assert "<body>" in html_content
    assert "test/repo" in html_content
    assert "2023-01-01 12:00:00" in html_content
    assert "7.5" in html_content

def test_generate_html_report_with_scores(sample_results):
    """Test HTML report generation with scores."""
    html_content = generate_html_report(sample_results)
    assert "Manutenzione" in html_content
    assert "8.5" in html_content
    assert "Collaborazione" in html_content
    assert "7.0" in html_content
    assert "Documentazione" in html_content
    assert "9.0" in html_content
    assert "Distribuzione" in html_content
    assert "6.5" in html_content
    assert "Codice" in html_content
    assert "7.5" in html_content
    assert "Adozione" in html_content
    assert "8.0" in html_content
    assert "Sicurezza" in html_content
    assert "9.5" in html_content
    assert "Integrazione" in html_content
    assert "7.0" in html_content

def test_generate_html_report_with_details(sample_results):
    """Test HTML report generation with details."""
    html_content = generate_html_report(sample_results)
    assert "Data dell'ultimo commit" in html_content
    assert "10 giorni fa" in html_content
    assert "Complessità media del codice" in html_content
    assert "Media complessità" in html_content

def test_generate_html_report_with_suggestions(sample_results):
    """Test HTML report generation with suggestions."""
    html_content = generate_html_report(sample_results)
    assert "Aumenta la frequenza dei commit." in html_content
    assert "Migliora la complessità del codice." in html_content

def test_generate_html_report_with_history(sample_results):
    """Test HTML report generation with history."""
    html_content = generate_html_report(sample_results)
    assert "2022-12-01 12:00:00" in html_content
    assert "7.0" in html_content
    assert "2022-11-01 12:00:00" in html_content
    assert "6.5" in html_content

def test_generate_html_report_empty_results():
    """Test HTML report generation with empty results."""
    empty_results = {}
    html_content = generate_html_report(empty_results)
    assert "<html>" in html_content
    assert "<body>" in html_content

def test_generate_html_report_missing_template():
    """Test HTML report generation when the template is missing."""
    with patch("html_report.os.path.join", return_value="nonexistent_template.html"):
        html_content = generate_html_report({})
        assert "Template HTML non trovato" in html_content

def test_category_labels_mapping():
    """Test that category labels are mapped correctly."""
    assert CATEGORY_LABELS_MAPPING["manutenzione"] == "Manutenzione"
    assert CATEGORY_LABELS_MAPPING["collaborazione"] == "Collaborazione"
    assert CATEGORY_LABELS_MAPPING["documentazione"] == "Documentazione"
    assert CATEGORY_LABELS_MAPPING["distribuzione"] == "Distribuzione"
    assert CATEGORY_LABELS_MAPPING["codice"] == "Codice"
    assert CATEGORY_LABELS_MAPPING["adozione"] == "Adozione"
    assert CATEGORY_LABELS_MAPPING["sicurezza"] == "Sicurezza"
    assert CATEGORY_LABELS_MAPPING["integrazione"] == "Integrazione"

def test_generate_html_report_with_na_scores(sample_results):
    """Test HTML report generation with N/A scores."""
    sample_results["dettagli"]["codice"]["complessita_media"]["punteggio"] = None
    sample_results["dettagli"]["codice"]["complessita_media"]["score_is_na"] = True
    html_content = generate_html_report(sample_results)
    assert "N/A" in html_content

def test_generate_html_report_with_missing_data():
    """Test HTML report generation with missing data."""
    missing_data_results = {
        "nome_repository": "test/repo",
        "url": "https://github.com/test/repo",
        "data_analisi": "2023-01-01 12:00:00",
    }
    html_content = generate_html_report(missing_data_results)
    assert "Repository" in html_content
    assert "N/A" in html_content

def test_generate_html_report_with_invalid_punteggio_totale(sample_results):
    """Test HTML report generation with invalid punteggio_totale."""
    sample_results["punteggio_totale"] = "invalid"
    html_content = generate_html_report(sample_results)
    assert "0" in html_content

def test_generate_html_report_with_invalid_dettagli(sample_results):
    """Test HTML report generation with invalid dettagli."""
    sample_results["dettagli"]["codice"]["complessita_media"]["punteggio"] = "invalid"
    html_content = generate_html_report(sample_results)
    assert "N/A" in html_content

def test_generate_html_report_with_invalid_dettagli_score_is_na(sample_results):
    """Test HTML report generation with invalid score_is_na."""
    sample_results["dettagli"]["codice"]["complessita_media"]["score_is_na"] = "invalid"
    html_content = generate_html_report(sample_results)
    assert "N/A" in html_content

class TestMain(unittest.TestCase):
    """Test suite for the main function."""

if __name__ == '__main__':
    # Instead of using unittest.main(), use pytest for nicer output
    # This will keep the unittest structure but use pytest's runner
    import sys
    # Pass all arguments after the script name to pytest
    pytest_args = ["-v", __file__] + sys.argv[1:]
    sys.exit(pytest.main(pytest_args))
