#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
import datetime
import functools
import concurrent.futures
from typing import Dict, List, Any, Tuple, Optional
import subprocess
import re
import tempfile
import shutil
import logging
import signal
import math

import requests
import pandas as pd
from github import Github
from github.Repository import Repository
from github.GithubException import GithubException
from tqdm import tqdm
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich.panel import Panel
from rich import print as rprint
from html_report import generate_html_report
import bandit

try:
    import safety  # type: ignore
    safety_available = True
except ImportError:
    safety = None
    safety_available = False

# Decoratore per gestire i timeout con signal
def timeout_handler(func):
    """Decorator per gestire i timeout delle chiamate API usando signal.
    Imposta un timeout di DEFAULT_TIMEOUT secondi per la funzione decorata."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Definisce l'handler del segnale per gestire il timeout
        def handle_timeout(signum, frame):
            raise TimeoutError(f"Timeout di {DEFAULT_TIMEOUT}s superato per '{func.__name__}'")

        try:
            # Imposta il timer solo se la piattaforma lo supporta
            if hasattr(signal, 'SIGALRM'):
                # Salva il gestore precedente per ripristinarlo successivamente
                old_handler = signal.signal(signal.SIGALRM, handle_timeout)
                # Imposta il timeout
                signal.alarm(DEFAULT_TIMEOUT)
                
            # Esegue la funzione
            result = func(*args, **kwargs)
            
            # Cancella il timer se la piattaforma lo supporta
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                # Ripristina il gestore precedente
                signal.signal(signal.SIGALRM, old_handler)
                
            return result
        except TimeoutError as e:
            logger.error(f"Timeout durante l'esecuzione di {func.__name__}: {e}")
            print(f"Timeout durante l'esecuzione di {func.__name__}: {e}")
            return None, 0, False
        except Exception as e:
            logger.error(f"Errore durante l'esecuzione di {func.__name__}: {e}")
            print(f"Errore durante l'esecuzione di {func.__name__}: {e}")
            return None, 0, False
    return wrapper

# Configurazione del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('repolizer')

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Configurazione
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CONFIG_FILE = "config.json"

# Costanti per la gestione delle API
MAX_ITEMS_PER_REQUEST = 100  # Numero massimo di elementi per richiesta API

# Timeout predefinito per operazioni (in secondi)
DEFAULT_TIMEOUT = 30

# Mapping per etichette delle categorie nei grafici
CATEGORY_LABELS_MAPPING = {
    "manutenzione": "Manutenzione",
    "collaborazione": "Collaborazione",
    "documentazione": "Documentazione",
    "distribuzione": "Distribuzione",
    "codice": "Codice",
    "adozione": "Adozione",
    "sicurezza": "Sicurezza",
    "integrazione": "Integrazione"
}


class RepoAnalyzer:
    """Classe per analizzare repository GitHub."""
    
    def __init__(self, repo_name: str, config_file: str = CONFIG_FILE, clone_repo: bool = False):
        self.repo_name = repo_name
        self.config_file = config_file
        self.clone_repo = clone_repo
        self._cache = {}
        self.results = {}
        self.repo = None  # Initialize repo to None
        self.local_repo_path = None  # Initialize local_repo_path
        self.github = None  # Initialize github connection
        self.console = Console()  # Initialize rich console
        import json
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            self.config = {}
            logger.error(f"Error loading config: {e}")

    def __enter__(self):
        # Initialize GitHub API connection
        if not GITHUB_TOKEN:
            print("GITHUB_TOKEN non trovato. Imposta il token nelle variabili d'ambiente.")
            return None
            
        self.github = Github(GITHUB_TOKEN)
        
        # Get the repository from GitHub API
        self.repo = self._get_repository()
        if not self.repo:
            return None
            
        # Clone repository if requested
        if self.clone_repo and self.repo:
            try:
                # Create a temporary directory for the clone
                temp_dir = tempfile.mkdtemp(prefix="repolizer_")
                
                print(f"Clonazione del repository in corso in: {temp_dir}")
                clone_url = self.repo.clone_url
                # Replace HTTPS URL with authenticated URL
                if GITHUB_TOKEN and clone_url.startswith("https://"):
                    clone_url = f"https://{GITHUB_TOKEN}@{clone_url[8:]}"
                    
                subprocess.run(["git", "clone", clone_url, temp_dir], check=True, 
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                
                self.local_repo_path = temp_dir
                print(f"Repository clonato con successo.")
            except subprocess.CalledProcessError as e:
                print(f"Errore nella clonazione del repository: {e.stderr.decode() if e.stderr else str(e)}")
                if self.local_repo_path and os.path.exists(self.local_repo_path):
                    shutil.rmtree(self.local_repo_path, ignore_errors=True)
                self.local_repo_path = None
            except Exception as e:
                print(f"Errore nella clonazione del repository: {e}")
                if self.local_repo_path and os.path.exists(self.local_repo_path):
                    shutil.rmtree(self.local_repo_path, ignore_errors=True)
                self.local_repo_path = None
                
        # Configura l'elenco delle licenze OSI approvate
        self.osi_approved_licenses = [
            "mit", "apache-2.0", "gpl-3.0", "gpl-2.0", "bsd-3-clause", 
            "lgpl-3.0", "mpl-2.0", "agpl-3.0", "unlicense", "bsd-2-clause",
            "lgpl-2.1", "cc0-1.0", "epl-2.0", "apache", "bsd", "gpl", "lgpl",
            "mozilla", "eclipse", "artistic", "zlib", "isc", "boost",
            "wtfpl", "cc-by-4.0", "cc-by-sa-4.0"
        ]
        
        # Check API rate limits and show info
        self._check_api_limits()
            
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up temporary cloned repository if exists
        if self.local_repo_path and os.path.exists(self.local_repo_path):
            try:
                shutil.rmtree(self.local_repo_path, ignore_errors=True)
                print(f"Repository temporaneo rimosso: {self.local_repo_path}")
            except Exception as e:
                print(f"Attenzione: Impossibile rimuovere la directory temporanea {self.local_repo_path}: {e}")
                
        return False

    def _load_config(self) -> Dict:
        # ...existing code...
        import json
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading config: {e}")
            return {}
            
    def _save_report_json(self, report_data: Dict, report_dir: str = "reports") -> str:
        import os, json, datetime
        try:
            os.makedirs(report_dir, exist_ok=True)
            # Fix: Use 'report_' prefix instead of repository name which could contain slashes
            filename = f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = os.path.join(report_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=4)
            return file_path
        except Exception as e:
            logger.error(f"Error saving JSON report: {e}")
            return ""
            
    def _save_report_html(self, html_content: str, report_data: Dict, report_dir: str = "reports") -> str:
        import os, datetime
        try:
            os.makedirs(report_dir, exist_ok=True)
            # Fix: Use 'report_' prefix instead of repository name which could contain slashes
            filename = f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            file_path = os.path.join(report_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return file_path
        except Exception as e:
            logger.error(f"Error saving HTML report: {e}")
            return ""

    def _check_api_limits(self) -> None:
        """Verifica i limiti delle API GitHub e mostra informazioni utili."""
        try:
            rate_limit = self.github.get_rate_limit()
            core_remaining = rate_limit.core.remaining
            core_limit = rate_limit.core.limit
            reset_time = rate_limit.core.reset.strftime("%H:%M:%S")
            
            print(f"\nLimiti API GitHub: {core_remaining}/{core_limit} richieste rimanenti")
            print(f"Reset dei limiti alle: {reset_time}")
            
            if core_remaining < 100:
                print("\nATTENZIONE: Stai per raggiungere il limite di richieste API!")
                print("L'analisi potrebbe essere incompleta o fallire.")
        except Exception as e:
            print(f"Impossibile verificare i limiti API: {e}")
    
    def _get_repository(self) -> Optional[Repository]:
        """Ottiene il repository da GitHub.

        Returns:
            Oggetto Repository o None in caso di errore
        """
        try:
            repo = self.github.get_repo(self.repo_name)
            logger.info(f"Repository '{self.repo_name}' recuperato con successo.")
            return repo
        except GithubException as e:
            logger.error(f"Errore nel recupero del repository '{self.repo_name}': {e.status} {e.data}")
            if e.status == 404:
                print(f"Errore: Repository '{self.repo_name}' non trovato.")
            elif e.status == 401:
                print("Errore: Autenticazione GitHub fallita. Verifica il tuo GITHUB_TOKEN.")
            else:
                print(f"Errore nel recupero del repository: {e}")
            return None
            
    def _get_cached_data(self, key: str, fetch_func, *args, **kwargs):
        """Ottiene dati dalla cache o li recupera e li memorizza.
        
        Args:
            key: Chiave per identificare i dati nella cache
            fetch_func: Funzione da chiamare per recuperare i dati
            *args, **kwargs: Argomenti da passare alla funzione
            
        Returns:
            I dati recuperati
        """
        if key not in self._cache:
            try:
                # Utilizza il timeout del client GitHub invece del signal
                if hasattr(fetch_func, '__wrapped__'):
                    # Se la funzione è wrappata (es. da decoratori), accedi alla funzione originale
                    original_func = fetch_func.__wrapped__
                else:
                    original_func = fetch_func
                
                # Imposta il timeout solo se la funzione è un metodo dell'API GitHub
                if hasattr(original_func, '__self__') and isinstance(original_func.__self__, Github):
                    old_timeout = self.github.timeout
                    self.github.timeout = 20
                
                try:
                    result = fetch_func(*args, **kwargs)
                except IndexError:
                    # Handle empty paginated lists (like when a repo has no releases)
                    logger.debug(f"Empty result when fetching data for {key}")
                    result = []
                    
                # Ripristina il timeout originale se necessario
                if hasattr(original_func, '__self__') and isinstance(original_func.__self__, Github):
                    self.github.timeout = old_timeout
                
                # Assicurati che il risultato sia una lista se è un iteratore
                if hasattr(result, '__iter__') and not isinstance(result, (list, dict, str)):
                    result = list(result)
                
                self._cache[key] = result
            except TimeoutError as e:
                logger.error(f"Timeout durante il recupero dei dati per {key}: {e}")
                return None
            except Exception as e:
                # Log more specific error for debugging
                logger.error(f"Errore nel recupero dei dati per {key}: {e}", exc_info=True)
                print(f"Errore nel recupero dei dati per {key}: {e}")
                return None
        # Ensure the key exists before returning
        return self._cache.get(key)

    def _check_complexity(self, path: str = ".") -> float:
        """Esegue una scansione con Radon per calcolare la complessità media."""
        # Default neutral value
        default_complexity = 5.0
        
        try:
            # Check if radon is installed first
            try:
                subprocess.run(["radon", "--version"], check=True, capture_output=True, timeout=5)
            except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
                logger.warning("Radon non trovato o non eseguibile. Assicurati che sia installato e nel PATH.")
                return default_complexity

            effective_path = self.local_repo_path if self.local_repo_path else path
            complexities = []

            if self.local_repo_path:
                python_files = []
                for root, _, files in os.walk(effective_path):
                    python_files.extend([os.path.join(root, f) for f in files if f.endswith('.py')])
                
                if python_files:
                    # Analyze individual files if found
                    files_to_analyze = python_files[:20] # Limit analysis for performance
                    logger.debug(f"Analisi complessità su {len(files_to_analyze)} file Python...")
                    for py_file in files_to_analyze:
                        try:
                            cmd_result = subprocess.run(
                                ["radon", "cc", py_file, "-s", "-a"], 
                                capture_output=True, text=True, timeout=10, check=False # Don't check=True, parse output manually
                            )
                            if cmd_result.returncode == 0 and cmd_result.stdout.strip():
                                for line in cmd_result.stdout.splitlines():
                                    match = re.search(r"\((\d+)\)$", line.strip())
                                    if match:
                                        complexities.append(int(match.group(1)))
                            elif cmd_result.returncode != 0:
                                logger.debug(f"Radon ha fallito per il file {py_file}: {cmd_result.stderr}")
                        except subprocess.TimeoutExpired:
                            logger.warning(f"Timeout analisi complessità per il file: {py_file}")
                        except Exception as e_file:
                            logger.warning(f"Errore analisi complessità per il file {py_file}: {e_file}")
                            
                    if complexities:
                        avg_complexity = sum(complexities) / len(complexities)
                        logger.info(f"Complessità media calcolata da {len(complexities)} blocchi: {avg_complexity:.2f}")
                        
                        # Provide more granular complexity score conversion
                        if avg_complexity <= 2.0:
                            return 10.0  # Excellent: Very simple, maintainable code
                        elif avg_complexity <= 4.0:
                            return 9.0   # Very good: Simple, clean code
                        elif avg_complexity <= 6.0:
                            return 8.0   # Good: Reasonably simple code
                        elif avg_complexity <= 8.0:
                            return 7.0   # Fairly good: Moderate complexity
                        elif avg_complexity <= 10.0:
                            return 6.0   # Acceptable: Getting complex
                        elif avg_complexity <= 12.0:
                            return 5.0   # Moderate: Definitely complex
                        elif avg_complexity <= 14.0:
                            return 4.0   # Concerning: High complexity
                        elif avg_complexity <= 16.0:
                            return 3.0   # Poor: Very high complexity
                        elif avg_complexity <= 20.0:
                            return 2.0   # Bad: Extremely complex
                        else:
                            return 1.0   # Critical: Unmaintainable complexity
                    else:
                        logger.warning("Nessun dato di complessità raccolto dai file Python individuali.")
                        # Fall through to directory analysis if individual file analysis failed or yielded no results
                
            # Fallback: Analyze directory average if no local repo or no complexities found in files
            logger.debug(f"Tentativo di analisi complessità media sulla directory: {effective_path}")
            try:
                cmd_result = subprocess.run(
                    ["radon", "cc", effective_path, "-s", "-a"], # Use -a for average directly
                    capture_output=True, text=True, timeout=30, check=False
                )
                if cmd_result.returncode == 0 and cmd_result.stdout.strip():
                    # Search for the average value, typically the last line
                    avg_line = cmd_result.stdout.strip().splitlines()[-1]
                    match = re.search(r"Average complexity:.*?(\d+\.\d+)", avg_line)
                    if match:
                        avg_complexity = float(match.group(1))
                        logger.info(f"Complessità media della directory: {avg_complexity:.2f}")
                        
                        # Apply the same granular scoring for directory analysis
                        if avg_complexity <= 2.0:
                            return 10.0  # Excellent: Very simple, maintainable code
                        elif avg_complexity <= 4.0:
                            return 9.0   # Very good: Simple, clean code
                        elif avg_complexity <= 6.0:
                            return 8.0   # Good: Reasonably simple code
                        elif avg_complexity <= 8.0:
                            return 7.0   # Fairly good: Moderate complexity
                        elif avg_complexity <= 10.0:
                            return 6.0   # Acceptable: Getting complex
                        elif avg_complexity <= 12.0:
                            return 5.0   # Moderate: Definitely complex
                        elif avg_complexity <= 14.0:
                            return 4.0   # Concerning: High complexity
                        elif avg_complexity <= 16.0:
                            return 3.0   # Poor: Very high complexity
                        elif avg_complexity <= 20.0:
                            return 2.0   # Bad: Extremely complex
                        else:
                            return 1.0   # Critical: Unmaintainable complexity
                    else:
                        logger.warning(f"Impossibile estrarre la complessità media dall'output di Radon: {avg_line}")
                elif cmd_result.returncode != 0:
                    logger.warning(f"Radon ha fallito per la directory {effective_path}: {cmd_result.stderr}")

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout analisi complessità per la directory: {effective_path}")
            except Exception as e_dir:
                logger.warning(f"Errore analisi complessità per la directory {effective_path}: {e_dir}")

        except Exception as e:
            logger.error(f"Errore imprevisto durante l'analisi della complessità: {e}", exc_info=True)

        logger.warning(f"Impossibile calcolare la complessità, restituendo valore di default: {default_complexity}")
        return default_complexity # Return default if all attempts fail

    def _check_style(self, path: str = ".") -> float:
        """Esegue una scansione per valutare l'aderenza allo stile (meno errori => punteggio più alto).
        
        Utilizza flake8 e pylint se disponibili per una valutazione più completa.
        """
        try:
            # Assicurati di avere una copia locale del repo
            effective_path = self.local_repo_path if self.local_repo_path else path
            
            # Prepara per score aggregato
            style_score = 0.0
            tools_used = 0
            
            # Prova con flake8 (PEP8)
            try:
                flake8_result = subprocess.run(
                    ["flake8", effective_path, "--exit-zero", "--statistics", "--count"],
                    capture_output=True, text=True, check=False
                )
                if flake8_result.stdout:
                    # Inserisci qui eventuale parsing dei risultati di flake8
                    lines = [l for l in flake8_result.stdout.splitlines() if l.strip()]
                    errors = len(lines)
                    # Più errori -> punteggio più basso, max 10.0
                    flake8_score = max(0.0, 10.0 - (errors / 10.0))
                    style_score += flake8_score
                tools_used += 1

            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                pass 
            
            # Prova con pylint
            try:
                # Trova tutti i file Python nel repository
                py_files = []
                if self.local_repo_path:
                    for root, _, files in os.walk(effective_path):
                        py_files.extend([os.path.join(root, f) for f in files if f.endswith('.py')])
                
                # Se ci sono file Python, esegui pylint
                if py_files:
                    # Limita a massimo 30 file per evitare timeout
                    pylint_files = py_files[:30]
                    process = subprocess.run(["pylint", "--output-format=text"] + pylint_files,
                                           capture_output=True, text=True, timeout=45)
                    output = process.stdout
                    
                    # Cerca il punteggio di pylint nel formato "Your code has been rated at X.XX/10"
                    match = re.search(r"rated at (\d+\.\d+)/10", output)
                    if match:
                        pylint_score = float(match.group(1))
                        style_score += pylint_score
                        tools_used += 1
                        logger.debug(f"Pylint analysis complete: score {pylint_score}/10")
                    else:
                        # Se non troviamo il rating esplicito, calcoliamo in base agli errori
                        error_count = len([l for l in output.splitlines() if " E:" in l])
                        pylint_fallback_score = max(0.0, 10.0 - (error_count / 5.0))
                        style_score += pylint_fallback_score
                        tools_used += 1
                        logger.debug(f"Pylint analysis complete: {error_count} errors found, estimated score: {pylint_fallback_score:.2f}/10")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Pylint analysis skipped: {e}")
                # Non aggiungere nulla allo score o ai tools usati
                
            # Calcola punteggio medio se almeno uno strumento è stato usato
            if tools_used > 0:
                return style_score / tools_used
            else:
                logger.warning("No style analysis tools available.")
                return 5.0  # Valore neutro se nessuno strumento è disponibile
        except Exception as e:
            logger.error(f"Style analysis error: {e}", exc_info=True)
            return 0.0 # Return 0 in case of unexpected error

    def _check_code_smells(self, path: str = ".") -> float:
        """Esegue un'analisi per rilevare 'code smells'. Punteggio più alto con meno segnalazioni.
        
        Utilizza una combinazione di strumenti: flake8, pycodestyle, pytest e radon se disponibili.
        """
        try:
            # Assicurati di avere una copia locale del repo
            effective_path = self.local_repo_path if self.local_repo_path else path
            
            # Prepara per score aggregato
            smell_score = 0.0
            tools_used = 0
            
            # 1. Flake8 per errori di formattazione e bug potenziali
            try:
                process = subprocess.run(["flake8", "--select=E,F", effective_path], 
                                        capture_output=True, text=True, timeout=30)
                if process.returncode <= 1:  # 0=success, 1=violations found
                    lines = [l for l in process.stdout.splitlines() if l.strip()]
                    smells = len(lines)
                    # Più segnalazioni -> punteggio più basso
                    flake8_smell_score = max(0.0, 10.0 - (smells / 15.0))
                    smell_score += flake8_smell_score
                    tools_used += 1
                    logger.debug(f"Flake8 smell analysis: {smells} issues found, score: {flake8_smell_score:.2f}/10")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Flake8 smell analysis skipped: {e}")
                # Non aggiungere nulla allo score o ai tools usati
            
            # 2. Radon per complessità ciclomatica
            try:
                # Use radon to scan for complexity-related issues
                process = subprocess.run(["radon", "cc", effective_path, "--min", "C"], 
                                       capture_output=True, text=True, timeout=30)
                output = process.stdout
                # Conta il numero di funzioni con complessità elevata
                complex_funcs = len([l for l in output.splitlines() if any(grade in l for grade in ["C:", "D:", "E:", "F:"])])
                radon_smell_score = max(0.0, 10.0 - (complex_funcs / 5.0))
                smell_score += radon_smell_score
                tools_used += 1
                logger.debug(f"Radon analysis: {complex_funcs} complex functions found, score: {radon_smell_score:.2f}/10")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Radon analysis skipped: {e}")
                # Non aggiungere nulla allo score o ai tools usati

            # 3. Pycodestyle per errori di stile ulteriori
            try:
                process = subprocess.run(["pycodestyle", effective_path], 
                                       capture_output=True, text=True, timeout=30)
                lines = [l for l in process.stdout.splitlines() if l.strip()]
                style_issues = len(lines)
                pycodestyle_score = max(0.0, 10.0 - (style_issues / 20.0))
                smell_score += pycodestyle_score
                tools_used += 1
                logger.debug(f"Pycodestyle analysis: {style_issues} issues found, score: {pycodestyle_score:.2f}/10")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Pycodestyle analysis skipped: {e}")
                # Non aggiungere nulla allo score o ai tools usati
            
            # 4. Verifica presenza di code smell comunemente riconoscibili nei file
            try:
                custom_smells = 0
                py_files = []
                if self.local_repo_path:
                    for root, _, files in os.walk(effective_path):
                        for f in files:
                            if f.endswith('.py'):
                                py_path = os.path.join(root, f)
                                try:
                                    with open(py_path, 'r', encoding='utf-8') as pyfile:
                                        content = pyfile.read()
                                        # Cerca pattern problematici
                                        smells_patterns = [
                                            r"except\s*:",  # Bare except
                                            r"except\s+Exception:",  # Too broad exception handling
                                            r"\bprint\s*\(",  # print() calls in production code
                                            r"#\s*TODO",  # TODO comments
                                            r"\bglobal\s+",  # global statements
                                            r"exec\s*\(",  # exec calls
                                            r"eval\s*\(",  # eval calls
                                            r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*$"  # missing main block content
                                        ]
                                        for pattern in smells_patterns:
                                            custom_smells += len(re.findall(pattern, content))
                                except Exception:
                                    pass  # Skip problematic files
                                    
                    custom_smell_score = max(0.0, 10.0 - (custom_smells / 10.0))
                    smell_score += custom_smell_score
                    tools_used += 1
                    logger.debug(f"Custom smell analysis: {custom_smells} issues found, score: {custom_smell_score:.2f}/10")
            except Exception as e:
                logger.debug(f"Custom smell analysis error: {e}")
                # Non aggiungere nulla allo score o ai tools usati
                                
            # Calcola il punteggio medio se almeno uno strumento è stato usato
            if tools_used > 0:
                return smell_score / tools_used
            else:
                logger.warning("No code smell analysis tools available.")
                return 5.0  # Valore neutro se nessuno strumento è disponibile
                
        except Exception as e:
            logger.error(f"Code smell analysis error: {e}", exc_info=True)
            return 0.0 # Return 0 in case of unexpected error

    def _check_comment_coverage(self, path: str = ".") -> float:
        """Esempio elementare: conta righe di commento vs righe totali (solo .py)."""
        try:
            effective_path = self.local_repo_path if self.local_repo_path else path
            total_lines, comment_lines = 0, 0
            for root, dirs, files in os.walk(effective_path):
                for fname in files:
                    if fname.endswith(".py"):
                        with open(os.path.join(root, fname), "r", encoding="utf-8") as f:
                            for line in f:
                                line_stripped = line.strip()
                                if line_stripped.startswith("#"):
                                    comment_lines += 1
                                if line_stripped:
                                    total_lines += 1
            ratio = comment_lines / total_lines if total_lines else 0
            # Scale score: 0% comments -> 0 points, 50% comments -> 10 points
            score = min(ratio * 20.0, 10.0) 
            logger.debug(f"Comment coverage: {ratio*100:.1f}%, score: {score:.1f}")
            return score
        except Exception as e:
            logger.error(f"Errore nel calcolo della copertura dei commenti: {e}", exc_info=True)
            return 0.0

    def _ensure_tz_aware(self, dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        if dt and dt.tzinfo is None:
            import pytz
            return dt.replace(tzinfo=pytz.UTC)
        return dt

    def _fetch_issues_data(self):
        """Ottiene dati su issues aperte/chiuse e calcola i tempi medi di chiusura e risposta."""
        if "issues_data" in self._cache:
            return self._cache["issues_data"]
        
        try:
            issues = self.repo.get_issues(state="all")
            closed_times = []
            response_times = []
            total_issues = 0
            closed_issues = 0
            
            for issue in issues:
                total_issues += 1
                if issue.state == 'closed':
                    closed_issues += 1
                    closed_at = self._ensure_tz_aware(issue.closed_at)
                    created_at = self._ensure_tz_aware(issue.created_at)
                    if closed_at and created_at:
                        # Ensure dates are comparable
                        delta = (closed_at - created_at).days
                        if delta >= 0:
                            closed_times.append(delta)
                
                # Calcola il tempo di prima risposta se ci sono commenti
                try:
                    comments = list(issue.get_comments())
                    if comments and issue.user and comments[0].user:
                        # Verifica che la prima risposta non sia dell'autore dell'issue
                        if issue.user.id != comments[0].user.id:
                            comment_date = self._ensure_tz_aware(comments[0].created_at)
                            issue_date = self._ensure_tz_aware(issue.created_at)
                            if comment_date and issue_date:
                                first_response_time = (comment_date - issue_date).days
                                if first_response_time >= 0:
                                    response_times.append(first_response_time)
                except Exception as e:
                    logger.debug(f"Errore nel calcolo del tempo di risposta per issue #{issue.number}: {e}")
            
            result = {
                "closed_times": closed_times,
                "response_times": response_times,
                "total_issues": total_issues,
                "closed_issues": closed_issues,
                "avg_close_time": sum(closed_times) / len(closed_times) if closed_times else None,
                "avg_response_time": sum(response_times) / len(response_times) if response_times else None
            }
            
            self._cache["issues_data"] = result
            return result
        except Exception as e:
            logger.error(f"Errore nel recupero dei dati delle issues: {e}", exc_info=True)
            return {"closed_times": [], "response_times": [], "total_issues": 0, "closed_issues": 0, "avg_close_time": None, "avg_response_time": None}

    def _fetch_pr_data(self):
        """Ottiene dati su PR aperte/chiuse e calcola ratio e tempi chiusura."""
        if "pr_data" in self._cache:
            return self._cache["pr_data"]
        pulls = self.repo.get_pulls(state="all")
        total_pr = pulls.totalCount
        merged_pr = 0
        closed_times = []
        for pr in pulls:
            if pr.merged:
                merged_pr += 1
                closed_at = self._ensure_tz_aware(pr.closed_at)
                created_at = self._ensure_tz_aware(pr.created_at)
                if closed_at and created_at:
                    delta_days = (closed_at - created_at).days
                    if delta_days >= 0:
                        closed_times.append(delta_days)
        self._cache["pr_data"] = {
            "total": total_pr,
            "merged": merged_pr,
            "merged_times": closed_times
        }
        return self._cache["pr_data"]

    def _fetch_tags_data(self):
        """Ottiene la frequenza media tra i tag (in giorni), gestendo tag non cronologici.
        
        Returns:
            La media dei giorni tra i tag consecutivi, o 0 se non ci sono abbastanza tag
        """
        if "tags_data" in self._cache:
            return self._cache["tags_data"]
        
        try:
            tags = list(self.repo.get_tags())
            
            if len(tags) < 2:
                self._cache["tags_data"] = 0.0
                return 0.0
            
            # Estrai le date dai tag e ordinale cronologicamente
            tag_dates = []
            for tag in tags:
                try:
                    # Attempt to get commit date associated with the tag
                    commit_info = tag.commit
                    if commit_info and commit_info.commit and commit_info.commit.author:
                        tag_date = self._ensure_tz_aware(commit_info.commit.author.date)
                        if tag_date:
                            tag_dates.append((tag.name, tag_date))
                    # Fallback: try getting the date from the tag object itself if commit date fails
                    elif hasattr(tag, 'object') and hasattr(tag.object, 'created_at'):
                         tag_date = self._ensure_tz_aware(tag.object.created_at)
                         if tag_date:
                             tag_dates.append((tag.name, tag_date))

                except Exception as e:
                    logger.warning(f"Impossibile ottenere la data per il tag {tag.name}: {e}")
                    continue
            
            # Ordina le date cronologicamente (dalla più vecchia alla più recente)
            tag_dates.sort(key=lambda x: x[1])
            
            # Calcola le differenze di giorni tra tag consecutivi
            date_diffs = []
            for i in range(len(tag_dates) - 1):
                # Ensure dates are valid before subtraction
                if tag_dates[i+1][1] and tag_dates[i][1]:
                    date_diff = abs((tag_dates[i+1][1] - tag_dates[i][1]).days)
                    date_diffs.append(date_diff)
            
            # Calcola la media
            avg_days = sum(date_diffs) / len(date_diffs) if date_diffs else 0.0
            self._cache["tags_data"] = avg_days
            return avg_days
            
        except Exception as e:
            logger.error(f"Errore durante il recupero dei dati dei tag: {e}", exc_info=True)
            self._cache["tags_data"] = 0.0
            return 0.0

    def _fetch_popolarita_data(self):
        """Ottiene dati relativi a stelle, fork, watchers, contributori e dipendenti."""
        if "popolarita_data" in self._cache:
            return self._cache["popolarita_data"]
        
        repo_data = {
            "stars": self.repo.stargazers_count if self.repo else 0,
            "forks": self.repo.forks_count if self.repo else 0,
            "watchers": self.repo.subscribers_count if self.repo else 0,
            "contributori": 0,
            "dipendenti": 0
        }
        
        try:
            # Ottieni il conteggio dei contributori (handle potential pagination issues)
            contributors_paginator = self.repo.get_contributors()
            # Efficiently get count if available, otherwise iterate (up to a limit)
            if hasattr(contributors_paginator, 'totalCount'):
                 repo_data["contributori"] = contributors_paginator.totalCount
            else:
                 # Fallback: iterate manually but limit to avoid excessive API calls
                 count = 0
                 for _ in contributors_paginator[:500]: # Limit to 500 contributors check
                     count += 1
                 repo_data["contributori"] = count
                 if count == 500:
                     logger.warning("Raggiunto limite di 500 contributori durante il conteggio manuale.")

        except Exception as e:
            logger.error(f"Errore nel recupero dei contributori: {e}", exc_info=True)
            print(f"Errore nel recupero dei contributori: {e}")
        
        try:
            # Cerca repository che dipendono da questo (GitHub API)
            used_by_url = f"https://github.com/{self.repo_name}/network/dependents"
            repo_data["dipendenti_url"] = used_by_url
            
            # Semplice approssimazione usando search API (può essere imprecisa)
            # Use a simpler query to avoid parsing errors
            query = f'"{self.repo_name}"' # Search for the repo name string literal in code
            dependents = self.github.search_code(query)
            repo_data["dipendenti"] = dependents.totalCount if dependents else 0
        except GithubException as e:
             if e.status == 403: # Often rate limit or access issue
                 logger.warning(f"Errore API GitHub (403) nel recupero dei dipendenti: {e.data.get('message', '')}")
                 print(f"Avviso: Impossibile cercare i dipendenti a causa di limiti API o permessi.")
             elif e.status == 422: # Query parsing error
                 logger.error(f"Errore API GitHub (422) nel recupero dei dipendenti - Query non valida: {query}. Dettagli: {e.data.get('message', '')}", exc_info=True)
                 print(f"Errore: La query di ricerca per i dipendenti ('{query}') non è valida o non è stata compresa da GitHub.")
                 repo_data["dipendenti"] = 0 # Set to 0 as we couldn't get the data
             else:
                 logger.error(f"Errore nel recupero dei dipendenti: {e}", exc_info=True)
                 print(f"Errore nel recupero dei dipendenti: {e}")
        except Exception as e:
            logger.error(f"Errore generico nel recupero dei dipendenti: {e}", exc_info=True)
            print(f"Errore generico nel recupero dei dipendenti: {e}")
        
        self._cache["popolarita_data"] = repo_data
        return repo_data

    def _check_documentation_files(self):
        """Verifica se readme, doc estesa, license, contributo e esempi sono presenti (in modo minimale)."""
        if "doc_files_data" in self._cache:
            return self._cache["doc_files_data"]
        data = {
            "has_readme": False,
            "has_extended_docs": False,
            "has_license": False,
            "has_contrib_coc": False,
            "has_examples": False
        }
        try:
            effective_repo = self.repo
            if self.local_repo_path:
                # Se abbiamo clonato, usa la directory locale per il controllo della documentazione
                effective_repo = self.local_repo_path  # Usa il percorso locale
                file_names = [f.lower() for f in os.listdir(effective_repo)]
                data["has_readme"] = any("readme" in fn for fn in file_names)
                data["has_license"] = any("license" in fn or "copying" in fn for fn in file_names)
                data["has_contrib_coc"] = any("contributing" in fn or "code_of_conduct" in fn for fn in file_names)
                
                # Verifica se esiste cartella /docs o wiki
                data["has_extended_docs"] = "docs" in [f.lower() for f in os.listdir(effective_repo)]  # Assumiamo ci sia una directory "docs"
                
                # Verifica presenza directory /examples
                data["has_examples"] = "examples" in [f.lower() for f in os.listdir(effective_repo)]  # Assumiamo ci sia una directory "examples"
                
            else:
                # Se non clonato, usa l'API di GitHub
                contents = self.repo.get_contents("")
                file_names = [c.name.lower() for c in contents]
                data["has_readme"] = any("readme" in fn for fn in file_names)
                data["has_license"] = any("license" in fn or "copying" in fn for fn in file_names)
                data["has_contrib_coc"] = any("contributing" in fn or "code_of_conduct" in fn for fn in file_names)
                # Verifica se esiste cartella /docs o wiki
                if "docs" in [c.name.lower() for c in contents] or self.repo.has_wiki:
                    data["has_extended_docs"] = True
                # Verifica presenza directory /examples
                if "examples" in file_names:
                    data["has_examples"] = True
        except Exception as e:
            logger.warning(f"Errore nel controllo dei file di documentazione: {e}")
        
        self._cache["doc_files_data"] = data
        return data

    def _fetch_community_data(self):
        """Ottiene dati relativi alla community e alle collaborazioni nel repository.
        
        Returns:
            Un dizionario contenente informazioni sulla community del repository
        """
        if "community_data" in self._cache:
            logger.debug("Returning cached community data")
            return self._cache["community_data"]
            
        data = {
            "discussions_enabled": False,
            "templates_enabled": False,
            "tono_costruttivita": 5,  # Default value
            "label_usage": False
        }
        
        try:
            # Verifica se Discussions è abilitato
            try:
                data["discussions_enabled"] = getattr(self.repo, "has_discussions", False)
            except Exception as e:
                logger.warning(f"Errore nella verifica delle discussioni: {e}")
                # Mantiene il valore predefinito False
            
            # Controllo più accurato per i template di issue e PR
            try:
                templates_found = False
                
                # Lista di percorsi da controllare per i template
                template_paths = [
                    # Root directory templates
                    "ISSUE_TEMPLATE.md", "issue_template.md", 
                    "PULL_REQUEST_TEMPLATE.md", "pull_request_template.md",
                    
                    # .github directory templates
                    ".github/ISSUE_TEMPLATE.md", ".github/issue_template.md",
                    ".github/PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md",
                    
                    # Template directories
                    ".github/ISSUE_TEMPLATE", ".github/issue_template",
                    ".github/PULL_REQUEST_TEMPLATE", ".github/pull_request_template"
                ]
                
                # Controlla i file nella root
                root_contents = self._get_cached_data(
                    "root_contents", 
                    lambda: list(self.repo.get_contents(""))
                )
                
                if root_contents:
                    root_paths = [item.path.lower() for item in root_contents]
                    if any(path.lower() in root_paths for path in ["ISSUE_TEMPLATE.md", "issue_template.md", "PULL_REQUEST_TEMPLATE.md", "pull_request_template.md"]):
                        templates_found = True
                
                # Se non trovati nella root, controlla nella directory .github
                if not templates_found:
                    github_dir_exists = any(item.path == ".github" and item.type == "dir" for item in root_contents)
                    
                    if github_dir_exists:
                        try:
                            github_contents = self._get_cached_data(
                                "github_dir_contents",
                                lambda: list(self.repo.get_contents(".github"))
                            )
                            
                            github_paths = [item.path.lower() for item in github_contents]
                            
                            # Controlla file di template diretti
                            if any(path.lower().endswith(("issue_template.md", "pull_request_template.md")) for path in github_paths):
                                templates_found = True
                                
                            # Controlla directory di template
                            if not templates_found:
                                template_dirs = [".github/ISSUE_TEMPLATE", ".github/issue_template", 
                                                ".github/PULL_REQUEST_TEMPLATE", ".github/pull_request_template"]
                                
                                for template_dir in template_dirs:
                                    try:
                                        template_contents = self.repo.get_contents(template_dir)
                                        if template_contents:
                                            templates_found = True
                                            break
                                    except Exception:
                                        continue
                        except Exception as e:
                            logger.warning(f"Errore nel controllo dei template in .github: {e}")
                
                data["templates_enabled"] = templates_found
            except Exception as e:
                logger.warning(f"Errore nel controllo dei template: {e}")
                # Mantiene il valore predefinito False
            
            # Analisi del tono costruttivo nelle issues e PR
            try:
                tone_score = 0
                tone_samples = 0
                
                # Analizza il tono nelle issue recenti
                try:
                    issues = self._get_cached_data(
                        "recent_issues", 
                        lambda: list(self.repo.get_issues(state='all')[:5])
                    )
                    
                    for issue in issues:
                        # Controlla costruttività dal titolo (euristiche semplici)
                        title = issue.title.lower()
                        body = issue.body.lower() if issue.body else ""
                        
                        # Parole positive e costruttive
                        positive_words = [
                            # English
                            "thanks", "please", "suggestion", "help", "appreciate", "improve", 
                            "enhancement", "feature", "good", "great", "excellent", "awesome",
                            "wonderful", "brilliant", "helpful", "valuable", "useful", "nice", 
                            "kudos", "support", "clear", "solved", "fix", "fixed", "resolved",
                            "solution", "progress", "improvement", "enhanced", 
                            # Italian
                            "grazie", "per favore", "miglioramento", "ottimo", "buono", "eccellente",
                            "fantastico", "meraviglioso", "utile", "aiuto", "chiaro", "supporto",
                            "risolto", "soluzione", "risolvere", "sistemato", "suggerimento",
                            "prego", "ben fatto", "complimenti", "apprezzato"
                        ]
                        # Parole negative o non costruttive
                        negative_words = [
                            # English
                            "broken", "terrible", "awful", "hate", "stupid", "useless", "worst",
                            "ridiculous", "wtf", "crap", "bad", "horrible", "sucks", "suck",
                            "garbage", "trash", "junk", "poor", "disappointing", "waste", 
                            "rubbish", "nonsense", "lousy", "pathetic", "dumb", "mess",
                            # Italian
                            "rotto", "terribile", "odio", "inutile", "stupido", "pessimo",
                            "ridicolo", "spazzatura", "orribile", "schifoso", "deludente",
                            "assurdo", "insensato", "disastro", "pessimo", "scadente", "brutto",
                            "fastidioso", "inadeguato", "fallimentare", "scarso"
                        ]
                        
                        # Analisi semplice
                        pos_count = sum(1 for word in positive_words if word in title or word in body)
                        neg_count = sum(1 for word in negative_words if word in title or word in body)
                        
                        # Punteggio: maggiore è positivo, meno è negativo
                        sample_score = 5 + min(pos_count, 5) - min(neg_count, 5)
                        sample_score = max(0, min(10, sample_score))  # Limita tra 0 e 10
                        
                        tone_score += sample_score
                        tone_samples += 1
                        
                        # Controlla anche alcuni commenti
                        try:
                            comments = self._get_cached_data(
                                f"issue_{issue.number}_comments",
                                lambda: list(issue.get_comments())
                            )
                            
                            # Verifica se ci sono commenti prima di analizzarli
                            if comments and len(comments) > 0:
                                # Analizza fino a 3 commenti
                                for comment in comments[:3]:
                                    comment_text = comment.body.lower() if comment.body else ""
                                    pos_count = sum(1 for word in positive_words if word in comment_text)
                                    neg_count = sum(1 for word in negative_words if word in comment_text)
                                    
                                    sample_score = 5 + min(pos_count, 5) - min(neg_count, 5)
                                    sample_score = max(0, min(10, sample_score))
                                    
                                    tone_score += sample_score
                                    tone_samples += 1
                        except Exception as e:
                            logger.warning(f"Errore nell'analisi dei commenti dell'issue {issue.number}: {e}")
                except Exception as e:
                    logger.warning(f"Errore nell'analisi delle issues: {e}")
                
                # Analizza il tono nelle PR recenti
                try:
                    pull_requests = self._get_cached_data(
                        "recent_prs",
                        lambda: list(self.repo.get_pulls(state='all')[:5])
                    )
                    
                    for pr in pull_requests:
                        # Analisi simile alle issue
                        title = pr.title.lower()
                        body = pr.body.lower() if pr.body else ""
                        
                        positive_words = ["fix", "improve", "update", "enhance", "optimize", "thanks", "please", 
                                         "feature", "support", "refactor", "clean", "sistemato", "migliorato"]
                        negative_words = ["hack", "workaround", "terrible", "awful", "hate", "wtf", "crap", 
                                         "broken", "stupid", "rotto", "odio"]
                        
                        pos_count = sum(1 for word in positive_words if word in title or word in body)
                        neg_count = sum(1 for word in negative_words if word in title or word in body)
                        
                        sample_score = 5 + min(pos_count, 5) - min(neg_count, 5)
                        sample_score = max(0, min(10, sample_score))
                        
                        tone_score += sample_score
                        tone_samples += 1
                        
                        # Controlla anche i commenti della PR
                        try:
                            review_comments = self._get_cached_data(
                                f"pr_{pr.number}_comments",
                                lambda: list(pr.get_review_comments())
                            )
                            
                            # Verifica se ci sono commenti di revisione prima di analizzarli
                            if review_comments and len(review_comments) > 0:
                                # Analizza fino a 3 commenti
                                for comment in review_comments[:3]:
                                    comment_text = comment.body.lower() if comment.body else ""
                                    pos_count = sum(1 for word in positive_words if word in comment_text)
                                    neg_count = sum(1 for word in negative_words if word in comment_text)
                                    
                                    sample_score = 5 + min(pos_count, 5) - min(neg_count, 5)
                                    sample_score = max(0, min(10, sample_score))
                                    
                                    tone_score += sample_score
                                    tone_samples += 1
                        except Exception as e:
                            logger.warning(f"Errore nell'analisi dei commenti della PR {pr.number}: {e}")
                except Exception as e:
                    logger.warning(f"Errore nell'analisi delle PR: {e}")
                
                # Calcola il punteggio medio del tono
                if tone_samples > 0:
                    data["tono_costruttivita"] = round(tone_score / tone_samples, 1)
                else:
                    data["tono_costruttivita"] = 5  # Default neutro se non ci sono campioni
            except Exception as e:
                logger.error(f"Errore nell'analisi del tono: {e}", exc_info=True)
                data["tono_costruttivita"] = 5
                
            # Controlla se ci sono label usati nelle issue
            try:
                issues = self._get_cached_data(
                    "sample_issues_for_labels",
                    lambda: list(self.repo.get_issues(state="all")[:10])
                )
                
                for issue in issues:
                    if issue.labels:
                        data["label_usage"] = True
                        break
            except Exception as e:
                logger.warning(f"Errore nel controllo dell'uso dei label: {e}")

        except Exception as e:
            logger.error(f"Errore generale nel recupero dei dati della community: {e}", exc_info=True)

        # Salva nella cache
        self._cache["community_data"] = data
        return data

    def analyze(self) -> Dict:
        if not self.repo:
            return {"error": "Repository non trovato o non accessibile"}

        print(f"\nAnalisi del repository: {self.repo_name}")
        
        # Analizza ogni categoria di parametri
        self.results = {
            "nome_repository": self.repo_name,
            "url": f"https://github.com/{self.repo_name}",
            "data_analisi": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "punteggi": {},
            "dettagli": {},
            "suggerimenti": {},
            "storico": []
        }

        # Analizza ogni categoria di parametri
        for categoria, parametri in self.config["parametri"].items():
            print(f"\nAnalisi categoria: {categoria}")
            self.results["dettagli"][categoria] = {}
            
            for nome_param, info_param in track(parametri.items(), description=f"Analisi {categoria}"):
                try:
                    valore, punteggio, conta_punteggio = self._analyze_parameter(categoria, nome_param, info_param)
                    
                    self.results["dettagli"][categoria][nome_param] = {
                        "valore": valore if valore is not None else "N/A",
                        "punteggio": punteggio if punteggio is not None else None,
                        "peso": info_param.get("peso", 1),
                        "descrizione": info_param.get("descrizione", ""),
                        "conta_punteggio": conta_punteggio,
                        "score_is_na": punteggio is None or punteggio == "N/A"
                    }
                except Exception as e:
                    self.console.print(f"[red]Errore nell'analisi del parametro {nome_param}: {e}[/red]")
                    self.results["dettagli"][categoria][nome_param] = {
                        "valore": "Errore",
                        "punteggio": None,  # None instead of 0 for errors
                        "peso": info_param.get("peso", 1),
                        "descrizione": info_param.get("descrizione", ""),
                        "conta_punteggio": False,
                        "score_is_na": True
                    }

        # Calcola i punteggi per categoria e il punteggio totale
        self._calculate_scores()
        
        # Visualizza i suggerimenti nel terminale
        if self.results.get("suggerimenti"):
            self.console.print("\n[bold]Suggerimenti per il miglioramento:[/bold]")
            for categoria, suggerimenti in self.results["suggerimenti"].items():
                if suggerimenti:  # Mostra la categoria solo se ci sono suggerimenti
                    self.console.print(f"\n[bold]{categoria.upper()}:[/bold]")
                    for suggerimento in suggerimenti:
                        self.console.print(f"  • {suggerimento}")
        
        # Calcola il punteggio totale
        punteggi = list(self.results["punteggi"].values())
        if punteggi:
            self.results["punteggio_totale"] = round(sum(punteggi) / len(punteggi), 2)
            
            # Display scores in terminal
            self._display_scores_terminal()
            
            # Aggiungi una valutazione qualitativa
            valutazione = "VALUTAZIONE QUALITATIVA: "
            if self.results["punteggio_totale"] >= 8:
                valutazione += "Eccellente\n\nRepository di alta qualità con ottime pratiche di sviluppo."
            elif self.results["punteggio_totale"] >= 6:
                valutazione += "Buono\n\nRepository ben mantenuto con alcune aree di miglioramento."
            elif self.results["punteggio_totale"] >= 4:
                valutazione += "Mediocre\n\nRepository con significative carenze in diverse aree."
            else:
                valutazione += "Scarso\n\nRepository che richiede significativi miglioramenti."
                
            # Identifica le aree più problematiche
            aree_problematiche = [CATEGORY_LABELS_MAPPING.get(categoria, categoria) # Use mapped labels
                                for categoria, punteggio in self.results["punteggi"].items() 
                                if punteggio < 4]
            if aree_problematiche:
                valutazione += "\n\nAree di miglioramento: " + ", ".join(aree_problematiche)
                
            self.results["valutazione_qualitativa"] = valutazione
        
        # Aggiorna lo storico dei punteggi
        self._update_history()
        
        # Esegui analisi di sicurezza aggiuntiva (Bandit) e aggiungi ai risultati
        # Nota: Questo punteggio non è attualmente integrato nel punteggio totale
        # ma viene mostrato e salvato nel report.
        security_score_bandit = self._check_security(self.local_repo_path if self.local_repo_path else ".")
        self.results["dettagli"].setdefault("sicurezza", {})["bandit_score"] = {
            "valore": f"Punteggio Bandit: {security_score_bandit:.2f}/10",
            "punteggio": security_score_bandit,
            "peso": 1, # Considera se includere nel calcolo del punteggio di categoria
            "descrizione": "Punteggio basato sull'analisi di sicurezza statica con Bandit (0=molti problemi, 10=nessun problema).",
            "conta_punteggio": False # Non conta nel punteggio di categoria per ora
        }
        print(f"Security score (Bandit): {security_score_bandit:.2f}")
        
        return self.results

    def _normalize_score(self, value: float, min_val: float, max_val: float, out_min: float = 0, out_max: float = 10, inverse: bool = False) -> float:
        """Normalizza un valore in un range specifico.

        Args:
            value: Valore da normalizzare
            min_val: Valore minimo del range di input
            max_val: Valore massimo del range di input
            out_min: Valore minimo del range di output (default: 0)
            out_max: Valore massimo del range di output (default: 10)
            inverse: Se True, inverte la scala (valori più alti diventano più bassi)

        Returns:
            Valore normalizzato nel range specificato
        """
        try:
            if min_val == max_val:
                return out_min if inverse else out_max

            # Limita il valore all'intervallo di input
            value = max(min_val, min(value, max_val))

            # Calcola il valore normalizzato
            normalized = (value - min_val) / (max_val - min_val)
            if inverse:
                normalized = 1 - normalized

            # Scala al range di output
            return out_min + (normalized * (out_max - out_min))
        except (TypeError, ValueError):
            return 0.0

    @timeout_handler
    def _analyze_parameter(self, categoria: str, nome_param: str, info_param: Dict) -> Tuple[Any, float, bool]:
        """Analizza un singolo parametro del repository e genera suggerimenti.

        Args:
            categoria: Nome della categoria del parametro
            nome_param: Nome del parametro
            info_param: Informazioni sul parametro

        Returns:
            Tupla con il valore del parametro, il punteggio normalizzato (0-10) e un flag per il conteggio del punteggio
        """
        # Inizializza le variabili con valori di default
        valore = "Non analizzato"
        punteggio = 0
        conta_punteggio = True
        score_is_na = False  # Flag per indicare se il punteggio è N/A (non analizzato)
        
        # Assicurati che il dizionario suggerimenti esista nei risultati
        if "suggerimenti" not in self.results:
            self.results["suggerimenti"] = {}
            
        # Inizializza i suggerimenti per questa categoria se non esistono
        if categoria not in self.results["suggerimenti"]:
            self.results["suggerimenti"][categoria] = []
            
        try:
            # Popolarità & Impatto
            if categoria == "distribuzione":
                pop_data = self._fetch_popolarita_data()
                if nome_param == "stelle":
                    valore = f"{pop_data['stars']} stelle"
                    # Improved stars scoring with logarithmic scale for more realistic assessment
                    # Log scale rewards early stars more significantly while still giving credit to highly starred repos
                    if pop_data['stars'] > 0:
                        log_stars = max(0, min(10, 2.5 * (1 + (math.log10(pop_data['stars'] + 1) / math.log10(1000)))))
                        punteggio = log_stars
                    else:
                        punteggio = 0
                    
                    # More granular suggestion based on score
                    if punteggio < 1:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Visibilità inesistente. Richiede un'azione immediata e su vasta scala. Concentrati su annunci iniziali su tutte le piattaforme rilevanti e contatta influencer."
                        )
                    elif punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Visibilità molto bassa. È cruciale iniziare una promozione attiva e mirata. Condividi su social media specifici, forum e considera un breve post di blog introduttivo."
                        )
                    elif punteggio < 3:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "La visibilità è ancora molto bassa. Intensifica gli sforzi di promozione di base e cerca le prime interazioni."
                        )
                    elif punteggio < 4:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Visibilità in crescita, ma ancora limitata. Aumenta la frequenza della promozione e valuta guest post su blog di settore."
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "La visibilità sta migliorando. Continua a promuovere e inizia a interagire con i primi osservatori."
                        )
                    elif punteggio < 6:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buona base di visibilità iniziale. Inizia a concentrarti sull'engagement dei primi utenti e chiedi feedback."
                        )
                    elif punteggio < 7:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Visibilità solida. Continua a condividere aggiornamenti e crea contenuti più coinvolgenti come brevi tutorial."
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Ottima visibilità. Mantieni un engagement attivo e cerca opportunità di collaborazione con altri progetti simili."
                        )
                    elif punteggio < 9:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Visibilità elevata. Nutri la community e cerca modi per espandere ulteriormente la portata, magari con eventi online."
                        )
                    elif punteggio <= 10:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Visibilità eccezionale. Continua a mantenere l'impegno e ascolta i feedback per una crescita continua, valutando un programma per contributori."
                        )
                        
                elif nome_param == "forks":
                    valore = f"{pop_data['forks']} fork"
                    punteggio = self._normalize_score(pop_data['forks'], 0, 500, 0, 10)

                    # Suggerimenti più granulari basati sul punteggio
                    if punteggio < 1:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di fork estremamente basso. Rendi il progetto più accessibile con una documentazione basilare e un README chiaro."
                        )
                    elif punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochissimi fork. Incoraggia il riutilizzo del codice con esempi chiari e casi d'uso ben documentati. Evidenzia i vantaggi del fork."
                        )
                    elif punteggio < 3:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di fork è ancora molto basso. Mostra come contribuire facilmente e come il fork può beneficiare altri sviluppatori."
                        )
                    elif punteggio < 4:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di fork è in crescita, ma ancora limitato. Fornisci guide su come personalizzare e estendere il progetto tramite fork."
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Migliora la documentazione e gli esempi per incoraggiare più fork e riutilizzo del codice. Sottolinea la licenza e i termini d'uso."
                        )
                    elif punteggio < 6:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Un numero discreto di fork. Mantieni la documentazione aggiornata e rispondi alle domande sui fork."
                        )
                    elif punteggio < 7:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di fork. Considera di evidenziare i progetti che utilizzano il tuo codice e di mostrare i fork più attivi."
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Ottimo numero di fork. Continua a supportare la community dei fork e considera di integrarne i contributi più validi."
                        )
                    elif punteggio < 9:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di fork elevato. Promuovi le best practice per il forking e la contribuzione al progetto principale."
                        )
                    elif punteggio <= 10:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di fork eccezionale. Mantieni un ambiente collaborativo e valorizza i contributi derivati dai fork."
                        )
                        
                elif nome_param == "watchers":
                    valore = f"{pop_data['watchers']} watchers"
                    punteggio = self._normalize_score(pop_data['watchers'], 0, 200, 0, 10)

                    # Suggerimenti più granulari basati sul punteggio
                    if punteggio < 1:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di osservatori estremamente basso. Inizia a comunicare anche i minimi progressi e spiega come seguire il repository per rimanere aggiornati."
                        )
                    elif punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochissimi osservatori. Comunica attivamente gli aggiornamenti e incoraggia gli utenti a seguire il repository per non perdere novità importanti."
                        )
                    elif punteggio < 3:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di osservatori è ancora basso. Sottolinea il valore di seguire il progetto per essere informati su bugfix, nuove funzionalità e release."
                        )
                    elif punteggio < 4:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di osservatori sta crescendo lentamente. Mantieni una comunicazione costante e mostra i vantaggi di seguire attivamente il progetto."
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Mantieni gli utenti informati sugli aggiornamenti attraverso release notes dettagliate e annunci chiari sulle nuove funzionalità o correzioni."
                        )
                    elif punteggio < 6:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Un buon numero di osservatori sta seguendo il progetto. Continua a fornire aggiornamenti significativi e tempestivi."
                        )
                    elif punteggio < 7:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di osservatori. Mantieni il loro interesse con aggiornamenti regolari, magari evidenziando le prossime roadmap o funzionalità in sviluppo."
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Ottimo numero di osservatori. Continua a comunicare in modo efficace e considera di utilizzare canali multipli per gli aggiornamenti (es. newsletter, social media)."
                        )
                    elif punteggio < 9:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di osservatori elevato. Mantieni un flusso costante di informazioni di valore e interagisci con la community di osservatori."
                        )
                    elif punteggio <= 10:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di osservatori eccezionale. Continua a fornire aggiornamenti di alta qualità e considera di coinvolgere attivamente gli osservatori nel futuro del progetto."
                        )
                        
                elif nome_param == "contributori":
                    valore = f"{pop_data['contributori']} contributori"
                    punteggio = self._normalize_score(pop_data['contributori'], 0, 50, 0, 10)

                    # Suggerimenti più granulari basati sul punteggio
                    if punteggio < 1:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Nessun contributore. È fondamentale creare un ambiente accogliente per i nuovi arrivati. Inizia con issue 'good first issue' molto chiare e semplici."
                        )
                    elif punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochi contributori. Crea issue con 'good first issue' e 'help wanted' ben definite per incoraggiare la partecipazione. Offri supporto ai nuovi contributori."
                        )
                    elif punteggio < 3:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di contributori è molto basso. Documenta chiaramente il processo di contribuzione e mostra come anche piccoli cambiamenti sono apprezzati."
                        )
                    elif punteggio < 4:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di contributori è in crescita, ma ancora limitato. Crea una guida per i contributori e tag 'good first issue' per attrarre nuovi sviluppatori. Sii reattivo alle loro PR."
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Crea una guida per i contributori dettagliata e tagga le issue adatte ai principianti ('good first issue'). Incoraggia la discussione e il feedback sulle PR."
                        )
                    elif punteggio < 6:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Un numero discreto di contributori. Mantieni la comunicazione aperta e riconosci i loro contributi pubblicamente."
                        )
                    elif punteggio < 7:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di contributori. Riconosci il loro lavoro regolarmente e mantieni la community attiva con discussioni e proposte."
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Ottimo numero di contributori. Valorizza i contributi significativi e considera di coinvolgere i contributori attivi nel processo decisionale."
                        )
                    elif punteggio < 9:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di contributori elevato. Promuovi un ambiente collaborativo e considera di nominare maintainer per aree specifiche del progetto."
                        )
                    elif punteggio <= 10:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero di contributori eccezionale. Continua a coltivare la community, ringrazia pubblicamente i contributori e mantieni una governance chiara."
                        )
                        
                elif nome_param == "dipendenti":
                    valore = f"{pop_data['dipendenti']} progetti dipendenti"
                    punteggio = self._normalize_score(pop_data['dipendenti'], 0, 100, 0, 10)

                    # Suggerimenti più granulari basati sul punteggio
                    if punteggio < 1:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Nessun progetto dipendente. È fondamentale rendere il tuo progetto facilmente utilizzabile. Pubblica su gestori di pacchetti e crea una documentazione di base."
                        )
                    elif punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochissimi progetti dipendenti. Pubblica su gestori di pacchetti (es. Maven, NuGet) e crea tutorial o guide introduttive per facilitare l'adozione."
                        )
                    elif punteggio < 3:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di progetti dipendenti è molto basso. Concentrati sulla creazione di esempi d'uso pratici e sulla promozione del tuo pacchetto nelle community pertinenti."
                        )
                    elif punteggio < 4:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il numero di progetti dipendenti è in crescita, ma migliorabile. Considera di scrivere articoli di blog o brevi video che mostrino come integrare il tuo progetto."
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Considera di pubblicare il pacchetto su gestori di pacchetti come npm o PyPI per aumentarne l'adozione. Fornisci esempi di codice ben documentati."
                        )
                    elif punteggio < 6:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Un numero discreto di progetti dipendenti. Mantieni la compatibilità con le versioni precedenti e comunica chiaramente eventuali breaking changes."
                        )
                    elif punteggio < 7:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Discreto numero di dipendenti. Mantieni compatibilità e comunica chiaramente le breaking changes. Considera di offrire supporto alla migrazione per le nuove versioni."
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di dipendenti. Continua a rilasciare aggiornamenti stabili e ben documentati. Monitora l'utilizzo e raccogli feedback dai progetti dipendenti."
                        )
                    elif punteggio < 9:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero elevato di progetti dipendenti. Concentrati sulla stabilità, sulla fornitura di API chiare e ben documentate e sull'ascolto delle esigenze dei tuoi utenti."
                        )
                    elif punteggio <= 10:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Numero eccezionale di progetti dipendenti. Mantieni un'alta qualità del codice, una comunicazione trasparente e considera di coinvolgere la community dei progetti dipendenti nello sviluppo futuro."
                        )
                        
                elif nome_param == "engagement_rate":
                    valore = f"{self._check_engagement_rate():.2f}"
                    punteggio = self._check_engagement_rate()
                    
                elif nome_param == "distribuzione_contributi":
                    distribution_score = self._check_contributor_distribution()
                    if distribution_score > 0:
                        valore = f"Punteggio distribuzione: {distribution_score:.2f}/10"
                    else:
                        valore = "Non calcolabile"
                    punteggio = distribution_score
                    
                    if punteggio < 3:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "La maggior parte del lavoro è svolto da un singolo contributore. Incentiva una partecipazione più ampia della community"
                        )
                    elif punteggio < 6:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "La distribuzione dei contributi è moderatamente centralizzata. Considera di incoraggiare più partecipazione da altri contributori"
                        )
                
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                    conta_punteggio = False
                
                return valore, round(punteggio, 2), conta_punteggio
            
            # Attività & Manutenzione
            elif categoria == "manutenzione":
                if nome_param == "release_tag_frequenza":
                    try:
                        # Prima verifica le release ufficiali
                        try:
                            releases = self._get_cached_data(
                                "releases",
                                lambda: list(self.repo.get_releases()[:MAX_ITEMS_PER_REQUEST])
                            )
                        except IndexError:
                            # Handle the case when there are no releases
                            releases = []
                            
                        # Poi cerca i tag
                        tags_data = self._fetch_tags_data()
                        
                        # Determina quale metrica usare
                        if releases:
                            now = datetime.datetime.now(datetime.timezone.utc)
                            year_ago = now - datetime.timedelta(days=365)
                            
                            # Ensure that all datetimes have timezone information
                            recent_releases = []
                            for r in releases:
                                release_date = self._ensure_tz_aware(r.created_at)
                                if release_date and release_date > year_ago:
                                    recent_releases.append(r)
                            
                            release_count = len(recent_releases)
                            valore = f"{release_count} release negli ultimi 12 mesi"
                            punteggio = self._normalize_score(release_count, 0, 12, 0, 10)  # Idealmente una release al mese
                            
                            if release_count == 0:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Non ci sono release negli ultimi 12 mesi. Considera di creare release regolari"
                                )
                            elif release_count < 4:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Aumenta la frequenza delle release per fornire aggiornamenti più regolari"
                                )
                        elif tags_data > 0:
                            # Usa informazioni dai tag se non ci sono release
                            valore = f"Media giorni tra tag: {round(tags_data, 1)}"
                            # Meno giorni tra i tag => punteggio più alto (max 10 points per aggiornamenti mensili o più frequenti)
                            punteggio = max(0.0, 10.0 - (tags_data / 30.0))
                            
                            if tags_data > 90:  # Più di 3 mesi tra i tag in media
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "La frequenza di tagging è bassa. Considera di taggare versioni più regolarmente"
                                )
                        else:
                            valore = "Nessuna release o tag trovato"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Non sono state trovate release o tag. Considera di utilizzare il sistema di release di GitHub"
                            )
                    except Exception as e:
                        logger.error(f"Errore nell'analisi delle release e tag: {e}", exc_info=True)
                        valore = "Errore analisi"
                        punteggio = 0
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Si è verificato un errore nell'analisi delle release e tag"
                        )

                elif nome_param == "attivita_issues_ratio":
                    try:
                        issues = self._get_cached_data(
                            "issues",
                            lambda: list(self.repo.get_issues(state='all')[:MAX_ITEMS_PER_REQUEST])
                        )
                        if issues:
                            total_issues = len(issues)
                            closed_issues = len([i for i in issues if i.state == 'closed'])
                            ratio = closed_issues / total_issues if total_issues > 0 else 0
                            valore = round(ratio * 100, 2)  # Percentuale
                            punteggio = self._normalize_score(ratio, 0.5, 0.9, 0, 10)  # Idealmente tra 50% e 90%
                            
                            if ratio < 0.5:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "La percentuale di issues chiuse è bassa. Dedica più tempo alla risoluzione delle issues"
                                )
                            elif ratio > 0.9:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Quasi tutte le issues sono chiuse. Verifica di non chiudere le issues troppo rapidamente"
                                )
                        else:
                            valore = 0
                            punteggio = 5
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Non sono state trovate issues. Considera di abilitare il tracker delle issues"
                            )
                    except Exception as e:
                        print(f"Errore nell'analisi delle issues: {e}")
                        valore = "Errore analisi"
                        punteggio = 0
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Si è verificato un errore nell'analisi delle issues"
                        )

                elif nome_param == "data_ultimo_commit":
                    # Usa la cache per ottenere il commit più recente
                    last_commit = self._get_cached_data(
                        "last_commit",
                        lambda: self.repo.get_commits()[0] if self.repo and self.repo.get_commits().totalCount > 0 else None
                    )
                    
                    if last_commit:
                        try:
                            # Ensure commit and author data exist
                            commit_data = last_commit.commit
                            author_data = commit_data.author if commit_data else None
                            last_commit_date = self._ensure_tz_aware(author_data.date) if author_data else None

                            if last_commit_date:
                                now = datetime.datetime.now(datetime.timezone.utc)
                                days_since_last_commit = (now - last_commit_date).days
                                # Assicuriamoci che il valore sia positivo
                                days_since_last_commit = max(0, days_since_last_commit)
                                valore = f"{days_since_last_commit} giorni fa"
                                
                                # More granular scoring based on recency
                                if days_since_last_commit <= 7:
                                    punteggio = 10.0  # Very recent activity (within a week)
                                elif days_since_last_commit <= 14:
                                    punteggio = 9.0   # Recent activity (within two weeks)
                                elif days_since_last_commit <= 30:
                                    punteggio = 8.0   # Active (within a month)
                                elif days_since_last_commit <= 60:
                                    punteggio = 7.0   # Somewhat active (within two months)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "L'attività di commit è buona, ma cerca di mantenerla più frequente (idealmente entro 30 giorni)."
                                    )
                                elif days_since_last_commit <= 90:
                                    punteggio = 6.0   # Less active (within three months)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "L'attività di commit è rallentata. Considera di aumentare la frequenza degli aggiornamenti."
                                    )
                                elif days_since_last_commit <= 120:
                                    punteggio = 5.0   # Moderately inactive (four months)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository non riceve commit da alcuni mesi. Valuta di riprendere lo sviluppo attivo."
                                    )
                                elif days_since_last_commit <= 180:
                                    punteggio = 4.0   # Starting to stagnate (six months)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository non riceve commit da diversi mesi. Considera di riprendere lo sviluppo attivo."
                                    )
                                elif days_since_last_commit <= 270:
                                    punteggio = 3.0   # Stagnant (nine months)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository sembra poco manutenuto (ultimo commit tra 6 e 9 mesi fa). Pianifica aggiornamenti."
                                    )
                                elif days_since_last_commit <= 365:
                                    punteggio = 2.0   # Very stagnant (a year)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository sembra poco manutenuto (ultimo commit tra 9 e 12 mesi fa). Pianifica aggiornamenti o valuta l'archiviazione."
                                    )
                                elif days_since_last_commit <= 730:
                                    punteggio = 1.0   # Nearly abandoned (two years)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository è pressoché inattivo (ultimo commit tra 1 e 2 anni fa). Valuta seriamente l'archiviazione se non è più mantenuto."
                                    )
                                else:
                                    punteggio = 0.0   # Abandoned (more than two years)
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository è inattivo da oltre due anni. Considera di archiviarlo se non è più mantenuto."
                                    )
                            else:
                                valore = "Data non disponibile"
                                punteggio = 5 # Neutral score if date is missing
                                logger.warning("Data autore non trovata per l'ultimo commit.")
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Impossibile determinare la data dell'ultimo commit."
                                )
                        except Exception as e:
                            logger.error(f"Errore nel calcolo della data dell'ultimo commit: {e}", exc_info=True)
                            print(f"Errore nel calcolo della data dell'ultimo commit: {e}")
                            valore = "Errore data"
                            punteggio = 5  # Valore neutro in caso di errore
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Si è verificato un errore nel recupero della data dell'ultimo commit."
                            )
                    else:
                        valore = "Nessun commit trovato"
                        punteggio = 0
                        logger.warning("Nessun commit trovato nel repository.")
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Non sono stati trovati commit. Il repository potrebbe essere vuoto o inaccessibile."
                        )

                elif nome_param == "frequenza_commit":
                    # Usa la cache per ottenere i commit
                    commits = self._get_cached_data(
                        "recent_commits",
                        lambda: list(self.repo.get_commits()[:100]) if self.repo else []
                    )
                    
                    if commits and len(commits) >= 2:
                        try:
                            # Get dates safely, ensuring commit and author exist
                            first_commit_data = commits[-1].commit
                            first_author_data = first_commit_data.author if first_commit_data else None
                            first_date = self._ensure_tz_aware(first_author_data.date) if first_author_data else None

                            last_commit_data = commits[0].commit
                            last_author_data = last_commit_data.author if last_commit_data else None
                            last_date = self._ensure_tz_aware(last_author_data.date) if last_author_data else None
                            
                            # Proceed only if both dates are valid
                            if first_date and last_date:
                                # Ensure last_date is more recent
                                if first_date > last_date:
                                    first_date, last_date = last_date, first_date
                                
                                days_diff = (last_date - first_date).days
                                
                                # Avoid division by zero if commits are on the same day
                                if days_diff > 0:
                                    commits_per_day = len(commits) / days_diff
                                    valore = f"{commits_per_day:.2f} commit/giorno (ultimi {len(commits)})"
                                    
                                    # More granular scoring based on commits frequency
                                    if commits_per_day >= 5.0:
                                        punteggio = 10.0  # Excellent: Very active development
                                    elif commits_per_day >= 3.0:
                                        punteggio = 9.5   # Exceptional: Highly active development
                                    elif commits_per_day >= 2.0:
                                        punteggio = 9.0   # Great: Very active development
                                    elif commits_per_day >= 1.5:
                                        punteggio = 8.5   # Very good: Active daily development
                                    elif commits_per_day >= 1.0:
                                        punteggio = 8.0   # Good: About one commit per day
                                    elif commits_per_day >= 0.7:
                                        punteggio = 7.0   # Fairly good: Regular commits (5+ per week)
                                    elif commits_per_day >= 0.5:
                                        punteggio = 6.0   # Moderate: Several commits per week
                                    elif commits_per_day >= 0.3:
                                        punteggio = 5.0   # Acceptable: About 2 commits per week
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "La frequenza dei commit è accettabile, ma potrebbe essere aumentata per una maggiore continuità"
                                        )
                                    elif commits_per_day >= 0.15:
                                        punteggio = 4.0   # Below average: About 1 commit per week
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "Aumenta la frequenza dei commit per mantenere uno sviluppo più costante (almeno 2-3 a settimana)"
                                        )
                                    elif commits_per_day >= 0.1:
                                        punteggio = 3.0   # Slow: Less than 1 commit per week
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "La frequenza dei commit è bassa. Cerca di commitare almeno settimanalmente"
                                        )
                                    elif commits_per_day >= 0.05:
                                        punteggio = 2.0   # Very slow: About 1-2 commits per month
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "La frequenza dei commit è molto bassa (1-2 al mese). Considera di aumentare l'attività di sviluppo"
                                        )
                                    elif commits_per_day > 0:
                                        punteggio = 1.0   # Minimal: Less than 1 commit per month
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "L'attività di commit è minima (meno di uno al mese). Il progetto necessita di maggiore attività"
                                        )
                                    else:
                                        punteggio = 0.0   # Inactive
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "Non ci sono stati commit recenti nel periodo analizzato"
                                        )
                                else:
                                    # Handle case where all commits are within the same day or less than 24h apart
                                    valore = f"{len(commits)} commit recenti (stesso giorno)"
                                    
                                    # More granular scoring based on number of same-day commits
                                    if len(commits) >= 20:
                                        punteggio = 10.0  # Excellent: Very intense development
                                    elif len(commits) >= 15:
                                        punteggio = 9.5   # Exceptional: Many commits in one day
                                    elif len(commits) >= 10:
                                        punteggio = 9.0   # Great: Many commits in one day
                                    elif len(commits) >= 8:
                                        punteggio = 8.5   # Very good: Active development
                                    elif len(commits) >= 6:
                                        punteggio = 8.0   # Good: Solid development session
                                    elif len(commits) >= 5:
                                        punteggio = 7.5   # Fairly good: Good development session
                                    elif len(commits) >= 4:
                                        punteggio = 7.0   # Above average: Good development activity
                                    elif len(commits) >= 3:
                                        punteggio = 6.0   # Moderate: Several commits
                                    elif len(commits) == 2:
                                        punteggio = 5.0   # Acceptable: A couple of commits
                                    else:
                                        punteggio = 4.0   # Below average: Minimal commits
                                    
                                    logger.debug("Commit troppo ravvicinati per calcolare frequenza giornaliera sensata.")
                            else:
                                valore = "Date commit non valide"
                                punteggio = 5  # Neutral score if dates are missing
                                logger.warning("Date autore non trovate per alcuni commit recenti.")
                        except Exception as e:
                            logger.error(f"Errore nel calcolo della frequenza dei commit: {e}", exc_info=True)
                            print(f"Errore nel calcolo della frequenza dei commit: {e}")
                            valore = "Errore calcolo"
                            punteggio = 5
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Si è verificato un errore nel calcolo della frequenza dei commit"
                            )
                    elif commits and len(commits) == 1:
                        valore = "1 commit recente"
                        punteggio = 1  # Low score for single commit
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "È stato trovato un solo commit recente. Aumenta la frequenza di sviluppo"
                        )
                    else:  # No commits or empty list
                        valore = "Nessun commit recente"
                        punteggio = 0
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Non sono stati trovati commit recenti. Il repository potrebbe essere inattivo"
                        )

                        
                elif nome_param == "stato_archivio":
                    valore = "Attivo" if not self.repo.archived else "Archiviato"
                    punteggio = 10 if not self.repo.archived else 0
                    conta_punteggio = True
                    return valore, round(punteggio, 2), conta_punteggio
                
                elif nome_param == "attivita_issues_tempo":
                    issues_data = self._fetch_issues_data()
                    closed_times = issues_data.get("closed_times", [])
                    
                    # Make sure we have numeric values and the list is not empty
                    if closed_times and all(isinstance(x, (int, float)) for x in closed_times):
                        avg_time = sum(closed_times) / len(closed_times)
                        valore = f"Tempo medio chiusura issues: {round(avg_time, 1)} giorni"
                        punteggio = max(0.0, 10.0 - (avg_time / 10.0))
                    else:
                        valore = "Nessuna issue chiusa o dati non validi"
                        punteggio = 0
                elif nome_param == "attivita_pr_ratio":
                    pr_data = self._fetch_pr_data()
                    if pr_data["total"] > 0:
                        ratio = pr_data["merged"] / pr_data["total"]
                        valore = f"PR merge ratio: {round(ratio*100, 1)}%"
                        punteggio = round(ratio*10, 2)
                    else:
                        valore = "Nessuna PR trovata"
                        punteggio = 0
                elif nome_param == "attivita_pr_tempo":
                    pr_data = self._fetch_pr_data()
                    times = pr_data["merged_times"]
                    if times:
                        avg_close = sum(times)/len(times)
                        valore = f"Tempo medio chiusura PR: {round(avg_close, 1)} giorni"
                        punteggio = max(0.0, 10.0 - (avg_close / 10.0))
                    else:
                        valore = "Nessuna PR chiusa/mergiata"
                        punteggio = 0
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio

            # Qualità del codice
            elif categoria == "codice":
                if nome_param == "complessita_media":
                    valore = "Media complessità"
                    complexity = self._check_complexity(".")
                    # Più bassa la complessità media, più alto il punteggio.
                    punteggio = max(0.0, 10.0 - (complexity / 2.0))
                elif nome_param == "aderenza_stile":
                    valore = "Controllo stile"
                    punteggio = self._check_style(".")
                elif nome_param == "code_smells":
                    valore = "Analisi code smells"
                    punteggio = self._check_code_smells(".")
                elif nome_param == "commenti_codice":
                    valore = "Copertura commenti"
                    punteggio = self._check_comment_coverage(".")
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                    conta_punteggio = False

                return valore, round(punteggio, 2), conta_punteggio

            # Documentazione
            elif categoria == "documentazione":
                doc_data = self._check_documentation_files()
                if nome_param == "readme":
                    valore = "Presente" if doc_data["has_readme"] else "Assente"
                    punteggio = 10 if doc_data["has_readme"] else 0
                elif nome_param == "documentazione_estesa":
                    valore = "Docs/Wiki rilevati" if doc_data["has_extended_docs"] else "Nessuna doc estesa"
                    punteggio = 10 if doc_data["has_extended_docs"] else 0
                elif nome_param == "file_license":
                    valore = "File LICENSE trovato" if doc_data["has_license"] else "Assente"
                    punteggio = 10 if doc_data["has_license"] else 0
                elif nome_param == "file_contrib_coc":
                    valore = "File CONTRIBUTING/CODE_OF_CONDUCT" if doc_data["has_contrib_coc"] else "Non trovato"
                    punteggio = 10 if doc_data["has_contrib_coc"] else 0
                elif nome_param == "qualita_esempi":
                    valore = "Cartella /examples esistente" if doc_data["has_examples"] else "Nessun esempio"
                    punteggio = 10 if doc_data["has_examples"] else 0
                elif nome_param == "badge_readme":
                    valore = "Presente" if self._check_badges_in_readme() else "Assente"
                    punteggio = 10 if self._check_badges_in_readme() else 0
                elif nome_param == "changelog_presenza":
                    # Implementazione del nuovo parametro changelog_presenza
                    has_changelog = self._check_changelog_presence()
                    valore = "Presente" if has_changelog else "Assente"
                    punteggio = 10 if has_changelog else 0
                    
                    if not has_changelog:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Aggiungi un file CHANGELOG.md per tracciare le modifiche e migliorare la trasparenza delle release"
                        )
                elif nome_param == "semantic_versioning":
                    # Implementazione del nuovo parametro semantic_versioning
                    semver_score, semver_status = self._check_semantic_versioning()
                    valore = semver_status
                    punteggio = semver_score
                    
                    if semver_score < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Adotta Semantic Versioning (MAJOR.MINOR.PATCH) nei tag e nelle release per una migliore gestione delle dipendenze"
                        )
                elif nome_param == "licenza_osi_approvata":
                    # Implementazione per verificare se la licenza è approvata dall'OSI
                    is_approved, license_name = self._check_license_osi_approved()
                    valore = license_name
                    punteggio = 10 if is_approved else 0
                    
                    if not is_approved:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Considera di adottare una licenza approvata dall'OSI (es. MIT, Apache 2.0, GPL) per facilitare l'adozione del progetto"
                        )

                return valore, round(punteggio, 2), conta_punteggio
            
            # Community & Collaborazione
            elif categoria == "collaborazione":
                com_data = self._fetch_community_data()
                if nome_param == "github_discussions":
                    valore = "Abilitato" if com_data["discussions_enabled"] else "Non disponibile"
                    punteggio = 10 if com_data["discussions_enabled"] else 5
                    
                    if not com_data["discussions_enabled"]:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Abilita GitHub Discussions per facilitare conversazioni più ampie sulla community e sul progetto"
                        )
                elif nome_param == "issue_pr_templates":
                    valore = "Presenti" if com_data["templates_enabled"] else "Non disponibili"
                    punteggio = 10 if com_data["templates_enabled"] else 5
                    
                    if not com_data["templates_enabled"]:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Crea template per issue e PR per standardizzare le richieste e facilitare i contributi"
                        )
                elif nome_param == "tono_costruttivita":
                    valore = f"Indice di costruttività: {com_data['tono_costruttivita']}/10"
                    punteggio = com_data["tono_costruttivita"]
                    
                    if com_data["tono_costruttivita"] < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Migliora il tono delle comunicazioni nelle issue e PR. Più cortesia e chiarezza favoriscono una community più sana"
                        )
                elif nome_param == "uso_label_issues":
                    valore = "Labels in uso" if com_data["label_usage"] else "Nessun label rilevato"
                    punteggio = 10 if com_data["label_usage"] else 5
                    
                    if not com_data["label_usage"]:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Utilizza i label nelle issue per organizzare meglio le richieste e facilitarne la gestione"
                        )
                elif nome_param == "attivita_discussions":
                    valore = f"{self._check_discussions_activity():.2f}"
                    punteggio = self._check_discussions_activity()

                return valore, round(punteggio, 2), conta_punteggio

            # Sicurezza
            elif categoria == "sicurezza":
                if nome_param == "file_security":
                    # Miglioriamo la verifica della presenza di SECURITY.md e altri file di sicurezza
                    valore = "Non trovato" # Default to not found
                    punteggio = 0
                    security_files_found = []
                    
                    try:
                        # Lista di possibili file di sicurezza da cercare
                        security_file_patterns = [
                            "SECURITY.md", 
                            "security.md", 
                            "SECURITY.rst", 
                            "SECURITY.txt",
                            "security.txt",
                            "SECURITY_POLICY.md",
                            ".github/SECURITY.md"
                        ]
                        
                        # Check local repo first if available
                        if self.local_repo_path:
                            # Controlla nel filesystem locale
                            # Check root
                            for pattern in security_file_patterns:
                                if not '/' in pattern and os.path.exists(os.path.join(self.local_repo_path, pattern)):
                                    security_files_found.append(pattern)
                                    break # Found one in root
                            # Check .github if not found in root
                            if not security_files_found and os.path.isdir(os.path.join(self.local_repo_path, ".github")):
                                for pattern in security_file_patterns:
                                     if pattern.startswith(".github/") and os.path.exists(os.path.join(self.local_repo_path, pattern)):
                                         security_files_found.append(pattern)
                                         break # Found one in .github
                        else:
                            # Controlla prima la root tramite API
                            contents = self._get_cached_data(
                                "root_contents", 
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            root_files = {item.name.lower(): item for item in contents if item.type == "file"}
                            github_dir_item = next((item for item in contents if item.path.lower() == ".github" and item.type == "dir"), None)

                            for pattern in security_file_patterns:
                                pattern_lower = pattern.lower()
                                if not '/' in pattern_lower and pattern_lower in root_files:
                                     security_files_found.append(pattern)
                                     break # Found in root

                            # Controlla anche nella directory .github if not found and dir exists
                            if not security_files_found and github_dir_item:
                                try:
                                    github_contents = self._get_cached_data(
                                        "github_dir_contents",
                                        lambda: list(self.repo.get_contents(".github"))
                                    )
                                    github_files = {item.name.lower(): item for item in github_contents if item.type == "file"}
                                    
                                    # Check for security files in .github directory
                                    for pattern in security_file_patterns:
                                        if pattern.startswith(".github/"):
                                            filename = pattern.split("/")[1].lower()
                                            if filename in github_files:
                                                security_files_found.append(pattern)
                                                break  # Found in .github
                                except Exception:
                                    pass # Ignore errors fetching .github contents
                        
                        if security_files_found:
                            valore = f"Trovato: {security_files_found[0]}" # Show first found file
                            punteggio = 10  # Assign full score when security file is found
                        else:
                            valore = "Non trovato"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi un file SECURITY.md per descrivere la policy di sicurezza del progetto"
                            )  
                    except Exception as e:
                        logger.warning(f"Errore nella verifica dei file di sicurezza: {e}")
                        valore = "Errore verifica"
                        punteggio = 0

                elif nome_param == "github_security_features":
                    # Verifichiamo l'uso delle funzioni di sicurezza GitHub come dependabot e CODEOWNERS
                    valore = "Non rilevato"
                    punteggio = 0
                    security_features = []
                    
                    try:
                        # Files/dirs to check
                        check_items = {
                            "Dependabot": [".github/dependabot.yml", ".github/dependabot.yaml"],
                            "CodeQL": [".github/workflows/codeql-analysis.yml", ".github/workflows/codeql.yml"], # Common names
                            "CODEOWNERS": [".github/CODEOWNERS"]
                        }
                        
                        if self.local_repo_path:
                            # Cerca i file/dir nel filesystem locale
                            for feature, paths in check_items.items():
                                for path in paths:
                                    # Handle both files and directories
                                    full_path = os.path.join(self.local_repo_path, path)
                                    
                                    # Check if it's a directory that should exist
                                    if path.endswith('/') or '.' not in os.path.basename(path):
                                        if os.path.isdir(full_path) and os.listdir(full_path):  # Directory exists and not empty
                                            security_features.append(feature)
                                            break
                                    # Check if it's a file that should exist
                                    elif os.path.isfile(full_path):
                                        security_features.append(feature)
                                        break
                                        
                                    # Special case for patterns with directories
                                    elif '/' in path:
                                        dir_path = os.path.dirname(full_path)
                                        # If the directory exists, check if the file exists
                                        if os.path.isdir(dir_path):
                                            if os.path.isfile(full_path):
                                                security_features.append(feature)
                                                break
                        else:
                            # Usa API GitHub per il controllo
                            contents = self._get_cached_data(
                                "root_contents", 
                                lambda: list(self.repo.get_contents(""))
                            )
                            github_dir_item = next((item for item in contents if item.path.lower() == ".github" and item.type == "dir"), None)

                            if github_dir_item:
                                try:
                                    github_contents = self._get_cached_data(
                                        "github_dir_contents",
                                        lambda: list(self.repo.get_contents(".github"))
                                    )
                                    
                                    github_content_paths = {item.path.lower() for item in github_contents}
                                    
                                    # Check for Dependabot and CODEOWNERS files
                                    for feature, paths in check_items.items():
                                         if feature != "CodeQL": # Check CodeQL separately
                                             for path in paths:
                                                 if path.lower() in github_content_paths:
                                                     security_features.append(feature)
                                                     break # Found feature

                                    # Check for CodeQL workflow
                                    workflows_dir_item = next((item for item in github_contents if item.path.lower() == ".github/workflows" and item.type == "dir"), None)
                                    if workflows_dir_item:
                                         try:
                                             workflows_contents = self._get_cached_data(
                                                 "workflows_dir_contents",
                                                 lambda: list(self.repo.get_contents(".github/workflows"))
                                             )
                                             workflow_files = {item.name.lower() for item in workflows_contents if item.type == "file"}
                                             for path in check_items["CodeQL"]:
                                                 filename = os.path.basename(path).lower()
                                                 if filename in workflow_files:
                                                     security_features.append("CodeQL")
                                                     break # Found CodeQL
                                         except Exception:
                                             pass # Ignore errors fetching workflows
                                except Exception:
                                    pass # Ignore errors fetching .github contents
                        
                        # Valuta i risultati
                        unique_features = sorted(list(set(security_features)))
                        if unique_features:
                            valore = ", ".join(unique_features)
                            punteggio = 10
                        else:
                            valore = "Nessuna funzionalità di sicurezza rilevata"
                            punteggio = 0
                    except Exception as e:
                        logger.warning(f"Errore nel controllo delle funzioni di sicurezza: {e}")
                        valore = "Errore verifica"
                        punteggio = 0
                
                elif nome_param == "analisi_sast":
                    # Verifichiamo la presenza di analisi di sicurezza statica (SAST) nella pipeline CI
                    valore = "Non rilevato"
                    punteggio = 0
                    sast_tools_found = []
                    
                    try:
                        # Pattern di ricerca per strumenti SAST comuni in file di CI/CD
                        sast_patterns = {
                            "CodeQL": ["uses: github/codeql-action", "codeql-analysis", "codeql_queries"],
                            "SonarQube/SonarCloud": ["sonarqube", "sonarcloud", "sonar-scanner", "sonar:sonar"],
                            "ESLint": ["eslint --security", "eslint-plugin-security"],
                            "Bandit": ["bandit -r", "pip install bandit", "safety check"],
                            "SpotBugs": ["spotbugs", "findsecbugs"],
                            "Snyk": ["snyk test", "uses: snyk/actions"],
                            "Semgrep": ["semgrep", "semgrep-action"],
                            "Checkmarx": ["checkmarx", "cx-flow"],
                            "OWASP ZAP": ["owasp/zap", "zap-baseline", "zaproxy"],
                            "Veracode": ["veracode"],
                            "Fortify": ["fortify", "hpe-security"],
                            "Gosec": ["gosec", "securego"],
                            "Brakeman": ["brakeman -q"],
                            "Trivy": ["trivy scan", "aquasecurity/trivy"]
                        }
                        
                        if self.local_repo_path:
                            # Cerca nei file di configurazione CI/CD per strumenti SAST
                            ci_paths = [
                                ".github/workflows",                   # GitHub Actions
                                ".gitlab-ci.yml",                      # GitLab CI
                                ".travis.yml",                         # Travis CI
                                "azure-pipelines.yml",                 # Azure Pipelines
                                "Jenkinsfile",                         # Jenkins
                                ".circleci/config.yml",                # CircleCI
                                "bitbucket-pipelines.yml",             # Bitbucket Pipelines
                                ".drone.yml",                          # Drone CI
                                "appveyor.yml",                        # AppVeyor
                            ]
                            
                            for ci_path in ci_paths:
                                full_path = os.path.join(self.local_repo_path, ci_path)
                                
                                # Controllo speciale per directory GitHub Actions
                                if ci_path == ".github/workflows" and os.path.isdir(full_path):
                                    for root, _, files in os.walk(full_path):
                                        for file in files:
                                            if file.endswith(('.yml', '.yaml')):
                                                workflow_path = os.path.join(root, file)
                                                try:
                                                    with open(workflow_path, 'r', encoding='utf-8') as f:
                                                        content = f.read()
                                                        for tool, patterns in sast_patterns.items():
                                                            if any(pattern in content for pattern in patterns):
                                                                sast_tools_found.append(f"{tool} (in {os.path.basename(workflow_path)})")
                                                except Exception as e:
                                                    logger.debug(f"Errore nella lettura del file workflow {workflow_path}: {e}")
                                
                                # Controllo per file CI singoli
                                elif os.path.isfile(full_path):
                                    try:
                                        with open(full_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                            for tool, patterns in sast_patterns.items():
                                                if any(pattern in content for pattern in patterns):
                                                    sast_tools_found.append(f"{tool} (in {os.path.basename(full_path)})")
                                    except Exception as e:
                                        logger.debug(f"Errore nella lettura del file CI {full_path}: {e}")
                        else:
                            # Usa API GitHub per controllare i file di CI/CD
                            # Prima controlla se esiste la directory .github/workflows
                            try:
                                root_contents = self._get_cached_data(
                                    "root_contents", 
                                    lambda: list(self.repo.get_contents(""))
                                )
                                
                                github_dir_item = next((item for item in root_contents if item.path.lower() == ".github" and item.type == "dir"), None)
                                
                                if github_dir_item:
                                    github_contents = self._get_cached_data(
                                        "github_dir_contents",
                                        lambda: list(self.repo.get_contents(".github"))
                                    )
                                    
                                    workflows_dir_item = next((item for item in github_contents if item.path.lower() == ".github/workflows" and item.type == "dir"), None)
                                    
                                    if workflows_dir_item:
                                        workflows_contents = self._get_cached_data(
                                            "workflows_dir_contents",
                                            lambda: list(self.repo.get_contents(".github/workflows"))
                                        )
                                        
                                        for workflow in workflows_contents:
                                            if workflow.type == "file" and workflow.name.lower().endswith(('.yml', '.yaml')):
                                                try:
                                                    workflow_content = self.repo.get_contents(workflow.path).decoded_content.decode('utf-8')
                                                    
                                                    for tool, patterns in sast_patterns.items():
                                                        if any(pattern in workflow_content for pattern in patterns):
                                                            sast_tools_found.append(f"{tool} (in {workflow.name})")
                                                except Exception as e:
                                                    logger.debug(f"Errore nel recupero del contenuto del workflow {workflow.path}: {e}")
                                
                                # Controlla altri file CI noti
                                ci_files = [".travis.yml", ".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci/config.yml"]
                                for ci_file in ci_files:
                                    if '/' not in ci_file:  # File nella root
                                        ci_file_item = next((item for item in root_contents if item.name.lower() == ci_file.lower()), None)
                                        if ci_file_item:
                                            try:
                                                ci_content = self.repo.get_contents(ci_file_item.path).decoded_content.decode('utf-8')
                                                for tool, patterns in sast_patterns.items():
                                                    if any(pattern in ci_content for pattern in patterns):
                                                        sast_tools_found.append(f"{tool} (in {ci_file})")
                                            except Exception as e:
                                                logger.debug(f"Errore nel recupero del contenuto del file CI {ci_file}: {e}")
                                    elif ci_file.startswith(".circleci/"):  # File in .circleci
                                        circleci_dir_item = next((item for item in root_contents if item.path.lower() == ".circleci" and item.type == "dir"), None)
                                        if circleci_dir_item:
                                            try:
                                                circleci_contents = self._get_cached_data(
                                                    "circleci_dir_contents",
                                                    lambda: list(self.repo.get_contents(".circleci"))
                                                )
                                                config_file = next((item for item in circleci_contents if item.name.lower() == "config.yml"), None)
                                                if config_file:
                                                    ci_content = self.repo.get_contents(config_file.path).decoded_content.decode('utf-8')
                                                    for tool, patterns in sast_patterns.items():
                                                        if any(pattern in ci_content for pattern in patterns):
                                                            sast_tools_found.append(f"{tool} (in {ci_file})")
                                            except Exception as e:
                                                logger.debug(f"Errore nel recupero dei contenuti di .circleci: {e}")
                                
                            except Exception as e:
                                logger.warning(f"Errore nel controllo degli strumenti SAST via API GitHub: {e}")

                        # Verifica anche per altri file che potrebbero contenere configurazioni di sicurezza
                        # come sonar-project.properties o .eslintrc
                        if self.local_repo_path:
                            sast_config_files = [
                                "sonar-project.properties", 
                                ".eslintrc", 
                                ".eslintrc.js", 
                                ".eslintrc.json",
                                ".bandit",
                                ".snyk"
                            ]
                            for root, _, files in os.walk(self.local_repo_path):
                                for file in files:
                                    if file in sast_config_files:
                                        tool_name = "SonarQube" if file == "sonar-project.properties" else \
                                                  "ESLint" if file.startswith(".eslintrc") else \
                                                  "Bandit" if file == ".bandit" else \
                                                  "Snyk" if file == ".snyk" else "SAST Tool"
                                        sast_tools_found.append(f"{tool_name} (config: {file})")
                        
                        # Valuta i risultati
                        unique_tools = list(set([tool.split(' (')[0] for tool in sast_tools_found]))  # Estrai solo il nome dello strumento
                        if unique_tools:
                            valore = f"Trovati: {', '.join(unique_tools)}"
                            # Più strumenti SAST = punteggio più alto, max 10
                            punteggio = min(10, len(unique_tools) * 3.3)
                            # After populating sast_tools_found, give specific points if 'Bandit' was detected
                            if "Bandit" in sast_tools_found:
                                punteggio += 5  # Increase score if Bandit is found
                        else:
                            valore = "Non rilevato"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Integra strumenti di analisi di sicurezza statica (SAST) come CodeQL, SonarQube o Snyk nella pipeline CI/CD"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nel controllo degli strumenti SAST: {e}", exc_info=True)
                        valore = "Errore verifica"
                        punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio

            # Testing & CI/CD
            elif categoria == "integrazione":
                if nome_param == "presenza_test_suite":
                    # Verifichiamo la presenza di directory o file di test con modalità più approfondita
                    valore = False
                    punteggio = 0
                    test_files_found = []
                    
                    try:
                        # Pattern di ricerca per test più completi
                        test_dir_patterns = ["test", "tests", "spec", "unittest", "pytest"]
                        test_file_patterns = ["test_", "_test", "spec_", "_spec", "suite"]
                        
                        if self.local_repo_path:
                            # Controlla le directory locali in modo ricorsivo
                            for root, dirs, files in os.walk(self.local_repo_path):
                                # Cerca directory di test
                                for dir_name in dirs:
                                    if any(pattern in dir_name.lower() for pattern in test_dir_patterns):
                                        rel_path = os.path.relpath(os.path.join(root, dir_name), self.local_repo_path)
                                        test_files_found.append(rel_path)
                                
                                # Cerca file di test
                                for file_name in files:
                                    if (any(pattern in file_name.lower() for pattern in test_file_patterns) or 
                                        file_name.lower().startswith(("test", "spec"))):
                                        if file_name.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".php")):
                                            rel_path = os.path.relpath(os.path.join(root, file_name), self.local_repo_path)
                                            test_files_found.append(rel_path)
                        else:
                            # Ricerca attraverso API GitHub
                            # Prima controllo cartelle di test nella root
                            root_contents = self._get_cached_data(
                                "root_contents",
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            for item in root_contents:
                                if item.type == "dir" and any(pattern in item.name.lower() for pattern in test_dir_patterns):
                                    test_files_found.append(item.name)
                                elif item.type == "file" and any(pattern in item.name.lower() for pattern in test_file_patterns):
                                    if item.name.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".php")):
                                        test_files_found.append(item.name)
                            
                            # Se non troviamo niente, facciamo una ricerca di termini chiave nei file del repo
                            # Questo è limitato per ridurre l'utilizzo dell'API
                            if not test_files_found:
                                try:
                                    repo_search = self.github.search_code(f"repo:{self.repo_name} filename:test_*.py OR filename:*_test.py")
                                    if repo_search.totalCount > 0:
                                        test_files_found.append(f"~{repo_search.totalCount} file di test trovati via ricerca")
                                except Exception:
                                    pass  # Ignora errori nella ricerca
                        
                        # Valuta i risultati
                        if test_files_found:
                            valore = f"{len(test_files_found)} test trovati"
                            punteggio = 10  # Se troviamo test, diamo punteggio massimo
                        else:
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi test automatizzati per migliorare la qualità e affidabilità del codice"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nella ricerca di test: {e}")
                        valore = "Errore verifica"
                        punteggio = 0
                
                elif nome_param == "integrazione_continua":
                    # Verifichiamo la presenza di configurazione CI/CD con rilevamento migliorato
                    valore = False
                    punteggio = 0
                    ci_configs_found = []
                    
                    try:
                        # Lista estesa di pattern per configurazioni CI/CD comuni
                        ci_configs = {
                            "github_actions": [".github/workflows", ".github/actions"],
                            "travis_ci": [".travis.yml"],
                            "gitlab_ci": [".gitlab-ci.yml"],
                            "azure_pipelines": ["azure-pipelines.yml"],
                            "jenkins": ["Jenkinsfile"],
                            "circle_ci": [".circleci", ".circleci/config.yml"],
                            "bitbucket": ["bitbucket-pipelines.yml"],
                            "drone": [".drone.yml"],
                            "appveyor": ["appveyor.yml"],
                            "aws_codebuild": ["buildspec.yml"],
                            "teamcity": [".teamcity"]
                        }
                        
                        if self.local_repo_path:
                            # Check for CI configuration files in local repository
                            for root, dirs, files in os.walk(self.local_repo_path):
                                # Avoid going too deep in the repository structure
                                if root.count(os.sep) - self.local_repo_path.count(os.sep) > 3:
                                    continue
                    
                                # Scan files in the current directory
                                for file in files:
                                    # Check each language's build tools
                                    for ci_type, patterns in ci_configs.items():
                                        for pattern in patterns:
                                            # Handle wildcard patterns (e.g., *.csproj)
                                            if pattern.startswith('*') and file.endswith(pattern[1:]):
                                                ci_configs_found.append(ci_type)
                                            # Exact file match
                                            elif file.lower() == pattern.lower():
                                                ci_configs_found.append(ci_type)
                        else:
                            # Usa API GitHub per il controllo
                            # Verifica configurazioni nella root
                            root_contents = self._get_cached_data(
                                "root_contents",
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            # Cerca file CI nella root
                            for ci_type, patterns in ci_configs.items():
                                for pattern in patterns:
                                    if '/' not in pattern:  # Solo root files
                                        for item in root_contents:
                                            if item.type == "file" and item.name.lower() == pattern.lower():
                                                ci_configs_found.append(ci_type)
                                                break
                            
                            # Cerca directory speciali come .circleci o .github nella root
                            github_dir = None
                            circleci_dir = None
                            for item in root_contents:
                                if item.type == "dir":
                                    if item.name.lower() == ".github":
                                        github_dir = item
                                    elif item.name.lower() == ".circleci":
                                        circleci_dir = item
                                        ci_configs_found.append("circle_ci")
                            
                            # Se c'è .github, controlla se ha workflows
                            if github_dir:
                                try:
                                    github_contents = self._get_cached_data(
                                        "github_dir_contents",
                                        lambda: list(self.repo.get_contents(".github"))
                                    )
                                    
                                    for item in github_contents:
                                        if item.type == "dir" and item.name.lower() == "workflows":
                                            # Verifica che ci siano file nella directory workflows
                                            try:
                                                workflows_contents = self._get_cached_data(
                                                    "workflows_contents",
                                                    lambda: list(self.repo.get_contents(".github/workflows"))
                                                )
                                                if workflows_contents:
                                                    ci_configs_found.append("github_actions")
                                            except Exception:
                                                pass
                                            break
                                except Exception:
                                    pass
                        
                        # Valuta i risultati
                        if ci_configs_found:
                            unique_ci = list(set(ci_configs_found))  # Remove duplicates
                            valore = ", ".join(unique_ci)
                            punteggio = 10  # Se troviamo CI/CD, diamo punteggio massimo
                        else:
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Configura un sistema di CI/CD come GitHub Actions per automatizzare test e deployment"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nel controllo CI/CD: {e}", exc_info=True)
                        valore = "Errore verifica CI/CD"
                        punteggio = 0
                
                # Inside the _analyze_parameter method, under the "integrazione" category
                elif nome_param == "build_tool_standard":
                    tools_description, tools_score = self._check_build_tools_standard()
                    valore = tools_description
                    punteggio = tools_score
                    
                    if punteggio < 5:
                        self.results["suggerimenti"].setdefault("integrazione", []).append(
                            "Considera l'utilizzo di strumenti di build standard per il linguaggio utilizzato, "
                            "come Maven/Gradle per Java, npm/yarn per JavaScript, o pip/setuptools per Python."
                        )

                elif nome_param in ["test_coverage", "sicurezza_ci"]:
                    valore = "Analisi non disponibile"
                    punteggio = 5  # Valore neutro
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio

            # Setup & Usabilità
            elif categoria == "adozione":

                if nome_param == "facilita_setup":
                    # Enhanced setup analysis with comprehensive checks
                    valore = "Analisi in corso"
                    punteggio = 5  # Default neutral value
                    
                    # Expanded list of setup files by ecosystem
                    setup_files = {
                        "python": ["setup.py", "requirements.txt", "Pipfile", "pyproject.toml", "setup.cfg", "environment.yml"],
                        "javascript": ["package.json", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json"],
                        "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
                        "build": ["Makefile", "CMakeLists.txt", "build.gradle", "pom.xml", "build.xml", "build.sbt"],
                        "ruby": ["Gemfile", "Gemfile.lock"],
                        "php": ["composer.json", "composer.lock"],
                        "go": ["go.mod", "go.sum"]
                    }
                    
                    all_setup_files = [file for files in setup_files.values() for file in files]
                    found_files = {}
                    readme_contains_setup = False
                    installation_guide = None
                    
                    try:
                        # Check for setup files
                        if self.local_repo_path:
                            # Check local repository with better traversal
                            for root, _, files in os.walk(self.local_repo_path):
                                # Limit depth for better performance
                                rel_path = os.path.relpath(root, self.local_repo_path)
                                depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                                if depth > 2:  # Don't go deeper than 2 levels
                                    continue
                                
                                for file in files:
                                    file_lower = file.lower()
                                    # Check each ecosystem's setup files
                                    for ecosystem, ecosystem_files in setup_files.items():
                                        if file_lower in [s.lower() for s in ecosystem_files]:
                                            found_files.setdefault(ecosystem, []).append(file)
                                    
                                    # Also check README for setup instructions
                                    if file_lower in ["readme.md", "readme", "readme.txt", "readme.rst"]:
                                        readme_path = os.path.join(root, file)
                                        try:
                                            with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                                                readme_content = f.read().lower()
                                                # Check for installation sections in README
                                                if any(section in readme_content for section in ["# installation", "## installation", 
                                                                                            "# setup", "## setup", 
                                                                                            "# getting started", "## getting started",
                                                                                            "# quick start", "## quick start",
                                                                                            "# installazione", "## installazione"]):
                                                    readme_contains_setup = True
                                                    installation_guide = "README contiene istruzioni di installazione"
                                        except Exception as e:
                                            logger.debug(f"Errore nella lettura del README {readme_path}: {e}")
                        else:
                            # Use GitHub API with more comprehensive checks
                            contents = self._get_cached_data(
                                "root_contents",
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            for item in contents:
                                if item.type == "file":
                                    file_lower = item.name.lower()
                                    # Check each ecosystem's setup files
                                    for ecosystem, ecosystem_files in setup_files.items():
                                        if file_lower in [s.lower() for s in ecosystem_files]:
                                            found_files.setdefault(ecosystem, []).append(item.name)
                                    
                                    # Check README for setup instructions
                                    if file_lower in ["readme.md", "readme", "readme.txt", "readme.rst"]:
                                        try:
                                            readme_content = self.repo.get_contents(item.path).decoded_content.decode('utf-8', errors='ignore').lower()
                                            # Check for installation sections in README
                                            if any(section in readme_content for section in ["# installation", "## installation", 
                                                                                        "# setup", "## setup", 
                                                                                        "# getting started", "## getting started",
                                                                                        "# quick start", "## quick start",
                                                                                        "# installazione", "## installazione"]):
                                                readme_contains_setup = True
                                                installation_guide = "README contiene istruzioni di installazione"
                                        except Exception as e:
                                            logger.debug(f"Errore nel recupero del README {item.path}: {e}")
                        
                        # Calculate score based on multiple factors
                        ecosystems_count = len(found_files)
                        total_files = sum(len(files) for files in found_files.values())
                        
                        # Base score from setup files (weighted by ecosystem coverage)
                        if total_files > 0:
                            # More ecosystems covered = better score
                            ecosystem_coverage = min(ecosystems_count * 2, 6)  # Up to 6 points for ecosystem coverage
                            
                            # More setup files = more comprehensive setup
                            file_coverage = min(total_files * 0.8, 4)  # Up to 4 points for number of files
                            
                            # Calculate base score combining both factors
                            setup_score = ecosystem_coverage + file_coverage
                            
                            # Bonus for README with installation instructions
                            if readme_contains_setup:
                                setup_score = min(10, setup_score + 2)  # +2 bonus for good documentation
                            
                            punteggio = setup_score
                            
                            # Prepare descriptive value with ecosystem breakdown
                            ecosystem_descriptions = []
                            for ecosystem, files in found_files.items():
                                if len(files) > 2:
                                    ecosystem_descriptions.append(f"{ecosystem} ({len(files)} files)")
                                else:
                                    ecosystem_descriptions.append(f"{ecosystem} ({', '.join(files)})")
                            
                            valore = f"Setup files trovati: {' + '.join(ecosystem_descriptions)}"
                            if installation_guide:
                                valore += f" e {installation_guide}"
                                
                            # Targeted suggestions based on missing ecosystems
                            if punteggio < 8:
                                missing_ecosystems = []
                                if "docker" not in found_files:
                                    missing_ecosystems.append("Docker (Dockerfile/docker-compose.yml)")
                                if "python" not in found_files and "javascript" not in found_files:
                                    missing_ecosystems.append("setup di base (requirements.txt/package.json)")
                                
                                if missing_ecosystems:
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        f"Migliora la facilità di installazione aggiungendo file per {' e '.join(missing_ecosystems)}"
                                    )
                                
                                if not readme_contains_setup:
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Aggiungi una sezione 'Installation' o 'Getting Started' al README con istruzioni chiare"
                                    )
                        else:
                            valore = "Nessun file di setup rilevato"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi file di setup come requirements.txt, package.json o Dockerfile per facilitare l'installazione"
                            )
                            if not readme_contains_setup:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Documenta le istruzioni di installazione nel README con esempi e prerequisiti"
                                )
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi dei file di setup: {e}", exc_info=True)
                        valore = "Errore nell'analisi"
                        punteggio = 5
                
                elif nome_param == "configurabilita":
                    # Check for configuration files and options
                    valore = "Analisi in corso"
                    config_files = [
                        # General config files
                        "config.json", "config.yml", "config.yaml", ".env.example", 
                        "settings.py", ".env", ".env.sample", ".env.template",
                        # Framework specific configs
                        "app.config.js", "next.config.js", "webpack.config.js",
                        "nuxt.config.js", "vue.config.js", "angular.json",
                        "django_settings.py", "settings.gradle", "application.properties",
                        "application.yml", "appsettings.json"
                    ]
                    found_configs = []
                    
                    try:
                        if self.local_repo_path:
                            for root, _, files in os.walk(self.local_repo_path):
                                # Don't go too deep into the repository to avoid long analysis
                                if root.count(os.sep) - self.local_repo_path.count(os.sep) > 3:
                                    continue
                                    
                                for file in files:
                                    # Check for standard config files
                                    if file.lower() in [c.lower() for c in config_files]:
                                        found_configs.append(file)
                                    
                                    # Check Python files for CLI argument libraries
                                    if file.endswith('.py'):
                                        try:
                                            file_path = os.path.join(root, file)
                                            with open(file_path, 'r', encoding='utf-8') as f:
                                                content = f.read()
                                                # Check for various command-line parsing libraries
                                                if 'argparse' in content and 'ArgumentParser' in content:
                                                    found_configs.append('command-line arguments (via argparse)')
                                                    break
                                                elif 'import click' in content or 'from click import' in content:
                                                    found_configs.append('command-line arguments (via click)')
                                                    break
                                                elif 'import typer' in content or 'from typer import' in content:
                                                    found_configs.append('command-line arguments (via typer)')
                                                    break
                                                elif 'docopt' in content:
                                                    found_configs.append('command-line arguments (via docopt)')
                                                    break
                                                # Check for environment variable usage
                                                elif 'os.environ' in content or 'os.getenv' in content:
                                                    found_configs.append('environment variables')
                                                    break
                                        except Exception as e:
                                            logger.debug(f"Error analyzing Python file {file}: {e}")
                                            pass
                        else:
                            # Check via GitHub API
                            contents = self._get_cached_data(
                                "root_contents",
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            for item in contents:
                                if item.type == "file" and item.name.lower() in [c.lower() for c in config_files]:
                                    found_configs.append(item.name)
                            
                            # Look for config in common Python files - limited to reduce API calls
                            try:
                                likely_files = ['main.py', 'app.py', 'run.py', 'cli.py', 'config.py', 'settings.py']
                                likely_files.append(self.repo_name.split('/')[-1] + '.py')
                                
                                for filename in likely_files:
                                    py_file = next((item for item in contents if item.name == filename), None)
                                    if py_file:
                                        content = self.repo.get_contents(py_file.path).decoded_content.decode('utf-8')
                                        if 'argparse' in content and 'ArgumentParser' in content:
                                            found_configs.append('command-line arguments (via argparse)')
                                            break
                                        elif 'import click' in content or 'from click import' in content:
                                            found_configs.append('command-line arguments (via click)')
                                            break
                                        elif 'import typer' in content or 'from typer import' in content:
                                            found_configs.append('command-line arguments (via typer)')
                                            break
                                        elif 'os.environ' in content or 'os.getenv' in content:
                                            found_configs.append('environment variables')
                                            break
                            except Exception as e:
                                logger.debug(f"Error analyzing Python files via API: {e}")
                                pass
                        
                        # Remove duplicates while preserving order
                        unique_configs = []
                        for config in found_configs:
                            if config not in unique_configs:
                                unique_configs.append(config)
                        
                        if unique_configs:
                            # More granular scoring based on number and variety of config options
                            config_count = len(unique_configs)
                            config_score = min(config_count * 2.0, 10)
                            
                            # Bonus for having multiple configuration methods
                            config_categories = set()
                            if any('command-line' in c for c in unique_configs):
                                config_categories.add('cli')
                            if any(c.endswith(('.json', '.yml', '.yaml')) for c in unique_configs):
                                config_categories.add('file')
                            if any('env' in c.lower() for c in unique_configs):
                                config_categories.add('env')
                            
                            if len(config_categories) > 1:
                                config_score = min(10, config_score + 1)  # Bonus for multiple config methods
                                
                            valore = f"Opzioni di configurazione trovate: {', '.join(unique_configs)}"
                            punteggio = config_score
                        else:
                            valore = "Configurazione limitata o assente"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi file di configurazione o supporto per variabili d'ambiente per aumentare la flessibilità"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi della configurabilità: {e}")
                        valore = "Errore nell'analisi"
                        punteggio = 5
                
                elif nome_param == "documentazione_installazione":
                    # Check for installation documentation
                    valore = "Analisi in corso"
                    installation_sections = ["install", "installation", "getting started", "setup", "usage", "quick start", "installazione", "iniziare"]
                    
                    try:
                        readme_content = None
                        installation_found = False
                        
                        # Try to get README content
                        if self.local_repo_path:
                            readme_files = ["README.md", "readme.md", "README.rst", "readme.rst"]
                            for readme_file in readme_files:
                                readme_path = os.path.join(self.local_repo_path, readme_file)
                                if os.path.exists(readme_path):
                                    with open(readme_path, 'r', encoding='utf-8') as f:
                                        readme_content = f.read().lower()
                                    break
                        else:
                            # Use GitHub API
                            try:
                                readme = self._get_cached_data(
                                    "readme_content",
                                    lambda: self.repo.get_readme()
                                )
                                if readme:
                                    readme_content = readme.decoded_content.decode('utf-8').lower()
                            except Exception:
                                pass
                        
                        if readme_content:
                            # Check for installation sections using headers (markdown style)
                            for section in installation_sections:
                                if f"# {section}" in readme_content or f"## {section}" in readme_content or f"### {section}" in readme_content:
                                    installation_found = True
                                    break
                            
                            # Check for code blocks that might indicate installation commands
                            if not installation_found and ("```" in readme_content or "pip install" in readme_content or "npm install" in readme_content):
                                installation_found = True
                        
                        if installation_found:
                            valore = "Documentazione di installazione trovata"
                            punteggio = 10
                        else:
                            valore = "Documentazione di installazione mancante"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi una sezione 'Installation' o 'Getting Started' al README per facilitare l'uso del progetto"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi della documentazione di installazione: {e}")
                        valore = "Errore nell'analisi"
                        punteggio = 5
                
                elif nome_param == "presenza_dockerfile":
                    valore = "Presente" if self._check_dockerfile_presence() else "Assente"
                    punteggio = 10 if self._check_dockerfile_presence() else 0
                
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio

            else:
                valore = "Non analizzato"
                punteggio = 0
                conta_punteggio = False

            return valore, round(punteggio, 2), conta_punteggio

        except Exception as e:
            logger.error(f"Errore nell'analisi del parametro {nome_param}: {e}", exc_info=True)
            valore = "Errore"
            punteggio = None  # Set to None instead of 0 for errors
            conta_punteggio = False
            score_is_na = True
            
        # Return tuple with additional metadata about score status
        return_value = (valore, punteggio if punteggio is not None else None, conta_punteggio)
        
        # Add score_is_na to results for this parameter
        if nome_param in self.results["dettagli"].get(categoria, {}):
            self.results["dettagli"][categoria][nome_param]["score_is_na"] = score_is_na

        return return_value

    def _calculate_scores(self):
        """Calcola i punteggi per ogni categoria e il punteggio totale."""
        for categoria, parametri in self.results["dettagli"].items():
            punteggio_categoria = 0
            peso_totale = 0
            for nome_param, info_param in parametri.items():
                if info_param["conta_punteggio"]:
                    # Skip parameters with NA scores or None values
                    if info_param.get("score_is_na", False) or info_param["punteggio"] is None:
                        continue
                    punteggio_categoria += info_param["punteggio"] * info_param["peso"]
                    peso_totale += info_param["peso"]
            
            # Extra check for security category to ensure it's not unfairly scored
            if categoria == "sicurezza" and peso_totale > 0:
                # Make sure security score is properly calculated even with some missing checks
                self.results["punteggi"][categoria] = round(punteggio_categoria / peso_totale, 2)
            elif peso_totale > 0:
                self.results["punteggi"][categoria] = round(punteggio_categoria / peso_totale, 2)
            else:
                self.results["punteggi"][categoria] = 0

    def _display_scores_terminal(self):
        """Visualizza i punteggi nel terminale."""
        table = Table(title="Punteggi delle Categorie")
        table.add_column("Categoria", justify="left", style="cyan", no_wrap=True)
        table.add_column("Punteggio", justify="right", style="magenta")

        for categoria, punteggio in self.results["punteggi"].items():
            # Utilizza il mapping delle etichette se disponibile
            display_categoria = CATEGORY_LABELS_MAPPING.get(categoria, categoria)
            table.add_row(display_categoria, str(punteggio))

        self.console.print(table)

    def _update_history(self):
        """Aggiorna lo storico dei punteggi nel file di configurazione. (Disabilitato)"""
        # Funzionalità disabilitata per evitare di modificare config.json
        logger.info("Salvataggio dello storico nel file di configurazione è disabilitato.")
        pass

    def _check_security(self, path: str = ".") -> float:
        """Esegue una scansione di sicurezza con Bandit (se disponibile)."""
        if not bandit:
            logger.warning("Bandit non è installato. Salta l'analisi di sicurezza statica.")
            return 5.0  # Valore neutro se Bandit non è disponibile
        if not self.local_repo_path:
            logger.warning("Bandit richiede il clone del repository (--clone). Salta l'analisi.")
            return 5.0  # Neutral score if not cloned

        try:
            effective_path = self.local_repo_path  # Always use cloned path for Bandit
            logger.info(f"Esecuzione di Bandit su: {effective_path}")
            
            # Add confidence level to the analysis
            result = subprocess.run(
                ["bandit", "-r", effective_path, "-f", "json", "-q", "--confidence-level", "medium"],
                capture_output=True, text=True, timeout=120, check=False
            )

            # Process the output if we have any (return code 0 = no issues, 1 = issues found)
            if result.returncode in [0, 1] and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    issues = data.get("results", [])
                    metrics = data.get("metrics", {})
                    
                    # Get total lines of code analyzed
                    total_loc = metrics.get("_totals", {}).get("loc", 0) 
                    if total_loc == 0:  # Avoid division by zero
                        total_loc = 1
                    
                    # Count issues by severity and confidence level
                    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
                    confidence_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
                    issue_types = {}
                    
                    for issue in issues:
                        severity = issue.get("issue_severity", "LOW")
                        confidence = issue.get("issue_confidence", "LOW")
                        issue_id = issue.get("test_id", "")
                        
                        # Count by severity
                        if severity in severity_counts:
                            severity_counts[severity] += 1
                        
                        # Count by confidence level
                        if confidence in confidence_counts:
                            confidence_counts[confidence] += 1
                        
                        # Track issue types for more specific recommendations
                        issue_types.setdefault(issue_id, 0)
                        issue_types[issue_id] += 1
                    
                    # Calculate weighted issues with more granular weighting based on severity and confidence
                    # High severity + high confidence is weighted most heavily
                    weighted_issues = 0
                    for issue in issues:
                        severity = issue.get("issue_severity", "LOW")
                        confidence = issue.get("issue_confidence", "LOW")
                        
                        # Combined weight matrix
                        if severity == "HIGH" and confidence == "HIGH":
                            weighted_issues += 10.0  # Critical issues
                        elif severity == "HIGH" and confidence == "MEDIUM":
                            weighted_issues += 7.0
                        elif severity == "HIGH" and confidence == "LOW":
                            weighted_issues += 5.0
                        elif severity == "MEDIUM" and confidence == "HIGH":
                            weighted_issues += 4.0
                        elif severity == "MEDIUM" and confidence == "MEDIUM":
                            weighted_issues += 2.0
                        elif severity == "MEDIUM" and confidence == "LOW":
                            weighted_issues += 1.0
                        elif severity == "LOW" and confidence == "HIGH":
                            weighted_issues += 0.7
                        elif severity == "LOW" and confidence == "MEDIUM":
                            weighted_issues += 0.4
                        else:  # LOW severity, LOW confidence
                            weighted_issues += 0.2
                    
                    # Calculate issue density per 1000 lines
                    issue_density = (weighted_issues / total_loc) * 1000 if total_loc > 0 else 0
                    
                    # More granular scoring scale
                    if len(issues) == 0:
                        score = 10.0  # Perfect score for no issues
                    else:
                        # Use a more granular scoring system with 10 distinct levels
                        if issue_density <= 0.5:
                            score = 9.5  # Almost perfect - very minor issues
                        elif issue_density <= 1.0:
                            score = 9.0  # Excellent - minimal issues
                        elif issue_density <= 2.0:
                            score = 8.5  # Very good - few minor issues
                        elif issue_density <= 3.0:
                            score = 8.0  # Good - some minor issues
                        elif issue_density <= 5.0:
                            score = 7.0  # Fairly good - noticeable but not serious issues
                        elif issue_density <= 8.0:
                            score = 6.0  # Acceptable - moderate issues present
                        elif issue_density <= 12.0:
                            score = 5.0  # Moderate concern - significant issues present
                        elif issue_density <= 18.0:
                            score = 4.0  # Concerning - many significant issues
                        elif issue_density <= 25.0:
                            score = 3.0  # Poor - serious security concerns
                        elif issue_density <= 40.0:
                            score = 2.0  # Very poor - major security vulnerabilities
                        elif issue_density <= 60.0:
                            score = 1.0  # Critical - severe security problems
                        else:
                            score = 0.0  # Extremely critical - immediate action required
                    
                    logger.info(
                        f"Bandit analysis: {len(issues)} issues found "
                        f"({severity_counts['HIGH']}H/{confidence_counts['HIGH']}HC, "
                        f"{severity_counts['MEDIUM']}M/{confidence_counts['MEDIUM']}MC, "
                        f"{severity_counts['LOW']}L/{confidence_counts['LOW']}LC). "
                        f"Density: {issue_density:.2f}/kloc. Score: {score:.2f}"
                    )

                    # Clear previous security suggestions before adding new ones
                    self.results["suggerimenti"].setdefault("sicurezza", [])
                    
                    # Add more detailed suggestions based on findings
                    if severity_counts["HIGH"] > 0:
                        high_priority = [issue_id for issue_id, count in issue_types.items() 
                                        if any(issue.get("test_id") == issue_id and 
                                            issue.get("issue_severity") == "HIGH" 
                                            for issue in issues)]
                        
                        # Create more specific suggestions for common high-severity issues
                        if high_priority:
                            common_issues = {}
                            for issue in issues:
                                if issue.get("issue_severity") == "HIGH":
                                    issue_type = issue.get("test_id")
                                    issue_text = issue.get("test_name", "Unknown")
                                    if issue_type:
                                        common_issues.setdefault(issue_type, {"count": 0, "name": issue_text})
                                        common_issues[issue_type]["count"] += 1
                            
                            # Add specific recommendations for top 3 high-severity issues
                            top_issues = sorted(common_issues.items(), key=lambda x: x[1]["count"], reverse=True)[:3]
                            for issue_id, data in top_issues:
                                self.results["suggerimenti"]["sicurezza"].append(
                                    f"Priorità alta: Risolvi le {data['count']} vulnerabilità di tipo '{data['name']}' (ID: {issue_id})."
                                )
                        
                        # General suggestion for high severity issues
                        self.results["suggerimenti"]["sicurezza"].append(
                            f"Risolvi le {severity_counts['HIGH']} vulnerabilità ad alta severità identificate da Bandit."
                        )
                    
                    if severity_counts["MEDIUM"] > 0:
                        self.results["suggerimenti"]["sicurezza"].append(
                            f"Rivedi le {severity_counts['MEDIUM']} vulnerabilità a media severità identificate da Bandit."
                        )
                    
                    # Generate focused suggestions for common security issues
                    security_recommendations = {
                        "B102": "Rimuovi i comandi 'exec' dal codice in quanto permettono l'esecuzione di codice arbitrario",
                        "B103": "Imposta correttamente i permessi di creazione file per evitare vulnerabilità di sicurezza",
                        "B104": "Limita l'uso di comandi hardcoded per prevenire iniezioni di comandi",
                        "B105": "Rimuovi i password hardcoded dal codice e usa variabili d'ambiente o gestori di segreti",
                        "B108": "Evita l'uso di 'assert' in codice di produzione poiché potrebbe essere rimosso dall'ottimizzatore",
                        "B110": "Non utilizzare connessioni non sicure, passa a HTTPS/TLS",
                        "B301": "Evita l'uso di 'pickle' che può portare a esecuzione di codice arbitrario",
                        "B324": "Non utilizzare algoritmi hash insicuri (MD5/SHA1), usa alternative più sicure",
                        "B506": "Fix YAML.load() vulnerabilities by using YAML.safe_load()",
                        "B605": "Evita l'uso di subprocess con shell=True per prevenire iniezione di comandi",
                        "B607": "Evita di usare subprocess con argomenti da input non sanitizzato"
                    }
                    
                    # Add specific recommendations based on issues found
                    for issue_id, recommendation in security_recommendations.items():
                        if any(issue.get("test_id") == issue_id for issue in issues):
                            count = sum(1 for issue in issues if issue.get("test_id") == issue_id)
                            self.results["suggerimenti"]["sicurezza"].append(f"{recommendation} ({count} occorrenze).")
                    
                    if len(issues) == 0:
                        # Add positive feedback if no issues found
                        self.results["suggerimenti"]["sicurezza"].append(
                            "Nessuna vulnerabilità rilevata da Bandit. Continua a mantenere questo standard."
                        )
                    elif score >= 8.0:
                        # Add positive feedback for good scores
                        self.results["suggerimenti"]["sicurezza"].append(
                            "Buon livello di sicurezza generale. Risolvi le vulnerabilità minori rimaste per un codice completamente sicuro."
                        )

                    # Add details about the analysis to the results
                    self.results.setdefault("dettagli_sicurezza", {})
                    self.results["dettagli_sicurezza"]["bandit_issues"] = len(issues)
                    self.results["dettagli_sicurezza"]["high_severity"] = severity_counts["HIGH"]
                    self.results["dettagli_sicurezza"]["medium_severity"] = severity_counts["MEDIUM"]
                    self.results["dettagli_sicurezza"]["low_severity"] = severity_counts["LOW"]
                    self.results["dettagli_sicurezza"]["issue_density"] = issue_density

                    return score
                    
                except json.JSONDecodeError as json_e:
                    logger.error(f"Errore nel parsing dell'output JSON di Bandit: {json_e}\nOutput:\n{result.stdout[:500]}...")
                    return 3.0  # Lower default score on parsing error
                    
            elif result.returncode == 0 and not result.stdout:
                # No issues found and no output
                logger.info("Bandit non ha rilevato vulnerabilità (nessun output)")
                self.results["suggerimenti"].setdefault("sicurezza", []).append(
                    "Nessuna vulnerabilità rilevata da Bandit. Continua a mantenere questo standard."
                )
                return 10.0  # Perfect score for no issues
                
            else:
                # Handle error cases
                if result.returncode > 1:
                    logger.warning(f"Bandit ha restituito un codice di errore: {result.returncode}. Stderr: {result.stderr}")
                    # Try to provide more specific error information
                    if "No such file or directory" in result.stderr:
                        logger.warning("Bandit non ha trovato file da analizzare")
                        self.results["suggerimenti"].setdefault("sicurezza", []).append(
                            "L'analisi di sicurezza ha riscontrato problemi nell'accesso ai file del repository."
                        )
                    return 4.0  # Slightly below neutral on error
                else:
                    logger.warning(f"Bandit non ha prodotto output o ha fallito silenziosamente (return code {result.returncode}).")
                    return 5.0  # Neutral score on unexpected behavior

        except subprocess.TimeoutExpired:
            logger.error("Timeout durante l'esecuzione di Bandit (superati 120s).")
            self.results["suggerimenti"].setdefault("sicurezza", []).append(
                "L'analisi di sicurezza è stata interrotta per timeout. Il repository potrebbe essere troppo grande o complesso."
            )
            return 3.0  # Lower score on timeout
        except FileNotFoundError:
            logger.error("Comando 'bandit' non trovato. Assicurati che Bandit sia installato e nel PATH.")
            self.results["suggerimenti"].setdefault("sicurezza", []).append(
                "Installa Bandit (pip install bandit) per abilitare l'analisi di sicurezza completa."
            )
            return 5.0  # Neutral score if command not found
        except Exception as e:
            logger.error(f"Errore imprevisto durante l'esecuzione di Bandit: {e}", exc_info=True)
            self.results["suggerimenti"].setdefault("sicurezza", []).append(
                "Si è verificato un errore durante l'analisi di sicurezza. Verifica la configurazione dell'ambiente."
            )
            return 2.0  # Low score on unexpected error

    def _check_dependencies_safety(self, path: str) -> Tuple[str, float]:
        """Esegue una scansione delle dipendenze con Safety (se disponibile)."""
        if not safety:
            logger.warning("Safety non è installato. Salta l'analisi delle dipendenze.")
            return "Richiede 'safety'", 5.0

        if not self.local_repo_path:
            logger.warning("Safety richiede il clone del repository (--clone). Salta l'analisi.")
            return "Richiede --clone", 5.0

        effective_path = self.local_repo_path
        requirements_files = []
        
        # Find common requirements files with expanded file types
        dependency_files = {
            "python": ["requirements.txt", "requirements-dev.txt", "dev-requirements.txt", "setup.py", 
                    "pyproject.toml", "Pipfile", "Pipfile.lock", "constraints.txt", "requirements-prod.txt"],
            "node": ["package.json", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json"],
            "ruby": ["Gemfile", "Gemfile.lock"],
            "php": ["composer.json", "composer.lock"]
        }
        
        # First look for Python dependency files
        for root, _, files in os.walk(effective_path):
            for file in files:
                if file in dependency_files["python"]:
                    # Prioritize requirements.txt if found
                    if file == "requirements.txt":
                        requirements_files.insert(0, os.path.join(root, file))
                    else:
                        requirements_files.append(os.path.join(root, file))
        
        if not requirements_files:
            logger.info("Nessun file di dipendenze Python (requirements.txt, setup.py, pyproject.toml) trovato.")
            
            # Check for other dependency systems and add a note in logs
            for dep_type, file_list in dependency_files.items():
                if dep_type == "python":
                    continue
                
                for root, _, files in os.walk(effective_path):
                    for file in files:
                        if file in file_list:
                            logger.info(f"Trovato file di dipendenze {dep_type} ({file}), ma Safety supporta solo dipendenze Python.")
                            return f"Dipendenze {dep_type} non supportate", 5.0
            
            return "Nessun file dipendenze", 8.0  # Good score if no deps declared

        # Analyze each requirements file and merge results
        total_vulnerabilities = 0
        high_severity_vulns = 0
        medium_severity_vulns = 0
        low_severity_vulns = 0
        files_with_vulns = []
        scan_errors = 0
        files_analyzed = 0
        vulnerability_details = []
        
        for req_file_to_scan in requirements_files[:3]:  # Limit to first 3 files to avoid excessive scanning
            logger.info(f"Esecuzione di Safety su: {req_file_to_scan}")
            
            try:
                # Run safety using subprocess to capture output and handle errors
                # Use --json for structured output and add severity level parameter
                cmd = ["safety", "check", "-r", req_file_to_scan, "--json", "--full-report"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)

                if result.returncode == 0 and result.stdout:
                    # Safety returns 0 even if vulnerabilities are found when using --json
                    try:
                        # Safety's JSON output handling with better parsing
                        json_output_str = None
                        
                        # Find the JSON part in the output (could be wrapped in other text)
                        for line in result.stdout.strip().splitlines():
                            if line.startswith('[') and line.endswith(']'):
                                json_output_str = line
                                break
                        
                        # If no clear JSON line was found, try the last line as a fallback
                        if not json_output_str and result.stdout.strip():
                            json_output_str = result.stdout.strip().splitlines()[-1]
                        
                        if json_output_str:
                            vulnerabilities = json.loads(json_output_str)
                            
                            # Parse vulnerability data with more detail
                            file_vulns = 0
                            
                            if isinstance(vulnerabilities, list):
                                for vuln in vulnerabilities:
                                    if not vuln:
                                        continue
                                        
                                    file_vulns += 1
                                    
                                    # Try to extract severity if available (may vary by Safety version)
                                    severity = "unknown"
                                    if len(vuln) > 4:  # Some versions include severity
                                        severity_field = vuln[4] if isinstance(vuln, list) else vuln.get("severity", "unknown")
                                        severity = str(severity_field).lower()
                                    
                                    # Count vulnerabilities by severity
                                    if "high" in severity or "critical" in severity:
                                        high_severity_vulns += 1
                                    elif "medium" in severity or "moderate" in severity:
                                        medium_severity_vulns += 1
                                    else:
                                        low_severity_vulns += 1
                                    
                                    # Extract package and vuln details for suggestions
                                    if isinstance(vuln, list) and len(vuln) >= 3:
                                        package_name = vuln[0]
                                        affected_version = vuln[1]
                                        vuln_id = vuln[2]
                                        vulnerability_details.append({
                                            "package": package_name,
                                            "version": affected_version,
                                            "id": vuln_id,
                                            "severity": severity
                                        })
                                        
                            if file_vulns > 0:
                                files_with_vulns.append(os.path.basename(req_file_to_scan))
                                total_vulnerabilities += file_vulns
                                
                            files_analyzed += 1
                                
                    except json.JSONDecodeError:
                        logger.error(f"Errore nel parsing dell'output JSON di Safety: {result.stdout[:500]}")
                        scan_errors += 1
                    except IndexError:
                        logger.error(f"Output JSON di Safety vuoto o non trovato: {result.stdout[:500]}")
                        scan_errors += 1
                    except Exception as e:
                        logger.error(f"Errore nell'elaborazione dell'output di Safety: {e}")
                        scan_errors += 1

                elif result.returncode != 0:
                    logger.warning(f"Safety ha restituito un codice di errore: {result.returncode}. Stderr: {result.stderr}")
                    # Check stderr for common errors like missing file
                    if "No such file or directory" in result.stderr:
                        logger.error(f"File dipendenze non trovato da Safety: {req_file_to_scan}")
                        scan_errors += 1
                    else:
                        scan_errors += 1

            except subprocess.TimeoutExpired:
                logger.error(f"Timeout durante l'esecuzione di Safety su {req_file_to_scan} (superati 90s).")
                scan_errors += 1
            except FileNotFoundError:
                logger.error("Comando 'safety' non trovato. Assicurati che Safety sia installato e nel PATH.")
                return "Richiede 'safety'", 5.0  # Neutral score if tool not found
            except Exception as e:
                logger.error(f"Errore imprevisto durante l'esecuzione di Safety: {e}", exc_info=True)
                scan_errors += 1
        
        # Calculate results based on all analyzed files
        if files_analyzed == 0:
            return "Errore in tutte le analisi", 2.0
            
        if scan_errors == len(requirements_files):
            return f"Errori in {scan_errors}/{len(requirements_files)} analisi", 2.0
            
        if total_vulnerabilities == 0:
            logger.info("Safety non ha trovato vulnerabilità nelle dipendenze.")
            return "Nessuna vulnerabilità trovata", 10.0
        else:
            logger.warning(f"Safety ha trovato un totale di {total_vulnerabilities} vulnerabilità nelle dipendenze.")
            
            # More granular scoring based on number and severity of vulnerabilities
            # High severity vulns have 3x impact, medium 1.5x, low 0.5x
            weighted_score = (high_severity_vulns * 3) + (medium_severity_vulns * 1.5) + (low_severity_vulns * 0.5)
            
            # Adjust based on total number of files analyzed
            if files_analyzed > 1:
                weighted_score = weighted_score / files_analyzed
            
            # Convert to 0-10 scale with more granularity
            if weighted_score == 0:
                score = 10.0
            elif weighted_score <= 0.5:
                score = 9.5  # Minimal issues
            elif weighted_score <= 1:
                score = 9.0
            elif weighted_score <= 2:
                score = 8.0
            elif weighted_score <= 3:
                score = 7.0
            elif weighted_score <= 4:
                score = 6.0
            elif weighted_score <= 6:
                score = 5.0
            elif weighted_score <= 8:
                score = 4.0
            elif weighted_score <= 10:
                score = 3.0
            elif weighted_score <= 15:
                score = 2.0
            elif weighted_score <= 20:
                score = 1.0
            else:
                score = 0.0  # Critical security issues
            
            # Add detailed suggestions based on vulnerability findings
            self.results["suggerimenti"].setdefault("sicurezza", [])
            
            # Clear any previous Safety-specific suggestions
            self.results["suggerimenti"]["sicurezza"] = [
                s for s in self.results["suggerimenti"]["sicurezza"] 
                if "vulnerabilità trovate da Safety" not in s
            ]
            
            # Basic suggestion
            base_suggestion = f"Aggiorna le dipendenze per risolvere le {total_vulnerabilities} vulnerabilità trovate da Safety"
            
            # Add severity breakdown if available
            if high_severity_vulns > 0 or medium_severity_vulns > 0:
                severity_breakdown = []
                if high_severity_vulns > 0:
                    severity_breakdown.append(f"{high_severity_vulns} ad alta severità")
                if medium_severity_vulns > 0:
                    severity_breakdown.append(f"{medium_severity_vulns} a media severità")
                if low_severity_vulns > 0:
                    severity_breakdown.append(f"{low_severity_vulns} a bassa severità")
                    
                base_suggestion += f" ({', '.join(severity_breakdown)})"
            
            self.results["suggerimenti"]["sicurezza"].append(base_suggestion + ".")
            
            # Add file-specific info if multiple files have vulnerabilities
            if len(files_with_vulns) > 1:
                self.results["suggerimenti"]["sicurezza"].append(
                    f"Vulnerabilità trovate nei file: {', '.join(files_with_vulns)}"
                )
                
            # Add detailed suggestions for critical packages (up to 3)
            critical_packages = [v for v in vulnerability_details 
                                if "high" in v.get("severity", "").lower() or "critical" in v.get("severity", "").lower()]
            
            if critical_packages:
                # Group by package and count vulnerabilities
                package_vulns = {}
                for v in critical_packages:
                    package_name = v.get("package", "unknown")
                    package_vulns.setdefault(package_name, 0)
                    package_vulns[package_name] += 1
                    
                # Add suggestions for top 3 most vulnerable packages
                top_packages = sorted(package_vulns.items(), key=lambda x: x[1], reverse=True)[:3]
                for package, count in top_packages:
                    self.results["suggerimenti"]["sicurezza"].append(
                        f"Priorità alta: Aggiorna il pacchetto '{package}' che ha {count} vulnerabilità critiche."
                    )
            
            # Store detailed vulnerability information for reporting
            self.results.setdefault("dettagli_sicurezza", {})
            self.results["dettagli_sicurezza"]["safety_vulnerabilities"] = total_vulnerabilities
            self.results["dettagli_sicurezza"]["safety_high_severity"] = high_severity_vulns
            self.results["dettagli_sicurezza"]["safety_medium_severity"] = medium_severity_vulns
            self.results["dettagli_sicurezza"]["safety_low_severity"] = low_severity_vulns
            
            return f"{total_vulnerabilities} vulnerabilità trovate ({high_severity_vulns} critiche)", score

    def generate_report(self):
        """Genera il report con i punteggi utilizzando i nomi delle categorie mappati."""
        report_data = self.results.copy()
        
        # Mappa i nomi delle categorie per la visualizzazione
        display_punteggi = {}
        for categoria, punteggio in report_data["punteggi"].items():
            display_categoria = CATEGORY_LABELS_MAPPING.get(categoria, categoria)
            display_punteggi[display_categoria] = punteggio
            
        # Mantieni i punteggi originali per la compatibilità, ma aggiungi la versione mappata
        report_data["display_punteggi"] = display_punteggi
        
        return report_data

    def _check_engagement_rate(self) -> float:
        """Calcola il tasso di engagement (stelle, fork, watchers per mese)."""
        try:
            stars = self.repo.stargazers_count
            forks = self.repo.forks_count
            watchers = self.repo.subscribers_count
            created_at = self.repo.created_at
            months_active = max(1, (datetime.datetime.now() - created_at).days // 30)
            
            # Calculate basic engagement rate
            engagement_rate = (stars + forks + watchers) / months_active
            
            # Calculate weighted engagement rate (stars carry more weight than watchers)
            weighted_engagement_rate = (stars * 1.0 + forks * 1.2 + watchers * 0.8) / months_active
            
            # Calculate engagement ratio (engagement versus project age)
            # Newer projects get a slight boost as it's harder to gain traction early
            age_factor = max(1.0, 1.5 - (months_active / 24))  # Projects <= 24 months get a bonus
            adjusted_rate = engagement_rate * age_factor
            
            # Log the specific metrics for transparency
            logger.debug(f"Engagement metrics - Stars: {stars}, Forks: {forks}, Watchers: {watchers}")
            logger.debug(f"Project age: {months_active} months, Raw rate: {engagement_rate:.2f}, Weighted: {weighted_engagement_rate:.2f}")
            
            # More granular scoring with multiple thresholds instead of linear normalization
            if adjusted_rate >= 40:
                return 10.0  # Exceptional engagement
            elif adjusted_rate >= 30:
                return 9.5   # Outstanding engagement
            elif adjusted_rate >= 25:
                return 9.0   # Excellent engagement
            elif adjusted_rate >= 20:
                return 8.5   # Very high engagement
            elif adjusted_rate >= 15:
                return 8.0   # High engagement
            elif adjusted_rate >= 10:
                return 7.0   # Good engagement
            elif adjusted_rate >= 7:
                return 6.0   # Above average engagement
            elif adjusted_rate >= 5:
                return 5.0   # Average engagement
            elif adjusted_rate >= 3:
                return 4.0   # Below average engagement
            elif adjusted_rate >= 2:
                return 3.0   # Low engagement
            elif adjusted_rate >= 1:
                return 2.0   # Very low engagement
            elif adjusted_rate > 0:
                return 1.0   # Minimal engagement
            else:
                return 0.0   # No engagement
                
        except Exception as e:
            logger.error(f"Errore nel calcolo del tasso di engagement: {e}", exc_info=True)
            return 0.0

    def _check_dockerfile_presence(self) -> bool:
        """Verifica la presenza di un Dockerfile nel repository."""
        try:
            contents = self.repo.get_contents("")
            return any(file.name.lower() == "dockerfile" for file in contents)
        except Exception as e:
            # Added minimal handling: return False in case of error
            return False

    def _check_discussions_activity(self) -> float:
        """Calcola il livello di attività nelle GitHub Discussions."""
        try:
            # Safely check if discussions are enabled - attribute may not exist
            has_discussions = False
            try:
                has_discussions = getattr(self.repo, "has_discussions", False)
            except Exception:
                # Fallback check by trying to access discussions directly
                try:
                    discussions = self.repo.get_discussions()
                    has_discussions = True
                except Exception:
                    logger.debug("Discussions non disponibili o non supportate da PyGithub")
                    return 0.0  # Discussions not available or not supported by PyGithub version
            
            if not has_discussions:
                logger.debug("Discussions non abilitate per questo repository")
                return 0.0  # Discussions not enabled
            
            try:
                discussions = self.repo.get_discussions()
                all_discussions = []
                recent_discussions = []
                very_recent_discussions = []
                active_discussions = []
                answered_discussions = []
                
                # Analyze discussions with different time windows
                now = datetime.datetime.now(datetime.timezone.utc)
                
                for d in discussions[:20]:  # Expanded limit for better analysis
                    all_discussions.append(d)
                    
                    # Get creation date and ensure it's timezone aware
                    created_at = self._ensure_tz_aware(d.created_at)
                    days_since_creation = (now - created_at).days if created_at else 999
                    
                    # Get relevant attributes safely
                    comments_count = getattr(d, "comments_count", 0)
                    is_answered = getattr(d, "answered", False)
                    
                    # Categorize discussions
                    if days_since_creation <= 30:
                        recent_discussions.append(d)
                        
                    if days_since_creation <= 7:
                        very_recent_discussions.append(d)
                    
                    # Active discussions have comments or are recent
                    if comments_count > 3 or days_since_creation <= 14:
                        active_discussions.append(d)
                    
                    # Track answered discussions
                    if is_answered:
                        answered_discussions.append(d)
                
                # Calculate total comments in recent discussions
                recent_comments = sum(getattr(d, "comments_count", 0) for d in recent_discussions)
                very_recent_comments = sum(getattr(d, "comments_count", 0) for d in very_recent_discussions)
                
                # Enhanced metrics for discussions activity
                total_discussions = len(all_discussions)
                total_active_discussions = len(active_discussions)
                total_recent_discussions = len(recent_discussions)
                total_very_recent = len(very_recent_discussions)
                total_answered = len(answered_discussions)
                
                # Log detailed metrics for better transparency
                logger.debug(f"Discussions metrics - Total: {total_discussions}, " +
                            f"Recent (30d): {total_recent_discussions}, " +
                            f"Very recent (7d): {total_very_recent}, " + 
                            f"Active: {total_active_discussions}, " +
                            f"Answered: {total_answered}, " +
                            f"Recent comments: {recent_comments}")
                
                # No discussions case
                if total_discussions == 0:
                    logger.debug("Discussions abilitate ma nessuna discussione trovata")
                    return 0.0
                    
                # Calculate weighted activity score with more emphasis on recent activity
                base_score = total_discussions * 0.5
                recency_score = total_recent_discussions * 1.0
                very_recent_score = total_very_recent * 2.0
                activity_score = total_active_discussions * 1.5
                answer_score = total_answered * 1.0
                comments_score = recent_comments * 0.3 + very_recent_comments * 0.5
                
                weighted_score = base_score + recency_score + very_recent_score + activity_score + answer_score + comments_score
                
                # More granular scoring with multiple thresholds instead of linear normalization
                if weighted_score >= 50:
                    return 10.0  # Exceptional discussion activity
                elif weighted_score >= 40:
                    return 9.5   # Outstanding discussion activity
                elif weighted_score >= 30:
                    return 9.0   # Excellent discussion activity
                elif weighted_score >= 25:
                    return 8.5   # Very high discussion activity
                elif weighted_score >= 20:
                    return 8.0   # High discussion activity
                elif weighted_score >= 15:
                    return 7.0   # Good discussion activity
                elif weighted_score >= 10:
                    return 6.0   # Above average discussion activity
                elif weighted_score >= 7:
                    return 5.0   # Average discussion activity
                elif weighted_score >= 5:
                    return 4.0   # Below average discussion activity
                elif weighted_score >= 3:
                    return 3.0   # Low discussion activity
                elif weighted_score >= 2:
                    return 2.0   # Very low discussion activity
                elif weighted_score > 0:
                    return 1.0   # Minimal discussion activity
                else:
                    return 0.0   # No discussion activity
                
            except Exception as e:
                logger.error(f"Errore nell'accesso alle discussions: {e}", exc_info=True)
                return 0.0
        except Exception as e:
            logger.error(f"Errore nel calcolo dell'attività delle Discussions: {e}", exc_info=True)
            return 0.0

    def _check_badges_in_readme(self) -> bool:
        """Verifica la presenza di badge nel README del repository."""
        try:
            # Try to get README content
            readme_content = None
            
            if self.local_repo_path:
                # Look for README files in local repo
                readme_files = ["README.md", "readme.md", "README.rst", "readme.rst"]
                for readme_file in readme_files:
                    readme_path = os.path.join(self.local_repo_path, readme_file)
                    if os.path.exists(readme_path):
                        with open(readme_path, 'r', encoding='utf-8') as f:
                            readme_content = f.read()
                        break
            else:
                # Use GitHub API
                try:
                    readme = self._get_cached_data(
                        "readme_content",
                        lambda: self.repo.get_readme()
                    )
                    if readme:
                        readme_content = readme.decoded_content.decode('utf-8')
                except Exception as e:
                    logger.warning(f"Errore nel recupero del README: {e}")
                    return False
            
            if not readme_content:
                return False
                
            # Check for common badge patterns in README
            badge_patterns = [
                r"!\[.*?\]\(https://img\.shields\.io",  # Shields.io badges
                r"!\[.*?\]\(https://travis-ci\.org",     # Travis CI badges
                r"!\[.*?\]\(https://github\.com/.*?/workflows",  # GitHub Actions badges
                r"!\[.*?\]\(https://codecov\.io",        # Codecov badges
                r"!\[.*?\]\(https://circleci\.com",      # CircleCI badges
                r"<img.*?src=\"https://img\.shields\.io", # HTML shield badges
                r"<img.*?src=\"https://github\.com/.*?/workflows", # HTML GitHub Actions badges
                r"!\[.*?\]\(https://app\.codacy\.com",   # Codacy badges
                r"!\[.*?\]\(https://coveralls\.io",      # Coveralls badges
                r"!\[.*?\]\(https://badge\.fury\.io"     # Fury.io badges
            ]
            
            for pattern in badge_patterns:
                if re.search(pattern, readme_content):
                    return True
                    
            return False
        except Exception as e:
            logger.error(f"Errore nella verifica dei badge nel README: {e}", exc_info=True)
            return False

    def _check_changelog_presence(self) -> bool:
        """Verifica la presenza di un file CHANGELOG nel repository."""
        try:
            changelog_patterns = [
                "CHANGELOG.md", "changelog.md",
                "CHANGELOG.txt", "changelog.txt",
                "CHANGES.md", "changes.md",
                "HISTORY.md", "history.md",
                "NEWS.md", "news.md",
                "RELEASES.md", "releases.md"
            ]
            
            if self.local_repo_path:
                # Check in local repository
                for pattern in changelog_patterns:
                    if os.path.exists(os.path.join(self.local_repo_path, pattern)):
                        logger.debug(f"Trovato file changelog: {pattern}")
                        return True
            else:
                # Check using GitHub API
                contents = self._get_cached_data(
                    "root_contents",
                    lambda: list(self.repo.get_contents(""))
                )
                
                for item in contents:
                    if item.type == "file" and item.name.lower() in [p.lower() for p in changelog_patterns]:
                        logger.debug(f"Trovato file changelog: {item.name}")
                        return True
            
            return False
        except Exception as e:
            logger.warning(f"Errore nella verifica del file changelog: {e}")
            return False

    def _check_semantic_versioning(self) -> Tuple[float, str]:
        """
        Verifica se il repository adotta Semantic Versioning nei tag e nelle release.
        
        Returns:
            Tuple[float, str]: Punteggio (0-10) e descrizione dello stato di adozione SemVer
        """
        try:
            # Get tags and releases
            tags = self._get_cached_data(
                "tags",
                lambda: list(self.repo.get_tags()[:30])  # Limit to 30 most recent tags
            )
            
            releases = self._get_cached_data(
                "releases",
                lambda: list(self.repo.get_releases()[:30])  # Limit to 30 most recent releases
            )
            
            # Enhanced patterns for semantic versioning with more specific matching
            # Strict SemVer: MAJOR.MINOR.PATCH with optional prerelease and build metadata
            semver_pattern = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$')
            
            # Partial SemVer: at least MAJOR.MINOR
            partial_semver_pattern = re.compile(r'^v?(\d+)\.(\d+)(?:\.(\d+))?')
            
            # Calendar versioning: YYYY.MM.DD or YY.MM.DD
            calver_pattern = re.compile(r'^v?(?:20)?(\d{2})\.(\d{1,2})\.(\d{1,2})$')
            
            # Track version consistency to reward consistent patterns
            consistent_versioning = True
            version_types = set()
            
            # Check tags first as they're more reliable
            if tags:
                semver_tags = 0
                partial_semver_tags = 0
                calver_tags = 0
                total_tags = min(len(tags), 10)  # Only check up to 10 tags for performance
                
                # Look at the most recent tags first - more important for current practices
                for tag in tags[:total_tags]:
                    tag_name = tag.name
                    
                    # Identify version format and track it
                    if semver_pattern.match(tag_name):
                        semver_tags += 1
                        version_types.add("semver")
                    elif partial_semver_pattern.match(tag_name):
                        partial_semver_tags += 1
                        version_types.add("partial")
                    elif calver_pattern.match(tag_name):
                        calver_tags += 1
                        version_types.add("calver")
                
                # Calculate compliance percentages
                strict_percent = (semver_tags / total_tags) * 100 if total_tags > 0 else 0
                partial_percent = ((semver_tags + partial_semver_tags) / total_tags) * 100 if total_tags > 0 else 0
                calver_percent = (calver_tags / total_tags) * 100 if total_tags > 0 else 0
                
                # Check if versioning is consistent (mainly one type)
                consistent_versioning = len(version_types) <= 1 or (
                    # Allow one dominant type with a few exceptions
                    (semver_tags >= total_tags * 0.7) or
                    (partial_semver_tags >= total_tags * 0.7) or
                    (calver_tags >= total_tags * 0.7)
                )
                
                # Enhanced granular scoring based on SemVer compliance
                if strict_percent >= 90:
                    base_score = 10.0  # Excellent: Nearly perfect SemVer compliance
                    description = "SemVer completo adottato (eccellente)"
                elif strict_percent >= 80:
                    base_score = 9.5   # Very good: Strong SemVer compliance
                    description = "SemVer completo adottato (ottimo)"
                elif strict_percent >= 70:
                    base_score = 9.0   # Good: Good SemVer compliance with some exceptions
                    description = "SemVer completo adottato (buono)"
                elif strict_percent >= 60:
                    base_score = 8.5   # Above average: Mostly SemVer compliant
                    description = "SemVer adottato con alcune eccezioni"
                elif strict_percent >= 50:
                    base_score = 8.0   # Fair: Half strict SemVer compliant
                    description = "SemVer adottato in metà dei tag"
                elif partial_percent >= 90:
                    base_score = 7.5   # Good partial: Nearly perfect partial SemVer 
                    description = "SemVer parziale (MAJOR.MINOR) adottato consistentemente"
                elif partial_percent >= 80:
                    base_score = 7.0   # Decent partial: Strong partial SemVer
                    description = "SemVer parziale (MAJOR.MINOR) adottato"
                elif partial_percent >= 70:
                    base_score = 6.5   # Above average partial
                    description = "SemVer parziale adottato con alcune eccezioni"
                elif partial_percent >= 60:
                    base_score = 6.0   # Fair partial
                    description = "SemVer parziale adottato nella maggioranza dei tag"
                elif partial_percent >= 50:
                    base_score = 5.5   # Moderate partial
                    description = "SemVer parziale adottato in metà dei tag"
                elif calver_percent >= 80:
                    base_score = 6.0   # Good CalVer (alternative but consistent versioning)
                    description = "Versioning basato su calendario (CalVer) adottato"
                elif partial_percent >= 30:
                    base_score = 4.0   # Poor: Some partial SemVer usage
                    description = "SemVer parzialmente adottato (limitato)"
                elif strict_percent > 0 or partial_percent > 0:
                    base_score = 3.0   # Very poor: Occasional SemVer usage
                    description = "SemVer usato occasionalmente"
                else:
                    base_score = 0.0   # None: No SemVer usage
                    description = "SemVer non utilizzato"
                
                # Apply consistency bonus/penalty
                if consistent_versioning and (strict_percent > 0 or partial_percent > 0 or calver_percent > 0):
                    final_score = min(10.0, base_score + 0.5)  # Bonus for consistency
                    if "adottato" in description and not "consistentemente" in description:
                        description += " in modo consistente"
                else:
                    final_score = max(0.0, base_score - 0.5)  # Penalty for inconsistency
                    if strict_percent > 0 or partial_percent > 0:
                        description += " (inconsistente)"
                
                # Add specific suggestions to results
                if strict_percent < 80 and strict_percent > 0:
                    self.results["suggerimenti"].setdefault("documentazione", []).append(
                        "Migliora l'adozione del Semantic Versioning utilizzando consistentemente il formato MAJOR.MINOR.PATCH per tutti i tag."
                    )
                elif partial_percent < 50 and strict_percent == 0:
                    self.results["suggerimenti"].setdefault("documentazione", []).append(
                        "Adotta il Semantic Versioning (MAJOR.MINOR.PATCH) per facilitare la gestione delle dipendenze e la chiarezza delle release."
                    )
                
                return round(final_score, 1), description
            
            # If no tags, check releases
            elif releases:
                semver_releases = 0
                partial_semver_releases = 0
                calver_releases = 0
                total_releases = min(len(releases), 10)  # Only check up to 10 releases
                
                for release in releases[:total_releases]:
                    release_name = release.title or release.tag_name or ""
                    
                    # Identify version format and track it
                    if semver_pattern.match(release_name):
                        semver_releases += 1
                        version_types.add("semver")
                    elif partial_semver_pattern.match(release_name):
                        partial_semver_releases += 1
                        version_types.add("partial")
                    elif calver_pattern.match(release_name):
                        calver_releases += 1
                        version_types.add("calver")
                
                # Calculate compliance percentages
                strict_percent = (semver_releases / total_releases) * 100 if total_releases > 0 else 0
                partial_percent = ((semver_releases + partial_semver_releases) / total_releases) * 100 if total_releases > 0 else 0
                calver_percent = (calver_releases / total_releases) * 100 if total_releases > 0 else 0
                
                # Check if versioning is consistent
                consistent_versioning = len(version_types) <= 1 or (
                    (semver_releases >= total_releases * 0.7) or
                    (partial_semver_releases >= total_releases * 0.7) or
                    (calver_releases >= total_releases * 0.7)
                )
                
                # Similar scoring logic as for tags, but with slightly lower base values
                # because releases might be named differently from their tag
                if strict_percent >= 90:
                    base_score = 9.5  # Excellent in releases
                    description = "SemVer completo nelle release (eccellente)"
                elif strict_percent >= 80:
                    base_score = 9.0  # Very good in releases
                    description = "SemVer completo nelle release (ottimo)"
                elif strict_percent >= 70:
                    base_score = 8.5  # Good in releases
                    description = "SemVer completo nelle release (buono)"
                elif strict_percent >= 60:
                    base_score = 8.0  # Above average in releases
                    description = "SemVer completo nella maggioranza delle release"
                elif strict_percent >= 50:
                    base_score = 7.5  # Fair in releases
                    description = "SemVer completo in metà delle release"
                elif partial_percent >= 80:
                    base_score = 6.5  # Good partial in releases
                    description = "SemVer parziale nelle release"
                elif partial_percent >= 60:
                    base_score = 6.0  # Decent partial in releases
                    description = "SemVer parziale nella maggioranza delle release"
                elif partial_percent >= 50:
                    base_score = 5.5  # Moderate partial in releases
                    description = "SemVer parziale in metà delle release"
                elif calver_percent >= 80:
                    base_score = 6.0  # Good CalVer in releases
                    description = "Versioning basato su calendario nelle release"
                elif partial_percent >= 30:
                    base_score = 3.5  # Poor in releases
                    description = "SemVer parzialmente adottato nelle release (limitato)"
                elif strict_percent > 0 or partial_percent > 0:
                    base_score = 2.5  # Very poor in releases
                    description = "SemVer usato occasionalmente nelle release"
                else:
                    base_score = 0.0  # None in releases
                    description = "SemVer non utilizzato nelle release"
                
                # Apply consistency modifier
                if consistent_versioning and (strict_percent > 0 or partial_percent > 0 or calver_percent > 0):
                    final_score = min(10.0, base_score + 0.5)  # Bonus for consistency
                    if "adottato" in description and not "consistentemente" in description:
                        description += " in modo consistente"
                else:
                    final_score = max(0.0, base_score - 0.5)  # Penalty for inconsistency
                    if strict_percent > 0 or partial_percent > 0:
                        description += " (inconsistente)"
                
                # Add specific suggestions
                if strict_percent < 80 and strict_percent > 0:
                    self.results["suggerimenti"].setdefault("documentazione", []).append(
                        "Migliora l'adozione del Semantic Versioning nelle release utilizzando il formato MAJOR.MINOR.PATCH."
                    )
                elif partial_percent < 50 and strict_percent == 0:
                    self.results["suggerimenti"].setdefault("documentazione", []).append(
                        "Adotta il Semantic Versioning (MAJOR.MINOR.PATCH) nelle release per facilitare la gestione delle dipendenze."
                    )
                
                return round(final_score, 1), description
            
            # No tags or releases found
            self.results["suggerimenti"].setdefault("documentazione", []).append(
                "Considera di creare tag e release utilizzando il Semantic Versioning (MAJOR.MINOR.PATCH)."
            )
            return 0.0, "Nessun tag o release trovato"
            
        except Exception as e:
            logger.warning(f"Errore nella verifica del Semantic Versioning: {e}", exc_info=True)
            return 0.0, "Errore nell'analisi del versioning"

    def _check_license_osi_approved(self) -> Tuple[bool, str]:
        try:
            # Prima prova ad ottenere la licenza dall'API GitHub (se disponibile)
            try:
                license_data = self._get_cached_data(
                    "license_info", 
                    lambda: self.repo.get_license()
                )
                
                if license_data:
                    license_info = license_data
                    license_name = license_data.license.name if license_data.license else "Licenza non standard"
                    
                    # Se GitHub ha già identificato che è OSI-approved, possiamo fidarci
                    if hasattr(license_data.license, "spdx_id") and license_data.license.spdx_id:
                        if license_data.license.spdx_id.lower() in self.osi_approved_licenses:
                            return True, license_name
            except Exception as e:
                logger.debug(f"Impossibile ottenere informazioni sulla licenza tramite API: {e}")
            
            # Se GitHub API non ha fornito informazioni chiare, proviamo a controllare i file di licenza
            license_content = None
            
            if self.local_repo_path:
                # Cerca file di licenza comuni nel repository locale
                license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", 
                               "COPYING.md", "COPYING.txt"]
                for license_file in license_files:
                    full_path = os.path.join(self.local_repo_path, license_file)
                    if os.path.isfile(full_path):
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                license_content = f.read().lower()
                            break
                        except Exception as e:
                            logger.debug(f"Errore nella lettura del file di licenza {license_file}: {e}")
            else:
                # Cerca attraverso l'API GitHub
                contents = self._get_cached_data(
                    "root_contents",
                    lambda: list(self.repo.get_contents(""))
                )
                
                for item in contents:
                    if item.type == "file" and item.name.lower() in ["license", "license.md", "license.txt", 
                                                                   "copying", "copying.md", "copying.txt"]:
                        try:
                            content_data = self.repo.get_contents(item.path)
                            license_content = content_data.decoded_content.decode('utf-8', errors='ignore').lower()
                            break
                        except Exception as e:
                            logger.debug(f"Errore nel recupero del contenuto della licenza {item.path}: {e}")
            
            # Se abbiamo un contenuto di licenza, cerchiamo di identificarlo
            if license_content:
                # Controlla se una delle licenze OSI approvate viene menzionata esplicitamente
                for license_key in self.osi_approved_licenses:
                    license_pattern = re.compile(r'\b' + re.escape(license_key) + r'\b', re.IGNORECASE)
                    if license_pattern.search(license_content):
                        # Se troviamo una corrispondenza, controlliamo anche alcuni falsi positivi comuni
                        if "not licensed under" in license_content and license_key in license_content.split("not licensed under")[1][:50]:
                            continue
                        
                        return True, f"Licenza compatibile con {license_key.upper()}"
                
                # Controllo euristico per licenze comuni
                if "permission is hereby granted, free of charge" in license_content and "copyright" in license_content:
                    if "the software is provided \"as is\", without warranty" in license_content:
                        return True, "Licenza MIT o simile (OSI approvata)"
                
                # Il file di licenza esiste ma non è stata identificata come OSI-approved
                return False, "Licenza non riconosciuta come OSI-approvata"
            
            # Se abbiamo informazioni dalla API ma non abbiamo potuto determinare se è OSI-approved
            if license_info:
                return False, license_name
                
            # Non abbiamo trovato alcuna licenza
            return False, "Nessuna licenza trovata"
            
        except Exception as e:
            logger.error(f"Errore nella verifica della licenza OSI: {e}", exc_info=True)
            return (False, "Errore")  # temporary stub

    def _check_build_tools_standard(self) -> Tuple[str, float]:
        """Verifica la presenza di strumenti di build standard nel repository.
        
        Returns:
            Tuple[str, float]: Una tupla con la descrizione dei build tool trovati e il punteggio normalizzato
        """
        try:
            # Dictionary of common build tools by language/platform with their standard files
            build_tools = {
                "Java": ["pom.xml", "build.gradle", "build.gradle.kts", "gradlew", "mvnw", "build.xml"],
                "JavaScript/Node.js": ["package.json", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json", "webpack.config.js", "rollup.config.js"],
                "Python": ["setup.py", "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock"],
                "C/C++": ["Makefile", "CMakeLists.txt", ".cmake", "configure.ac", "autogen.sh"],
                "Go": ["go.mod", "go.sum", "Makefile.go"],
                "Rust": ["Cargo.toml", "Cargo.lock"],
                "Ruby": ["Gemfile", "Gemfile.lock", "Rakefile", ".gemspec"],
                "PHP": ["composer.json", "composer.lock"],
                "C#/.NET": ["*.csproj", "*.sln", "packages.config", "NuGet.Config"],
                "Swift": ["Package.swift", "Podfile", "Cartfile"],
                "Scala": ["build.sbt", ".scala-build"],
                "Haskell": ["stack.yaml", "package.yaml", "cabal.project"],
                "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
            }
            
            detected_tools = {}
            
            if self.local_repo_path:
                # Search in local repository
                for root, dirs, files in os.walk(self.local_repo_path):
                    # Avoid going too deep in the repository structure
                    if root.count(os.sep) - self.local_repo_path.count(os.sep) > 3:
                        continue
                    
                    # Scan files in the current directory
                    for file in files:
                        # Check each language's build tools
                        for language, tool_files in build_tools.items():
                            for tool_file in tool_files:
                                # Handle wildcard patterns (e.g., *.csproj)
                                if tool_file.startswith('*') and file.endswith(tool_file[1:]):
                                    detected_tools.setdefault(language, []).append(file)
                                # Exact file match
                                elif file.lower() == tool_file.lower():
                                    detected_tools.setdefault(language, []).append(file)
            else:
                # Use GitHub API
                # First check root directory
                contents = self._get_cached_data(
                    "root_contents",
                    lambda: list(self.repo.get_contents(""))
                )
                
                # Scan the root directory first
                for item in contents:
                    if item.type == "file":
                        # Check each language's build tools
                        for language, tool_files in build_tools.items():
                            for tool_file in tool_files:
                                # Handle wildcard patterns (e.g., *.csproj)
                                if tool_file.startswith('*') and item.name.endswith(tool_file[1:]):
                                    detected_tools.setdefault(language, []).append(item.name)
                                # Exact file match
                                elif item.name.lower() == tool_file.lower():
                                    detected_tools.setdefault(language, []).append(item.name)
                
                # If needed, check a few key subdirectories for common structure patterns
                # This is limited to avoid excessive API calls
                common_subdirs = ["build", "tools", "scripts"]
                for subdir in common_subdirs:
                    try:
                        subdir_path = next((item.path for item in contents if item.type == "dir" and item.name.lower() == subdir), None)
                        if subdir_path:
                            subdir_contents = self._get_cached_data(
                                f"{subdir}_contents",
                                lambda path=subdir_path: list(self.repo.get_contents(path))
                            )
                            
                            for item in subdir_contents:
                                if item.type == "file":
                                    # Check each language's build tools
                                    for language, tool_files in build_tools.items():
                                        for tool_file in tool_files:
                                            # Handle wildcard patterns
                                            if tool_file.startswith('*') and item.name.endswith(tool_file[1:]):
                                                detected_tools.setdefault(language, []).append(f"{subdir}/{item.name}")
                                            # Exact file match
                                            elif item.name.lower() == tool_file.lower():
                                                detected_tools.setdefault(language, []).append(f"{subdir}/{item.name}")
                    except Exception as e:
                        logger.debug(f"Errore nell'analisi del sottodirettorio {subdir}: {e}")
            
            # Calculate score and prepare description
            if detected_tools:
                num_languages = len(detected_tools)
                description_parts = []
                
                for language, files in detected_tools.items():
                    unique_files = list(set(files))  # Remove duplicates
                    if len(unique_files) > 2:
                        description_parts.append(f"{language}: {unique_files[0]}, {unique_files[1]}, ...")
                    else:
                        description_parts.append(f"{language}: {', '.join(unique_files)}")
                
                description = "; ".join(description_parts)
                
                # Score based on number of detected build tools and languages
                # More languages with build tools = higher score, up to 10
                score = min(10.0, 5.0 + (num_languages * 1.5))
                
                return description, score
            else:
                return "Nessuno strumento di build standard rilevato", 0.0
                
        except Exception as e:
            logger.error(f"Errore nell'analisi degli strumenti di build: {e}", exc_info=True)
            return "Errore nell'analisi", 0.0

    def _check_contributor_distribution(self) -> float:
        """
        Analizza la distribuzione dei contributi per valutare il "bus factor" del repository.
        
        Calcola diverse metriche di distribuzione:
        - Quanto lavoro è concentrato sui top contributor
        - Indice Gini adattato per misurare la diseguaglianza tra contributori
        - Numero effettivo di contributori attivi
        
        Returns:
            float: Punteggio da 0 (distribuzione pessima) a 10 (distribuzione ottimale)
        """
        try:
            contributors = self._get_cached_data(
                "all_contributors",
                lambda: list(self.repo.get_contributors()[:100])  # Limita a 100 contributori per performance
            )
            
            if not contributors or len(contributors) == 0:
                logger.info("Nessun contributore trovato")
                return 0.0
                
            # Estrai i contributi per ogni contributore
            contributions = [c.contributions for c in contributors if c.contributions > 0]
            contributions.sort(reverse=True)  # Ordina in modo decrescente
            
            total_commits = sum(contributions)
            if total_commits == 0:
                logger.info("Nessun commit trovato")
                return 0.0
                
            # Numero totale di contributori con almeno un commit
            num_contributors = len(contributions)
            
            # 1. Metrica: rapporto tra i commit del contributore principale e il totale
            top_contributor_ratio = contributions[0] / total_commits
            
            # 2. Metrica: concentrazione nei top 20% contributori (principio di Pareto)
            top_20_percent_idx = max(1, int(num_contributors * 0.2))
            top_20_percent_commits = sum(contributions[:top_20_percent_idx])
            top_20_percent_ratio = top_20_percent_commits / total_commits
            
            # 3. Metrica: calcolo di un indice Gini adattato (0=distribuito equamente, 1=un solo contributore)
            # Ordina i contributi in modo crescente per il calcolo del Gini
            sorted_contrib = sorted(contributions)
            cum_contrib = [sum(sorted_contrib[:i+1]) for i in range(len(sorted_contrib))]
            lorenz_points = [x / cum_contrib[-1] for x in cum_contrib]
            gini = 1 - sum((lorenz_points[i-1] + lorenz_points[i]) / num_contributors 
                        for i in range(1, num_contributors))
                        
            # 4. Metrica: "contributori effettivi" basato sull'indice di Shannon
            # Trasforma i contributi in probabilità
            probs = [c / total_commits for c in contributions]
            shannon = -sum(p * math.log(p) for p in probs if p > 0)
            effective_contributors = math.exp(shannon)
            
            # 5. Metrica: "bus factor" approssimativo 
            # Quanti contributori principali servono per raggiungere il 50% dei commit
            cumulative = 0
            bus_factor = 0
            for contrib in contributions:
                cumulative += contrib
                bus_factor += 1
                if cumulative / total_commits >= 0.5:
                    break
            
            # Log delle metriche per debugging
            logger.debug(f"Statistiche distribuzione: contributori={num_contributors}, " +
                        f"top_ratio={top_contributor_ratio:.2f}, top20%_ratio={top_20_percent_ratio:.2f}, " +
                        f"gini={gini:.2f}, effettivi={effective_contributors:.1f}, bus_factor={bus_factor}")
            
            # Calcolo punteggio complessivo con pesi diversi per le metriche
            # Un punteggio più alto rappresenta una distribuzione più sana
            
            # 1. Score basato sul rapporto del top contributor (meglio se più basso)
            top_contrib_score = 10 * (1 - top_contributor_ratio)
            
            # 2. Score basato sul rapporto del top 20% (meglio se più vicino a 0.5)
            # Obiettivo: 20% contributori → ~50% contributi (ideale per progetti sani)
            pareto_score = 10 * (1 - abs(top_20_percent_ratio - 0.6))
            
            # 3. Score basato sull'indice Gini (meglio se più basso)
            gini_score = 10 * (1 - gini)
            
            # 4. Score basato sui contributori effettivi relativo al totale
            if num_contributors >= 5:
                # Idealmente il numero di contributori effettivi è almeno 50% del totale
                effective_ratio = effective_contributors / num_contributors
                effective_score = 10 * min(1, effective_ratio / 0.5)
            else:
                # Per progetti piccoli
                effective_score = 10 * min(1, effective_contributors / 2.5)
            
            # 5. Score basato sul bus factor (più alto = meglio)
            bus_factor_score = min(10, bus_factor * 2)
            
            # Combina i punteggi con pesi appropriati
            # Enfatizza il bus factor e i contributori effettivi
            weights = [0.15, 0.15, 0.2, 0.25, 0.25]
            combined_score = (
                weights[0] * top_contrib_score +
                weights[1] * pareto_score +
                weights[2] * gini_score +
                weights[3] * effective_score +
                weights[4] * bus_factor_score
            )
            
            # Aggiunge suggerimenti in base al punteggio
            if combined_score < 3:
                self.results["suggerimenti"].setdefault("distribuzione", []).append(
                    "La maggior parte del lavoro è svolto da un singolo contributore. Aumenta il 'bus factor' "
                    "incoraggiando altri a contribuire e documentando la conoscenza del codice."
                )
            elif combined_score < 5:
                self.results["suggerimenti"].setdefault("distribuzione", []).append(
                    "La distribuzione dei contributi è fortemente centralizzata. Considera di assegnare "
                    "responsabilità specifiche ad altri contributori per diversificare la conoscenza del codice."
                )
            elif combined_score < 7:
                self.results["suggerimenti"].setdefault("distribuzione", []).append(
                    "La distribuzione dei contributi è moderatamente centralizzata. Continua ad allargare "
                    "la base di contributori attivi per una maggiore resilienza del progetto."
                )
                
            # Aggiungi dettagli alla sezione risultati per reporting
            self.results.setdefault("metriche_distribuzione", {})
            self.results["metriche_distribuzione"] = {
                "top_contributor_ratio": round(top_contributor_ratio * 100, 1),
                "top_20_percent_ratio": round(top_20_percent_ratio * 100, 1),
                "gini_index": round(gini, 2),
                "effective_contributors": round(effective_contributors, 1),
                "bus_factor": bus_factor,
                "total_contributors": num_contributors
            }
            
            return round(max(0.0, min(10.0, combined_score)), 2)
            
        except Exception as e:
            logger.error(f"Errore nell'analisi della distribuzione dei contributi: {e}", exc_info=True)
            return 0.0

    def _check_dependencies_freshness(self) -> float:
        """
        Verifica se le dipendenze del progetto sono aggiornate.
        
        Analizza i file di dipendenze comuni (requirements.txt, package.json, etc.) 
        e valuta quanto sono aggiornate le versioni specificate rispetto alle più recenti.
        
        Returns:
            float: Punteggio da 0 a 10, dove 10 indica dipendenze completamente aggiornate
        """
        try:
            logger.info("Verificando l'aggiornamento delle dipendenze...")
            
            # Assicurati di avere un repository clonato
            if not self.local_repo_path:
                logger.warning("Verifica dipendenze richiede --clone. Restituisco valore di default.")
                return 5.0  # Valore neutro se non abbiamo accesso locale
            
            # Definisce i tipi di file di dipendenze da cercare e le loro funzioni di analisi
            dependency_file_types = {
                "python": ["requirements.txt", "Pipfile", "Pipfile.lock", "pyproject.toml"],
                "javascript": ["package.json", "package-lock.json", "yarn.lock"],
                "java": ["pom.xml", "build.gradle"],
                "ruby": ["Gemfile", "Gemfile.lock"],
                "php": ["composer.json", "composer.lock"],
                "dotnet": ["*.csproj", "packages.config"]
            }
            
            # Inizializza le statistiche
            total_deps = 0
            outdated_deps = 0
            severely_outdated_deps = 0  # Per versioni criticamente vecchie
            dependency_files_found = {}
            
            # 1. Trova i file di dipendenze nel repository
            for root, _, files in os.walk(self.local_repo_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    
                    # Controlla ogni tipo di file di dipendenze
                    for platform, file_patterns in dependency_file_types.items():
                        for pattern in file_patterns:
                            if pattern.startswith('*') and filename.endswith(pattern[1:]):
                                # Pattern wildcard
                                dependency_files_found.setdefault(platform, []).append(file_path)
                                break
                            elif filename.lower() == pattern.lower():
                                # Match esatto
                                dependency_files_found.setdefault(platform, []).append(file_path)
                                break
            
            # Se non troviamo file di dipendenze, restituisci un valore neutro
            if not dependency_files_found:
                logger.info("Nessun file di dipendenze trovato. Restituisco valore neutro.")
                return 5.0
            
            logger.info(f"File di dipendenze trovati: {dependency_files_found}")
            
            # 2. Analizza i file di dipendenze per piattaforma
            for platform, file_paths in dependency_files_found.items():
                if platform == "python":
                    python_results = self._check_python_dependencies(file_paths)
                    total_deps += python_results.get('total', 0)
                    outdated_deps += python_results.get('outdated', 0)
                    severely_outdated_deps += python_results.get('severely_outdated', 0)
                    
                elif platform == "javascript":
                    js_results = self._check_js_dependencies(file_paths)
                    total_deps += js_results.get('total', 0)
                    outdated_deps += js_results.get('outdated', 0)
                    severely_outdated_deps += js_results.get('severely_outdated', 0)
                    
                # Per le altre piattaforme, usa un'analisi semplificata
                else:
                    other_results = self._check_generic_dependencies(file_paths, platform)
                    total_deps += other_results.get('total', 0)
                    outdated_deps += other_results.get('outdated', 0)
            
            # 3. Calcola il punteggio finale basato sulle statistiche
            if total_deps == 0:
                logger.info("Nessuna dipendenza analizzabile trovata")
                return 5.0  # Valore neutro
                
            # Calcola percentuali
            outdated_percent = min(100, (outdated_deps / total_deps) * 100)
            severely_outdated_percent = min(100, (severely_outdated_deps / total_deps) * 100)
            
            # Calcola punteggio: pesa di più le dipendenze gravemente obsolete
            base_score = 10.0 - (outdated_percent / 10)  # Perde 1 punto ogni 10% di dipendenze obsolete
            penalty = severely_outdated_percent / 5      # Penalità aggiuntiva per dipendenze gravemente obsolete
            
            final_score = max(0, min(10, base_score - penalty))
            
            logger.info(f"Analisi dipendenze completata: {total_deps} dipendenze trovate, " +
                        f"{outdated_deps} obsolete ({outdated_percent:.1f}%), " +
                        f"{severely_outdated_deps} gravemente obsolete ({severely_outdated_percent:.1f}%)")
            logger.info(f"Punteggio freschezza dipendenze: {final_score:.2f}/10")
            
            # Aggiungi suggerimenti basati sui risultati
            if outdated_deps > 0:
                suggestion = f"Aggiorna le {outdated_deps} dipendenze obsolete per migliorare sicurezza e performance"
                if severely_outdated_deps > 0:
                    suggestion += f", di cui {severely_outdated_deps} criticamente vecchie"
                if "sicurezza" in self.results.get("suggerimenti", {}):
                    self.results["suggerimenti"]["sicurezza"].append(suggestion)
            
            return round(final_score, 2)
            
        except Exception as e:
            logger.error(f"Errore nella verifica della freschezza delle dipendenze: {e}", exc_info=True)
            return 5.0  # Valore neutro in caso di errore
        
    def _check_python_dependencies(self, file_paths: List[str]) -> Dict[str, int]:
        """
        Analizza i file di dipendenze Python e verifica se sono aggiornate.
        
        Args:
            file_paths: Lista di percorsi di file di dipendenze Python
            
        Returns:
            Dizionario con statistiche delle dipendenze
        """
        result = {'total': 0, 'outdated': 0, 'severely_outdated': 0}
        
        try:
            # Prioritizza requirements.txt se presente
            requirements_files = [f for f in file_paths if os.path.basename(f).lower() == 'requirements.txt']
            if not requirements_files:
                requirements_files = file_paths
                
            for file_path in requirements_files:
                if not os.path.exists(file_path):
                    continue
                    
                filename = os.path.basename(file_path).lower()
                
                # Usa pip per verificare le dipendenze obsolete
                if filename == 'requirements.txt':
                    try:
                        # Usa pip per controllare le versioni obsolete
                        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
                            # Copia il contenuto del requirements nel file temporaneo
                            with open(file_path, 'r', encoding='utf-8') as req_file:
                                # Filtra le righe di commento e vuote
                                valid_lines = [line.strip() for line in req_file if line.strip() and not line.strip().startswith('#')]
                                # Scrivi solo dipendenze valide nel file temporaneo
                                temp_file.write('\n'.join(valid_lines))
                        
                        # Usa pip check per verificare le dipendenze obsolete
                        pip_cmd = ["pip", "list", "--outdated", "--format=json"]
                        env = os.environ.copy()
                        env["PIP_REQUIRE_VIRTUALENV"] = "false"  # Consenti pip di funzionare fuori da un virtualenv
                        
                        process = subprocess.run(
                            pip_cmd,
                            capture_output=True, 
                            text=True, 
                            timeout=60,
                            check=False,
                            env=env
                        )
                        
                        if process.returncode == 0 and process.stdout:
                            try:
                                outdated_packages = json.loads(process.stdout)
                                
                                # Conta quanti pacchetti nel requirements.txt sono nell'elenco degli obsoleti
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    for line in f:
                                        line = line.strip()
                                        if line and not line.startswith('#'):
                                            # Estrai il nome del pacchetto
                                            match = re.match(r'^([a-zA-Z0-9_-]+).*?(?:==|>=|<=|>|<|~=|!=)?\s*([0-9a-zA-Z.-]+)?', line)
                                            if match:
                                                package_name = match.group(1).lower()
                                                package_version = match.group(2) if len(match.groups()) > 1 else None
                                                
                                                result['total'] += 1
                                                
                                                # Controlla se è obsoleto
                                                for outdated in outdated_packages:
                                                    if outdated.get('name', '').lower() == package_name:
                                                        result['outdated'] += 1
                                                        
                                                        # Calcola se è gravemente obsoleto (più di 2 versioni principali indietro)
                                                        if package_version and 'latest_version' in outdated:
                                                            current_parts = package_version.split('.')
                                                            latest_parts = outdated['latest_version'].split('.')
                                                            
                                                            if len(current_parts) >= 1 and len(latest_parts) >= 1:
                                                                try:
                                                                    # Se la MAJOR version è indietro di 2 o più
                                                                    if int(latest_parts[0]) - int(current_parts[0]) >= 2:
                                                                        result['severely_outdated'] += 1
                                                                except ValueError:
                                                                    pass
                                                        break
                            except json.JSONDecodeError:
                                logger.warning("Errore nel parsing dell'output JSON di pip list --outdated")
                    except Exception as e:
                        logger.warning(f"Errore nell'esecuzione di pip list --outdated: {e}")

                # Analisi di Pipfile/Pipfile.lock
                elif filename in ['pipfile', 'pipfile.lock']:
                    try:
                        if filename == 'pipfile':
                            # Analisi semplice di Pipfile
                            with open(file_path, 'r', encoding='utf-8') as f:
                                in_packages = False
                                for line in f:
                                    line = line.strip()
                                    if '[packages]' in line:
                                        in_packages = True
                                        continue
                                    if in_packages and line.startswith('['):
                                        in_packages = False
                                        continue
                                    if in_packages and '=' in line:
                                        result['total'] += 1
                                        # Semplice euristica per versioni specifiche
                                        if '==' in line:
                                            result['outdated'] += 1
                        
                        elif filename == 'pipfile.lock':
                            # Analisi di Pipfile.lock (formato JSON)
                            with open(file_path, 'r', encoding='utf-8') as f:
                                try:
                                    data = json.load(f)
                                    if 'default' in data:
                                        result['total'] += len(data['default'])
                                        # Difficile determinare se sono obsolete senza API esterne
                                        # Proviamo a stimare in base all'hash
                                        if '_meta' in data and 'pipfile-spec' in data['_meta']:
                                            if data['_meta']['pipfile-spec'] < 6:  # spec versione vecchia
                                                result['outdated'] += len(data['default']) // 2
                                except json.JSONDecodeError:
                                    pass
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi del file {filename}: {e}")
                
                # Analisi di pyproject.toml
                elif filename == 'pyproject.toml':
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Cerca sezioni di dipendenze in formato TOML
                            dependencies_section = re.search(r'\[tool\.poetry\.dependencies\](.*?)(\[|\Z)', content, re.DOTALL)
                            if dependencies_section:
                                deps = dependencies_section.group(1)
                                # Conta le dipendenze
                                package_matches = re.findall(r'^([a-zA-Z0-9_-]+)\s*=\s*["\'](.+?)["\']', deps, re.MULTILINE)
                                result['total'] += len(package_matches)
                                
                                # Stima dipendenze obsolete (dipendenze con versioni fisse specificate)
                                fixed_versions = re.findall(r'^[a-zA-Z0-9_-]+\s*=\s*["\']={2,3}[0-9]+\.[0-9]+\.[0-9]+["\']', deps, re.MULTILINE)
                                result['outdated'] += len(fixed_versions)
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi di pyproject.toml: {e}")
        
        except Exception as e:
            logger.error(f"Errore nell'analisi delle dipendenze Python: {e}", exc_info=True)
        
        return result

    def _check_js_dependencies(self, file_paths: List[str]) -> Dict[str, int]:
        """
        Analizza i file di dipendenze JavaScript/Node.js e verifica se sono aggiornate.
        
        Args:
            file_paths: Lista di percorsi di file di dipendenze JavaScript
            
        Returns:
            Dizionario con statistiche delle dipendenze
        """
        result = {'total': 0, 'outdated': 0, 'severely_outdated': 0}
        
        try:
            # Prioritizza package.json
            package_json_files = [f for f in file_paths if os.path.basename(f).lower() == 'package.json']
            if not package_json_files:
                package_json_files = file_paths
            
            for file_path in package_json_files:
                if not os.path.exists(file_path):
                    continue
                
                filename = os.path.basename(file_path).lower()
                
                if filename == 'package.json':
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Controlla le dipendenze
                            dependencies = {}
                            dependencies.update(data.get('dependencies', {}))
                            dependencies.update(data.get('devDependencies', {}))
                            
                            result['total'] += len(dependencies)
                            
                            for pkg, version in dependencies.items():
                                # Conta dipendenze con versioni fisse o intervalli stretti
                                if version.startswith('^0.') or version.startswith('~0.'):
                                    result['outdated'] += 1
                                    result['severely_outdated'] += 1
                                elif version.startswith('^') or version.startswith('~'):
                                    # Le versioni con ^ o ~ sono generalmente meno problematiche
                                    pass
                                elif version.startswith('>='):
                                    # Il formato >= è generalmente aggiornato
                                    pass
                                else:
                                    # Versioni esatte sono spesso obsolete
                                    version_match = re.match(r'^([0-9]+)\.([0-9]+)\.([0-9]+)', version)
                                    if version_match:
                                        major = int(version_match.group(1))
                                        if major == 0:
                                            result['outdated'] += 1
                                            result['severely_outdated'] += 1
                                        elif major == 1:
                                            result['outdated'] += 0.5  # Contiamo come mezza dipendenza obsoleta
                    except json.JSONDecodeError as e:
                        logger.warning(f"Errore nel parsing di package.json: {e}")
                
                elif filename in ['package-lock.json', 'yarn.lock']:
                    # Un approccio più complesso sarebbe confrontare con i dati di un registry npm
                    # Ma per semplicità facciamo solo una stima basata sulla data del file
                    try:
                        file_age_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(file_path))).days
                        
                        # Stima basata sull'età del file di lock
                        if file_age_days > 365:  # Più di un anno
                            result['total'] += 10  # Stima
                            result['outdated'] += 8
                            result['severely_outdated'] += 5
                        elif file_age_days > 180:  # Più di sei mesi
                            result['total'] += 10  # Stima
                            result['outdated'] += 5
                            result['severely_outdated'] += 2
                        elif file_age_days > 90:  # Più di tre mesi
                            result['total'] += 10  # Stima
                            result['outdated'] += 3
                        else:  # Relativamente recente
                            result['total'] += 10  # Stima
                            result['outdated'] += 1
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi dell'età del file {filename}: {e}")
        
        except Exception as e:
            logger.error(f"Errore nell'analisi delle dipendenze JavaScript: {e}", exc_info=True)
        
        return result

    def _check_generic_dependencies(self, file_paths: List[str], platform: str) -> Dict[str, int]:
        """
        Analisi generica per altre piattaforme di dipendenze.
        
        Args:
            file_paths: Lista di percorsi di file di dipendenze
            platform: Nome della piattaforma
            
        Returns:
            Dizionario con statistiche delle dipendenze
        """
        result = {'total': 0, 'outdated': 0, 'severely_outdated': 0}
        
        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    continue
                    
                filename = os.path.basename(file_path).lower()
                
                # Per Java/Maven
                if platform == "java" and filename == "pom.xml":
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Cerca dipendenze
                            dependencies = re.findall(r'<dependency>.*?</dependency>', content, re.DOTALL)
                            result['total'] += len(dependencies)
                            
                            # Stima euristica delle dipendenze obsolete
                            for dep in dependencies:
                                version_match = re.search(r'<version>(.*?)</version>', dep)
                                if version_match:
                                    version = version_match.group(1)
                                    if '$' in version:  # Variable reference - probably up to date
                                        pass
                                    elif version.startswith('1.'):
                                        result['outdated'] += 1
                                        if version.startswith('1.0.') or version.startswith('1.1.') or version.startswith('1.2.'):
                                            result['severely_outdated'] += 1
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi di pom.xml: {e}")
                
                # Per Gradle
                elif platform == "java" and filename == "build.gradle":
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Cerca dipendenze
                            dependencies = re.findall(r'(implementation|api|compile)\s+[\'"]([^\'"]*)[\'":]', content)
                            result['total'] += len(dependencies)
                            
                            # Stima euristica
                            for _, dep in dependencies:
                                if ':1.' in dep:  # Vecchia versione 1.x
                                    result['outdated'] += 1
                                    if ':1.0.' in dep or ':1.1.' in dep:
                                        result['severely_outdated'] += 1
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi di build.gradle: {e}")
                
                # Per Ruby/Gemfile
                elif platform == "ruby" and filename in ["gemfile", "gemfile.lock"]:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if filename == "gemfile":
                                gems = re.findall(r'gem\s+[\'"]([^\'"]*)[\'"](?:,\s*[\'"]([^\'"]*)[\'"])?', content)
                                result['total'] += len(gems)
                            else:  # gemfile.lock
                                gems = re.findall(r'^\s{4}([^ ]+) \((.*?)\)', content, re.MULTILINE)
                                result['total'] += len(gems)
                                
                            # Stima euristica basata sull'età del file
                            file_age_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(file_path))).days
                            if file_age_days > 365:
                                result['outdated'] = result['total'] * 0.7  # 70% obsoleto se file vecchio > 1 anno
                                result['severely_outdated'] = result['total'] * 0.3
                            elif file_age_days > 180:
                                result['outdated'] = result['total'] * 0.4
                                result['severely_outdated'] = result['total'] * 0.1
                            elif file_age_days > 90:
                                result['outdated'] = result['total'] * 0.2
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi di {filename}: {e}")
                        
                # Altri file di dipendenze generici - stima basata sull'età del file
                else:
                    try:
                        # Leggi il file e prova a contare le dipendenze in modo generico
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Cerca pattern di versione generici
                            versions = re.findall(r'[0-9]+\.[0-9]+\.[0-9]+', content)
                            result['total'] += len(versions)
                            
                            # Stima basata sull'età del file
                            file_age_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(file_path))).days
                            if file_age_days > 365:
                                result['outdated'] = result['total'] * 0.6  # 60% obsoleto se file vecchio > 1 anno
                            elif file_age_days > 180:
                                result['outdated'] = result['total'] * 0.3
                            elif file_age_days > 90:
                                result['outdated'] = result['total'] * 0.1
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi generica del file {filename}: {e}")
        
        except Exception as e:
            logger.error(f"Errore nell'analisi delle dipendenze {platform}: {e}", exc_info=True)
        
        # Assicura che i valori siano interi
        result['total'] = int(result['total'])
        result['outdated'] = int(result['outdated'])
        result['severely_outdated'] = int(result['severely_outdated'])
        
        return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analizzatore di repository GitHub")
    repo_group = parser.add_mutually_exclusive_group(required=True)
    repo_group.add_argument("repository", nargs="?", help="Nome del repository nel formato 'username/repository'")
    repo_group.add_argument("-r", "--repo", dest="repository", help="Nome del repository nel formato 'username/repository'")
    parser.add_argument("--clone", action="store_true", help="Clona il repository localmente per analisi più approfondite")
    args = parser.parse_args()

    # Validate repository name
    if not args.repository:
        print("Errore: È necessario specificare un repository nel formato 'username/repository'")
        print("Esempio: python repolizer.py username/repository")
        print("      o: python repolizer.py -r username/repository")
        parser.print_help()
        exit(1)

    try:
        with RepoAnalyzer(args.repository, clone_repo=args.clone) as analyzer:
            results = analyzer.analyze()
            
            # Utilizza generate_report per avere report con etichette mappate
            report_data = analyzer.generate_report()
            
            json_file = analyzer._save_report_json(report_data)
            if json_file:
                print(f"Report JSON salvato in: {json_file}")
                
            # Generate the HTML report and save it
            html_content = generate_html_report(report_data)
            if html_content:
                html_file = analyzer._save_report_html(html_content, report_data)
                if html_file:
                    print(f"Report HTML salvato in: {html_file}")
    except Exception as e:
        print(f"\nSi è verificato un errore durante l'analisi: {e}")
        logger.error(f"Errore durante l'analisi: {e}", exc_info=True)
        exit(1)