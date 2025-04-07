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
from typing import Dict, List, Any, Tuple, Optional
import subprocess
import re
import tempfile
import shutil

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

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Configurazione
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CONFIG_FILE = "config.json"

# Costanti per la gestione delle API
MAX_ITEMS_PER_REQUEST = 100  # Numero massimo di elementi per richiesta API


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
            output = subprocess.check_output(["radon", "cc", effective_path, "-s", "-A"], stderr=subprocess.STDOUT).decode("utf-8")
            complexities = []
            for line in output.splitlines():
                match = re.search(r"\((\d+)\)$", line.strip())
                if match:
                    complexities.append(int(match.group(1)))
            if complexities:
                return sum(complexities) / len(complexities)
        except FileNotFoundError:
            print("Radon non trovato. Assicurati che sia installato.")
        except Exception:
            pass
        return 0.0

    def _check_style(self, path: str = ".") -> float:
        """Esegue una scansione con flake8 per valutare l'aderenza allo stile (meno errori => punteggio più alto)."""
        try:
            effective_path = self.local_repo_path if self.local_repo_path else path
            process = subprocess.run(["flake8", effective_path], capture_output=True, text=True)
            # Se flake8 restituisce un codice di errore > 1, flake8 potrebbe essere fallito del tutto
            if process.returncode > 1:
                return 0.0
            lines = [l for l in process.stdout.splitlines() if l.strip()]
            errors = len(lines)
            # Più errori -> punteggio più basso
            return max(0.0, 10.0 - (errors / 5.0))
        except FileNotFoundError:
            print("Flake8 non trovato. Assicurati che sia installato.")
        except Exception:
            return 0.0

    def _check_code_smells(self, path: str = ".") -> float:
        """Riutilizza flake8 come indicatore di 'code smells'. Punteggio più alto con meno segnalazioni."""
        try:
            effective_path = self.local_repo_path if self.local_repo_path else path
            process = subprocess.run(["flake8", effective_path], capture_output=True, text=True)
            # Eventuali errori interni a flake8
            if process.returncode > 1:
                return 0.0
            lines = [l for l in process.stdout.splitlines() if l.strip()]
            smells = len(lines)
            # Più segnalazioni -> punteggio più basso
            return max(0.0, 10.0 - (smells / 10.0))
        except FileNotFoundError:
            print("Flake8 non trovato. Assicurati che sia installato.")
        except Exception:
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
        """Ottiene dati su issues aperte/chiuse e calcola i tempi medi di chiusura."""
        if "issues_data" in self._cache:
            return self._cache["issues_data"]
        issues = self.repo.get_issues(state="all")
        closed_times = []
        for issue in issues:
            if issue.closed_at and issue.created_at:
                delta = (issue.closed_at - issue.created_at).days
                if delta >= 0:
                    closed_times.append(delta)
        self._cache["issues_data"] = closed_times
        return closed_times

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
                closed_times.append((pr.closed_at - pr.created_at).days)
        self._cache["pr_data"] = {
            "total": total_pr,
            "merged": merged_pr,
            "merged_times": closed_times
        }
        return self._cache["pr_data"]

    def _fetch_tags_data(self):
        """Ottiene la frequenza approssimativa tra i tag (in giorni), se presenti."""
        if "tags_data" in self._cache:
            return self._cache["tags_data"]
        tags = list(self.repo.get_tags())
        if len(tags) < 2:
            self._cache["tags_data"] = 0.0
            return 0.0
        date_diffs = []
        for i in range(len(tags) - 1):
            t1 = tags[i].commit.commit.author.date
            t2 = tags[i+1].commit.commit.author.date
            date_diffs.append(abs((t2 - t1).days))
        avg_days = sum(date_diffs)/len(date_diffs) if date_diffs else 0.0
        self._cache["tags_data"] = avg_days
        return avg_days

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
        except:
            pass
        self._cache["doc_files_data"] = data
        return data

    def _fetch_community_data(self):
        if "community_data" in self._cache:
            return self._cache["community_data"]
        data = {
            "discussions_enabled": False,
            "templates_enabled": False,
            "tono_costruttivita": 5,  # Placeholder
            "label_usage": False
        }
        try:
            # Verifica se Discussions è abilitato
            # Nota: Alcune versioni di PyGithub potrebbero non supportare `has_discussions`
            # Qui assumiamo bozza, come fallback: controlliamo se esiste almeno una Discussion
            discussions = self.repo.get_discussions()
            if discussions.totalCount > 0:
                data["discussions_enabled"] = True
        except:
            pass

        try:
            # Controllo file in .github/ISSUE_TEMPLATE e PULL_REQUEST_TEMPLATE
            contents = self.repo.get_contents(".github")
            template_files = [c.name.lower() for c in contents]
            if any("template" in fn for fn in template_files):
                data["templates_enabled"] = True
        except:
            pass

        try:
            # Controlla se c'è almeno un label usato in qualche issue
            issues = self.repo.get_issues(state="all")
            for issue in issues:
                if issue.labels:
                    data["label_usage"] = True
                    break
        except:
            pass

        # "tono_costruttivita" rimane un placeholder
        self._cache["community_data"] = data
        return data

    def analyze(self) -> Dict:
        """Analizza il repository in base ai parametri configurati.

        Returns:
            Dizionario con i risultati dell'analisi
        """
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
            # Utilizziamo un approccio più compatibile per il timeout
            import signal
            import platform
            
            # Imposta un timeout solo su sistemi che supportano SIGALRM (non Windows)
            timeout_enabled = platform.system() != "Windows"
            if timeout_enabled:
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"L'analisi del parametro {nome_param} ha impiegato troppo tempo")
                
                # Imposta un timeout di 30 secondi per l'analisi di ogni parametro
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)
                
            # Popolarità & Impatto
            if categoria == "popolarita_impatto":
                pop_data = self._fetch_popolarita_data()
                if nome_param == "stelle":
                    valore = f"{pop_data['stars']} stelle"
                    punteggio = self._normalize_score(pop_data['stars'], 0, 1000, 0, 10)
                    
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
                        releases = self._get_cached_data(
                            "releases",
                            lambda: list(self.repo.get_releases()[:MAX_ITEMS_PER_REQUEST])
                        )
                        if releases:
                            now = datetime.datetime.now(datetime.timezone.utc)
                            year_ago = now - datetime.timedelta(days=365)
                            recent_releases = [r for r in releases if r.created_at > year_ago]
                            valore = len(recent_releases)
                            punteggio = self._normalize_score(valore, 0, 12, 0, 10)  # Idealmente una release al mese
                            
                            if valore == 0:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Non ci sono release negli ultimi 12 mesi. Considera di creare release regolari"
                                )
                            elif valore < 4:
                                self.results["suggerimenti"].setdefault(categoria, []).append(
                                    "Aumenta la frequenza delle release per fornire aggiornamenti più regolari"
                                )
                        else:
                            valore = 0
                            punteggio = 0
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Non sono state trovate release. Considera di utilizzare il sistema di release di GitHub"
                            )
                    except Exception as e:
                        print(f"Errore nell'analisi delle release: {e}")
                        valore = "Errore analisi"
                        punteggio = 0
                        self.results["suggerimenti"].setdefault(categoria, []).append(
                            "Si è verificato un errore nell'analisi delle release"
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
                            last_commit_date = last_commit.commit.author.date
                            # Assicuriamoci che la data abbia timezone
                            if not last_commit_date.tzinfo:
                                last_commit_date = last_commit_date.replace(tzinfo=datetime.timezone.utc)
                                
                            now = datetime.datetime.now(datetime.timezone.utc)
                            days_since_last_commit = (now - last_commit_date).days
                            # Assicuriamoci che il valore sia positivo
                            days_since_last_commit = max(0, days_since_last_commit)
                            valore = days_since_last_commit
                            punteggio = self._normalize_score(days_since_last_commit, 365, 0, 0, 10, inverse=True)  # Più recente è meglio
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
                    closed_times = self._fetch_issues_data()
                    if closed_times:
                        valore = f"Tempo medio chiusura issues: {round(sum(closed_times)/len(closed_times), 1)} giorni"
                        punteggio = max(0.0, 10.0 - ((sum(closed_times)/len(closed_times)) / 10.0))
                    else:
                        valore = "Nessuna issue chiusa"
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
                elif nome_param == "release_tag_frequenza":
                    avg_days = self._fetch_tags_data()
                    if avg_days > 0:
                        valore = f"Media giorni tra tag: {round(avg_days, 1)}"
                        # Meno giorni tra i tag => punteggio più alto
                        punteggio = max(0.0, 10.0 - (avg_days / 30.0))
                    else:
                        valore = "Nessun tag/release trovata"
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
                elif nome_param == "issue_pr_templates":
                    valore = "Presenti" if com_data["templates_enabled"] else "Non disponibili"
                    punteggio = 10 if com_data["templates_enabled"] else 5
                elif nome_param == "tono_costruttivita":
                    valore = "Analisi placeholder"
                    punteggio = com_data["tono_costruttivita"]  # Esempio: 5
                elif nome_param == "uso_label_issues":
                    valore = "Labels in uso" if com_data["label_usage"] else "Nessun label rilevato"
                    punteggio = 10 if com_data["label_usage"] else 5

                return valore, round(punteggio, 2), conta_punteggio

            # Sicurezza
            elif categoria == "sicurezza":
                if nome_param == "file_security":
                    # Verifichiamo la presenza di SECURITY.md
                    valore = False
                    punteggio = 0
                    
                    try:
                        contents = self.repo.get_contents("")
                        files = [f.name.upper() for f in contents if f.type == "file"]
                        
                        if "SECURITY.md".upper() in files:
                            valore = True
                            punteggio = 10
                        else:
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi un file SECURITY.md per descrivere la policy di sicurezza"
                            )
                    except Exception:
                        pass
                elif nome_param in ["github_security_features", "dipendenze_aggiornate"]:
                    valore = "Analisi non disponibile"
                    punteggio = 5  # Valore neutro
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio

            # Testing & CI/CD
            elif categoria == "testing_cicd":
                if nome_param == "presenza_test_suite":
                    # Verifichiamo la presenza di directory o file di test
                    valore = False
                    punteggio = 0
                    
                    try:
                        if self.local_repo_path:
                            # Controlla le directory locali
                            contents = os.listdir(self.local_repo_path)
                            test_dirs = [d for d in contents if os.path.isdir(os.path.join(self.local_repo_path, d)) and "test" in d.lower()]
                            test_files = [f for f in contents if os.path.isfile(os.path.join(self.local_repo_path, f)) and "test" in f.lower()]
                        else:
                            # Ottieni il contenuto del repository
                            contents = self.repo.get_contents("")
                            test_dirs = [f.name for f in contents if f.type == "dir" and "test" in f.name.lower()]
                            test_files = [f.name for f in contents if f.type == "file" and "test" in f.name.lower()]
                        
                        if test_dirs or test_files:
                            valore = True
                            punteggio = 10
                        else:
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Aggiungi test automatizzati per migliorare la qualità del codice"
                            )
                    except Exception:
                        pass
                elif nome_param == "integrazione_continua":
                    # Verifichiamo la presenza di configurazione CI
                    valore = False
                    punteggio = 0
                    
                    try:
                        # Controlla le common CI configurations
                        ci_configs = [
                            ".github/workflows",  # GitHub Actions
                            ".travis.yml",        # Travis CI
                            ".gitlab-ci.yml",     # GitLab CI
                            "azure-pipelines.yml", # Azure Pipelines
                            "Jenkinsfile",        # Jenkins
                            ".circleci"           # CircleCI
                        ]
                        
                        if self.local_repo_path:
                            # Usa il filesystem locale
                            files_and_dirs = [os.path.join(dp, f) for dp, dn, filenames in os.walk(self.local_repo_path) for f in filenames]
                            files_and_dirs += [os.path.join(self.local_repo_path, d) for d in os.listdir(self.local_repo_path) if os.path.isdir(os.path.join(self.local_repo_path, d))]
                        else:
                            # Utilizza l'API di GitHub
                            contents = self.repo.get_contents("")
                            files_and_dirs = [f.path for f in contents]
                        
                        for config in ci_configs:
                            if any(config in path for path in files_and_dirs):
                                valore = True
                                punteggio = 10
                                break
                                
                        if not valore:
                            self.results["suggerimenti"].setdefault(categoria, []).append(
                                "Configura un sistema di CI/CD per automatizzare i test e il deployment"
                            )
                    except Exception:
                        pass
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
                    valore = "Analisi non disponibile"
                    punteggio = 5  # Valore neutro
                else:
                    valore = "Non analizzato"
                    punteggio = 0
                
                return valore, round(punteggio, 2), conta_punteggio
                
            # Se arriviamo qui, non è stata trovata una corrispondenza
            return "Non analizzato", 0, False
            
        except TimeoutError:
            print(f"Timeout durante l'analisi del parametro {nome_param}")
            return "Timeout", 0, False
        except Exception as e:
            print(f"Errore nell'analisi del parametro {nome_param}: {e}")
            return "Errore", 0, False
        finally:
            # Disattiva il timeout se abilitato
            if timeout_enabled:
                signal.alarm(0)

    def _calculate_scores(self) -> None:
        """Calcola i punteggi per ogni categoria basandosi sui parametri analizzati."""
        for categoria, dettagli in self.results["dettagli"].items():
            pesi_totali = 0
            somma_pesata = 0
            for param in dettagli.values():
                if param.get("punteggio") is not None and param.get("punteggio") > 0 and not param.get("errore", False):
                    # Usa "conta_punteggio" per saltare quelli da escludere
                    if param.get("conta_punteggio", True):
                        somma_pesata += (param["punteggio"] * param["peso"])
                        pesi_totali += param["peso"]
            if pesi_totali > 0:
                self.results["punteggi"][categoria] = round(somma_pesata / pesi_totali, 2)
            else:
                self.results["punteggi"][categoria] = 0.0
        
        # Calcola il punteggio totale
        punteggi = list(self.results["punteggi"].values())
        if punteggi:
            self.results["punteggio_totale"] = round(sum(punteggi) / len(punteggi), 2)

    def _update_history(self) -> None:
        """Aggiorna lo storico dei punteggi."""
        try:
            # Carica lo storico esistente se presente
            history_file = f"{self.repo_name.replace('/', '_')}_history.json"
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = []

            # Crea una nuova entry completa per lo storico
            current_analysis = {
                "data": self.results["data_analisi"],
                "punteggio_totale": self.results.get("punteggio_totale", 0),
                "punteggi": self.results.get("punteggi", {}),
                # Includi anche i dettagli completi per ogni parametro
                "dettagli_parametri": {}
            }

            # Aggiungi i dettagli di tutti i parametri per ogni categoria
            for categoria, parametri in self.results.get("dettagli", {}).items():
                current_analysis["dettagli_parametri"][categoria] = {}
                for nome_param, dati in parametri.items():
                    current_analysis["dettagli_parametri"][categoria][nome_param] = {
                        "valore": dati.get("valore", "N/A"),
                        "punteggio": dati.get("punteggio", 0)
                    }

            # Aggiungi l'analisi corrente allo storico
            history.append(current_analysis)

            # Mantieni solo le ultime 10 analisi
            history = history[-10:]

            # Salva lo storico aggiornato
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            # Aggiorna i risultati con lo storico
            self.results["storico"] = history

        except Exception as e:
            print(f"Errore nell'aggiornamento dello storico: {e}")
            self.results["storico"] = []

    def visualize_results(self) -> None:
        """Visualizza i risultati dell'analisi generando un report HTML interattivo."""
        if not self.results or not self.results.get("punteggi"):
            print("Nessun risultato disponibile. Esegui prima l'analisi.")
            return

        try:
            # Visualizza i suggerimenti nel terminale
            if self.results.get("suggerimenti"):
                print("\nSuggerimenti per il miglioramento:")
                for categoria, suggerimenti in self.results["suggerimenti"].items():
                    if suggerimenti:
                        print(f"\n{categoria.replace('_', ' ').title()}:")
                        for suggerimento in suggerimenti:
                            print(f"- {suggerimento}")

            # Genera il report HTML utilizzando il modulo html_report
            output_file = generate_html_report(self.results)
            print(f"\nReport HTML generato: {output_file}")
            print("Apri il file nel tuo browser per visualizzare il report interattivo.")
        except Exception as e:
            print(f"Errore nella generazione del report HTML: {e}")



def main():
    """Funzione principale."""
    parser = argparse.ArgumentParser(description="Analizzatore di Repository GitHub")
    parser.add_argument("--repo", required=True, help="Nome del repository (username/repository)")
    parser.add_argument("--config", default=CONFIG_FILE, help="File di configurazione")
    parser.add_argument("--output", help="File di output per il report JSON")
    parser.add_argument("--no-viz", action="store_true", help="Disabilita la visualizzazione grafica")
    parser.add_argument("--clone", action="store_true", help="Clona il repository localmente per un'analisi più approfondita.")
    
    args = parser.parse_args()
    
    # Analizza il repository
    with RepoAnalyzer(args.repo, args.config, args.clone) as analyzer:
        results = analyzer.analyze()
    
    # Salva i risultati in un file JSON se specificato
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nReport salvato in: {args.output}")
    
    # Visualizza i risultati se non disabilitato
    if not args.no_viz:
        analyzer.visualize_results()


if __name__ == "__main__":
    main()