#!/usr/bin/env python3

import requests
import re
import time
import os
import json
import logging
import argparse
import concurrent.futures
import atexit
import threading
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Set, List, Tuple

import nltk  # Added nltk import
from nltk.stem import SnowballStemmer
from thefuzz import fuzz

# --- Configuration ---

# Load environment variables from .env file if it exists
load_dotenv()

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent.resolve()

# --- Logging Setup ---

# Configure logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Stream Handler (Console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

# File Handler (File)
log_file_path = SCRIPT_DIR / "repolizer.log"
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setFormatter(log_formatter)

# Get logger instance
logger = logging.getLogger("repolizer")
logger.setLevel(logging.INFO)  # Default level
logger.addHandler(stream_handler)
logger.addHandler(file_handler)
logger.propagate = False # Prevent double logging if root logger is configured

# --- Constants ---

DEFAULT_REPOS_FILE = SCRIPT_DIR / "repos.txt"
DEFAULT_CACHE_FILE = SCRIPT_DIR / "cache.json"
DEFAULT_CACHE_HOURS = 24
DEFAULT_MAX_WORKERS = 5
DEFAULT_MAX_PAGES = 10
DEFAULT_PER_PAGE = 30
GITHUB_API_BASE_URL = "https://api.github.com"

# Expanded list of Italian words for language detection (lowercase)
ITALIAN_GITHUB_WORDS = set([
    "ciao", "buongiorno", "progetto", "documentazione", "utilizzo",
    "installazione", "configurazione", "esempio", "questo", "quello",
    "come", "italiano", "italiana", "sviluppo", "funzionalità", "istruzioni",
    "grazie", "prego", "sviluppatore", "libreria", "strumento",
    "applicazione", "codice", "sorgente", "contribuire", "licenza",
    "versione", "aggiornamento", "interfaccia", "utente", "dati",
    "scaricare", "implementazione", "comunità", "supporto", "problema",
    "guida", "requisiti", "avanzato", "base", "note", "rilascio",
    "software", "hardware", "rete", "server", "database", "sistema",
    "informazioni", "sicurezza", "accesso", "password", "account",
    "errore", "warning", "notifica", "risolvere", "soluzione",
    "gestione", "processo", "modello", "design", "architettura",
    "analisi", "test", "validazione", "controllo", "ottimizzazione",
    "miglioramento", "performance", "qualità", "efficienza",
    "risultato", "obiettivo", "pianificazione", "programmazione",
    "monitoraggio", "reporting", "comunicazione", "collaborazione",
    "team", "management", "risorse", "budget", "costo", "tempo",
    "rischio", "opportunità", "innovazione", "tecnologia",
    "digitale", "online", "offline", "web", "mobile", "cloud",
    "algoritmo", "intelligenza", "artificiale", "robotica", "automazione", "virtuale", "realtà", "aumentata",
    "esperienza", "interazione", "grafica",
    "contenuto", "testo", "immagine", "video", "audio",
    "documento", "file", "cartella", "repository", "commit", "branch",
    "pull", "request", "issue", "wiki", "readme", "changelog",
    "build", "deploy", "script", "programma",
    "API", "SDK", "framework", "plugin", "modulo", "componente",
    "servizio", "processo", "thread", "mutex", "semaphore",
    "buffer", "socket", "http", "https", "ssl", "tls",
    "url", "domain",
    "database", "sql", "nosql", "cache", "coda", "messaggio", "evento",
    "front-end", "back-end", "full-stack", "devops", "sre",
    "agile", "scrum", "kanban",
    "software", "libero", "opensource", "aperto",
    "manuale", "tutorial", "esempio", "uso", "pratica",
    "schema", "anti-schema", "rifattorizzazione", "debug",
    "profilazione", "log",
    "autenticazione", "autorizzazione", "crittografia",
    "sicurezza", "informatica", "vulnerabilità", "exploit", "patch",
    "test", "unitari", "integrazione", "end-to-end",
    "copertura", "report", "analisi", "statica", "dinamica",
    "integrazione", "continua", "delivery", "deployment",
    "controllo", "versione", "fork", "clone", "push", "tirare", "unire",
    "risolto", "in corso", "da fare", "bloccato", "richiesta",
    "discussione", "suggerimento", "opinione", "feedback", "domanda",
    "risposta", "soluzione", "approccio", "metodo", "tecnica",
    "utilità",
    "tecnica", "wiki",
    "supporto",
    "bug", "tracker", "segnalazione", "problemi",
    "funzionalità",
    "comunicazione", "email", "incontro", "conferenza", "webinar", "presentazione",
    "laboratorio", "programmazione", "sfida", "concorso",
    "personale", "secondario",
    "avvio", "azienda", "società", "consulenza", "servizi",
    "calcolo", "distribuito",
    "scienza", "dati", "grandi dati",
    "elaborazione", "linguaggio", "naturale", "visione", "artificiale",
    "realtà", "estesa", "immersiva", "ologrammi",
    "interfacce", "cervello-computer", "impianti",
    "città", "case", "reti", "agricoltura",
    "obiettivi", "sviluppo", "sostenibile", "agenda", "mondiali",
    "economia", "circolare", "lineare", "modello", "transizione",
    "energia", "rinnovabile", "solare", "eolico", "idroelettrico",
    "biomassa", "geotermico", "nucleare", "fusione", "fissione",
    "ambiente", "cambiamento", "climatico", "emissioni", "gas",
    "effetto", "serra", "riscaldamento", "globale", "inquinamento",
    "acqua", "aria", "suolo", "rifiuti", "riciclo", "riuso", "riduzione",
    "biodiversità", "conservazione", "specie", "estinzione", "ecosistema",
    "salute", "benessere", "medicina", "prevenzione", "cura", "malattia",
    "alimentazione", "sana", "biologica", "vegetariana", "vegana",
    "km0", "locale", "stagionale", "filiera", "corta", "equo", "solidale",
    "lavoro", "digitale", "remoto", "smart", "flessibile", "autonomo",
    "formazione", "apprendimento", "competenza", "abilità", "talento",
    "innovazione", "sociale", "tecnologica", "culturale", "artistica",
    "istruzione", "scuola", "università", "ricerca", "dottorato",
    "comunità", "locale", "globale", "inclusiva", "partecipativa",
    "cittadinanza", "attiva", "responsabile", "consapevole",
    "democrazia", "partecipativa", "diretta", "trasparenza", "accountability",
    "etica", "integrità", "responsabilità", "sostenibilità",
    "finanza", "etica", "sociale", "alternativa", "cooperativa", "impact", "investing",
    "impresa", "sociale", "cooperativa", "benefit", "startup",
    "cultura", "arte", "musica", "cinema", "teatro", "letteratura",
    "sport", "tempo", "libero", "turismo", "sostenibile", "responsabile"
])

# Expanded Italian cities and regions for location detection (lowercase)
ITALIAN_LOCATIONS = set([
    "italia", "milano", "roma", "napoli",
    "torino", "firenze", "bologna", "palermo", "genova",
    "sicilia", "sardegna", "toscana",
    "lazio", "lombardia", "veneto", "piemonte",
    "catania", "bari", "verona", "padova", "trieste", "cagliari",
    "brescia", "parma", "modena", "pisa", "siena", "perugia", "puglia",
    "calabria", "campania", "liguria", "abruzzo", "umbria", "marche",
    "emilia-romagna", "friuli", "trentino", "alto adige",
    "valle d'aosta", ".it",
    "l'aquila", "ancona", "potenza", "catanzaro", "aosta", "bolzano",
    "trento", "udine", "gorizia", "pordenone", "trieste", "venezia",
    "vicenza", "treviso", "rovigo", "belluno", "vercelli", "biella",
    "alessandria", "asti", "cuneo", "novara", "verbano-cusio-ossola",
    "massa", "carrara", "lucca", "livorno", "arezzo", "grosseto",
    "prato", "pistoia", "pesaro", "urbino", "macerata", "fermo",
    "ascoli piceno", "viterbo", "rieti", "latina", "frosinone",
    "caserta", "avellino", "benevento", "salerno", "matera", "foggia",
    "taranto", "brindisi", "lecce", "barletta-andria-trani", "cosenza",
    "crotone", "reggio calabria", "vibo valentia", "sassari", "nuoro",
    "oristano", "sud sardegna", "centro italia", "nord italia", "sud italia",
    "isole", "appennini", "alpi", "adriatico", "tirreno", "ionio",
    "lago maggiore", "lago di como", "lago di garda", "italia settentrionale",
    "italia centrale", "italia meridionale", "siciliana", "sardo",
    "adriatica", "tirrenica", "ionica", "padana", "pianura padana",
    "costiera", "appenninica", "alpina", "mediterraneo", "mediterranea",
    "veneto", "friuli venezia giulia", "siciliane", "sarde",
    "comune", "provincia", "regione", "stato", "nazione"
])

# Download nltk resources (only needs to be done once)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find("stemmers/snowball")
except LookupError:
    nltk.download('snowball')

# --- Scraper Class ---

class GitHubRepoScraper:
    """Scrapes GitHub for repositories based on specific criteria, focusing on Italian ones."""

    def __init__(
        self,
        token: Optional[str] = None,
        cache_duration_hours: int = DEFAULT_CACHE_HOURS,
        max_workers: int = DEFAULT_MAX_WORKERS,
        repos_file: Path = DEFAULT_REPOS_FILE,
        cache_file: Path = DEFAULT_CACHE_FILE,
        fuzzy_match_threshold: int = 80,
        location_bias: float = 0.9
    ):
        self.base_url = GITHUB_API_BASE_URL
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28" # Recommended practice
        }
        if token:
            logger.info("Using GitHub token for authentication.")
            self.headers["Authorization"] = f"Bearer {token}" # Bearer is preferred
        else:
            logger.warning("No GitHub token provided. API rate limits will be significantly lower.")

        self.max_workers = max_workers
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.repos_file = repos_file
        self.cache_file = cache_file
        self.fuzzy_match_threshold = fuzzy_match_threshold
        self.location_bias = location_bias # Bias towards location matches if user is known to be Italian

        self.session = self._setup_session()
        self.stemmer = SnowballStemmer("italian")

        self._cache_lock = threading.Lock()
        self._repos_set_lock = threading.Lock()

        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()
        self.existing_repos: Set[str] = self._load_existing_repos()

        # Register save_cache to be called on exit
        atexit.register(self._save_cache)

    def _setup_session(self) -> requests.Session:
        """Configures and returns a requests Session with retry logic."""
        session = requests.Session()
        session.headers.update(self.headers)

        retry_strategy = Retry(
            total=5,  # Increased retries
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"], # Corrected allowed_methods -> method_whitelist for older urllib3
            # Use `allowed_methods` if using urllib3 v2.0+
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _load_existing_repos(self) -> Set[str]:
        """Loads the set of already known repository names from the repos file."""
        if not self.repos_file.exists():
            logger.info(f"Repos file not found at {self.repos_file}, starting fresh.")
            return set()
        try:
            with open(self.repos_file, "r", encoding='utf-8') as f:
                repos = {line.strip() for line in f if line.strip()}
                logger.info(f"Loaded {len(repos)} existing repo names from {self.repos_file}")
                return repos
        except Exception as e:
            logger.error(f"Failed to load existing repos from {self.repos_file}: {e}", exc_info=True)
            return set()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Loads the API cache from the cache file, filtering expired entries."""
        if not self.cache_file.exists():
            logger.info(f"Cache file not found at {self.cache_file}, creating new cache.")
            return {}
        try:
            with open(self.cache_file, "r", encoding='utf-8') as f:
                cache_data = json.load(f)

            valid_cache = {}
            current_time = datetime.now(timezone.utc) # Use timezone-aware datetime
            expired_count = 0

            for key, value in cache_data.items():
                if isinstance(value, dict) and 'timestamp' in value and 'data' in value:
                    try:
                        # Parse timestamp assuming ISO format with potential timezone
                        timestamp = datetime.fromisoformat(value['timestamp']).replace(tzinfo=timezone.utc)
                        if current_time - timestamp < self.cache_duration:
                            valid_cache[key] = value
                        else:
                            expired_count += 1
                    except ValueError:
                        logger.warning(f"Invalid timestamp format in cache for key {key}: {value.get('timestamp')}")
                        expired_count += 1
                else:
                    logger.warning(f"Invalid cache entry structure for key {key}")
                    expired_count += 1

            logger.info(f"Loaded {len(valid_cache)} valid entries from cache file {self.cache_file} ({expired_count} expired/invalid).")
            return valid_cache
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from cache file {self.cache_file}: {e}", exc_info=True)
            # Consider backing up the corrupted file here
            return {}
        except Exception as e:
            logger.error(f"Failed to load cache from {self.cache_file}: {e}", exc_info=True)
            return {}

    def _save_cache(self):
        """Save the current cache to the cache file."""
        try:
            # Create a deep copy of the cache to avoid modifying the original
            cache_copy = {}
            for url, entry in self.cache.items():
                # Skip non-serializable objects like MagicMock (adds test compatibility)
                if hasattr(entry, '__dict__') and hasattr(entry, '__class__') and entry.__class__.__name__ == 'MagicMock':
                    continue

                # Add serializable entries only
                try:
                    # Test JSON serializability
                    json.dumps(entry)
                    cache_copy[url] = entry
                except (TypeError, OverflowError):
                    # Skip non-serializable entries
                    continue

            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

            # Write the cache to file
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_copy, f, indent=2)  # Add indent for readability

            # Use try-except when logging to prevent issues with closed file handles
            try:
                logger.info(f"Successfully saved cache with {len(cache_copy)} entries to {self.cache_file}")
            except (ValueError, IOError):
                # Fallback to print if logging fails
                print(f"Successfully saved cache with {len(cache_copy)} entries to {self.cache_file}")

        except Exception as e:
            try:
                logger.error(f"Could not save cache to {self.cache_file}: {e}")
            except (ValueError, IOError):
                # Fallback to print if logging fails
                print(f"ERROR: Could not save cache to {self.cache_file}: {e}")

    def _get_with_cache(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Makes a GET request using the session, utilizing and updating the cache."""
        # Create a canonical cache key (sort params)
        param_string = json.dumps(params, sort_keys=True) if params else ""
        cache_key = f"{url}?{param_string}"

        # Check cache first (read is generally safe without lock)
        if cache_key in self.cache:
            logger.debug(f"Cache hit for {url}")
            return self.cache[cache_key]['data']

        logger.debug(f"Cache miss for {url}, fetching from API.")
        try:
            response = self.session.get(url, params=params, timeout=20) # Add timeout

            # Check rate limit info *before* raising for status
            remaining = int(response.headers.get('X-RateLimit-Remaining', -1))
            reset_timestamp = int(response.headers.get('X-RateLimit-Reset', 0))
            if remaining != -1:
                 logger.debug(f"Rate limit: {remaining} remaining. Resets at {datetime.fromtimestamp(reset_timestamp, timezone.utc)}")
                 if remaining < 10:
                    logger.warning(f"GitHub API rate limit low: {remaining} requests remaining.")
                    if remaining < 2:
                        reset_time = datetime.fromtimestamp(reset_timestamp, timezone.utc)
                        now = datetime.now(timezone.utc)
                        sleep_time = max(0, (reset_time - now).total_seconds()) + 2 # Add 2s buffer
                        logger.warning(f"Rate limit critically low. Sleeping for {sleep_time:.1f} seconds until {reset_time}.")
                        time.sleep(sleep_time)

            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            # Save to cache (use lock for write operation)
            with self._cache_lock:
                self.cache[cache_key] = {
                    'data': data,
                    'timestamp': datetime.now(timezone.utc).isoformat() # Store UTC timestamp
                }
            return data

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            is_rate_limit = status_code == 403 and 'rate limit exceeded' in e.response.text.lower()
            is_secondary_limit = status_code == 403 and 'secondary rate limit' in e.response.text.lower()

            if is_rate_limit or is_secondary_limit:
                reset_timestamp = int(e.response.headers.get('X-RateLimit-Reset', 0))
                retry_after = int(e.response.headers.get('Retry-After', 0)) # Check Retry-After header too

                sleep_time = 60 # Default sleep
                if reset_timestamp > 0:
                    reset_dt = datetime.fromtimestamp(reset_timestamp, timezone.utc)
                    now = datetime.now(timezone.utc)
                    sleep_time = max(0, (reset_dt - now).total_seconds()) + 5 # 5s buffer
                elif retry_after > 0:
                    sleep_time = retry_after + 5

                log_msg = "Primary" if is_rate_limit else "Secondary"
                logger.warning(f"{log_msg} rate limit exceeded for {url}. Sleeping for {sleep_time:.1f} seconds.")
                time.sleep(sleep_time)
                # Retry the request after sleeping
                return self._get_with_cache(url, params)
            elif status_code == 404:
                logger.warning(f"Resource not found (404): {url}")
                # Cache the 404 to avoid retrying constantly
                with self._cache_lock:
                     self.cache[cache_key] = {
                         'data': None, # Indicate not found
                         'timestamp': datetime.now(timezone.utc).isoformat()
                     }
                return None
            elif status_code == 401:
                 logger.error(f"Authentication failed (401) for {url}. Check your GITHUB_TOKEN.")
                 return None
            elif status_code == 422:
                 logger.error(f"Unprocessable Entity (422) for {url}. Request params: {params}. Response: {e.response.text}")
                 return None
            else:
                logger.error(f"HTTP error fetching {url}: {e}", exc_info=True)
                return None
        except requests.exceptions.Timeout:
             logger.warning(f"Request timed out for {url}")
             return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network or request error fetching {url}: {e}", exc_info=True)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from {url}: {e}. Response text: {response.text[:200]}...")
            return None
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error processing {url}: {e}", exc_info=True)
            return None

    def _check_text_for_italian(self, text: Optional[str]) -> bool:
        """Checks if a given text contains Italian keywords using stemming and fuzzy matching."""
        if not text:
            return False
        text_lower = text.lower()
        words = nltk.word_tokenize(text_lower)  # Split into words properly
        stemmed_words = [self.stemmer.stem(word) for word in words]  # Stem each word
        for word in stemmed_words:
            for italian_word in ITALIAN_GITHUB_WORDS:
                if fuzz.ratio(word, italian_word) >= self.fuzzy_match_threshold:
                    return True  # Fuzzy match found
        return False

    def _check_location_for_italian(self, location: Optional[str]) -> bool:
        """Checks if a given location string matches known Italian locations."""
        if not location:
            return False
        location_lower = location.lower()
        return any(loc in location_lower for loc in ITALIAN_LOCATIONS)

    def _is_italian_user_or_org(self, owner_info: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
        """Checks if a user or organization profile suggests an Italian origin."""
        if not owner_info:
            return False, "Owner info not available"

        owner_type = owner_info.get("type", "Unknown").lower()
        location = owner_info.get("location", "")
        name = owner_info.get("name", "")
        bio = owner_info.get("bio", "")
        description = owner_info.get("description", "") # For orgs
        blog = owner_info.get("blog", "") # Website/blog

        # 1. Check location explicitly (HIGH PRIORITY)
        if self._check_location_for_italian(location):
            return True, f"Location match ({location})"

        # 2. Check website/blog for '.it' domain or Italian keywords
        if blog:
            blog_lower = blog.lower()
            if ".it" in blog_lower:
                return True, f"Website domain match ({blog})"
            if self._check_text_for_italian(blog):
                 return True, f"Website text match ({blog})"

        # 3. Check name, bio/description for Italian keywords
        combined_text = f"{name} {bio} {description}".lower()
        if self._check_text_for_italian(combined_text):
            return True, f"{owner_type} profile text match"

        return False, f"No strong indicators in {owner_type} profile"

    def _has_italian_readme(self, repo_full_name: str) -> Tuple[bool, str]:
        """Checks if the repository's README content seems to be in Italian."""
        try:
            readme_api_url = f"{self.base_url}/repos/{repo_full_name}/readme"
            readme_info = self._get_with_cache(readme_api_url)

            if not readme_info or 'download_url' not in readme_info or not readme_info['download_url']:
                return False, "README not found or inaccessible"

            download_url = readme_info["download_url"]
            logger.debug(f"Fetching README content for {repo_full_name} from {download_url}")

            # Use cache for the download URL itself too
            readme_content_cached = self._get_with_cache(download_url)
            if isinstance(readme_content_cached, str): # Check if it was cached as text
                content = readme_content_cached
            elif readme_content_cached is None: # Handle cached 'not found'
                return False, "README download failed (cached)"
            else:
                # Fetch directly if not cached or cache format is unexpected
                try:
                    # Use the main session for retries, but handle potential non-JSON response
                    response = self.session.get(download_url, timeout=30)
                    response.raise_for_status()
                    content = response.text # Assuming text content

                    # Cache the raw content
                    with self._cache_lock:
                        self.cache[download_url] = {
                            'data': content,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                except requests.exceptions.RequestException as e:
                     logger.warning(f"Failed to download README content for {repo_full_name}: {e}")
                     return False, "README download failed"

            if not content:
                return False, "README is empty"

            content_lower = content.lower()
            # Simple heuristic: count occurrences of specific Italian words
            italian_word_count = sum(1 for word in ITALIAN_GITHUB_WORDS if word in content_lower)

            # Adjust threshold as needed - maybe relative to file size?
            # For now, a simple count.
            threshold = 3
            if italian_word_count >= threshold:
                return True, f"README contains {italian_word_count} Italian keywords (>= {threshold})"
            else:
                 return False, f"README contains only {italian_word_count} Italian keywords (< {threshold})"

        except Exception as e:
            logger.error(f"Error checking README content for {repo_full_name}: {e}", exc_info=True)
            return False, "Error processing README"

    def _process_repo(self, repo: Dict[str, Any]) -> Optional[str]:
        """
        Processes a single repository item from search results to determine if it's likely Italian.
        Returns the full_name if deemed Italian, otherwise None.
        """
        full_name = repo.get("full_name")
        if not full_name:
            logger.warning("Repository item missing 'full_name'. Skipping.")
            return None

        # --- Early Exit Checks ---
        with self._repos_set_lock: # Lock needed for read+write check
            if full_name in self.existing_repos:
                logger.debug(f"Repo {full_name} already in existing list. Skipping.")
                return None

        if repo.get("fork"):
             logger.debug(f"Repo {full_name} is a fork. Skipping.") # Option to include forks if desired
             return None

        # --- Heuristic Checks (Prioritize data already available) ---

        # 1. Check Repository Description and Topics
        description = repo.get("description", "")
        topics = repo.get("topics", [])
        repo_text = f"{description} {' '.join(topics)}".lower()

        if self._check_text_for_italian(description):
             logger.info(f"Found Italian repo: {full_name} (Reason: Italian keyword in description)")
             return full_name
        if any(self._check_text_for_italian(topic) for topic in topics):
             logger.info(f"Found Italian repo: {full_name} (Reason: Italian keyword in topics)")
             return full_name
        if any(loc in repo_text for loc in ITALIAN_LOCATIONS):
             logger.info(f"Found Italian repo: {full_name} (Reason: Italian location in description/topics)")
             return full_name


        # 2. Check Owner Profile (Requires an API call)
        owner = repo.get("owner")
        owner_info = None
        if owner and owner.get("url"):
            owner_info = self._get_with_cache(owner["url"])
        else:
             logger.warning(f"Owner info missing or incomplete for repo {full_name}")

        is_italian_owner, owner_reason = self._is_italian_user_or_org(owner_info)
        if is_italian_owner:
            logger.info(f"Found Italian repo: {full_name} (Reason: Owner profile - {owner_reason})")
            return full_name
        else:
            logger.debug(f"Owner of {full_name} not flagged as Italian ({owner_reason})")


        # 3. Check README Content (Requires potentially two API calls)
        has_italian_readme, readme_reason = self._has_italian_readme(full_name)
        if has_italian_readme:
            logger.info(f"Found Italian repo: {full_name} (Reason: {readme_reason})")
            return full_name
        else:
             logger.debug(f"README of {full_name} not flagged as Italian ({readme_reason})")


        # 4. Final Check: Repository Language (Less reliable for 'Italian' itself)
        language = repo.get("language", "")
        if language and language.lower() == "italian":

             logger.debug(f"Repo {full_name} language reported as Italian, but not flagged by other checks.")


        # If none of the checks passed
        logger.debug(f"Repo {full_name} did not meet Italian criteria.")
        return None

    def search_repos(
            self,
            base_queries: List[str],
            additional_query: Optional[str] = None,
            per_page: int = DEFAULT_PER_PAGE,
            max_pages: int = DEFAULT_MAX_PAGES
        ) -> List[str]:
            """
            Searches GitHub repositories using multiple queries and processes results concurrently.
            """
            new_repos_found: List[str] = []
            processed_repo_names: Set[str] = set() # Track processed repos within this run to avoid duplicates across queries

            search_queries = list(base_queries) # Copy base queries
            if additional_query:
                search_queries.append(additional_query)

            total_items_processed = 0

            for search_query in search_queries:
                logger.info(f"--- Starting search for query: '{search_query}' ---")
                page = 1
                items_in_query = 0
                while page <= max_pages:
                    params = {
                        "q": search_query,
                        "sort": "updated", # Sort by updated to potentially find more active/recent repos
                        "order": "desc",
                        "per_page": per_page,
                        "page": page
                    }
                    search_url = f"{self.base_url}/search/repositories"
                    logger.info(f"Fetching page {page} for query '{search_query}' (max: {max_pages})")
                    response_data = self._get_with_cache(search_url, params=params)

                    if response_data is None: # Handle API errors or cached 404s
                        logger.warning(f"Failed to fetch page {page} for query '{search_query}'. Stopping query.")
                        break

                    repos_data = response_data.get("items")
                    if not isinstance(repos_data, list):
                        logger.error(f"Unexpected API response format for query '{search_query}', page {page}. 'items' not found or not a list.")
                        break # Stop processing this query if response is malformed

                    if not repos_data:
                        logger.info(f"No more results found for query '{search_query}' on page {page}.")
                        break # No more items on this page or subsequent pages

                    total_count = response_data.get('total_count', 'N/A')
                    logger.info(f"Processing {len(repos_data)} repositories from page {page} (Total results for query: {total_count})")
                    items_in_query += len(repos_data)

                    page_new_repos: List[str] = []
                    futures: Dict[concurrent.futures.Future, str] = {}

                    # Process repositories in parallel using ThreadPoolExecutor
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="RepoWorker") as executor:
                        for repo in repos_data:
                            if isinstance(repo, dict) and repo.get("full_name"):
                                repo_name = repo["full_name"]
                                if repo_name not in processed_repo_names: # Avoid re-processing if seen in another query/page
                                    future = executor.submit(self._process_repo, repo)
                                    futures[future] = repo_name # Store future to repo_name mapping
                                else:
                                    logger.debug(f"Skipping {repo_name} as it was already processed in this run.")
                            else:
                                logger.warning(f"Invalid repo data structure found on page {page} for query '{search_query}'.")

                        for future in concurrent.futures.as_completed(futures):
                            repo_name = futures[future]
                            try:
                                result = future.result()
                                if result: # result is the full_name if Italian, else None
                                    if result not in processed_repo_names:
                                        page_new_repos.append(result)
                                        processed_repo_names.add(result) # Mark as processed
                            except Exception as exc:
                                logger.error(f"Error processing repo {repo_name}: {exc}", exc_info=True)

                    if page_new_repos:
                        logger.info(f"Found {len(page_new_repos)} new Italian repositories on page {page}.")
                        new_repos_found.extend(page_new_repos)
                    else:
                        logger.info(f"No new Italian repositories found on page {page}.")

                    # GitHub search API has a limit of 1000 results (around 34 pages of 30 results)
                    if page * per_page >= 1000:
                        logger.warning(f"Reached GitHub search API limit of 1000 results for query '{search_query}'. Stopping query.")
                        break

                    page += 1
                    # Optional: Add a small delay between pages if hitting secondary rate limits often
                    # time.sleep(1)

                logger.info(f"--- Finished search for query: '{search_query}'. Processed {items_in_query} items. ---")

                # Save cache periodically after each query finishes
                self._save_cache()

            total_items_processed = len(processed_repo_names) # This count reflects unique repos processed
            logger.info(f"Finished all searches. Total unique repositories processed in this run: {total_items_processed}")
            return new_repos_found

    def save_repos(self, new_repos: List[str]):
        """Appends newly found and unique repository names to the repos file."""
        if not new_repos:
            logger.info("No new unique repositories found to save.")
            return

        added_count = 0
        try:
            # Ensure parent directory exists
            self.repos_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.repos_file, "a", encoding='utf-8') as f:
                with self._repos_set_lock: # Lock for writing to file and updating set
                    for repo_full_name in new_repos:
                        # Double-check against the set in case it was added concurrently somehow (unlikely with current flow but safe)
                        # Or more importantly, if it was already loaded from the file initially
                        if repo_full_name not in self.existing_repos:
                            f.write(f"{repo_full_name}\n")
                            self.existing_repos.add(repo_full_name)
                            added_count += 1
            if added_count > 0:
                logger.info(f"Successfully appended {added_count} new repositories to {self.repos_file}")
            else:
                logger.info(f"All {len(new_repos)} found repositories were already in the list.")

        except Exception as e:
            logger.error(f"Failed to save repositories to {self.repos_file}: {e}", exc_info=True)

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(
        description="Scrape GitHub for repositories potentially related to Italy.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Additional custom search query (e.g., 'topic:ai location:milan').",
        default=None
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum pages of results to fetch per search query.",
        default=DEFAULT_MAX_PAGES
    )
    parser.add_argument(
        "--per-page",
        type=int,
        help="Number of results to fetch per page (max 100).",
        default=DEFAULT_PER_PAGE
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of concurrent workers for processing repositories.",
        default=DEFAULT_MAX_WORKERS
    )
    parser.add_argument(
        "--cache-hours",
        type=int,
        help="Duration in hours to keep cache entries valid.",
        default=DEFAULT_CACHE_HOURS
    )
    parser.add_argument(
        "--repos-file",
        type=Path,
        help="Path to the file for storing found repository names.",
        default=DEFAULT_REPOS_FILE
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        help="Path to the cache file.",
        default=DEFAULT_CACHE_FILE
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Path to the log file.",
        default=log_file_path # Use the path defined earlier
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG level logging."
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=int,
        help="Fuzzy matching threshold (0-100).",
        default=80
    )
    parser.add_argument(
        "--location-bias",
        type=float,
        help="Weight given to location matches",
        default=0.9
    )
    parser.add_argument(
        "--target-user",
        type=str,
        help="Target user or org's repo",
        default=None
    )
    args = parser.parse_args()

    # --- Configure Logging Level & File Handler Path ---
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    else:
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.INFO)

    # Update log file path if specified by argument
    if args.log_file != log_file_path:
        # Find and remove the default file handler
        default_fh = next((h for h in logger.handlers if isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file_path)), None)
        if default_fh:
            logger.removeHandler(default_fh)
            default_fh.close()
        # Add the new one
        new_file_handler = logging.FileHandler(args.log_file, encoding='utf-8')
        new_file_handler.setFormatter(log_formatter)
        new_file_handler.setLevel(logger.level)
        logger.addHandler(new_file_handler)
        logger.info(f"Logging to file: {args.log_file}")

    # --- Get Token ---
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
         logger.warning("GITHUB_TOKEN environment variable not set. Proceeding without authentication (expect low rate limits).")


    # --- Initialize and Run Scraper ---
    start_time = time.monotonic()
    logger.info(f"--- Starting Repolizer ---")
    logger.info(f"Using repos file: {args.repos_file.resolve()}")
    logger.info(f"Using cache file: {args.cache_file.resolve()}")

    try:
        scraper = GitHubRepoScraper(
            token=github_token,
            cache_duration_hours=args.cache_hours,
            max_workers=args.workers,
            repos_file=args.repos_file,
            cache_file=args.cache_file,
            fuzzy_match_threshold=args.fuzzy_threshold,
            location_bias=args.location_bias

        )

        # Define base search queries known to yield relevant results
        base_search_queries = []
        if args.target_user:
            base_search_queries = [f"user:{args.target_user} -fork:true"]
        else:
            base_search_queries = [
                "location:italy -fork:true",
                "location:italia -fork:true",
                'language:"jupyter notebook" location:italy -fork:true', # Example combo
                "topic:italy -fork:true",
                "topic:italia -fork:true",
                # Add more specific or broad queries as needed
                # "stars:>50 location:milan",
                # '".it" in:readme,description' # Search for .it TLD in text
            ]

        new_italian_repos = scraper.search_repos(
            base_queries=base_search_queries,
            additional_query=args.query,
            per_page=min(args.per_page, 100), # Cap per_page at 100
            max_pages=args.max_pages
        )

        logger.info(f"Search complete. Found {len(new_italian_repos)} potentially new Italian repositories.")

        scraper.save_repos(new_italian_repos)

    except Exception as e:
        logger.critical(f"An unhandled error occurred during scraping: {e}", exc_info=True)
        # Explicitly try saving cache on critical failure, atexit might not run depending on error
        if 'scraper' in locals() and isinstance(scraper, GitHubRepoScraper):
            logger.info("Attempting to save cache due to error...")
            scraper._save_cache() # Call the internal method directly

    finally:
        elapsed_time = time.monotonic() - start_time
        logger.info(f"--- Repolizer finished in {elapsed_time:.2f} seconds ---")
        # Cache saving is handled by atexit, but can call explicitly if needed:
        # if 'scraper' in locals() and isinstance(scraper, GitHubRepoScraper):
        #     scraper._save_cache()

if __name__ == "__main__":
    main()