import requests
import re
import time
import os
import json
import logging
import argparse
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("repolizer.log")
    ]
)
logger = logging.getLogger("repolizer")

class GitHubRepoScraper:
    def __init__(self, token=None, cache_duration=24, max_workers=5):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"
        
        self.max_workers = max_workers
        self.cache_duration = cache_duration  # hours
        
        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Expanded list of Italian words for language detection
        self.italian_words = [
            "ciao", "buongiorno", "progetto", "documentazione", "utilizzo",
            "installazione", "configurazione", "esempio", "questo", "quello",
            "come", "italiano", "sviluppo", "funzionalità", "istruzioni",
            "grazie", "prego", "sviluppatore", "libreria", "strumento", 
            "applicazione", "codice", "sorgente", "contribuire", "licenza",
            "versione", "aggiornamento", "interfaccia", "utente", "dati",
            "scaricare", "implementazione", "comunità", "supporto", "problema"
        ]
        
        # Expanded Italian cities and regions for location detection
        self.italian_locations = [
            "italia", "italy", "milano", "rome", "roma", "napoli", "torino",
            "florence", "firenze", "bologna", "palermo", "genova", "sicilia", 
            "sardegna", "toscana", "lazio", "lombardia", "veneto", "piemonte",
            "catania", "bari", "verona", "padova", "trieste", "cagliari",
            "brescia", "parma", "modena", "pisa", "siena", "perugia", "puglia",
            "calabria", "campania", "liguria", "abruzzo", "umbria", "marche",
            "emilia-romagna", "friuli", "trentino", "alto adige", "valle d'aosta"
        ]
        
        self.repos_file = Path("/Users/fab/GitHub/repolizer/repos.txt")
        self.cache_file = Path("/Users/fab/GitHub/repolizer/cache.json")
        
        self.cache = self._load_cache()
        self.existing_repos = self._load_existing_repos()
    
    def _load_existing_repos(self):
        if not self.repos_file.exists():
            return set()
        
        with open(self.repos_file, "r") as f:
            return {line.strip() for line in f if line.strip()}
    
    def _load_cache(self):
        if not self.cache_file.exists():
            return {}
            
        try:
            with open(self.cache_file, "r") as f:
                cache = json.load(f)
            
            # Filter out expired cache entries
            current_time = datetime.now()
            cache = {k: v for k, v in cache.items() 
                    if datetime.fromisoformat(v.get('timestamp', '2000-01-01')) > 
                    current_time - timedelta(hours=self.cache_duration)}
                    
            return cache
        except Exception as e:
            logger.warning(f"Could not load cache: {e}")
            return {}
    
    def _save_cache(self):
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")
    
    def _get_with_cache(self, url, params=None):
        """Make a GET request with caching support"""
        cache_key = f"{url}?{json.dumps(params or {})}"
        
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            logger.debug(f"Cache hit for {url}")
            return cache_entry['data']
            
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Save to cache
            self.cache[cache_key] = {
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            
            # Check rate limit
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 10:
                    logger.warning(f"GitHub API rate limit running low: {remaining} requests remaining")
                    if remaining < 3:
                        reset_time = int(response.headers['X-RateLimit-Reset'])
                        sleep_time = reset_time - time.time() + 10
                        if sleep_time > 0:
                            logger.info(f"Rate limit almost exhausted. Sleeping for {sleep_time:.0f} seconds")
                            time.sleep(sleep_time)
            
            return data
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403 and 'rate limit exceeded' in e.response.text.lower():
                reset_time = int(e.response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time.time() + 10, 60)
                logger.warning(f"Rate limit exceeded. Sleeping for {sleep_time:.0f} seconds")
                time.sleep(sleep_time)
                return self._get_with_cache(url, params)
            elif e.response.status_code == 404:
                logger.warning(f"Resource not found: {url}")
                return None
            else:
                logger.error(f"HTTP error: {e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _is_italian_user(self, user_info):
        if not user_info:
            return False
            
        # Check location
        location = user_info.get("location", "").lower()
        if location and any(loc in location for loc in self.italian_locations):
            return True
            
        # Check name or bio for Italian hints
        name = user_info.get("name", "").lower()
        bio = user_info.get("bio", "").lower() if user_info.get("bio") else ""
        
        combined_text = f"{name} {bio}"
        return any(word in combined_text for word in self.italian_words)
    
    def _is_italian_org(self, org_info):
        if not org_info:
            return False
            
        # Check location
        location = org_info.get("location", "").lower()
        if location and any(loc in location for loc in self.italian_locations):
            return True
            
        # Check name, description or website for Italian hints
        name = org_info.get("name", "").lower()
        description = org_info.get("description", "").lower() if org_info.get("description") else ""
        website = org_info.get("blog", "").lower() if org_info.get("blog") else ""
        
        combined_text = f"{name} {description} {website}"
        
        # Check for .it domains
        if ".it" in website:
            return True
            
        return any(word in combined_text for word in self.italian_words)
    
    def _has_italian_content(self, repo_name):
        try:
            # Check README content
            readme_url = f"{self.base_url}/repos/{repo_name}/readme"
            readme_resp = self._get_with_cache(readme_url)
            
            if readme_resp and 'download_url' in readme_resp:
                content = self.session.get(readme_resp["download_url"]).text.lower()
                # Count Italian words in content
                italian_word_count = sum(1 for word in self.italian_words if word in content)
                
                # If we find multiple Italian words, it's likely Italian content
                if italian_word_count >= 3:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking Italian content for {repo_name}: {e}")
            return False
    
    def _process_repo(self, repo):
        """Process a single repository to determine if it's Italian"""
        full_name = repo["full_name"]
        
        # Skip if already in our list
        if full_name in self.existing_repos:
            return None
        
        # Check if owner is Italian
        owner = repo["owner"]
        owner_url = owner["url"]
        owner_type = owner["type"]
        
        owner_info = self._get_with_cache(owner_url)
        
        is_italian = False
        if owner_info:
            if owner_type == "User":
                is_italian = self._is_italian_user(owner_info)
            else:  # Organization
                is_italian = self._is_italian_org(owner_info)
        
        # If not identified as Italian by user/org, check content
        if not is_italian:
            is_italian = self._has_italian_content(full_name)
        
        if is_italian:
            logger.info(f"Found Italian repo: {full_name}")
            return full_name
        
        return None
    
    def search_repos(self, query=None, per_page=30, max_pages=10):
        new_repos = []
        
        # Initial search parameters
        search_queries = [
            "location:italy",
            "location:italia",
            "language:italian",
            ".it"
        ]
        
        if query:
            search_queries.append(query)
        
        for search_query in search_queries:
            logger.info(f"Searching repositories with query: {search_query}")
            page = 1
            while page <= max_pages:
                params = {
                    "q": search_query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page
                }
                
                search_url = f"{self.base_url}/search/repositories"
                response_data = self._get_with_cache(search_url, params)
                
                if not response_data:
                    break
                
                repos_data = response_data.get("items", [])
                if not repos_data:
                    break
                
                logger.info(f"Processing page {page} with {len(repos_data)} repositories")
                
                # Process repositories in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_repo = {executor.submit(self._process_repo, repo): repo for repo in repos_data}
                    for future in concurrent.futures.as_completed(future_to_repo):
                        result = future.result()
                        if result:
                            new_repos.append(result)
                
                page += 1
            
            # Save cache periodically
            self._save_cache()
        
        return new_repos
    
    def save_repos(self, repos):
        if not repos:
            logger.info("No new repositories found")
            return
            
        with open(self.repos_file, "a") as f:
            for repo in repos:
                if repo not in self.existing_repos:
                    f.write(f"{repo}\n")
                    self.existing_repos.add(repo)
        
        logger.info(f"Saved {len(repos)} new repositories to {self.repos_file}")
        
        # Final cache save
        self._save_cache()

def main():
    parser = argparse.ArgumentParser(description="Scrape GitHub for Italian repositories")
    parser.add_argument("--query", type=str, help="Additional query to search for", default=None)
    parser.add_argument("--max-pages", type=int, help="Maximum pages to fetch per query", default=10)
    parser.add_argument("--per-page", type=int, help="Results per page", default=30)
    parser.add_argument("--workers", type=int, help="Number of concurrent workers", default=5)
    parser.add_argument("--cache-hours", type=int, help="Cache duration in hours", default=24)
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Load GitHub token from .env file
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        logger.warning("No GITHUB_TOKEN found in .env file. API rate limits will be restricted.")
    
    start_time = time.time()
    logger.info("Starting GitHub repository search for Italian content")
    
    scraper = GitHubRepoScraper(
        token=github_token, 
        cache_duration=args.cache_hours,
        max_workers=args.workers
    )
    
    italian_repos = scraper.search_repos(
        query=args.query,
        per_page=args.per_page,
        max_pages=args.max_pages
    )
    
    logger.info(f"Found {len(italian_repos)} Italian repositories")
    scraper.save_repos(italian_repos)
    
    elapsed = time.time() - start_time
    logger.info(f"Scraping completed in {elapsed:.1f} seconds")

if __name__ == "__main__":
    main()
