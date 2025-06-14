"""
Utility functions for the CheckOrchestrator class.
These functions handle repository operations, file management, and dependency loading.
"""

import os
import sys
import logging
import shutil
import tempfile
import subprocess
import time
import threading
import random
import requests
import json
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Optional, List, Set, Any

# Try importing RichHandler and Console
try:
    from rich.console import Console
    from rich.logging import RichHandler
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    RichHandler = None # Define as None if not available
    Console = None # Define as None if not available

# Configure logging
def setup_utils_logging(console: Optional['Console'] = None): # Add console parameter
    """Set up logging for the utils module"""
    logger = logging.getLogger(__name__)

    # Skip if root logger has handlers or this logger already has handlers
    if logger.handlers or (hasattr(logging.getLogger(), "root_handlers_configured") and
                          getattr(logging.getLogger(), "root_handlers_configured")):
        return logger

    logger.setLevel(logging.DEBUG)

    # Create log directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Create file handler for debug.log
    log_file = os.path.join(log_dir, 'debug.log')
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)

    # Create console handler (use RichHandler if available)
    if HAS_RICH and RichHandler and Console: # Check for Console too
        # Use the provided console instance if available, otherwise create one
        console_instance = console or Console() # Now Console should be defined
        console_handler = RichHandler(
            level=logging.INFO,
            rich_tracebacks=True,
            show_path=False,
            console=console_instance # Use the console instance
        )
    else:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

    # Create formatters (only needed for file handler and fallback console handler)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter( # Used only if RichHandler is not available
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add formatters to handlers
    file_handler.setFormatter(file_formatter)
    if not (HAS_RICH and RichHandler): # Only set formatter if not using RichHandler
        console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Get logger (pass None initially, it will create its own console if needed)
logger = setup_utils_logging(console=None)

class GitHubApiHandler:
    """
    Handler for GitHub API requests with intelligent rate limiting and retry logic
    """
    BASE_URL = "https://api.github.com"
    RETRY_STATUS_CODES = {403, 429, 500, 502, 503, 504}
    MAX_RETRIES = 8
    
    def __init__(self, token: Optional[str] = None, logger=None):
        """
        Initialize GitHub API handler
        
        Args:
            token: GitHub API token
            logger: Logger instance
        """
        self.token = token
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'repolizer-github-client'
        })
        
        if token:
            self.session.headers.update({'Authorization': f'token {token}'})
        
        # Rate limit tracking
        self.rate_limits = {
            'core': {'limit': 60, 'remaining': 60, 'reset': 0},
            'search': {'limit': 10, 'remaining': 10, 'reset': 0},
            'graphql': {'limit': 0, 'remaining': 0, 'reset': 0},
            'integration_manifest': {'limit': 0, 'remaining': 0, 'reset': 0}
        }
        self.last_updated = 0
        self.lock = threading.RLock()
    
    def _update_rate_limits(self, headers: Dict[str, str]) -> None:
        """
        Update rate limit information from API headers
        
        Args:
            headers: Response headers from GitHub API
        """
        with self.lock:
            # Extract rate limit info
            if 'X-RateLimit-Limit' in headers:
                resource = 'core'  # Default resource
                # Determine which resource this is for
                if 'X-RateLimit-Resource' in headers:
                    resource = headers['X-RateLimit-Resource']
                
                # Update our tracking
                self.rate_limits[resource] = {
                    'limit': int(headers.get('X-RateLimit-Limit', 0)),
                    'remaining': int(headers.get('X-RateLimit-Remaining', 0)),
                    'reset': int(headers.get('X-RateLimit-Reset', 0))
                }
                
                self.last_updated = time.time()
                
                # Log if we're running low
                if self.rate_limits[resource]['remaining'] < max(5, self.rate_limits[resource]['limit'] * 0.1):
                    reset_time = datetime.fromtimestamp(self.rate_limits[resource]['reset']).strftime('%H:%M:%S')
                    self.logger.warning(
                        f"GitHub API rate limit for {resource} is running low: "
                        f"{self.rate_limits[resource]['remaining']}/{self.rate_limits[resource]['limit']} "
                        f"remaining, resets at {reset_time}"
                    )
    
    def _calculate_wait_time(self, resource: str = 'core') -> int:
        """
        Calculate how long to wait for rate limit reset
        
        Args:
            resource: GitHub API resource ('core', 'search', etc.)
            
        Returns:
            Number of seconds to wait
        """
        with self.lock:
            # If we have requests remaining, no need to wait
            if self.rate_limits[resource]['remaining'] > 0:
                return 0
                
            # Calculate time until reset
            reset_time = self.rate_limits[resource]['reset']
            current_time = time.time()
            
            # Add a small buffer to ensure reset has occurred
            wait_time = reset_time - current_time + 2
            
            return max(0, int(wait_time))
    
    def _exponential_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff time with jitter
        
        Args:
            retry_count: Current retry attempt number
            
        Returns:
            Time to wait in seconds
        """
        # Base backoff: 1s, 2s, 4s, 8s, 16s, 32s, 64s, 128s
        base_delay = min(60, 2 ** retry_count)
        # Add jitter: +/- 20%
        jitter = base_delay * (random.uniform(0.8, 1.2))
        return jitter
    
    def request(self, method: str, url: str, resource: str = 'core', **kwargs) -> Optional[requests.Response]:
        """
        Make a GitHub API request with automatic retry and rate limit handling
        
        Args:
            method: HTTP method (GET, POST, etc)
            url: URL to request (can be full URL or relative path)
            resource: GitHub API resource type ('core', 'search', etc.)
            **kwargs: Additional arguments to pass to requests.request
            
        Returns:
            Response object or None if all retries failed
        """
        # Ensure URL is absolute
        if not urlparse(url).netloc:
            url = f"{self.BASE_URL}/{url.lstrip('/')}"
        
        retry_count = 0
        
        while retry_count <= self.MAX_RETRIES:
            # Check if we need to wait for rate limit reset
            wait_time = self._calculate_wait_time(resource)
            if wait_time > 0:
                self.logger.warning(f"Rate limit reached for {resource}. Waiting {wait_time}s for reset.")
                time.sleep(wait_time)
            
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Update rate limits from response headers
                self._update_rate_limits(response.headers)
                
                # Check for success
                if response.status_code < 400:
                    return response
                
                # Handle specific error codes
                if response.status_code in self.RETRY_STATUS_CODES:
                    # Specific handling for rate limiting
                    if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                        retry_after = int(response.headers.get('Retry-After', '60'))
                        self.logger.warning(f"Rate limit exceeded. Waiting for {retry_after}s as specified in headers.")
                        time.sleep(retry_after)
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', '60'))
                        self.logger.warning(f"Too many requests. Waiting for {retry_after}s as specified in headers.")
                        time.sleep(retry_after)
                    else:
                        # Server errors or other retryable errors
                        wait = self._exponential_backoff(retry_count)
                        self.logger.warning(
                            f"GitHub API request failed with status {response.status_code}. "
                            f"Retry {retry_count+1}/{self.MAX_RETRIES+1} in {wait:.2f}s"
                        )
                        time.sleep(wait)
                    
                    retry_count += 1
                    continue
                
                # Non-retryable error
                self.logger.error(f"⚠️ GitHub API request failed with status {response.status_code}: {response.text}")
                # For certain status codes, provide more specific error information
                if response.status_code == 401:
                    self.logger.error("Authentication failed. Check your GitHub token.")
                elif response.status_code == 404:
                    self.logger.error("Resource not found. Check the API endpoint URL.")
                elif response.status_code == 403 and 'abuse' in response.text.lower():
                    self.logger.error("GitHub abuse detection triggered. Consider reducing request frequency.")
                elif response.status_code >= 500:
                    self.logger.error("GitHub server error. The service might be experiencing issues.")
                
                return response
                
            except (requests.ConnectionError, requests.Timeout) as e:
                # Network errors - retry with backoff
                wait = self._exponential_backoff(retry_count)
                self.logger.warning(f"Network error in GitHub API request: {e}. Retry {retry_count+1}/{self.MAX_RETRIES+1} in {wait:.2f}s")
                time.sleep(wait)
                retry_count += 1
                continue
            
            except Exception as e:
                # Other unexpected errors - log and don't retry
                self.logger.error(f"⚠️ Unexpected error in GitHub API request: {e}")
                raise
        
        self.logger.error(f"⚠️ GitHub API request failed after {self.MAX_RETRIES+1} attempts: {url}")
        return None
    
    def get(self, url: str, resource: str = 'core', **kwargs) -> Optional[Dict]:
        """
        Make a GET request to the GitHub API
        
        Args:
            url: API endpoint (can be relative to api.github.com)
            resource: API resource type ('core', 'search', etc.)
            **kwargs: Additional arguments to pass to requests.get
            
        Returns:
            JSON response as dictionary or None if request failed
        """
        response = self.request('GET', url, resource, **kwargs)
        if response and response.status_code < 400:
            return response.json()
        return None
    
    def get_all_pages(self, url: str, resource: str = 'core', **kwargs) -> List[Dict]:
        """
        Get all pages of paginated GitHub API results
        
        Args:
            url: API endpoint (can be relative to api.github.com)
            resource: API resource type ('core', 'search', etc.)
            **kwargs: Additional arguments to pass to requests.get
            
        Returns:
            List of all items from all pages
        """
        all_items = []
        page = 1
        per_page = kwargs.pop('per_page', 100)  # Default to 100 items per page
        
        while True:
            # Add pagination parameters
            params = kwargs.pop('params', {})
            params.update({'page': page, 'per_page': per_page})
            
            # Make the request
            response = self.request('GET', url, resource, params=params, **kwargs)
            
            if not response or response.status_code >= 400:
                self.logger.error(f"⚠️ Failed to get page {page} of {url}")
                break
            
            # Parse response
            items = response.json()
            
            # GitHub returns an object for some endpoints and a list for others
            if isinstance(items, dict) and 'items' in items:
                page_items = items['items']
            elif isinstance(items, list):
                page_items = items
            else:
                page_items = [items]
            
            # Add items to our result
            all_items.extend(page_items)
            
            # Check if we've reached the last page
            if len(page_items) < per_page or 'next' not in response.links:
                break
            
            page += 1
        
        return all_items
    
    def get_remaining_rate_limit(self, resource: str = 'core') -> int:
        """
        Get remaining rate limit for a resource
        
        Args:
            resource: GitHub API resource ('core', 'search', etc.)
            
        Returns:
            Number of requests remaining
        """
        with self.lock:
            # If data is older than 5 minutes, refresh it
            if time.time() - self.last_updated > 300:
                try:
                    rate_limit_data = self.get('/rate_limit')
                    if rate_limit_data and 'resources' in rate_limit_data:
                        for res, data in rate_limit_data['resources'].items():
                            if res in self.rate_limits:
                                self.rate_limits[res] = {
                                    'limit': data['limit'],
                                    'remaining': data['remaining'],
                                    'reset': data['reset']
                                }
                    self.last_updated = time.time()
                except Exception as e:
                    self.logger.error(f"⚠️ Failed to refresh rate limit data: {e}")
            
            return self.rate_limits.get(resource, {}).get('remaining', 0)

class RateLimiter:
    """
    Enhanced rate limiter for API calls with support for backoff and specific GitHub handling
    """
    def __init__(self, max_calls: int = 30, time_period: int = 60, github_handler: Optional[GitHubApiHandler] = None):
        """
        Initialize a rate limiter
        
        Args:
            max_calls: Maximum number of calls in the time period
            time_period: Time period in seconds
            github_handler: GitHub API handler for GitHub-specific rate limiting
        """
        self.max_calls = max_calls
        self.time_period = time_period
        self.calls = {}  # Dictionary of call timestamps by category
        self.lock = threading.RLock()
        self.backoff_factors = {}  # Backoff factors by category
        self.logger = logging.getLogger(__name__)
        self.github_handler = github_handler
    
    def wait_if_needed(self, category: str = 'default', resource: str = 'core') -> bool:
        """
        Wait if rate limit is being approached
        
        Args:
            category: Category of API call (for logging)
            resource: GitHub API resource (used only if github_handler is provided)
            
        Returns:
            True if waited, False if no wait was needed
        """
        # For GitHub API requests, use the GitHub handler if available
        if self.github_handler and category.startswith('github'):
            remaining = self.github_handler.get_remaining_rate_limit(resource)
            
            # If we're running low on remaining requests, wait for reset
            if remaining <= max(3, self.max_calls * 0.05):
                wait_time = self.github_handler._calculate_wait_time(resource)
                if wait_time > 0:
                    self.logger.warning(
                        f"GitHub API rate limit for {resource} is low ({remaining} remaining). "
                        f"Waiting {wait_time}s for reset."
                    )
                    time.sleep(wait_time)
                    return True
        
        with self.lock:
            # Initialize for this category if needed
            if category not in self.calls:
                self.calls[category] = []
                self.backoff_factors[category] = 1.0
            
            # Clean up old calls
            current_time = time.time()
            self.calls[category] = [t for t in self.calls[category] if current_time - t <= self.time_period]
            
            # If we're over the rate limit
            if len(self.calls[category]) >= self.max_calls:
                # Calculate time to wait with exponential backoff
                wait_time = self.backoff_factors[category] * (self.time_period / self.max_calls) * (1 + random.random() * 0.5)
                self.backoff_factors[category] = min(10.0, self.backoff_factors[category] * 1.5)  # Increase backoff factor
                
                self.logger.warning(
                    f"Rate limit approached for {category}. "
                    f"Waiting {wait_time:.2f}s (backoff={self.backoff_factors[category]:.1f})"
                )
                time.sleep(wait_time)
                
                # Record this call
                self.calls[category].append(time.time())
                return True
            else:
                # Record this call
                self.calls[category].append(current_time)
                
                # Reset backoff factor if we're well below limit
                if len(self.calls[category]) < (self.max_calls / 2):
                    self.backoff_factors[category] = max(1.0, self.backoff_factors[category] * 0.8)
                
                return False

def ensure_dependencies() -> Dict[str, any]:
    """
    Ensure all required dependencies are installed.
    Returns a dictionary of imported modules.
    """
    dependencies = {}

    # Required dependencies with their import names
    required_deps = {
        "jsonlines": "jsonlines",
        "rich": ["rich.console", "rich.panel", "rich.progress", "rich.table", "rich.logging"], # Add rich.logging
        "gitpython": "git"
    }

    for package, modules in required_deps.items():
        if isinstance(modules, str):
            modules = [modules]

        for module_name in modules:
            try:
                # Import the top-level package first if needed (e.g., 'rich')
                top_level_package = module_name.split('.')[0]
                __import__(top_level_package)

                # Then import the specific module/submodule
                module = __import__(module_name, fromlist=['*'])

                # Store the module itself, not its name
                if '.' in module_name:
                    # For submodules like rich.console, store the last part as key
                    # Handle rich.logging specifically for RichHandler
                    if module_name == "rich.logging":
                        dependencies['RichHandler'] = getattr(module, 'RichHandler', None)
                    else:
                        # Get the actual class/function if possible (e.g., Console)
                        component_name = module_name.split('.')[-1].capitalize()
                        dependencies[component_name] = getattr(module, component_name, module)

                else:
                    dependencies[module_name] = module
            except ImportError:
                logger.info(f"{module_name} module not found. Attempting to install {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    # Re-attempt import after installation
                    top_level_package = module_name.split('.')[0]
                    __import__(top_level_package)
                    module = __import__(module_name, fromlist=['*'])

                    if '.' in module_name:
                         if module_name == "rich.logging":
                            dependencies['RichHandler'] = getattr(module, 'RichHandler', None)
                         else:
                            component_name = module_name.split('.')[-1].capitalize()
                            dependencies[component_name] = getattr(module, component_name, module)
                    else:
                        dependencies[module_name] = module
                    logger.info(f"{package} module installed successfully.")
                except Exception as e:
                    logger.error(f"⚠️ Failed to install {package}: {e}")
                    # Don't raise here, let the main script handle missing deps if critical
                    if '.' in module_name:
                        component_name = module_name.split('.')[-1].capitalize()
                        dependencies[component_name] = None
                    else:
                        dependencies[module_name] = None


    # Import specific classes directly and add them to dependencies if not already added
    try:
        # Direct imports for rich components
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
        from rich.table import Table
        from rich import print as rich_print
        from rich.logging import RichHandler # Ensure RichHandler is imported here too

        # Add the actual classes to dependencies, checking if they exist first
        if 'Console' not in dependencies: dependencies['Console'] = Console
        if 'Panel' not in dependencies: dependencies['Panel'] = Panel
        if 'Progress' not in dependencies: dependencies['Progress'] = Progress
        if 'SpinnerColumn' not in dependencies: dependencies['SpinnerColumn'] = SpinnerColumn
        if 'TextColumn' not in dependencies: dependencies['TextColumn'] = TextColumn
        if 'BarColumn' not in dependencies: dependencies['BarColumn'] = BarColumn
        if 'TimeElapsedColumn' not in dependencies: dependencies['TimeElapsedColumn'] = TimeElapsedColumn
        if 'Table' not in dependencies: dependencies['Table'] = Table
        if 'rich_print' not in dependencies: dependencies['rich_print'] = rich_print
        if 'RichHandler' not in dependencies: dependencies['RichHandler'] = RichHandler

    except ImportError as e:
        logger.error(f"⚠️ Error importing from rich: {e}")

    return dependencies

def create_temp_directory(prefix: str = "repolizer_") -> str:
    """
    Create a temporary directory for repository clones.
    
    Args:
        prefix: Prefix for the temporary directory name
        
    Returns:
        Path to the created temporary directory
    """
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    logger.debug(f"Created temporary directory: {temp_dir}")
    return temp_dir

def cleanup_directory(directory: str) -> bool:
    """
    Remove a directory and its contents.
    
    Args:
        directory: Path to the directory to remove
        
    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(directory):
        return True
        
    try:
        shutil.rmtree(directory)
        logger.info(f"Removed directory: {directory}")
        return True
    except Exception as e:
        logger.error(f"⚠️ Failed to remove directory {directory}: {e}")
        return False

def clone_repository(clone_url: str, repo_dir: str, depth: int = 1) -> bool:
    """
    Clone a repository to a local directory.
    
    Args:
        clone_url: URL of the repository to clone
        repo_dir: Directory to clone the repository to
        depth: Depth of the clone (default: 1 for shallow clone)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure git is imported
        import git
        
        # Remove directory if it exists
        if os.path.exists(repo_dir):
            cleanup_directory(repo_dir)
        
        # Clone repository
        git.Repo.clone_from(clone_url, repo_dir, depth=depth)
        logger.debug(f"⚙️ Repository cloned successfully to {repo_dir}")
        return True
    except ImportError:
        logger.error("Git module not available. Make sure gitpython is installed.")
        return False
    except Exception as e:
        logger.error(f"Failed to clone repository to {repo_dir}: {e}")
        return False

def load_jsonl_file(file_path: str) -> List[Dict]:
    """
    Load data from a JSONL file.
    
    Args:
        file_path: Path to the JSONL file
        
    Returns:
        List of dictionaries with the loaded data
    """
    import jsonlines
    
    data = []
    
    if not os.path.exists(file_path):
        logger.error(f"⚠️ File not found: {file_path}")
        return data
    
    try:
        with jsonlines.open(file_path) as reader:
            data = list(reader)
        logger.info(f"Loaded {len(data)} items from {file_path}")
    except Exception as e:
        logger.error(f"⚠️ Error loading data from {file_path}: {e}")
    
    return data

def save_to_jsonl(data: Dict, file_path: str, append: bool = True) -> bool:
    """
    Save data to a JSONL file.
    
    Args:
        data: Dictionary to save
        file_path: Path to the JSONL file
        append: Whether to append to existing file (default: True)
        
    Returns:
        True if successful, False otherwise
    """
    import jsonlines
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        mode = 'a' if append and os.path.exists(file_path) else 'w'
        with jsonlines.open(file_path, mode=mode) as writer:
            writer.write(data)
        logger.debug(f"Data {'appended to' if mode == 'a' else 'saved to'} {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving data to {file_path}: {e}")
        return False

def extract_processed_repo_ids(results_path: str) -> Set[str]:
    """
    Extract repository IDs from results file (JSONL or JSON).
    
    Args:
        results_path: Path to the results file
        
    Returns:
        Set of repository IDs that have been processed
    """
    import jsonlines
    
    processed_ids = set()
    
    if not os.path.exists(results_path):
        logger.info(f"No results file found at {results_path}")
        return processed_ids
    
    # Determine file format based on extension
    if results_path.lower().endswith('.json'):
        # Handle JSON format
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    # Handle both single result and array of results
                    if not isinstance(data, list):
                        data = [data]
                    
                    for result in data:
                        if "repository" in result and "id" in result["repository"]:
                            processed_ids.add(result["repository"]["id"])
                            
                            # Also add full_name if available for additional uniqueness check
                            if "full_name" in result["repository"]:
                                processed_ids.add(result["repository"]["full_name"])
                except json.JSONDecodeError as je:
                    logger.error(f"⚠️ Error parsing JSON file: {je}")
        except Exception as e:
            logger.error(f"⚠️ Error loading processed repository IDs from JSON: {e}")
    else:
        # Read JSONL with more robust error handling
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    try:
                        if line.strip():  # Skip empty lines
                            # Parse each line individually
                            result = json.loads(line)
                            if "repository" in result and "id" in result["repository"]:
                                processed_ids.add(result["repository"]["id"])
                                
                                # Also add full_name if available for additional uniqueness check
                                if "full_name" in result["repository"]:
                                    processed_ids.add(result["repository"]["full_name"])
                    except json.JSONDecodeError as je:
                        # Log the error but continue processing
                        logger.error(f"⚠️ Error parsing JSON at line {i+1}: {je}")
                        # Try to extract repository ID using regex in case the JSON is only partially corrupt
                        import re
                        id_match = re.search(r'"id":\s*("[^"]+"|[\d]+)', line)
                        if id_match:
                            id_value = id_match.group(1).strip('"')
                            try:
                                if id_value.isdigit():
                                    processed_ids.add(int(id_value))
                                else:
                                    processed_ids.add(id_value)
                                logger.info(f"Extracted ID {id_value} from partially corrupt JSON line {i+1}")
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Could not convert extracted ID: {e}")
                    except Exception as e:
                        logger.error(f"⚠️ Error processing results file at line {i+1}: {e}")
        except Exception as e:
            logger.error(f"⚠️ Error loading processed repository IDs: {e}")
    
    logger.debug(f"Found {len(processed_ids)} already processed repositories")
    return processed_ids

def get_check_category(check_module: str) -> str:
    """
    Extract category from a check module name.
    
    Args:
        check_module: Module name (e.g., 'checks.documentation.readme')
        
    Returns:
        Category name or None if not found
    """
    parts = check_module.split('.')
    if len(parts) >= 2:
        return parts[1]
    return None

def requires_local_access(check: Dict) -> bool:
    """
    Determine if a check requires local repository access.
    All checks should prefer local repository access when possible,
    with API calls used only as a fallback.
    
    Args:
        check: Check dictionary with module name
        
    Returns:
        True if the check requires local access, False otherwise
    """
    # All checks should prefer local access when available
    # Extract category for logging purposes
    check_module = check.get('module', '')
    category = get_check_category(check_module)
    
    if category:
        logger.debug(f"Check {check_module} (category: {category}) will use local access when available")
    else:
        logger.debug(f"Check {check_module} will use local access when available")
    
    # Always return True to prioritize local access for all checks
    return True

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.3f}s"
    
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {seconds:.3f}s"
    
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {seconds:.3f}s"

def safe_fs_operation(func, *args, timeout=10, default=None, **kwargs):
    """
    Execute a filesystem operation with timeout protection.
    
    Args:
        func: Function to execute
        args: Positional arguments for the function
        timeout: Timeout in seconds
        default: Default value to return on timeout
        kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function or default value on timeout
    """
    import platform
    import signal
    import threading
    import time
    
    # Get function name for better logging
    func_name = getattr(func, '__name__', str(func))
    
    # Skip setting alarm on Windows or when not in main thread
    is_main_thread = threading.current_thread() is threading.main_thread()
    can_use_signal = platform.system() != 'Windows' and is_main_thread

    if can_use_signal:
        def handler(signum, frame):
            raise TimeoutException(f"Operation timed out after {timeout} seconds")

        # Set the timeout handler
        original_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)

    try:
        if can_use_signal:
            # With signal timeout
            result = func(*args, **kwargs)
            signal.alarm(0)  # Disable the alarm
            return result
        else:
            # Without signal timeout (simple execution with time tracking)
            start_time = time.time()
            result = func(*args, **kwargs)
            
            # Log warning if operation was slow but didn't hit timeout
            elapsed = time.time() - start_time
            if elapsed > timeout * 0.8:  # If took more than 80% of timeout
                logger.warning(f"Operation {func_name} was slow ({elapsed:.2f}s) but completed")
                
            return result
    except TimeoutException:
        logger.warning(f"Operation {func_name} timed out after {timeout}s")
        return default
    except Exception as e:
        logger.warning(f"Operation {func_name} failed: {e}")
        return default
    finally:
        if can_use_signal:
            signal.alarm(0)  # Ensure the alarm is disabled
            # Restore original handler
            signal.signal(signal.SIGALRM, original_handler)

def safe_isdir(path, timeout=5):
    """Safely check if a path is a directory with timeout protection."""
    try:
        return safe_fs_operation(os.path.isdir, path, timeout=timeout, default=False)
    except Exception as e:
        logger.warning(f"Error checking if {path} is directory: {e}")
        return False

def safe_isfile(path, timeout=5):
    """Safely check if a path is a file with timeout protection."""
    try:
        return safe_fs_operation(os.path.isfile, path, timeout=timeout, default=False)
    except Exception as e:
        logger.warning(f"Error checking if {path} is file: {e}")
        return False

def safe_exists(path, timeout=5):
    """Safely check if a path exists with timeout protection."""
    try:
        return safe_fs_operation(os.path.exists, path, timeout=timeout, default=False)
    except Exception as e:
        logger.warning(f"Error checking if {path} exists: {e}")
        return False

def safe_listdir(path, timeout=10):
    """Safely list directory contents with timeout protection."""
    try:
        return safe_fs_operation(os.listdir, path, timeout=timeout, default=[])
    except Exception as e:
        logger.warning(f"Error listing directory {path}: {e}")
        return []

def safe_cleanup_directory(directory: str, timeout=30) -> bool:
    """
    Safely clean up a directory with timeout protection.
    
    Args:
        directory: Path to the directory to clean
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    if not safe_exists(directory, timeout=5):
        # Already gone, consider success
        return True
        
    try:
        # Define a cleanup function that will be executed with timeout
        def do_cleanup(path):
            import shutil
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.remove(path)
                return True
            except Exception as e:
                logger.error(f"⚠️ Error cleaning up {path}: {e}")
                return False
                
        # Execute with timeout protection
        return safe_fs_operation(do_cleanup, directory, timeout=timeout, default=False)
    except Exception as e:
        logger.error(f"⚠️ Error during cleanup of {directory}: {e}")
        return False

def monitor_resource_usage(tag="", threshold_mb=500):
    """
    Monitor and log resource usage of the current process.
    Useful for detecting memory leaks during batch processing.
    
    Args:
        tag: Identifier for logging (e.g., repository name or check name)
        threshold_mb: Memory threshold in MB to trigger warnings
        
    Returns:
        Dictionary with memory usage information
    """
    import os
    import psutil
    
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
        
        # Create result with detailed memory info
        result = {
            "memory_mb": round(memory_mb, 2),
            "cpu_percent": process.cpu_percent(interval=0.1),
            "num_threads": process.num_threads(),
            "open_files": len(process.open_files())
        }
        
        # Log if memory usage is high
        if memory_mb > threshold_mb:
            tag_str = f" [{tag}]" if tag else ""
            logger.warning(f"High memory usage{tag_str}: {memory_mb:.2f} MB, {result['num_threads']} threads")
        
        return result
    except:
        # Fail silently if psutil isn't available
        return {"memory_mb": 0, "cpu_percent": 0, "num_threads": 0, "open_files": 0}

# Initialize has_filesystem_utils before the try block
has_filesystem_utils = False 

# Try to import the filesystem utilities if available
try:
    logger.debug("Using filesystem_utils for timeout protection")
    has_filesystem_utils = True # Set to True only if import succeeds
except ImportError:
    logger.info("filesystem_utils module not available, using internal fallbacks")
    # No need to set has_filesystem_utils = False here, it's already the default
    
# --- Filesystem Utilities (Fallback implementations) ---
# Only defined if filesystem_utils is not available
if not has_filesystem_utils:
    @contextmanager
    def time_limit(seconds):
        """Context manager for setting a timeout on file operations (Unix/MainThread only)."""
        is_main_thread = threading.current_thread() is threading.main_thread()
        can_use_signal = platform.system() != 'Windows' and is_main_thread
        original_handler = None # Initialize outside conditional block

        if can_use_signal:
            def signal_handler(signum, frame):
                logger.warning(f"File processing triggered timeout after {seconds} seconds.")
                raise TimeoutError(f"File processing timed out after {seconds} seconds")
            try:
                # Fix: Use signal_handler function instead of signal.SIGALRM as handler
                original_handler = signal.signal(signal.SIGALRM, signal_handler)
                signal.alarm(seconds)
            except ValueError as e: # Handle potential errors setting signal (e.g., in thread)
                 logger.warning(f"Could not set signal alarm: {e}. Timeout protection may be limited.")
                 can_use_signal = False # Disable signal restoration if setup failed
            except Exception as e:
                 logger.error(f"⚠️ Unexpected error setting signal alarm: {e}", exc_info=True)
                 can_use_signal = False
        else:
            # If signals can't be used, this context manager does nothing for timeout.
            pass # No setup needed

        try:
            yield
        finally:
            if can_use_signal:
                try:
                    signal.alarm(0) # Disable the alarm
                    # Restore the original signal handler if there was one
                    if original_handler is not None:
                        signal.signal(signal.SIGALRM, original_handler) # Restore the original handler
                except Exception as e:
                     logger.error(f"⚠️ Error restoring signal handler: {e}", exc_info=True)

    # ... other fallback functions ...

    def safe_fs_operation(func, *args, timeout=5, default=None, **kwargs):
        """Safely execute a filesystem operation with timeout."""
        # Use getattr for safer access to __name__ in case func is a mock
        func_name = getattr(func, '__name__', 'unknown_fs_operation')
        try:
            # Use the fallback time_limit context manager
            with time_limit(timeout):
                return func(*args, **kwargs)
        except TimeoutError:
            # func_name already defined
            logger.warning(f"Filesystem operation timed out: {func_name}")
            return default
        except Exception as e:
            # func_name already defined
            logger.warning(f"Filesystem operation failed: {func_name}: {e}")
            return default

# Define TimeoutError if not available in Python version
if not hasattr(__builtins__, 'TimeoutError'):
    class TimeoutError(Exception):
        """Custom error for timeout exceptions."""
        pass

# Define TimeoutException for compatibility with code that uses it
class TimeoutException(Exception):
    """Custom exception for timeouts."""
    pass

def get_results_file_info(filename: str = 'results.jsonl') -> Dict[str, Any]:
    """
    Gets the full path and modification time of the results file.
    Checks for sample file as fallback.

    Args:
        filename: The base name of the results file (e.g., 'results.jsonl').

    Returns:
        A dictionary containing 'path' (str) and 'mtime' (float or None).
        Returns None for path/mtime if neither file exists.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    primary_path = os.path.join(base_dir, filename)
    sample_filename = f"sample_{filename}"
    sample_path = os.path.join(base_dir, sample_filename)

    file_path_to_use = None
    mtime = None

    if os.path.exists(primary_path):
        file_path_to_use = primary_path
    elif os.path.exists(sample_path):
        file_path_to_use = sample_path
        logger.info(f"Using sample file: {sample_filename}")
    else:
        logger.warning(f"Neither {filename} nor {sample_filename} found.")
        return {'path': None, 'mtime': None}

    try:
        mtime = os.path.getmtime(file_path_to_use)
    except OSError as e:
        logger.error(f"⚠️ Error getting modification time for {file_path_to_use}: {e}")
        mtime = None # Ensure mtime is None on error

    return {'path': file_path_to_use, 'mtime': mtime}

