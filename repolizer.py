#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Repolizer - Analizzatore di Repository GitHub

Questo script analizza repository GitHub in base a diversi parametri di qualità,
attività, manutenzione e impatto, calcolando punteggi ponderati.
"""

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

# Decoratore per gestire i timeout
def timeout_handler(func):
    """Decorator per gestire i timeout delle chiamate API."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TimeoutError as e:
            print(f"Timeout durante l'esecuzione di {func.__name__}: {e}")
            return None, 0, False
        except Exception as e:
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
            return self.github.get_repo(self.repo_name)
        except GithubException as e:
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
                print(f"Errore nel recupero dei dati per {key}: {e}")
                return None
        return self._cache[key]

    def _check_complexity(self, path: str = ".") -> float:
        """Esegue una scansione con Radon per calcolare la complessità media."""
        try:
            effective_path = self.local_repo_path if self.local_repo_path else path
            
            # Modificato per gestire meglio i possibili errori di Radon
            try:
                # Inizializza la variabile complexities qui per garantire che esista sempre
                complexities = []
                
                # Utilizza una directory più specifica se disponibile
                if self.local_repo_path:
                    # Trova tutti i file Python nella directory
                    python_files = []
                    for root, _, files in os.walk(effective_path):
                        python_files.extend([os.path.join(root, f) for f in files if f.endswith('.py')])
                    
                    # Se ci sono file Python, analizza ciascun file separatamente
                    if python_files:
                        for py_file in python_files[:20]:  # Limita a 20 file per evitare timeout
                            try:
                                cmd_result = subprocess.run(
                                    ["radon", "cc", py_file, "-s", "-a"], 
                                    capture_output=True, 
                                    text=True, 
                                    timeout=10
                                )
                                if cmd_result.returncode == 0 and cmd_result.stdout.strip():
                                    for line in cmd_result.stdout.splitlines():
                                        match = re.search(r"\((\d+)\)$", line.strip())
                                        if match:
                                            complexities.append(int(match.group(1)))
                            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                                continue  # Salta il file in caso di errore
                    else:
                        # Fallback all'analisi semplice della directory corrente
                        cmd_result = subprocess.run(
                            ["radon", "cc", ".", "-s", "--average-only"], 
                            capture_output=True, 
                            text=True, 
                            timeout=30
                        )
                        if cmd_result.returncode == 0:
                            # Cerca solo il valore medio
                            match = re.search(r"Average complexity: (\d+\.\d+)", cmd_result.stdout)
                            if match:
                                return float(match.group(1))
                else:
                    # Se non abbiamo clonato, prova ad analizzare il codice nella directory corrente
                    cmd_result = subprocess.run(
                        ["radon", "cc", ".", "-s", "--average-only"], 
                        capture_output=True, 
                        text=True, 
                        timeout=30
                    )
                    if cmd_result.returncode == 0:
                        match = re.search(r"Average complexity: (\d+\.\d+)", cmd_result.stdout)
                        if match:
                            return float(match.group(1))
                
                # Se abbiamo raccolto dati di complessità dai file individuali
                if complexities:
                    return sum(complexities) / len(complexities)
                
            except FileNotFoundError:
                logger.warning("Radon non trovato. Assicurati che sia installato.")
                return 5.0  # Valore neutro
            except Exception as e:
                logger.warning(f"Errore nell'esecuzione di radon: {e}")
                if hasattr(e, 'output') and e.output:
                    logger.debug(f"Output di radon: {e.output}")
                return 5.0  # Valore neutro
                
        except Exception as e:
            logger.error(f"Errore imprevisto durante l'analisi della complessità: {e}")
            return 5.0  # Valore di default neutro in caso di errore
            
        # Se non siamo riusciti a calcolare la complessità
        return 5.0  # Valore di default neutro

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
                pass
                
            # Calcola punteggio medio se almeno uno strumento è stato usato
            if tools_used > 0:
                return style_score / tools_used
            else:
                logger.warning("No style analysis tools available.")
                return 5.0  # Valore neutro se nessuno strumento è disponibile
        except Exception as e:
            logger.error(f"Style analysis error: {e}", exc_info=True)
            return 0.0

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
                pass
            
            # 2. Radon per complessità ciclomatica
            try:
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
                pass

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
                pass
            
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
                pass
                                
            # Calcola il punteggio medio se almeno uno strumento è stato usato
            if tools_used > 0:
                return smell_score / tools_used
            else:
                logger.warning("No code smell analysis tools available.")
                return 5.0  # Valore neutro se nessuno strumento è disponibile
                
        except Exception as e:
            logger.error(f"Code smell analysis error: {e}", exc_info=True)
            return 0.0

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
            return min(ratio * 20.0, 10.0)  # max 10 points if heavily commented
        except Exception:
            return 0.0

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
                    if issue.closed_at and issue.created_at:
                        # Bug fix: Ensure dates have timezone info for comparison
                        closed_at = issue.closed_at if issue.closed_at.tzinfo else issue.closed_at.replace(tzinfo=datetime.timezone.utc)
                        created_at = issue.created_at if issue.created_at.tzinfo else issue.created_at.replace(tzinfo=datetime.timezone.utc)
                        delta = (closed_at - created_at).days
                        if delta >= 0:
                            closed_times.append(delta)
                
                # Calcola il tempo di prima risposta se ci sono commenti
                try:
                    comments = list(issue.get_comments())
                    if comments and issue.user and comments[0].user:
                        # Verifica che la prima risposta non sia dell'autore dell'issue
                        if issue.user.id != comments[0].user.id:
                            # Bug fix: Ensure dates have timezone info
                            comment_date = comments[0].created_at if comments[0].created_at.tzinfo else comments[0].created_at.replace(tzinfo=datetime.timezone.utc)
                            issue_date = issue.created_at if issue.created_at.tzinfo else issue.created_at.replace(tzinfo=datetime.timezone.utc)
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
            if pr.merged and pr.created_at and pr.closed_at:
                merged_pr += 1
                # Bug fix: Ensure dates have timezone info
                closed_at = pr.closed_at if pr.closed_at.tzinfo else pr.closed_at.replace(tzinfo=datetime.timezone.utc)
                created_at = pr.created_at if pr.created_at.tzinfo else pr.created_at.replace(tzinfo=datetime.timezone.utc)
                closed_times.append((closed_at - created_at).days)
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
                    if tag.commit and tag.commit.commit and tag.commit.commit.author:
                        tag_date = tag.commit.commit.author.date
                        if tag_date:
                            # Bug fix: Ensure date has timezone info
                            if not tag_date.tzinfo:
                                tag_date = tag_date.replace(tzinfo=datetime.timezone.utc)
                            tag_dates.append((tag.name, tag_date))
                except Exception as e:
                    logger.warning(f"Impossibile ottenere la data per il tag {tag.name}: {e}")
                    continue
            
            # Ordina le date cronologicamente (dalla più vecchia alla più recente)
            tag_dates.sort(key=lambda x: x[1])
            
            # Calcola le differenze di giorni tra tag consecutivi
            date_diffs = []
            for i in range(len(tag_dates) - 1):
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
            # Ottieni il conteggio dei contributori
            contributors = list(self.repo.get_contributors())
            repo_data["contributori"] = len(contributors)
        except Exception as e:
            print(f"Errore nel recupero dei contributori: {e}")
        
        try:
            # Cerca repository che dipendono da questo (GitHub API)
            used_by_url = f"https://github.com/{self.repo_name}/network/dependents"
            repo_data["dipendenti_url"] = used_by_url
            
            # Semplice approssimazione usando search API
            dependents = self.github.search_repositories(f"depends on:{self.repo_name}")
            repo_data["dipendenti"] = dependents.totalCount
        except Exception as e:
            print(f"Errore nel recupero dei dipendenti: {e}")
        
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
                        "punteggio": punteggio if punteggio is not None else 0,
                        "peso": info_param.get("peso", 1),
                        "descrizione": info_param.get("descrizione", ""),
                        "conta_punteggio": conta_punteggio
                    }
                except Exception as e:
                    self.console.print(f"[red]Errore nell'analisi del parametro {nome_param}: {e}[/red]")
                    self.results["dettagli"][categoria][nome_param] = {
                        "valore": "Errore",
                        "punteggio": 0,
                        "peso": info_param.get("peso", 1),
                        "descrizione": info_param.get("descrizione", ""),
                        "conta_punteggio": False
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
            aree_problematiche = [categoria for categoria, punteggio in self.results["punteggi"].items() 
                                if punteggio < 4]
            if aree_problematiche:
                valutazione += "\n\nAree di miglioramento: " + ", ".join(aree_problematiche)
                
            self.results["valutazione_qualitativa"] = valutazione
        
        # Aggiorna lo storico dei punteggi
        self._update_history()
        
        security_score = self._check_security(self.local_repo_path if self.local_repo_path else ".")
        print(f"Security score (Bandit): {security_score:.2f}")
        
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
        
        # Assicurati che il dizionario suggerimenti esista nei risultati
        if "suggerimenti" not in self.results:
            self.results["suggerimenti"] = {}
            
        # Inizializza i suggerimenti per questa categoria se non esistono
        if categoria not in self.results["suggerimenti"]:
            self.results["suggerimenti"][categoria] = []
            
        try:
            # Popolarità & Impatto
            if categoria == "popolarita_impatto":
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
                    
                    if punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Considera di promuovere il repository attraverso blog post o social media per aumentare la visibilità"
                        )
                        
                elif nome_param == "forks":
                    valore = f"{pop_data['forks']} fork"
                    punteggio = self._normalize_score(pop_data['forks'], 0, 500, 0, 10)
                    
                    if punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Migliora la documentazione e gli esempi per incoraggiare più fork e riutilizzo del codice"
                        )
                        
                elif nome_param == "watchers":
                    valore = f"{pop_data['watchers']} watchers"
                    punteggio = self._normalize_score(pop_data['watchers'], 0, 200, 0, 10)
                    
                    if punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Mantieni gli utenti informati sugli aggiornamenti attraverso release notes dettagliate"
                        )
                        
                elif nome_param == "contributori":
                    valore = f"{pop_data['contributori']} contributori"
                    punteggio = self._normalize_score(pop_data['contributori'], 0, 50, 0, 10)
                    
                    if punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Crea una guida per i contributori e tag 'good first issue' per attrarre nuovi sviluppatori"
                        )
                        
                elif nome_param == "dipendenti":
                    valore = f"{pop_data['dipendenti']} progetti dipendenti"
                    punteggio = self._normalize_score(pop_data['dipendenti'], 0, 100, 0, 10)
                    
                    if punteggio < 5:
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Considera di pubblicare il pacchetto su gestori di pacchetti come npm o PyPI per aumentarne l'adozione"
                        )
                        
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                    conta_punteggio = False
                
                return valore, round(punteggio, 2), conta_punteggio
            
            # Attività & Manutenzione
            elif categoria == "attivita_manutenzione":
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
                                if r.created_at:
                                    # Add timezone info if missing
                                    if not r.created_at.tzinfo:
                                        release_date = r.created_at.replace(tzinfo=datetime.timezone.utc)
                                    else:
                                        release_date = r.created_at
                                        
                                    if release_date > year_ago:
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
                        lambda: self.repo.get_commits()[0] if self.repo.get_commits().totalCount > 0 else None
                    )
                    
                    if last_commit:
                        try:
                            last_commit_date = last_commit.commit.author.date if last_commit.commit and last_commit.commit.author else None
                            if last_commit_date:
                                # Assicuriamoci che la data abbia timezone
                                if not last_commit_date.tzinfo:
                                    last_commit_date = last_commit_date.replace(tzinfo=datetime.timezone.utc)
                                    
                                now = datetime.datetime.now(datetime.timezone.utc)
                                days_since_last_commit = (now - last_commit_date).days
                                # Assicuriamoci che il valore sia positivo
                                days_since_last_commit = max(0, days_since_last_commit)
                                valore = days_since_last_commit
                                punteggio = self._normalize_score(days_since_last_commit, 365, 0, 0, 10, inverse=True)  # Più recente è meglio
                            else:
                                valore = "Data non disponibile"
                                punteggio = 5
                        except Exception as e:
                            print(f"Errore nel calcolo della data dell'ultimo commit: {e}")
                            valore = "Errore data"
                            punteggio = 5  # Valore neutro in caso di errore
                    else:
                        valore = "Non disponibile"
                        punteggio = 0
                elif nome_param == "frequenza_commit":
                    # Usa la cache per ottenere i commit
                    commits = self._get_cached_data(
                        "recent_commits",
                        lambda: list(self.repo.get_commits()[:100])
                    )
                    
                    if commits and len(commits) >= 2:
                        try:
                            # Assicuriamoci che le date abbiano timezone
                            first_date = commits[-1].commit.author.date
                            last_date = commits[0].commit.author.date
                            
                            # Aggiungi timezone se mancante
                            if not first_date.tzinfo:
                                first_date = first_date.replace(tzinfo=datetime.timezone.utc)
                            if not last_date.tzinfo:
                                last_date = last_date.replace(tzinfo=datetime.timezone.utc)
                                
                            # Assicuriamoci che last_date sia più recente di first_date
                            if first_date > last_date:
                                first_date, last_date = last_date, first_date
                            
                            # Calcola la frequenza media dei commit
                            days_diff = (last_date - first_date).days
                            if days_diff > 0:
                                commits_per_day = len(commits) / days_diff
                                valore = round(commits_per_day, 2)
                                # Normalizza: 0.5 commit/giorno = 5 punti, 2 commit/giorno = 10 punti
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
                                valore = len(commits)
                                punteggio = self._normalize_score(len(commits), 1, 10, 0, 10)
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "I commit sono troppo ravvicinati. Considera di distribuire meglio le modifiche nel tempo"
                                )
                        except Exception as e:
                            print(f"Errore nel calcolo della frequenza dei commit: {e}")
                            valore = "Errore calcolo"
                            punteggio = 5
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Si è verificato un errore nel calcolo della frequenza dei commit"
                            )
                    else:
                        valore = 0
                        punteggio = 0
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Non sono stati trovati commit recenti. Il repository potrebbe essere inattivo"
                        )
                elif nome_param == "stato_archivio":
                    valore = self.repo.archived
                    punteggio = 0 if valore else 10  # 0 se archiviato, 10 se attivo
                elif nome_param == "distribuzione_contributi":
                    # Implementazione semplificata - analisi più dettagliata richiederebbe più chiamate API
                    valore = "Analisi non disponibile"
                    punteggio = 5  # Valore neutro
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

                return valore, round(punteggio, 2), conta_punteggio

            # Sicurezza
            elif categoria == "sicurezza":
                if nome_param == "file_security":
                    # Miglioriamo la verifica della presenza di SECURITY.md e altri file di sicurezza
                    valore = False
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
                        
                        if self.local_repo_path:
                            # Controlla nel filesystem locale
                            for root, _, files in os.walk(self.local_repo_path):
                                for filename in files:
                                    if any(filename.lower() == pattern.lower() for pattern in security_file_patterns):
                                        security_files_found.append(filename)
                                        break
                        else:
                            # Controlla prima la root tramite API
                            contents = self._get_cached_data(
                                "root_contents", 
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            for item in contents:
                                if item.type == "file" and any(item.name.lower() == pattern.lower() for pattern in security_file_patterns):
                                    security_files_found.append(item.name)
                            
                            # Controlla anche nella directory .github
                            try:
                                github_dir = None
                                for item in contents:
                                    if item.path.lower() == ".github" and item.type == "dir":
                                        github_dir = item
                                        break
                                        
                                if github_dir:
                                    try:
                                        github_contents = self._get_cached_data(
                                            "github_dir_contents",
                                            lambda: list(self.repo.get_contents(".github"))
                                        )
                                        
                                        for item in github_contents:
                                            if item.type == "file" and any(item.name.lower() == pattern.lower() for pattern in security_file_patterns):
                                                security_files_found.append(item.name)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        
                        if security_files_found:
                            valore = True
                            punteggio = 10
                        else:
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
                        special_files = [
                            ".github/dependabot.yml",
                            ".github/dependabot.yaml",
                            ".github/workflows/codeql-analysis.yml",  # GitHub code scanning
                            ".github/CODEOWNERS",                      # CODEOWNERS file
                        ]
                        
                        if self.local_repo_path:
                            # Cerca i file nel filesystem
                            for special_file in special_files:
                                path_parts = special_file.split('/')
                                curr_path = self.local_repo_path
                                
                                # Navigate through the directory structure
                                valid_path = True
                                # Bug fix: Correctly iterate through path parts
                                for part in path_parts[:-1]:
                                    curr_path = os.path.join(curr_path, part)
                                    if not os.path.exists(curr_path) or not os.path.isdir(curr_path):
                                        valid_path = False
                                        break
                                
                                if valid_path:
                                    final_path = os.path.join(curr_path, path_parts[-1])
                                    if os.path.exists(final_path) and os.path.isfile(final_path):
                                        security_features.append(os.path.basename(special_file))
                        else:
                            # Cerca tramite API GitHub
                            # Controlla se esiste .github directory
                            contents = self._get_cached_data(
                                "root_contents", 
                                lambda: list(self.repo.get_contents(""))
                            )
                            
                            github_dir = None
                            for item in contents:
                                if item.path.lower() == ".github" and item.type == "dir":
                                    github_dir = item
                                    break
                            
                            if github_dir:
                                try:
                                    github_contents = self._get_cached_data(
                                        "github_dir_contents",
                                        lambda: list(self.repo.get_contents(".github"))
                                    )
                                    
                                    # Cerca Dependabot e CODEOWNERS
                                    for item in github_contents:
                                        if item.type == "file" and (
                                            item.name.lower() in ["dependabot.yml", "dependabot.yaml", "codeowners"]):
                                            security_features.append(item.name)
                                    
                                    # Cerca cartella workflows per azioni di sicurezza
                                    workflows_dir = None
                                    for item in github_contents:
                                        if item.path.lower() == ".github/workflows" and item.type == "dir":
                                            workflows_dir = item
                                            break
                                            
                                    if workflows_dir:
                                        try:
                                            workflows_contents = self._get_cached_data(
                                                "workflows_dir_contents",
                                                lambda: list(self.repo.get_contents(".github/workflows"))
                                            )
                                            
                                            for item in workflows_contents:
                                                if item.type == "file" and "codeql" in item.name.lower():
                                                    security_features.append("CodeQL scan")
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        
                        # Valuta i risultati
                        if security_features:
                            valore = ", ".join(security_features)
                            punteggio = min(len(security_features) * 3, 10)  # Più funzionalità, punteggio più alto (max 10)
                            
                        if punteggio < 5:
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Attiva le funzioni di sicurezza di GitHub come Dependabot, CodeQL scanning e CODEOWNERS"
                            )
                    except Exception as e:
                        logger.warning(f"Errore nella verifica delle funzionalità di sicurezza: {e}")
                        valore = "Errore verifica"
                        punteggio = 0
                
                elif nome_param == "dipendenze_aggiornate":
                    valore = "Analisi non disponibile"
                    punteggio = 5  # Valore neutro
                else:
                    valore = "Non analizzato"
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
                                        test_files_found.append(os.path.join(os.path.relpath(root, self.local_repo_path), dir_name))
                                
                                # Cerca file di test
                                for file_name in files:
                                    if (any(pattern in file_name.lower() for pattern in test_file_patterns) or 
                                        file_name.lower().startswith(("test", "spec"))):
                                        if file_name.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".php")):
                                            test_files_found.append(os.path.join(os.path.relpath(root, self.local_repo_path), file_name))
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
                        
                        # File YAML comuni che potrebbero contenere configurazioni CI/CD
                        yaml_ci_keywords = [
                            "ci:", "cd:", "pipeline:", "build:", "test:", "deploy:",
                            "stages:", "jobs:", "matrix:", "runner", "workflow"
                        ]
                        
                        if self.local_repo_path:
                            # Controlla ogni possibile configurazione CI
                            for ci_type, patterns in ci_configs.items():
                                for pattern in patterns:
                                    path_parts = pattern.split('/')
                                    curr_path = self.local_repo_path
                                    
                                    # Navigate through the directory structure
                                    valid_path = True
                                    # Bug fix: Correctly iterate through path parts without unpacking
                                    for i in range(len(path_parts) - 1):
                                        part = path_parts[i]
                                        curr_path = os.path.join(curr_path, part)
                                        if not os.path.exists(curr_path) or not os.path.isdir(curr_path):
                                            valid_path = False
                                            break
                                    
                                    # Check if it's a file or directory we're looking for
                                    if valid_path:
                                        if '.' in path_parts[-1]:  # Probably a file
                                            final_path = os.path.join(curr_path, path_parts[-1])
                                            if os.path.exists(final_path) and os.path.isfile(final_path):
                                                ci_configs_found.append(ci_type)
                                                break
                                        else:  # Directory
                                            final_path = os.path.join(curr_path, path_parts[-1])
                                            if os.path.exists(final_path) and os.path.isdir(final_path):
                                                # For directories like .github/workflows, check if they contain any files
                                                if os.listdir(final_path):
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
                        logger.warning(f"Errore nel controllo CI/CD: {e}")
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
            return "Errore", 0, False

    def _calculate_scores(self):
        """Calcola i punteggi per ogni categoria e il punteggio totale."""
        for categoria, parametri in self.results["dettagli"].items():
            punteggio_categoria = 0
            peso_totale = 0
            for nome_param, info_param in parametri.items():
                if info_param["conta_punteggio"]:
                    punteggio_categoria += info_param["punteggio"] * info_param["peso"]
                    peso_totale += info_param["peso"]
            if peso_totale > 0:
                self.results["punteggi"][categoria] = round(punteggio_categoria / peso_totale, 2)
            else:
                self.results["punteggi"][categoria] = 0

    def _display_scores_terminal(self):
        """Visualizza i punteggi nel terminale."""
        table = Table(title="Punteggi delle Categorie")
        table.add_column("Categoria", justify="left", style="cyan", no_wrap=True)
        table.add_column("Punteggio", justify="right", style="magenta")

        for categoria, punteggio in self.results["punteggi"].items():
            table.add_row(categoria, str(punteggio))

        self.console.print(table)

    def _update_history(self):
        """Aggiorna lo storico dei punteggi nel file di configurazione."""
        try:
            with open(self.config_file, "r+", encoding="utf-8") as f:
                config_data = json.load(f)
                if "storico" not in config_data:
                    config_data["storico"] = []
                config_data["storico"].append({
                    "data_analisi": self.results["data_analisi"],
                    "punteggio_totale": self.results["punteggio_totale"],
                    "punteggi": self.results["punteggi"]
                })
                f.seek(0)
                json.dump(config_data, f, indent=4)
                f.truncate()
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento dello storico: {e}", exc_info=True)

    def _check_security(self, path: str = ".") -> float:
        """Esegue una scansione di sicurezza con Bandit (se disponibile)."""
        if not bandit:
            logger.warning("Bandit non è installato. Salta l'analisi di sicurezza.")
            return 5.0  # Valore neutro se Bandit non è disponibile

        try:
            effective_path = self.local_repo_path if self.local_repo_path else path
            result = subprocess.run(["bandit", "-r", effective_path, "-f", "json"], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                issues = data.get("results", [])
                if issues:
                    # Più problemi di sicurezza => punteggio più basso
                    return max(0.0, 10.0 - (len(issues) / 10.0))
                return 10.0  # Nessun problema rilevato
            else:
                logger.warning(f"Bandit ha restituito un codice di errore: {result.returncode}")
                return 5.0  # Valore neutro in caso di errore
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error(f"Errore durante l'esecuzione di Bandit: {e}", exc_info=True)
            return 5.0  # Valore neutro in caso di errore

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analizzatore di repository GitHub")
    parser.add_argument("repository", help="Nome del repository nel formato 'username/repository'")
    parser.add_argument("--clone", action="store_true", help="Clona il repository localmente per analisi più approfondite")
    args = parser.parse_args()

    with RepoAnalyzer(args.repository, clone_repo=args.clone) as analyzer:
        results = analyzer.analyze()
        print(json.dumps(results, indent=4, ensure_ascii=False))
        generate_html_report(results)