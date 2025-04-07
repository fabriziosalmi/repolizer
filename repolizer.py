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
    
    def __init__(self, repo_name: str, config_file: str = CONFIG_FILE):
        """Inizializza l'analizzatore di repository.

        Args:
            repo_name: Nome del repository nel formato 'username/repository'
            config_file: Percorso del file di configurazione
        """
        self.repo_name = repo_name
        self.config_file = config_file
        self.config = self._load_config()
        self.console = Console()
        
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
                # Imposta un timeout per evitare blocchi nelle richieste API
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("La richiesta API ha impiegato troppo tempo")
                
                # Imposta un timeout di 20 secondi per le richieste API
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(20)
                
                result = fetch_func(*args, **kwargs)
                
                # Disattiva il timeout
                signal.alarm(0)
                
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
                    valore, punteggio = self._analyze_parameter(categoria, nome_param, info_param)
                    
                    self.results["dettagli"][categoria][nome_param] = {
                        "valore": valore if valore is not None else "N/A",
                        "punteggio": punteggio if punteggio is not None else 0,
                        "peso": info_param.get("peso", 1),
                        "descrizione": info_param.get("descrizione", "")
                    }
                except Exception as e:
                    self.console.print(f"[red]Errore nell'analisi del parametro {nome_param}: {e}[/red]")
                    self.results["dettagli"][categoria][nome_param] = {
                        "valore": "Errore",
                        "punteggio": 0,
                        "peso": info_param.get("peso", 1),
                        "descrizione": info_param.get("descrizione", "")
                    }

        # Calcola i punteggi per categoria e il punteggio totale
        self._calculate_scores()
        
        # Aggiorna lo storico dei punteggi
        self._update_history()
        
        return self.results

    def _analyze_parameter(self, categoria: str, nome_param: str, info_param: Dict) -> Tuple[Any, float]:
        """Analizza un singolo parametro del repository e genera suggerimenti.

        Args:
            categoria: Nome della categoria del parametro
            nome_param: Nome del parametro
            info_param: Informazioni sul parametro

        Returns:
            Tupla con il valore del parametro e il punteggio normalizzato (0-10)
        """
        # Inizializza le variabili con valori di default
        valore = "Non analizzato"
        punteggio = 0
        
        try:
            # Imposta un timeout per l'analisi di ogni parametro
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"L'analisi del parametro {nome_param} ha impiegato troppo tempo")
            
            # Imposta un timeout di 30 secondi per l'analisi di ogni parametro
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            # Inizializza i suggerimenti per questa categoria se non esistono
            if categoria not in self.results.get("suggerimenti", {}):
                self.results["suggerimenti"][categoria] = []
            # Popolarità & Impatto
            if categoria == "popolarita_impatto":
                if nome_param == "stelle":
                    valore = self.repo.stargazers_count
                    punteggio = self._normalize_score(valore, 0, 10000, 0, 10)
                elif nome_param == "forks":
                    valore = self.repo.forks_count
                    punteggio = self._normalize_score(valore, 0, 5000, 0, 10)
                elif nome_param == "watchers":
                    valore = self.repo.subscribers_count
                    punteggio = self._normalize_score(valore, 0, 1000, 0, 10)
                elif nome_param == "contributori":
                    contributors = self._get_cached_data(
                        "contributors",
                        lambda: list(self.repo.get_contributors()[:MAX_ITEMS_PER_REQUEST])
                    )
                    if contributors:
                        valore = len(contributors)
                        punteggio = self._normalize_score(valore, 0, 100, 0, 10)
                    else:
                        valore = 0
                        punteggio = 0
                elif nome_param == "dipendenti":
                    # Questo richiede API aggiuntive o analisi più complesse
                    # Invece di usare N/A, usiamo un valore più descrittivo
                    valore = "Non disponibile"
                    punteggio = 5  # Valore di default
                else:
                    valore = "Non analizzato"
                    punteggio = 0

            # Attività & Manutenzione
            elif categoria == "attivita_manutenzione":
                if nome_param == "data_ultimo_commit":
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
                            else:
                                valore = len(commits)
                                punteggio = self._normalize_score(len(commits), 1, 10, 0, 10)
                        except Exception as e:
                            print(f"Errore nel calcolo della frequenza dei commit: {e}")
                            valore = "Errore calcolo"
                            punteggio = 5
                    else:
                        valore = 0
                        punteggio = 0
                else:
                    valore = "Non analizzato"
                    punteggio = 0

            # Qualità & Documentazione
            elif categoria == "qualita_documentazione":
                if nome_param == "readme":
                    try:
                        readme = self.repo.get_readme()
                        content = readme.decoded_content.decode("utf-8")
                        
                        # Analizza la qualità del README
                        lines = content.split("\n")
                        word_count = len(content.split())
                        has_sections = any(line.startswith("#") for line in lines)
                        has_code = "```" in content
                        has_links = "[" in content and "](" in content
                        
                        # Calcola il punteggio
                        score = 0
                        if word_count > 100: score += 2  # README base
                        if word_count > 500: score += 2  # README dettagliato
                        if has_sections: score += 2      # Struttura organizzata
                        if has_code: score += 2          # Esempi di codice
                        if has_links: score += 2         # Collegamenti utili
                        
                        valore = {
                            "parole": word_count,
                            "sezioni": has_sections,
                            "codice": has_code,
                            "link": has_links
                        }
                        punteggio = score
                        
                        # Aggiungi suggerimenti se necessario
                        if score < 10:
                            missing = []
                            if word_count <= 100: missing.append("contenuto più dettagliato")
                            if not has_sections: missing.append("sezioni organizzate")
                            if not has_code: missing.append("esempi di codice")
                            if not has_links: missing.append("link utili")
                            
                            if missing:
                                self.results["suggerimenti"][categoria].append(
                                    f"Migliora il README aggiungendo: {', '.join(missing)}"
                                )
                    except Exception as e:
                        print(f"Errore nell'analisi del README: {e}")
                        valore = "Non trovato"
                        punteggio = 0
                        self.results["suggerimenti"][categoria].append(
                            "Crea un README.md per documentare il progetto"
                        )
                else:
                    valore = "Non analizzato"
                    punteggio = 0

            # Manutenibilità & Test
            elif categoria == "manutenibilita_test":
                # Inizializza le variabili di default
                valore = "Non analizzato"
                punteggio = 0
                
                if nome_param == "test":
                    # Cerca file di test nel repository
                    try:
                        contents = self.repo.get_contents("")
                        test_files = []
                        test_dirs = []
                        
                        while contents:
                            file_content = contents.pop(0)
                            
                            if file_content.type == "dir":
                                if "test" in file_content.name.lower():
                                    test_dirs.append(file_content.path)
                                try:
                                    contents.extend(self.repo.get_contents(file_content.path))
                                except Exception:
                                    continue
                            elif file_content.type == "file":
                                if "test" in file_content.name.lower():
                                    test_files.append(file_content.path)
                        
                        # Calcola il punteggio in base ai test trovati
                        score = 0
                        if test_dirs: score += 5  # Directory dedicata ai test
                        score += min(5, len(test_files))  # Fino a 5 punti per i file di test
                        
                        valore = {
                            "directory_test": test_dirs,
                            "file_test": test_files
                        }
                        punteggio = score
                        
                        # Aggiungi suggerimenti se necessario
                        if score < 10:
                            if not test_dirs:
                                self.results["suggerimenti"][categoria].append(
                                    "Crea una directory dedicata ai test"
                                )
                            if len(test_files) < 5:
                                self.results["suggerimenti"][categoria].append(
                                    "Aumenta la copertura dei test aggiungendo più test"
                                )
                    except Exception as e:
                        print(f"Errore nell'analisi dei test: {e}")
                        valore = "Errore analisi"
                        punteggio = 0
                else:
                    valore = "Non analizzato"
                    punteggio = 0

            # Sicurezza
            elif categoria == "sicurezza":
                if nome_param == "vulnerabilita":
                    # Questo richiederebbe l'accesso alle API di sicurezza di GitHub
                    # Per ora, restituiamo un valore di default
                    valore = "Analisi non disponibile"
                    punteggio = 5
                    self.results["suggerimenti"][categoria].append(
                        "Attiva GitHub Security Alerts per monitorare le vulnerabilità"
                    )
                else:
                    valore = "Non analizzato"
                    punteggio = 0
            
            # Disattiva il timeout
            signal.alarm(0)
            
            return valore, punteggio
        
        except TimeoutError:
            print(f"Timeout durante l'analisi del parametro {nome_param}")
            return "Timeout", 0
        except Exception as e:
            print(f"Errore nell'analisi del parametro {nome_param}: {e}")
            return "Errore", 0

    def _normalize_score(self, value: float, min_val: float, max_val: float,
                        out_min: float = 0, out_max: float = 10,
                        inverse: bool = False) -> float:
        """Normalizza un valore in un intervallo specificato.

        Args:
            value: Valore da normalizzare
            min_val: Valore minimo dell'intervallo di input
            max_val: Valore massimo dell'intervallo di input
            out_min: Valore minimo dell'intervallo di output
            out_max: Valore massimo dell'intervallo di output
            inverse: Se True, inverte la scala (più alto diventa più basso)

        Returns:
            Valore normalizzato nell'intervallo specificato
        """
        try:
            # Assicurati che il valore sia nel range
            value = max(min_val, min(value, max_val))
            
            # Normalizza il valore
            if max_val == min_val:
                normalized = 0.5  # Valore medio se min e max sono uguali
            else:
                normalized = (value - min_val) / (max_val - min_val)
            
            # Inverti se richiesto
            if inverse:
                normalized = 1 - normalized
            
            # Scala al range di output
            score = out_min + (normalized * (out_max - out_min))
            
            return round(score, 2)
        except Exception as e:
            print(f"Errore nella normalizzazione del punteggio: {e}")
            return 0.0

    def _calculate_scores(self) -> None:
        """Calcola i punteggi per ogni categoria e il punteggio totale."""
        try:
            # Calcola i punteggi per categoria
            for categoria, parametri in self.results["dettagli"].items():
                valid_scores = []
                total_weight = 0
                
                for nome_param, info in parametri.items():
                    if info["punteggio"] is not None and info["valore"] not in ["Errore", "N/A"]:
                        weight = info.get("peso", 1)
                        valid_scores.append(info["punteggio"] * weight)
                        total_weight += weight
                
                if valid_scores and total_weight > 0:
                    # Media ponderata dei punteggi
                    self.results["punteggi"][categoria] = round(sum(valid_scores) / total_weight, 2)
                else:
                    self.results["punteggi"][categoria] = 0
            
            # Calcola il punteggio totale come media dei punteggi delle categorie
            if self.results["punteggi"]:
                self.results["punteggio_totale"] = round(
                    sum(self.results["punteggi"].values()) / len(self.results["punteggi"]),
                    2
                )
            else:
                self.results["punteggio_totale"] = 0
        except Exception as e:
            print(f"Errore nel calcolo dei punteggi: {e}")
            self.results["punteggio_totale"] = 0

    def _update_history(self) -> None:
        """Aggiorna lo storico dei punteggi del repository."""
        try:
            # Carica lo storico esistente se presente
            history_file = f"{self.repo_name.replace('/', '_')}_history.json"
            history = []
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            # Aggiungi i punteggi attuali allo storico
            history.append({
                "data": self.results["data_analisi"],
                "punteggi": self.results["punteggi"],
                "punteggio_totale": self.results["punteggio_totale"]
            })
            
            # Salva lo storico aggiornato
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            self.results["storico"] = history
        except Exception as e:
            print(f"Errore nell'aggiornamento dello storico: {e}")

    def visualize_results(self) -> None:
        """Visualizza i risultati dell'analisi generando un report HTML interattivo."""
        if not self.results or not self.results.get("punteggi"):
            print("Nessun risultato disponibile. Esegui prima l'analisi.")
            return

        try:
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
    
    args = parser.parse_args()
    
    # Analizza il repository
    analyzer = RepoAnalyzer(args.repo, args.config)
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