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

try:
    import bandit
except ImportError:
    bandit = None

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
    "attivita_manutenzione": "Manutenzione",
    "community_collaborazione": "Collaborazione",
    "documentazione": "Documentazione",
    "distribuzione": "Distribuzione",
    "qualita_codice": "Codice",
    "setup_usabilita": "Adozione",
    "sicurezza": "Sicurezza",
    "testing_cicd": "Integrazione"
}


class RepoAnalyzer:
    """Classe per analizzare repository GitHub."""
    
    def __init__(self, repo_name: str, config_file: str = CONFIG_FILE, clone_repo: bool = False):
        """Inizializza l'analizzatore di repository.

        Args:
            repo_name: Nome del repository nel formato 'username/repository'
            config_file: Percorso del file di configurazione
            clone_repo: Clona il repository localmente per analisi più approfondite (default: False)
        """
        self.repo_name = repo_name
        self.config_file = config_file
        self.config = self._load_config()
        self.console = Console()
        self.clone_repo = clone_repo
        self.local_repo_path = None  # path al repo clonato

        # Inizializza l'oggetto Github con o senza token
        if GITHUB_TOKEN:
            self.github = Github(GITHUB_TOKEN, per_page=100)
            self.console.print("[green]Token GitHub trovato. Utilizzando limiti API aumentati.[/green]")
        else:
            self.github = Github(per_page=100)
            self.console.print("[yellow]Attenzione: Token GitHub non trovato. Le richieste API potrebbero essere limitate.[/yellow]")
            self.console.print("[yellow]Crea un file .env con GITHUB_TOKEN=your_token per aumentare i limiti API.[/yellow]")
        
        # Ottieni il repository
        self.repo = self._get_repository()
        self.results = {}
        
        # Cache per ridurre le chiamate API
        self._cache = {}
        
        # Verifica i limiti API
        self._check_api_limits()

    def __enter__(self):
        """Context manager entry: Clona il repository se necessario."""
        if self.clone_repo and self.repo:
            try:
                self.local_repo_path = tempfile.mkdtemp()
                clone_url = self.repo.clone_url
                subprocess.run(["git", "clone", "--depth", "1", clone_url, self.local_repo_path], check=True, capture_output=True, text=True)  # clone con depth 1
            except subprocess.CalledProcessError as e:
                print(f"Errore durante il clone del repository: {e}")
                self.local_repo_path = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: Elimina il repository clonato."""
        if self.local_repo_path:
            try:
                shutil.rmtree(self.local_repo_path)
            except OSError as e:
                print(f"Errore nella rimozione della directory temporanea: {e}")

    def _load_config(self) -> Dict:
        """Carica la configurazione dal file JSON.

        Returns:
            Dizionario con la configurazione
        """
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Errore nel caricamento del file di configurazione: {e}")
            return {"parametri": {}}
            
    def _save_report_json(self, report_data: Dict, report_dir: str = "reports") -> str:
        """Salva il report JSON in un file con nome basato sul repository e data/ora.
        
        Args:
            report_data: Dati del report da salvare
            report_dir: Directory dove salvare i report (default: "reports")
            
        Returns:
            Percorso del file JSON creato
        """
        try:
            # Crea la directory se non esiste
            os.makedirs(report_dir, exist_ok=True)
            
            # Genera nome file con nome repo e timestamp
            repo_name = report_data.get("repo_name", "report").replace("/", "_")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            json_file = os.path.join(report_dir, f"{repo_name}_{timestamp}.json")
            
            # Salva il report
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
                
            return json_file
        except Exception as e:
            logger.error(f"Errore nel salvataggio del report JSON: {e}")
            return ""
            
    def _save_report_html(self, html_content: str, report_data: Dict, report_dir: str = "reports") -> str:
        """Salva il report HTML in un file con nome basato sul repository e data/ora.
        
        Args:
            html_content: Contenuto HTML del report
            report_data: Dati del report per generare il nome
            report_dir: Directory dove salvare i report (default: "reports")
            
        Returns:
            Percorso del file HTML creato
        """
        try:
            # Crea la directory se non esiste
            os.makedirs(report_dir, exist_ok=True)
            
            # Genera nome file con nome repo e timestamp
            repo_name = report_data.get("repo_name", "report").replace("/", "_")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = os.path.join(report_dir, f"{repo_name}_{timestamp}.html")
            
            # Salva il report
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            return html_file
        except Exception as e:
            logger.error(f"Errore nel salvataggio del report HTML: {e}")
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
                
                result = fetch_func(*args, **kwargs)
                
                # Ripristina il timeout originale se necessario
                if hasattr(original_func, '__self__') and isinstance(original_func.__self__, Github):
                    self.github.timeout = old_timeout
                
                # Assicurati che il risultato sia una lista se è un iteratore
                if hasattr(result, '__iter__') and not isinstance(result, (list, dict, str)):
                    result = list(result)
                
                self._cache[key] = result
            except TimeoutError as e:
                print(f"Timeout durante il recupero dei dati per {key}: {e}")
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
                        return avg_complexity
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
                        return avg_complexity
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
                process = subprocess.run(["flake8", effective_path], capture_output=True, text=True, timeout=30)
                # Se flake8 restituisce un codice di errore > 1, flake8 potrebbe essere fallito del tutto
                if process.returncode <= 1:  # 0=success, 1=violations found
                    lines = [l for l in process.stdout.splitlines() if l.strip()]
                    errors = len(lines)
                    # Più errori -> punteggio più basso, max 10.0
                    flake8_score = max(0.0, 10.0 - (errors / 10.0))
                    style_score += flake8_score
                    tools_used += 1
                    logger.debug(f"Flake8 analysis complete: {errors} issues found, score: {flake8_score:.2f}/10")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Flake8 analysis skipped: {e}")
                # Non aggiungere nulla allo score o ai tools usati
                
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
        """Ensure a datetime object is timezone-aware (UTC)."""
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
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
                    if punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il repository ha pochissima visibilità. Promuovilo attivamente attraverso blog post, social media e conferenze"
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Considera di promuovere il repository attraverso blog post o social media per aumentare la visibilità"
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Il repository ha una buona base di stelle. Mantieni l'engagement con la community per continuare la crescita"
                        )
                        
                elif nome_param == "forks":
                    valore = f"{pop_data['forks']} fork"
                    punteggio = self._normalize_score(pop_data['forks'], 0, 500, 0, 10)
                    
                    # More granular suggestion based on score
                    if punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochissimi fork. Incoraggia il riutilizzo del codice con esempi chiari e casi d'uso ben documentati"
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Migliora la documentazione e gli esempi per incoraggiare più fork e riutilizzo del codice"
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di fork. Considera di evidenziare i progetti che utilizzano il tuo codice"
                        )
                        
                elif nome_param == "watchers":
                    valore = f"{pop_data['watchers']} watchers"
                    punteggio = self._normalize_score(pop_data['watchers'], 0, 200, 0, 10)
                    
                    # More granular suggestion based on score
                    if punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochissimi osservatori. Comunica attivamente gli aggiornamenti e incoraggia gli utenti a seguire il repository"
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Mantieni gli utenti informati sugli aggiornamenti attraverso release notes dettagliate"
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di osservatori. Mantieni il loro interesse con aggiornamenti regolari"
                        )
                        
                elif nome_param == "contributori":
                    valore = f"{pop_data['contributori']} contributori"
                    punteggio = self._normalize_score(pop_data['contributori'], 0, 50, 0, 10)
                    
                    # More granular suggestion based on score
                    if punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochi contributori. Crea issue con 'good first issue' e 'help wanted' per incoraggiare la partecipazione"
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Crea una guida per i contributori e tag 'good first issue' per attrarre nuovi sviluppatori"
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Buon numero di contributori. Riconosci il loro lavoro e mantieni la community attiva"
                        )
                        
                elif nome_param == "dipendenti":
                    valore = f"{pop_data['dipendenti']} progetti dipendenti"
                    punteggio = self._normalize_score(pop_data['dipendenti'], 0, 100, 0, 10)
                    
                    # More granular suggestion based on score
                    if punteggio < 2:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Pochissimi progetti dipendenti. Pubblica su gestori di pacchetti e crea tutorial per facilitare l'adozione"
                        )
                    elif punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Considera di pubblicare il pacchetto su gestori di pacchetti come npm o PyPI per aumentarne l'adozione"
                        )
                    elif punteggio < 8:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Discreto numero di dipendenti. Mantieni compatibilità e comunica chiaramente le breaking changes"
                        )
                        
                elif nome_param == "engagement_rate":
                    valore = f"{self._check_engagement_rate():.2f}"
                    punteggio = self._check_engagement_rate()
                    
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
                        releases = self._get_cached_data(
                            "releases",
                            lambda: list(self.repo.get_releases()[:MAX_ITEMS_PER_REQUEST])
                        )
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
                                
                                # Stepped scoring based on recency
                                if days_since_last_commit <= 30:
                                    punteggio = 10.0
                                    # Suggestion: Keep up the good work (optional, maybe too verbose)
                                elif days_since_last_commit <= 90:
                                    punteggio = 8.0
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "L'attività di commit è buona, ma cerca di mantenerla più frequente (idealmente entro 30 giorni)."
                                    )
                                elif days_since_last_commit <= 180:
                                    punteggio = 6.0
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository non riceve commit da diversi mesi. Considera di riprendere lo sviluppo attivo."
                                    )
                                elif days_since_last_commit <= 365:
                                    punteggio = 3.0
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository sembra poco manutenuto (ultimo commit tra 6 e 12 mesi fa). Pianifica aggiornamenti o valuta l'archiviazione."
                                    )
                                else: # More than a year
                                    punteggio = 0.0
                                    self.results["suggerimenti"].setdefault(categoria, []).append(
                                        "Il repository è inattivo da oltre un anno. Considera di archiviarlo se non è più mantenuto."
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
                                    # Normalize: 0.5 commit/giorno = 5 punti, 2 commit/giorno = 10 punti
                                    punteggio = self._normalize_score(commits_per_day, 0, 2, 0, 10)
                                    
                                    if commits_per_day < 0.1:  # Meno di un commit ogni 10 giorni
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "La frequenza dei commit è molto bassa. Considera di aumentare l'attività di sviluppo"
                                        )
                                    elif commits_per_day < 0.3:  # Meno di un commit ogni 3 giorni
                                        self.results["suggerimenti"].setdefault(categoria, []).append(
                                            "Aumenta la frequenza dei commit per mantenere un sviluppo più costante"
                                        )
                                else:
                                    # Handle case where all commits are within the same day or less than 24h apart
                                    valore = f"{len(commits)} commit recenti (stesso giorno)"
                                    # Score based on number of commits if timeframe is too short
                                    punteggio = self._normalize_score(len(commits), 1, 10, 0, 10) 
                                    logger.debug("Commit troppo ravvicinati per calcolare frequenza giornaliera sensata.")
                            else:
                                valore = "Date commit non valide"
                                punteggio = 5 # Neutral score if dates are missing
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
                         punteggio = 1 # Low score for single commit
                    else: # No commits or empty list
                        valore = "Nessun commit recente"
                        punteggio = 0
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Non sono stati trovati commit recenti. Il repository potrebbe essere inattivo"
                        )
                elif nome_param == "stato_archivio":
                    valore = "Archiviato" if self.repo.archived else "Attivo"
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
            elif categoria == "qualita_codice":
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

                return valore, round(punteggio, 2), conta_punteggio

            # Community & Collaborazione
            elif categoria == "community_collaborazione":
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
            elif categoria == "testing_cicd":
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
                            for ci_type, patterns in ci_configs.items():
                                for pattern in patterns:
                                    # Handle both files and directories
                                    full_path = os.path.join(self.local_repo_path, pattern)
                                    
                                    # Check if it's a directory that should exist
                                    if pattern.endswith('/') or '.' not in os.path.basename(pattern):
                                        if os.path.isdir(full_path) and os.listdir(full_path):  # Directory exists and not empty
                                            ci_configs_found.append(ci_type)
                                            break
                                    # Check if it's a file that should exist
                                    elif os.path.isfile(full_path):
                                        ci_configs_found.append(ci_type)
                                        break
                                        
                                    # Special case for patterns with directories
                                    elif '/' in pattern:
                                        dir_path = os.path.dirname(full_path)
                                        # If the directory exists, check if the file exists
                                        if os.path.isdir(dir_path):
                                            if os.path.isfile(full_path):
                                                ci_configs_found.append(ci_type)
                                                break
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
                
                elif nome_param in ["test_coverage", "sicurezza_ci"]:
                    valore = "Analisi non disponibile"
                    punteggio = 5  # Valore neutro
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio

            # Setup & Usabilità
            elif categoria == "setup_usabilita":
                if nome_param == "facilita_setup":
                    # Improve the setup analysis with actual checks
                    valore = "Analisi in corso"
                    punteggio = 5  # Default neutral value
                    
                    setup_files = ["setup.py", "requirements.txt", "package.json", "Makefile", "Dockerfile", "docker-compose.yml"]
                    found_files = []
                    
                    try:
                        if self.local_repo_path:
                            # Check local repository
                            for root, _, files in os.walk(self.local_repo_path):
                                for file in files:
                                    if file.lower() in [s.lower() for s in setup_files]:
                                        found_files.append(file)
                        else:
                            # Use GitHub API
                            contents = self._get_cached_data(
                                "root_contents",
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            for item in contents:
                                if item.type == "file" and item.name.lower() in [s.lower() for s in setup_files]:
                                    found_files.append(item.name)
                        
                        if found_files:
                            setup_score = min(len(found_files) * 2.5, 10)  # Each setup file adds 2.5 points, max 10
                            valore = f"Setup files trovati: {', '.join(found_files)}"
                            punteggio = setup_score
                            
                            if punteggio < 5:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Aggiungi file come requirements.txt, setup.py o Dockerfile per facilitare l'installazione e l'esecuzione"
                                )
                        else:
                            valore = "Nessun file di setup rilevato"
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi file di setup come requirements.txt o setup.py per facilitare l'installazione"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nell'analisi dei file di setup: {e}")
                        valore = "Errore nell'analisi"
                        punteggio = 5
                
                elif nome_param == "configurabilita":
                    # Check for configuration files and options
                    valore = "Analisi in corso"
                    config_files = ["config.json", "config.yml", "config.yaml", ".env.example", "settings.py"]
                    found_configs = []
                    
                    try:
                        if self.local_repo_path:
                            for root, _, files in os.walk(self.local_repo_path):
                                for file in files:
                                    if file.lower() in [c.lower() for c in config_files]:
                                        found_configs.append(file)
                                        
                                    # Check Python files for argparse usage (configurability via command line)
                                    if file.endswith('.py'):
                                        try:
                                            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                                                content = f.read()
                                                if 'argparse' in content and 'ArgumentParser' in content:
                                                    found_configs.append('command-line arguments (via argparse)')
                                                    break
                                        except Exception:
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
                            
                            # Look for argparse in Python files - limited to reduce API calls
                            try:
                                main_py = next((item for item in contents if item.name == 'main.py' or item.name == self.repo_name.split('/')[-1] + '.py'), None)
                                if main_py:
                                    content = self.repo.get_contents(main_py.path).decoded_content.decode('utf-8')
                                    if 'argparse' in content and 'ArgumentParser' in content:
                                        found_configs.append('command-line arguments (via argparse)')
                            except Exception:
                                pass
                        
                        if found_configs:
                            config_score = min(len(found_configs) * 2.5, 10)
                            valore = f"Opzioni di configurazione trovate: {', '.join(found_configs)}"
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
            result = subprocess.run(
                ["bandit", "-r", effective_path, "-f", "json", "-q"],
                capture_output=True, text=True, timeout=120, check=False
            )

            if result.returncode in [0, 1] and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    issues = data.get("results", [])
                    metrics = data.get("metrics", {})
                    total_loc = metrics.get("_totals", {}).get("loc", 1)  # Avoid division by zero

                    severity_scores = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
                    for issue in issues:
                        severity = issue.get("issue_severity", "LOW")
                        if severity in severity_scores:
                            severity_scores[severity] += 1

                    weighted_issues = (severity_scores["HIGH"] * 3) + (severity_scores["MEDIUM"] * 2) + (severity_scores["LOW"] * 1)
                    issue_density = (weighted_issues / total_loc) * 1000 if total_loc > 0 else 0
                    score = self._normalize_score(issue_density, 20, 0, 0, 10)

                    logger.info(f"Bandit analysis: {len(issues)} issues found ({severity_scores['HIGH']}H, {severity_scores['MEDIUM']}M, {severity_scores['LOW']}L). Density: {issue_density:.2f}/kloc. Score: {score:.2f}")

                    # Clear previous security suggestions before adding new ones
                    self.results["suggerimenti"].setdefault("sicurezza", [])
                    
                    if severity_scores["HIGH"] > 0:
                        self.results["suggerimenti"]["sicurezza"].append(
                            f"Risolvi le {severity_scores['HIGH']} vulnerabilità ad alta severità identificate da Bandit."
                        )
                    if severity_scores["MEDIUM"] > 5:
                        self.results["suggerimenti"]["sicurezza"].append(
                            f"Rivedi le {severity_scores['MEDIUM']} vulnerabilità a media severità identificate da Bandit."
                        )
                    if len(issues) == 0:
                        # Add positive feedback if no issues found
                        self.results["suggerimenti"]["sicurezza"].append(
                            "Nessuna vulnerabilità rilevata da Bandit. Continua a mantenere questo standard."
                        )

                    return score
                except json.JSONDecodeError as json_e:
                    logger.error(f"Errore nel parsing dell'output JSON di Bandit: {json_e}\nOutput:\n{result.stdout[:500]}...")
                    return 2.0
            elif result.returncode > 1:
                logger.warning(f"Bandit ha restituito un codice di errore: {result.returncode}. Stderr: {result.stderr}")
                return 3.0
            else:
                logger.warning(f"Bandit non ha prodotto output o ha fallito silenziosamente (return code {result.returncode}).")
                return 4.0

        except subprocess.TimeoutExpired:
            logger.error("Timeout durante l'esecuzione di Bandit (superati 120s).")
            return 1.0
        except FileNotFoundError:
            logger.error("Comando 'bandit' non trovato. Assicurati che Bandit sia installato e nel PATH.")
            return 5.0
        except Exception as e:
            logger.error(f"Errore imprevisto durante l'esecuzione di Bandit: {e}", exc_info=True)
            return 0.0

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
        # Find common requirements files
        for root, _, files in os.walk(effective_path):
            for file in files:
                if file in ["requirements.txt", "requirements-dev.txt", "setup.py", "pyproject.toml"]:
                    # Prioritize requirements.txt if found
                    if file == "requirements.txt":
                         requirements_files.insert(0, os.path.join(root, file))
                    else:
                         requirements_files.append(os.path.join(root, file))
        
        if not requirements_files:
            logger.info("Nessun file di dipendenze (requirements.txt, setup.py, pyproject.toml) trovato.")
            return "Nessun file dipendenze", 8.0 # Good score if no deps declared

        # Analyze the first found requirements file (usually requirements.txt)
        req_file_to_scan = requirements_files[0]
        logger.info(f"Esecuzione di Safety su: {req_file_to_scan}")
        
        try:
            # Run safety using subprocess to capture output and handle errors
            # Use --json for structured output
            cmd = ["safety", "check", "-r", req_file_to_scan, "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)

            if result.returncode == 0 and result.stdout:
                 # Safety returns 0 even if vulnerabilities are found when using --json
                 try:
                     # Safety's JSON output is a list of lists/dicts, not a single JSON object
                     # We need to parse it carefully line by line or find the JSON part
                     # Let's assume the primary JSON output is the last line for simplicity
                     # More robust parsing might be needed for complex outputs.
                     json_output_str = result.stdout.strip().splitlines()[-1]
                     vulnerabilities = json.loads(json_output_str)
                     
                     # The structure might be [[vuln1], [vuln2], ...] or similar
                     # Let's count the number of vulnerability entries
                     num_vulnerabilities = 0
                     if isinstance(vulnerabilities, list):
                         # Count non-empty lists/dicts within the main list
                         num_vulnerabilities = sum(1 for item in vulnerabilities if item) 
                     
                     if num_vulnerabilities == 0:
                         logger.info("Safety non ha trovato vulnerabilità nelle dipendenze.")
                         return "Nessuna vulnerabilità trovata", 10.0
                     else:
                         logger.warning(f"Safety ha trovato {num_vulnerabilities} vulnerabilità nelle dipendenze.")
                         # Score inversely based on number of vulnerabilities
                         score = max(0.0, 10.0 - num_vulnerabilities) 
                         self.results["suggerimenti"].setdefault("sicurezza", []).append(
                             f"Aggiorna le dipendenze per risolvere le {num_vulnerabilities} vulnerabilità trovate da Safety."
                         )
                         return f"{num_vulnerabilities} vulnerabilità trovate", score
                 except json.JSONDecodeError:
                     logger.error(f"Errore nel parsing dell'output JSON di Safety: {result.stdout}")
                     return "Errore parsing Safety", 3.0
                 except IndexError:
                      logger.error(f"Output JSON di Safety vuoto o non trovato: {result.stdout}")
                      return "Output Safety vuoto", 4.0

            elif result.returncode != 0:
                 logger.warning(f"Safety ha restituito un codice di errore: {result.returncode}. Stderr: {result.stderr}")
                 # Check stderr for common errors like missing file
                 if "No such file or directory" in result.stderr:
                      logger.error(f"File dipendenze non trovato da Safety: {req_file_to_scan}")
                      return "File dipendenze non trovato", 2.0
                 return f"Errore Safety (codice {result.returncode})", 2.0
            else: # Return code 0 but no JSON output (shouldn't happen with --json)
                 logger.warning(f"Safety non ha prodotto output JSON atteso. Output: {result.stdout}")
                 return "Output Safety inatteso", 3.0

        except subprocess.TimeoutExpired:
            logger.error("Timeout durante l'esecuzione di Safety (superati 90s).")
            return "Timeout Safety", 1.0
        except FileNotFoundError:
             logger.error("Comando 'safety' non trovato. Assicurati che Safety sia installato e nel PATH.")
             return "Richiede 'safety'", 5.0 # Neutral score if tool not found
        except Exception as e:
            logger.error(f"Errore imprevisto durante l'esecuzione di Safety: {e}", exc_info=True)
            return "Errore Safety imprevisto", 0.0

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
            engagement_rate = (stars + forks + watchers) / months_active
            return self._normalize_score(engagement_rate, 0, 50, 0, 10)
        except Exception as e:
            logger.error(f"Errore nel calcolo del tasso di engagement: {e}")
            return 0.0

    def _check_dockerfile_presence(self) -> bool:
        """Verifica la presenza di un Dockerfile nel repository."""
        try:
            contents = self.repo.get_contents("")
            return any(file.name.lower() == "dockerfile" for file in contents)
        except Exception as e:
            logger.warning(f"Errore nel controllo del Dockerfile: {e}")
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
                    return 0.0  # Discussions not available or not supported by PyGithub version
            
            if not has_discussions:
                return 0.0  # Discussions not enabled
            
            try:
                discussions = self.repo.get_discussions()
                recent_discussions = []
                for d in discussions[:10]:  # Limit to avoid excessive API calls
                    if (datetime.datetime.now(datetime.timezone.utc) - self._ensure_tz_aware(d.created_at)).days <= 30:
                        recent_discussions.append(d)
                
                total_comments = sum(getattr(d, "comments_count", 0) for d in recent_discussions)
                
                # Normalize score: more discussions and comments => higher score
                score = self._normalize_score(len(recent_discussions) + total_comments, 0, 50, 0, 10)
                return score
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