"""
Caching Check

Checks if the repository implements caching mechanisms to improve performance.
"""
import os
import re
import logging
import time
import threading
from typing import Dict, Any, List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logger = logging.getLogger(__name__)

def check_caching(repo_path: str = None, repo_data: Dict = None, timeout: int = 30) -> Dict[str, Any]:
    """
    Check for caching implementation in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        timeout: Maximum time in seconds to process a single file (default: 30)
        
    Returns:
        Dictionary with check results
    """
    start_time = time.time()
    result = {
        "has_caching": False,
        "caching_types": [],
        "caching_libraries": [],
        "language_specific_caching": {},
        "files_with_caching": 0,
        "total_files_checked": 0,
        "files_skipped": 0,
        "files_timed_out": 0,
        "file_examples": [],
        "caching_score": 0,
        "execution_time_ms": 0,
        "early_stopped": False
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Define language-specific caching patterns to look for
    caching_patterns = {
        # Python
        ".py": {
            "patterns": [
                # Function/method decorators
                r'@cache', r'@lru_cache', r'@cached_property', r'@memoize', r'@cached',
                # Redis
                r'import\s+redis', r'from\s+redis\s+import', r'Redis\(', r'.set\(', r'.get\(', r'.mset\(',
                # Memcached
                r'import\s+memcache', r'import\s+pylibmc', r'MemcachedClient', r'Client\(',
                # Django caching
                r'from\s+django\.core\.cache', r'cache\.set', r'cache\.get', r'@cache_page', r'@cached',
                # Flask caching
                r'from\s+flask_caching', r'Flask-Caching', r'Cache\(', r'@cache\.cached',
                # File caching
                r'open\(.*[\'"]\s*wb[\'"]\s*\)', r'pickle\.dump', r'json\.dump',
                # In-memory caching
                r'cache\s*=\s*{}'
            ],
            "libraries": ['functools.lru_cache', 'redis', 'memcache', 'pylibmc', 'django.core.cache', 'flask_caching', 'cachetools', 'dogpile.cache']
        },
        # JavaScript
        ".js": {
            "patterns": [
                # Browser caching
                r'localStorage\.', r'sessionStorage\.', r'caches\.open\(', r'IndexedDB',
                # Service worker
                r'navigator\.serviceWorker', r'serviceWorkerRegistration', r'workbox',
                # HTTP Caching
                r'Cache-Control', r'Etag', r'If-None-Match', r'If-Modified-Since',
                # React/Vue
                r'React\.memo', r'React\.useMemo', r'React\.useCallback', r'<memo>',
                r'computed\(', r'keepAlive',
                # Libraries
                r'import\s+.*\s+from\s+[\'"]cache[\'"]', r'new\s+Cache\(',
                r'memoize', r'memo', r'memoizeOne', r'reselect',
                # Redis/other
                r'redis\.createClient', r'createClient', r'client\.set', r'client\.get',
                # In-memory cache
                r'const\s+cache\s*=\s*{}'
            ],
            "libraries": ['localStorage', 'sessionStorage', 'Cache API', 'IndexedDB', 'ServiceWorker', 'workbox', 'redux-persist', 'node-cache', 'redis', 'memory-cache']
        },
        # Java
        ".java": {
            "patterns": [
                # Java caching annotations
                r'@Cacheable', r'@CacheEvict', r'@CachePut', r'@Caching', r'@EnableCaching',
                # Common caching libraries
                r'import\s+.*\.cache\.', r'Cache<', r'CacheManager', r'Ehcache', 
                r'Caffeine', r'LoadingCache', r'CacheBuilder',
                # Redis/memcached
                r'Jedis', r'RedisClient', r'RedisTemplate', r'StringRedisTemplate',
                r'MemcachedClient',
                # In-memory caching 
                r'Map<.*>.*cache', r'HashMap<.*>.*cache', r'ConcurrentHashMap<.*>.*cache'
            ],
            "libraries": ['Spring Cache', 'Ehcache', 'Caffeine', 'Guava Cache', 'JCache', 'Hazelcast', 'Redis', 'Memcached']
        },
        # C#
        ".cs": {
            "patterns": [
                r'IMemoryCache', r'IDistributedCache', r'AddMemoryCache', r'AddDistributedCache',
                r'Cache\.', r'MemoryCache\.', r'services\.AddResponseCaching',
                r'\[ResponseCache\]', r'RedisCache', r'StackExchangeRedisCache',
                r'CacheItemPriority', r'Dictionary<.*>.*[cC]ache'
            ],
            "libraries": ['IMemoryCache', 'IDistributedCache', 'ResponseCaching', 'StackExchange.Redis', 'NCache', 'LazyCache']
        },
        # Go
        ".go": {
            "patterns": [
                r'import\s+"github\.com/go-redis/redis"', r'cache\.New', r'sync\.Map',
                r'redis\.NewClient', r'client\.Set', r'client\.Get', r'mc\.Set', r'mc\.Get',
                r'(?:var|type).*Cache'
            ],
            "libraries": ['go-redis', 'bigcache', 'freecache', 'groupcache', 'sync.Map', 'ristretto']
        },
        # PHP
        ".php": {
            "patterns": [
                r'apcu_store', r'apcu_fetch', r'apc_store', r'apc_fetch',
                r'memcache_set', r'memcache_get', r'Memcache::', r'Memcached::',
                r'opcache_', r'->set\(', r'->get\(', r'\$cache->', r'Cache::'
            ],
            "libraries": ['APCu', 'OPCache', 'Memcached', 'Redis', 'Laravel Cache', 'Symfony Cache']
        },
        # Ruby
        ".rb": {
            "patterns": [
                r'Rails\.cache\.', r'cache\s+do', r'fragment_cache', r'low_card_cache',
                r'redis\.set', r'redis\.get', r'mem_cache', r'dalli', r'ActiveSupport::Cache'
            ],
            "libraries": ['Rails.cache', 'ActiveSupport::Cache', 'Redis', 'Dalli', 'Memcached', 'LowCardCache']
        }
    }
    
    # Add common extensions that should be treated like others
    for base_ext, patterns in list(caching_patterns.items()):
        if base_ext == ".js":
            caching_patterns[".jsx"] = patterns
            caching_patterns[".ts"] = patterns
            caching_patterns[".tsx"] = patterns
    
    # Configuration files that might indicate caching settings
    config_files = [
        # Web server configs
        "nginx.conf", "apache2.conf", "httpd.conf", ".htaccess",
        # CI/CD caching
        ".github/workflows/", ".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml",
        # Framework configs
        "package.json", "webpack.config.js", "nuxt.config.js", "next.config.js",
        "angular.json", "vue.config.js", "gatsby-config.js",
        # Python frameworks
        "settings.py", "app.py", "config.py", "flask_app.py", "wsgi.py",
        # Package managers
        "pom.xml", "build.gradle", "Gemfile", "composer.json", "go.mod",
        # Container configs
        "Dockerfile", "docker-compose.yml",
        # Service configs
        "redis.conf", "memcached.conf"
    ]
    
    # Caching configuration keywords in config files
    config_caching_keywords = [
        "cache", "etag", "expires", "max-age", "s-maxage", "no-cache", "public", "private",
        "last-modified", "redis", "memcached", "varnish", "cdn", "service-worker",
        "browser-cache", "http-cache", "store", "persist", "memoize", "lazy"
    ]
    
    total_files_checked = 0
    files_with_caching = 0
    files_skipped = 0
    files_timed_out = 0
    caching_types_found = set()
    caching_libraries_found = set()
    language_caching = {}
    file_examples = []
    
    # Skip directories
    skip_dirs = ['.git', 'node_modules', 'venv', '.venv', 'env', '.env', 'dist', 'build',
                'target', '.idea', '.vscode', '__pycache__', 'vendor', 'bin', 'obj']
    
    # Performance optimization parameters
    MAX_FILES_TO_CHECK = 5000  # Limit for very large repos
    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    
    # Thread-safe timeout handler for file operations
    class TimeoutException(Exception):
        pass
    
    def read_file_with_timeout(file_path, timeout_sec):
        """Read a file with timeout using thread-safe approach"""
        result = {'content': None, 'timed_out': False}
        
        def read_file():
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    result['content'] = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                result['content'] = None
        
        def timeout_handler():
            result['timed_out'] = True
        
        # Create a timer that will fire after timeout_sec
        timer = threading.Timer(timeout_sec, timeout_handler)
        
        try:
            timer.start()
            # Start a separate thread to read the file
            file_thread = threading.Thread(target=read_file)
            file_thread.daemon = True
            file_thread.start()
            file_thread.join(timeout_sec)  # Wait for the read thread to complete or timeout
            
            if result['timed_out'] or file_thread.is_alive():
                logger.warning(f"Timeout while reading file: {file_path}")
                return None
            
            return result['content']
        finally:
            timer.cancel()  # Make sure to cancel the timer
    
    def process_source_file(file_path, ext, patterns, libraries):
        """Process a single source code file"""
        nonlocal files_with_caching, total_files_checked, files_skipped, files_timed_out
        
        try:
            # Skip very large files
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                files_skipped += 1
                return None
            
            total_files_checked += 1
            
            content = read_file_with_timeout(file_path, timeout)
            if content is None:
                files_timed_out += 1
                return None
            
            # Look for caching patterns
            found_patterns = []
            for pattern in patterns:
                if re.search(pattern, content):
                    found_patterns.append(pattern)
            
            if not found_patterns:
                return None
            
            files_with_caching += 1
            
            # Identify libraries used
            found_libraries = set()
            for library in libraries:
                for pattern in found_patterns:
                    if library.lower() in pattern.lower() or library.lower() in content.lower():
                        found_libraries.add(library)
                        break
            
            # Identify caching types
            found_types = set()
            for pattern in found_patterns:
                if 'redis' in pattern.lower():
                    found_types.add('redis')
                elif 'memcache' in pattern.lower():
                    found_types.add('memcached')
                elif 'local' in pattern.lower() or 'session' in pattern.lower():
                    found_types.add('browser')
                elif 'file' in pattern.lower() or 'open(' in pattern.lower() or 'dump' in pattern.lower():
                    found_types.add('file')
                elif '@cache' in pattern.lower() or 'memoize' in pattern.lower() or 'lru' in pattern.lower():
                    found_types.add('function')
                elif 'etag' in pattern.lower() or 'control' in pattern.lower() or 'modified' in pattern.lower():
                    found_types.add('http')
                else:
                    found_types.add('in-memory')
            
            # Find a code snippet for an example
            example = None
            for pattern in found_patterns:
                match = re.search(pattern, content)
                if match:
                    line = content[max(0, match.start() - 50):min(len(content), match.end() + 50)]
                    example = {
                        "file": os.path.relpath(file_path, repo_path),
                        "pattern": pattern,
                        "snippet": line.strip()
                    }
                    break
            
            return {
                "patterns": found_patterns,
                "libraries": found_libraries,
                "types": found_types,
                "example": example,
                "language": ext[1:]  # Remove the dot
            }
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return None
    
    # Collect all potential files to analyze
    files_to_process = []
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for file in files:
            _, ext = os.path.splitext(file)
            
            # Check if this file extension has defined caching patterns
            if ext in caching_patterns:
                file_path = os.path.join(root, file)
                files_to_process.append((file_path, ext))
            
            # Also check if it's a config file we care about
            file_path = os.path.join(root, file)
            for config_pattern in config_files:
                if isinstance(config_pattern, str) and not config_pattern.endswith('/') and file == config_pattern:
                    files_to_process.append((file_path, "config"))
    
    # Check if we need to limit the number of files
    if len(files_to_process) > MAX_FILES_TO_CHECK:
        logger.info(f"Repository has too many files ({len(files_to_process)}), limiting to {MAX_FILES_TO_CHECK}")
        files_to_process = files_to_process[:MAX_FILES_TO_CHECK]
        result["early_stopped"] = True
    
    # Process files in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(os.cpu_count() * 2, 8)) as executor:
        futures = []
        
        # Submit source code file tasks
        for file_path, ext in files_to_process:
            if ext in caching_patterns:
                patterns = caching_patterns[ext]["patterns"]
                libraries = caching_patterns[ext]["libraries"]
                future = executor.submit(process_source_file, file_path, ext, patterns, libraries)
                futures.append(future)
            elif ext == "config":
                # Handle config files separately
                future = executor.submit(check_config_file, file_path, repo_path, config_caching_keywords, set(), [])
                futures.append((future, file_path))
        
        # Process results as they complete
        for future in as_completed(futures):
            if isinstance(future, tuple):
                # Config file result
                future_obj, file_path = future
                config_has_caching = future_obj.result()
                if config_has_caching:
                    files_with_caching += 1
                    caching_types_found.add("config")
                total_files_checked += 1
            else:
                # Source file result
                result_data = future.result()
                if result_data:
                    caching_types_found.update(result_data["types"])
                    caching_libraries_found.update(result_data["libraries"])
                    
                    # Track language-specific patterns
                    lang = result_data["language"]
                    if lang not in language_caching:
                        language_caching[lang] = set()
                    language_caching[lang].update(result_data["patterns"])
                    
                    # Add to file examples if we have fewer than 5
                    if result_data["example"] and len(file_examples) < 5:
                        file_examples.append(result_data["example"])
    
    # Convert language patterns to a serializable format
    lang_caching_dict = {}
    for lang, patterns in language_caching.items():
        lang_caching_dict[lang] = list(patterns)
    
    # Update result with findings
    result["has_caching"] = files_with_caching > 0
    result["caching_types"] = sorted(list(caching_types_found))
    result["caching_libraries"] = sorted(list(caching_libraries_found))
    result["language_specific_caching"] = lang_caching_dict
    result["files_with_caching"] = files_with_caching
    result["total_files_checked"] = total_files_checked
    result["files_skipped"] = files_skipped
    result["files_timed_out"] = files_timed_out
    result["file_examples"] = file_examples
    
    # Calculate caching score (0-100 scale)
    # A more granular scoring system
    score = 0
    
    # Base score for having caching
    if result["has_caching"]:
        # Start with 1 for a successful check with minimal implementation
        score = 1
        
        # Add points for caching coverage - more granular scale
        if total_files_checked > 0:
            # Realistic target: 10% of files might need caching in a typical repo
            coverage_ratio = min(1.0, files_with_caching / (total_files_checked * 0.1))
            # Scale from 1-60 points for coverage
            coverage_points = int(coverage_ratio * 59) + 1
            score = max(score, coverage_points)
        
        # Points for variety of caching types (redis, memcached, http, browser, etc.)
        # Each type is worth 5 points, up to 25 points
        variety_points = min(25, len(caching_types_found) * 5)
        
        # Points for using established libraries
        # Each library is worth 3 points, up to 15 points
        library_points = min(15, len(caching_libraries_found) * 3)
        
        # Combine scores, starting from current score and adding variety and library points
        # This ensures a minimal score of 1 for any caching implementation
        score = min(100, score + variety_points + library_points)
    else:
        # No caching detected but check executed successfully
        score = 1
    
    # Record execution time
    execution_time = time.time() - start_time
    result["execution_time_ms"] = int(execution_time * 1000)
    
    # Ensure score is within 1-100 range (0 reserved for failed checks)
    score = min(100, max(1, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["caching_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    logger.info(f"Caching check completed in {execution_time:.2f}s, score: {result['caching_score']}, "
                f"files checked: {total_files_checked}, files with caching: {files_with_caching}")
    
    return result

def check_config_file(file_path, repo_path, keywords, types_found, file_examples):
    """Helper function to check configuration files for caching settings"""
    try:
        # Skip files that are too large
        if os.path.getsize(file_path) > 1024 * 1024:  # 1MB
            return False
            
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            
            # Check for caching keywords
            has_caching_config = False
            for keyword in keywords:
                if keyword in content:
                    has_caching_config = True
                    
                    # Categorize the caching type
                    if keyword == 'redis':
                        types_found.add('redis')
                    elif keyword == 'memcached':
                        types_found.add('memcached')
                    elif keyword in ['etag', 'max-age', 'expires', 'last-modified', 'http-cache']:
                        types_found.add('http')
                    elif keyword in ['local', 'browser-cache', 'service-worker']:
                        types_found.add('browser')
                    elif keyword in ['cdn']:
                        types_found.add('cdn')
                    else:
                        types_found.add('config')
                    
                    # Add to file examples if we have fewer than 5
                    if len(file_examples) < 5:
                        rel_path = os.path.relpath(file_path, repo_path)
                        # Find some context around the keyword
                        index = content.find(keyword)
                        if index != -1:
                            start = max(0, index - 50)
                            end = min(len(content), index + len(keyword) + 50)
                            snippet = content[start:end]
                            file_examples.append({
                                "file": rel_path,
                                "pattern": f"config:{keyword}",
                                "snippet": snippet.strip()
                            })
                    break
        
        return has_caching_config
    except Exception as e:
        logger.error(f"Error reading config file {file_path}: {e}")
        return False

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify caching implementation
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 1-100 scale (0 for failures)
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Get timeout setting from repository config if available
        timeout = repository.get('config', {}).get('file_timeout', 30)
        
        # Run the check
        result = check_caching(local_path, repository, timeout)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("caching_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running caching check: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,  # Score 0 for failed checks
            "result": {"error": str(e)},
            "errors": str(e)
        }