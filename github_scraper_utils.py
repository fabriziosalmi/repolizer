"""
Utility functions for the GitHub scraper.
This module contains reusable components extracted from the main scraper.
"""

import asyncio
import aiohttp
import logging
import json
import os
import yaml
import re
from typing import List, Dict, Optional, Any, Tuple, Union
from datetime import datetime, timedelta, date

# --- Token Validation Functions ---

async def validate_token(token: str, logger: logging.Logger) -> bool:
    """Validate a single GitHub token and log the result."""
    url = "https://api.github.com/user"
    headers = {
        "User-Agent": "TokenValidator/1.0",
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"Token validation successful (ending with ...{token[-4:]})")
                    # Add more detailed information about the token
                    user_data = await response.json()
                    if user_data and 'login' in user_data:
                        logger.info(f"Token authenticated as user: {user_data['login']}")
                    return True
                else:
                    error_data = await response.text()
                    logger.warning(f"Token validation failed (ending with ...{token[-4:]}): Status {response.status}")
                    logger.debug(f"Token validation error details: {error_data[:200]}")
                    return False
    except Exception as e:
        logger.warning(f"Token validation error for token ending with ...{token[-4:]}: {e}")
        return False

async def validate_tokens(tokens: List[str], logger: logging.Logger) -> List[str]:
    """Validate a list of GitHub tokens and return only valid ones."""
    valid_tokens = []
    
    if not tokens:
        logger.warning("No tokens provided for validation")
        return valid_tokens
        
    logger.info(f"Validating {len(tokens)} GitHub token(s)...")
    
    for token in tokens:
        if await validate_token(token, logger):
            valid_tokens.append(token)
        else:
            logger.warning(f"Token ending with ...{token[-4:]} is invalid and will be skipped")
    
    logger.info(f"Token validation complete. {len(valid_tokens)}/{len(tokens)} tokens are valid.")
    return valid_tokens

# --- Configuration Loading ---

def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration from a YAML file."""
    if not os.path.exists(config_path):
        logging.warning(f"Configuration file not found at: {config_path}")
        return {}
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logging.info(f"Loaded configuration from {config_path}")
            return config if config else {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {config_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error reading config file {config_path}: {e}")
        return {}

# --- Logging Setup ---

def setup_logging(config: Dict[str, Any], cli_log_level: Optional[str] = None) -> logging.Logger:
    """Configures logging based on YAML and CLI override."""
    log_config = config.get('logging', {})
    log_level_str = cli_log_level or log_config.get('default_level', 'info')
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Basic configuration for now - focusing on level and console output
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]  # Add file handlers etc. based on config if needed
    )
    
    logger = logging.getLogger("github_scraper")
    logger.setLevel(log_level)
    
    # Add a file handler if specified in config
    if log_config.get('destinations'):
        for dest in log_config.get('destinations', []):
            if dest.get('type') == 'file' and dest.get('path') and dest.get('enabled', True):
                try:
                    # Ensure log directory exists
                    log_dir = os.path.dirname(dest['path'])
                    if log_dir and not os.path.exists(log_dir):
                        os.makedirs(log_dir, exist_ok=True)
                        
                    file_handler = logging.FileHandler(dest['path'])
                    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                    logger.addHandler(file_handler)
                    logger.info(f"Added log file: {dest['path']}")
                except Exception as e:
                    logger.error(f"Failed to set up log file {dest.get('path')}: {e}")
    
    logger.info(f"Logging level set to: {log_level_str.upper()}")
    return logger

# --- GitHub API Testing Utilities ---

async def test_search_query(query: str, token: Optional[str] = None, quiet: bool = False) -> Tuple[int, Optional[Dict]]:
    """Test GitHub search API with a query string and return status code and data."""
    url = "https://api.github.com/search/repositories"
    headers = {
        "User-Agent": "GitHubAPIDiagnostic/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
    
    params = {"q": query, "per_page": 5}
    
    if not quiet:
        print(f"\n=== TESTING SEARCH QUERY: '{query}' ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                status = resp.status
                if not quiet:
                    print(f"Status: {status} {resp.reason}")
                
                if status == 200:
                    data = await resp.json()
                    total_count = data.get("total_count", 0)
                    items = data.get("items", [])
                    
                    if not quiet:
                        print(f"Total results: {total_count}")
                        print(f"First {len(items)} repositories:")
                        for i, repo in enumerate(items):
                            print(f"{i+1}. {repo.get('full_name')} - ⭐ {repo.get('stargazers_count')}")
                    
                    return status, data
                else:
                    error_text = await resp.text()
                    if not quiet:
                        print(f"Error: {error_text}")
                    
                    try:
                        error_data = json.loads(error_text)
                        return status, error_data
                    except:
                        return status, {"error": error_text}
        except Exception as e:
            if not quiet:
                print(f"Request failed: {e}")
            return 0, {"error": str(e)}

async def check_rate_limit(token: Optional[str] = None) -> Dict[str, Any]:
    """Check GitHub API rate limits for the given token or unauthenticated access."""
    url = "https://api.github.com/rate_limit"
    headers = {
        "User-Agent": "GitHubRateLimitChecker/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
    
    print("\n===== GitHub API Diagnostic =====")
    print(f"Time: {datetime.now()}")
    
    rate_info = {"core": {}, "search": {}}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rate_limits = data.get("resources", {})
                    
                    auth_type = "AUTHENTICATED" if token else "UNAUTHENTICATED"
                    print(f"\n=== {auth_type} RATE LIMITS ===")
                    
                    # Process core API limits
                    core = rate_limits.get("core", {})
                    core_limit = core.get("limit", 0)
                    core_remaining = core.get("remaining", 0)
                    core_reset = datetime.fromtimestamp(core.get("reset", 0))
                    print(f"Core API:  {core_remaining}/{core_limit} - Reset: {core_reset}")
                    rate_info["core"] = {
                        "limit": core_limit,
                        "remaining": core_remaining,
                        "reset": core_reset.isoformat()
                    }
                    
                    # Process search API limits
                    search = rate_limits.get("search", {})
                    search_limit = search.get("limit", 0)
                    search_remaining = search.get("remaining", 0)
                    search_reset = datetime.fromtimestamp(search.get("reset", 0))
                    print(f"Search API: {search_remaining}/{search_limit} - Reset: {search_reset}")
                    rate_info["search"] = {
                        "limit": search_limit,
                        "remaining": search_remaining,
                        "reset": search_reset.isoformat()
                    }
                    
                    return rate_info
                else:
                    error = await resp.text()
                    print(f"Rate limit check failed: {resp.status} - {error}")
                    return {"error": error}
        except Exception as e:
            print(f"Rate limit check failed: {e}")
            return {"error": str(e)}

# --- Query Building Utilities ---

def build_search_query(filters: Dict[str, Any], simple: bool = False) -> str:
    """Build a GitHub search query from filter parameters."""
    query_parts = []
    
    # Always include min_stars if present
    if "min_stars" in filters: 
        query_parts.append(f"stars:>={filters['min_stars']}")
    
    # Handle language filtering - simplified if requested
    if "languages" in filters and filters["languages"]:
        if simple or len(filters["languages"]) == 1:
            # Simple mode or single language - just use the first one
            query_parts.append(f"language:{filters['languages'][0]}")
        else:
            # Use the OR syntax for multiple languages
            lang_query = " OR ".join([f"language:{lang}" for lang in filters["languages"]])
            query_parts.append(f"({lang_query})")
    
    # Only add pushed_after if not in simple mode
    if "pushed_after_date" in filters and not simple:
        query_parts.append(f"pushed:>={filters['pushed_after_date']}")
    
    # Handle country-based filtering
    if "countries" in filters and filters["countries"] and not simple:
        if len(filters["countries"]) == 1:
            # Single country
            query_parts.append(f"location:{filters['countries'][0]}")
        else:
            # Multiple countries with OR
            country_query = " OR ".join([f"location:{country}" for country in filters["countries"]])
            query_parts.append(f"({country_query})")
    
    # Join all parts with spaces
    query = " ".join(query_parts) if query_parts else "is:public"
    return query

def parse_link_header(link_header: str) -> Dict[str, str]:
    """Parse GitHub API Link header to extract pagination URLs."""
    if not link_header:
        return {}
        
    links = {}
    try:
        matches = re.findall(r'<([^>]+)>;\s*rel="([^"]+)"', link_header)
        for url, rel in matches:
            links[rel] = url
        return links
    except Exception as e:
        logging.error(f"Error parsing Link header: {e}")
        return {}

# --- Dependency Checking ---

def check_dependencies() -> bool:
    """Check if all required dependencies are installed."""
    missing_deps = []
    
    try:
        import aiohttp
    except ImportError:
        missing_deps.append("aiohttp")
    
    try:
        import yaml
    except ImportError:
        missing_deps.append("pyyaml")
    
    try:
        import rich
    except ImportError:
        missing_deps.append("rich")
    
    if missing_deps:
        print("Error: The following required packages are missing:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install them using:")
        print(f"pip install {' '.join(missing_deps)}")
        return False
    
    return True
