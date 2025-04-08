#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test per il modulo batch_repolizer.py
"""

import os
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import unittest

# Aggiungi la directory principale al path per importare i moduli
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Importa il modulo da testare
from batch_repolizer import read_repo_list, process_repositories

@pytest.fixture
def sample_repo_list_file():
    """Fixture per creare un file temporaneo con un elenco di repository."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("user1/repo1\n")
        f.write("user2/repo2\n")
        f.write("# Questo è un commento\n")
        f.write("\n")  # Linea vuota
        f.write("user3/repo3\n")
        file_path = f.name
    
    yield file_path
    
    # Pulizia dopo il test
    if os.path.exists(file_path):
        os.unlink(file_path)

@pytest.fixture
def mock_repo_analyzer():
    """Fixture per simulare RepoAnalyzer."""
    with patch('batch_repolizer.BatchModeAnalyzer') as mock_analyzer_class:
        # Configura il mock per il context manager
        mock_instance = MagicMock()
        mock_analyzer_class.return_value.__enter__.return_value = mock_instance
        
        # Configura i risultati dell'analisi
        mock_instance.analyze.return_value = {
            'punteggio_totale': 7.5,
            'punteggi': {
                'manutenzione': 8.0,
                'codice': 7.0
            }
        }
        
        # Configura la generazione del report
        mock_instance.generate_report.return_value = {
            'nome_repository': 'user1/repo1',
            'data_analisi': '2023-01-01 12:00:00',
            'punteggio_totale': 7.5,
            'punteggi': {
                'manutenzione': 8.0,
                'codice': 7.0
            }
        }
        
        # Configura il salvataggio dei report
        mock_instance._save_report_json.return_value = 'reports/user1_repo1_20230101.json'
        mock_instance._save_report_html.return_value = 'reports/user1_repo1_20230101.html'
        
        yield mock_analyzer_class

def test_read_repo_list(sample_repo_list_file):
    """Test per la funzione read_repo_list."""
    repos = read_repo_list(sample_repo_list_file)
    
    # Verifica che i repository siano stati letti correttamente
    assert len(repos) == 3
    assert repos[0] == "user1/repo1"
    assert repos[1] == "user2/repo2"
    assert repos[2] == "user3/repo3"
    
    # Verifica che i commenti e le linee vuote siano stati ignorati
    assert "# Questo è un commento" not in repos
    assert "" not in repos

def test_read_repo_list_file_not_found():
    """Test per la funzione read_repo_list con un file inesistente."""
    with patch('builtins.print') as mock_print:
        repos = read_repo_list("file_inesistente.txt")
        assert repos == []
        mock_print.assert_called_with("Error: File 'file_inesistente.txt' not found.")

def test_read_repo_list_with_error():
    """Test per la funzione read_repo_list con un errore durante la lettura."""
    with patch('builtins.open', side_effect=Exception("Errore di test")):
        with patch('builtins.print') as mock_print:
            repos = read_repo_list("qualsiasi_file.txt")
            assert repos == []
            mock_print.assert_called_with("Error reading repository list: Errore di test")


def test_main_function():
    """Test per la funzione main."""
    with patch('batch_repolizer.read_repo_list') as mock_read_repo_list:
        mock_read_repo_list.return_value = ["user1/repo1", "user2/repo2"]
        
        with patch('batch_repolizer.process_repositories') as mock_process_repositories:
            with patch('batch_repolizer.argparse.ArgumentParser.parse_args') as mock_parse_args:
                # Configura gli argomenti della riga di comando
                mock_parse_args.return_value = MagicMock(
                    file="repos.txt",
                    clone=False,
                    no_rich=False
                )
                
                # Patch sys.exit per evitare che il test termini
                with patch('sys.exit'):
                    # Patch Console per verificare che venga creata con highlight=True
                    with patch('batch_repolizer.Console') as mock_console:
                        # Importa main solo ora per evitare che venga eseguito all'importazione
                        from batch_repolizer import main
                        
                        # Esegui la funzione da testare
                        main()
                        
                        # Verifica che read_repo_list sia stato chiamato con il file corretto
                        mock_read_repo_list.assert_called_with("repos.txt")
                        
                        # Verifica che process_repositories sia stato chiamato con i repository corretti
                        mock_process_repositories.assert_called_with(["user1/repo1", "user2/repo2"], clone_repos=False)
                        
                        # Verifica che Console sia stato creato con highlight=True
                        mock_console.assert_called_with(highlight=True)

def test_main_function_no_repos():
    """Test per la funzione main quando non ci sono repository."""
    with patch('batch_repolizer.read_repo_list') as mock_read_repo_list:
        mock_read_repo_list.return_value = []
        
        with patch('batch_repolizer.argparse.ArgumentParser.parse_args') as mock_parse_args:
            # Configura gli argomenti della riga di comando
            mock_parse_args.return_value = MagicMock(
                file="repos.txt",
                clone=False,
                no_rich=False
            )
            
            # Patch sys.exit per verificare che venga chiamato con il codice corretto
            with patch('sys.exit') as mock_exit:
                # Patch print per verificare il messaggio di errore
                with patch('builtins.print') as mock_print:
                    # Importa main solo ora per evitare che venga eseguito all'importazione
                    from batch_repolizer import main
                    
                    # Esegui la funzione da testare
                    main()
                    
                    # Verifica che sys.exit sia stato chiamato con il codice 1
                    mock_exit.assert_called_with(1)
                    
                    # Verifica che il messaggio di errore sia stato stampato
                    mock_print.assert_any_call("No repositories found in 'repos.txt'. Please check the file.")


def test_main_function_no_rich():
    """Test per la funzione main con l'opzione --no-rich."""
    with patch('batch_repolizer.read_repo_list') as mock_read_repo_list:
        mock_read_repo_list.return_value = ["user1/repo1", "user2/repo2"]
        
        with patch('batch_repolizer.process_repositories') as mock_process_repositories:
            with patch('batch_repolizer.argparse.ArgumentParser.parse_args') as mock_parse_args:
                # Configura gli argomenti della riga di comando con no_rich=True
                mock_parse_args.return_value = MagicMock(
                    file="repos.txt",
                    clone=False,
                    no_rich=True
                )
                
                # Patch sys.exit per evitare che il test termini
                with patch('sys.exit'):
                    # Patch Console per verificare che venga creata con highlight=False
                    with patch('batch_repolizer.Console') as mock_console:
                        # Importa main solo ora per evitare che venga eseguito all'importazione
                        from batch_repolizer import main
                        
                        # Esegui la funzione da testare
                        main()
                        
                        # Verifica che Console sia stato creato con highlight=False
                        mock_console.assert_called_with(highlight=False)


if __name__ == '__main__':
    # Usa pytest per un output più elegante
    import sys
    pytest_args = ["-v", __file__] + sys.argv[1:]
    sys.exit(pytest.main(pytest_args))