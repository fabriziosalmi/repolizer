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
from contextlib import contextmanager
import platform
import signal

# Try importing RichHandler and Console
try:
    from rich.console import Console
    from rich.logging import RichHandler
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    RichHandler = None
    Console = None

# Configure logging
def setup_utils_logging(console: Optional['Console'] = None):
    """Set up logging for the utils module"""
    logger = logging.getLogger(__name__)

    if logger.handlers or (hasattr(logging.getLogger(), "root_handlers_configured") and
                          getattr(logging.getLogger(), "root_handlers_configured")):
        return logger

    logger.setLevel(logging.DEBUG)

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'debug.log')
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)

    if HAS_RICH and RichHandler and Console:
        console_instance = console or Console()
        console_handler = RichHandler(
            level=logging.INFO,
            rich_tracebacks=True,
            show_path=False,
            console=console_instance
        )
    else:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    file_handler.setFormatter(file_formatter)
    if not (HAS_RICH and RichHandler):
        console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_utils_logging(console=None)

CATEGORY_WEIGHTS = {
    "performance": 10,
    "licensing": 9,
    "ci_cd": 8,
    "community": 7,
    "code": 6,
    "maintainability": 5,
    "security": 4,
    "accessibility": 3,
    "testing": 2,
    "documentation": 1,
    "default": 1
}

class GitHubApiHandler:
    """
    Handler for GitHub API requests with intelligent rate limiting and retry logic
    """
    BASE_URL = "https://api.github.com"
    RETRY_STATUS_CODES = {403, 429, 500, 502, 503, 504}
    MAX_RETRIES = 8
    
    def __init__(self, token: Optional[str] = None, logger=None):
        self.token = token
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'repolizer-github-client'
        })
        
        if token:
            self.session.headers.update({'Authorization': f'token {token}'})
        
        self.rate_limits = {
            'core': {'limit': 60, 'remaining': 60, 'reset': 0},
            'search': {'limit': 10, 'remaining': 10, 'reset': 0},
            'graphql': {'limit': 0, 'remaining': 0, 'reset': 0},
            'integration_manifest': {'limit': 0, 'remaining': 0, 'reset': 0}
        }
        self.last_updated = 0
        self.lock = threading.RLock()
    
    def _update_rate_limits(self, headers: Dict[str, str]) -> None:
        with self.lock:
            if 'X-RateLimit-Limit' in headers:
                resource = 'core'
                if 'X-RateLimit-Resource' in headers:
                    resource = headers['X-RateLimit-Resource']
                
                self.rate_limits[resource] = {
                    'limit': int(headers.get('X-RateLimit-Limit', 0)),
                    'remaining': int(headers.get('X-RateLimit-Remaining', 0)),
                    'reset': int(headers.get('X-RateLimit-Reset', 0))
                }
                
                self.last_updated = time.time()
                
                if self.rate_limits[resource]['remaining'] < max(5, self.rate_limits[resource]['limit'] * 0.1):
                    reset_time = datetime.fromtimestamp(self.rate_limits[resource]['reset']).strftime('%H:%M:%S')
                    self.logger.warning(
                        f"GitHub API rate limit for {resource} is running low: "
                        f"{self.rate_limits[resource]['remaining']}/{self.rate_limits[resource]['limit']} "
                        f"remaining, resets at {reset_time}"
                    )
    
    def _calculate_wait_time(self, resource: str = 'core') -> int:
        with self.lock:
            if self.rate_limits[resource]['remaining'] > 0:
                return 0
                
            reset_time = self.rate_limits[resource]['reset']
            current_time = time.time()
            
            wait_time = reset_time - current_time + 2
            
            return max(0, int(wait_time))
    
    def _exponential_backoff(self, retry_count: int) -> float:
        base_delay = min(60, 2 ** retry_count)
        jitter = base_delay * (random.uniform(0.8, 1.2))
        return jitter
    
    def request(self, method: str, url: str, resource: str = 'core', **kwargs) -> Optional[requests.Response]:
        if not urlparse(url).netloc:
            url = f"{self.BASE_URL}/{url.lstrip('/')}"
        
        retry_count = 0
        
        while retry_count <= self.MAX_RETRIES:
            wait_time = self._calculate_wait_time(resource)
            if wait_time > 0:
                self.logger.warning(f"Rate limit reached for {resource}. Waiting {wait_time}s for reset.")
                time.sleep(wait_time)
            
            try:
                response = self.session.request(method, url, **kwargs)
                
                self._update_rate_limits(response.headers)
                
                if response.status_code < 400:
                    return response
                
                if response.status_code in self.RETRY_STATUS_CODES:
                    if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                        retry_after = int(response.headers.get('Retry-After', '60'))
                        self.logger.warning(f"Rate limit exceeded. Waiting for {retry_after}s as specified in headers.")
                        time.sleep(retry_after)
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', '60'))
                        self.logger.warning(f"Too many requests. Waiting for {retry_after}s as specified in headers.")
                        time.sleep(retry_after)
                    else:
                        wait = self._exponential_backoff(retry_count)
                        self.logger.warning(
                            f"GitHub API request failed with status {response.status_code}. "
                            f"Retry {retry_count+1}/{self.MAX_RETRIES+1} in {wait:.2f}s"
                        )
                        time.sleep(wait)
                    
                    retry_count += 1
                    continue
                
                self.logger.error(f"⚠️ GitHub API request failed with status {response.status_code}: {response.text}")
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
                wait = self._exponential_backoff(retry_count)
                self.logger.warning(f"Network error in GitHub API request: {e}. Retry {retry_count+1}/{self.MAX_RETRIES+1} in {wait:.2f}s")
                time.sleep(wait)
                retry_count += 1
                continue
            
            except Exception as e:
                self.logger.error(f"⚠️ Unexpected error in GitHub API request: {e}")
                raise
        
        self.logger.error(f"⚠️ GitHub API request failed after {self.MAX_RETRIES+1} attempts: {url}")
        return None
    
    def get(self, url: str, resource: str = 'core', **kwargs) -> Optional[Dict]:
        response = self.request('GET', url, resource, **kwargs)
        if response and response.status_code < 400:
            return response.json()
        return None
    
    def get_all_pages(self, url: str, resource: str = 'core', **kwargs) -> List[Dict]:
        all_items = []
        page = 1
        per_page = kwargs.pop('per_page', 100)
        
        while True:
            params = kwargs.pop('params', {})
            params.update({'page': page, 'per_page': per_page})
            
            response = self.request('GET', url, resource, params=params, **kwargs)
            
            if not response or response.status_code >= 400:
                self.logger.error(f"⚠️ Failed to get page {page} of {url}")
                break
            
            items = response.json()
            
            if isinstance(items, dict) and 'items' in items:
                page_items = items['items']
            elif isinstance(items, list):
                page_items = items
            else:
                page_items = [items]
            
            all_items.extend(page_items)
            
            if len(page_items) < per_page or 'next' not in response.links:
                break
            
            page += 1
        
        return all_items
    
    def get_remaining_rate_limit(self, resource: str = 'core') -> int:
        with self.lock:
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
        self.max_calls = max_calls
        self.time_period = time_period
        self.calls = {}
        self.lock = threading.RLock()
        self.backoff_factors = {}
        self.logger = logging.getLogger(__name__)
        self.github_handler = github_handler
    
    def wait_if_needed(self, category: str = 'default', resource: str = 'core') -> bool:
        if self.github_handler and category.startswith('github'):
            remaining = self.github_handler.get_remaining_rate_limit(resource)
            
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
            if category not in self.calls:
                self.calls[category] = []
                self.backoff_factors[category] = 1.0
            
            current_time = time.time()
            self.calls[category] = [t for t in self.calls[category] if current_time - t <= self.time_period]
            
            if len(self.calls[category]) >= self.max_calls:
                wait_time = self.backoff_factors[category] * (self.time_period / self.max_calls) * (1 + random.random() * 0.5)
                self.backoff_factors[category] = min(10.0, self.backoff_factors[category] * 1.5)
                
                self.logger.warning(
                    f"Rate limit approached for {category}. "
                    f"Waiting {wait_time:.2f}s (backoff={self.backoff_factors[category]:.1f})"
                )
                time.sleep(wait_time)
                
                self.calls[category].append(time.time())
                return True
            else:
                self.calls[category].append(current_time)
                
                if len(self.calls[category]) < (self.max_calls / 2):
                    self.backoff_factors[category] = max(1.0, self.backoff_factors[category] * 0.8)
                
                return False

def ensure_dependencies() -> Dict[str, any]:
    dependencies = {}

    required_deps = {
        "jsonlines": "jsonlines",
        "rich": ["rich.console", "rich.panel", "rich.progress", "rich.table", "rich.logging"],
        "gitpython": "git"
    }

    for package, modules in required_deps.items():
        if isinstance(modules, str):
            modules = [modules]

        for module_name in modules:
            try:
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
            except ImportError:
                logger.info(f"{module_name} module not found. Attempting to install {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
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
                    if '.' in module_name:
                        component_name = module_name.split('.')[-1].capitalize()
                        dependencies[component_name] = None
                    else:
                        dependencies[module_name] = None

    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
        from rich.table import Table
        from rich import print as rich_print
        from rich.logging import RichHandler

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
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    logger.debug(f"Created temporary directory: {temp_dir}")
    return temp_dir

def cleanup_directory(directory: str) -> bool:
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
    try:
        import git
        
        if os.path.exists(repo_dir):
            cleanup_directory(repo_dir)
        
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
    import jsonlines
    
    try:
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
    import jsonlines
    
    processed_ids = set()
    
    if not os.path.exists(results_path):
        logger.info(f"No results file found at {results_path}")
        return processed_ids
    
    if results_path.lower().endswith('.json'):
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = [data]
                    
                    for result in data:
                        if "repository" in result and "id" in result["repository"]:
                            processed_ids.add(result["repository"]["id"])
                            
                            if "full_name" in result["repository"]:
                                processed_ids.add(result["repository"]["full_name"])
                except json.JSONDecodeError as je:
                    logger.error(f"⚠️ Error parsing JSON file: {je}")
        except Exception as e:
            logger.error(f"⚠️ Error loading processed repository IDs from JSON: {e}")
    else:
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    try:
                        if line.strip():
                            result = json.loads(line)
                            if "repository" in result and "id" in result["repository"]:
                                processed_ids.add(result["repository"]["id"])
                                
                                if "full_name" in result["repository"]:
                                    processed_ids.add(result["repository"]["full_name"])
                    except json.JSONDecodeError as je:
                        logger.error(f"⚠️ Error parsing JSON at line {i+1}: {je}")
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
    Handles potential variations in naming (e.g., ci_cd vs cicd).

    Args:
        check_module: Module name (e.g., 'checks.documentation.readme')

    Returns:
        Category name (lowercase) or 'default' if not determinable.
    """
    if not isinstance(check_module, str):
        return "default"
    parts = check_module.lower().split('.')
    if len(parts) >= 2:
        category = parts[1]
        if category == "cicd":
            category = "ci_cd"
        return category
    return "default"

def requires_local_access(check: Dict) -> bool:
    check_module = check.get('module', '')
    category = get_check_category(check_module)
    
    if category:
        logger.debug(f"Check {check_module} (category: {category}) will use local access when available")
    else:
        logger.debug(f"Check {check_module} will use local access when available")
    
    return True

def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.3f}s"
    
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {seconds:.3f}s"
    
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {seconds:.3f}s"

def safe_fs_operation(func, *args, timeout=10, default=None, **kwargs):
    import platform
    import signal
    import threading
    import time
    
    func_name = getattr(func, '__name__', str(func))
    
    is_main_thread = threading.current_thread() is threading.main_thread()
    can_use_signal = platform.system() != 'Windows' and is_main_thread

    if can_use_signal:
        def handler(signum, frame):
            raise TimeoutException(f"Operation timed out after {timeout} seconds")

        original_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)

    try:
        if can_use_signal:
            result = func(*args, **kwargs)
            signal.alarm(0)
            return result
        else:
            start_time = time.time()
            result = func(*args, **kwargs)
            
            elapsed = time.time() - start_time
            if elapsed > timeout * 0.8:
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
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)

def safe_isdir(path, timeout=5):
    try:
        return safe_fs_operation(os.path.isdir, path, timeout=timeout, default=False)
    except Exception as e:
        logger.warning(f"Error checking if {path} is directory: {e}")
        return False

def safe_isfile(path, timeout=5):
    try:
        return safe_fs_operation(os.path.isfile, path, timeout=timeout, default=False)
    except Exception as e:
        logger.warning(f"Error checking if {path} is file: {e}")
        return False

def safe_exists(path, timeout=5):
    try:
        return safe_fs_operation(os.path.exists, path, timeout=timeout, default=False)
    except Exception as e:
        logger.warning(f"Error checking if {path} exists: {e}")
        return False

def safe_listdir(path, timeout=10):
    try:
        return safe_fs_operation(os.listdir, path, timeout=timeout, default=[])
    except Exception as e:
        logger.warning(f"Error listing directory {path}: {e}")
        return []

def safe_cleanup_directory(directory: str, timeout=30) -> bool:
    if not safe_exists(directory, timeout=5):
        return True
        
    try:
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
                
        return safe_fs_operation(do_cleanup, directory, timeout=timeout, default=False)
    except Exception as e:
        logger.error(f"⚠️ Error during cleanup of {directory}: {e}")
        return False

def monitor_resource_usage(tag="", threshold_mb=500):
    import os
    import psutil
    
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        result = {
            "memory_mb": round(memory_mb, 2),
            "cpu_percent": process.cpu_percent(interval=0.1),
            "num_threads": process.num_threads(),
            "open_files": len(process.open_files())
        }
        
        if memory_mb > threshold_mb:
            tag_str = f" [{tag}]" if tag else ""
            logger.warning(f"High memory usage{tag_str}: {memory_mb:.2f} MB, {result['num_threads']} threads")
        
        return result
    except:
        return {"memory_mb": 0, "cpu_percent": 0, "num_threads": 0, "open_files": 0}

has_filesystem_utils = False 

try:
    logger.debug("Using filesystem_utils for timeout protection")
    has_filesystem_utils = True
except ImportError:
    logger.info("filesystem_utils module not available, using internal fallbacks")
    
if not has_filesystem_utils:
    @contextmanager
    def time_limit(seconds):
        is_main_thread = threading.current_thread() is threading.main_thread()
        can_use_signal = platform.system() != 'Windows' and is_main_thread
        original_handler = None

        if can_use_signal:
            def signal_handler(signum, frame):
                logger.warning(f"File processing triggered timeout after {seconds} seconds.")
                raise TimeoutError(f"File processing timed out after {seconds} seconds")
            try:
                original_handler = signal.signal(signal.SIGALRM, signal_handler)
                signal.alarm(seconds)
            except ValueError as e:
                 logger.warning(f"Could not set signal alarm: {e}. Timeout protection may be limited.")
                 can_use_signal = False
            except Exception as e:
                 logger.error(f"⚠️ Unexpected error setting signal alarm: {e}", exc_info=True)
                 can_use_signal = False
        else:
            pass

        try:
            yield
        finally:
            if can_use_signal:
                try:
                    signal.alarm(0)
                    if original_handler is not None:
                        signal.signal(signal.SIGALRM, original_handler)
                except Exception as e:
                     logger.error(f"⚠️ Error restoring signal handler: {e}", exc_info=True)

    def safe_fs_operation(func, *args, timeout=5, default=None, **kwargs):
        func_name = getattr(func, '__name__', 'unknown_fs_operation')
        try:
            with time_limit(timeout):
                return func(*args, **kwargs)
        except TimeoutError:
            logger.warning(f"Filesystem operation timed out: {func_name}")
            return default
        except Exception as e:
            logger.warning(f"Filesystem operation failed: {func_name}: {e}")
            return default

if not hasattr(__builtins__, 'TimeoutError'):
    class TimeoutError(Exception):
        pass

class TimeoutException(Exception):
    pass

def get_results_file_info(filename: str = 'results.jsonl') -> Dict[str, Any]:
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
        mtime = None

    return {'path': file_path_to_use, 'mtime': mtime}

def calculate_weighted_score(results: List[Dict]) -> float:
    """
    Calculates the overall weighted health score based on check results and category weights.

    Args:
        results: A list of dictionaries, where each dictionary represents
                 the result of a single check and must contain at least
                 'module' (str) and 'score' (float/int, 0-100).

    Returns:
        The weighted average score (0-100), or 0.0 if no valid results are found.
    """
    total_weighted_score = 0.0
    total_weight = 0.0

    if not results:
        logger.warning("Cannot calculate weighted score: No results provided.")
        return 0.0

    for result in results:
        if not isinstance(result, dict):
            logger.warning(f"Skipping invalid result item (not a dict): {result}")
            continue

        module = result.get('module')
        score = result.get('score')

        if module is None or score is None:
            logger.warning(f"Skipping result with missing 'module' or 'score': {result}")
            continue

        try:
            score = float(score)
            if not (0 <= score <= 100):
                 logger.warning(f"Skipping result with score out of range (0-100): {score} in {module}")
                 continue
        except (ValueError, TypeError):
            logger.warning(f"Skipping result with non-numeric score: {score} in {module}")
            continue

        category = get_check_category(module)
        weight = CATEGORY_WEIGHTS.get(category, CATEGORY_WEIGHTS["default"])

        if weight > 0:
            total_weighted_score += score * weight
            total_weight += weight
            logger.debug(f"Check: {module}, Category: {category}, Score: {score}, Weight: {weight}")
        else:
             logger.debug(f"Check: {module}, Category: {category}, Score: {score}, Weight: {weight} - Excluded")


    if total_weight == 0:
        logger.warning("Cannot calculate weighted score: Total weight of applicable checks is zero.")
        return 0.0

    weighted_average = total_weighted_score / total_weight
    final_score = max(0.0, min(100.0, weighted_average))

    logger.info(f"Calculated weighted score: {final_score:.2f} (Total Weighted Score: {total_weighted_score:.2f}, Total Weight: {total_weight:.2f})")
    return final_score

