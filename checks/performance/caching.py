"""
Caching Check

Checks if the repository implements caching mechanisms to improve performance.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_caching(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for caching implementation in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_caching": False,
        "caching_types": [],
        "caching_libraries": [],
        "language_specific_caching": {},
        "files_with_caching": 0,
        "total_files_checked": 0,
        "file_examples": [],
        "caching_score": 0
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
    caching_types_found = set()
    caching_libraries_found = set()
    language_caching = {}
    file_examples = []
    
    # Skip directories
    skip_dirs = ['.git', 'node_modules', 'venv', '.venv', 'env', '.env', 'dist', 'build',
                'target', '.idea', '.vscode', '__pycache__', 'vendor', 'bin', 'obj']
    
    # First, scan source code files
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for file in files:
            _, ext = os.path.splitext(file)
            
            # Check if this file extension has defined caching patterns
            if ext in caching_patterns:
                file_path = os.path.join(root, file)
                
                # Skip very large files
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 1000000:  # 1MB
                        continue
                except OSError:
                    continue
                
                total_files_checked += 1
                patterns = caching_patterns[ext]["patterns"]
                libraries = caching_patterns[ext]["libraries"]
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for caching patterns
                        found_patterns = []
                        for pattern in patterns:
                            if re.search(pattern, content):
                                found_patterns.append(pattern)
                                # Clean up pattern for readability
                                clean_pattern = pattern.replace(r'\s+', ' ').replace(r'\(', '(').replace(r'\.', '.')
                                
                                # Categorize the caching type
                                if 'redis' in pattern.lower():
                                    caching_types_found.add('redis')
                                elif 'memcache' in pattern.lower():
                                    caching_types_found.add('memcached')
                                elif 'local' in pattern.lower() or 'session' in pattern.lower():
                                    caching_types_found.add('browser')
                                elif 'file' in pattern.lower() or 'open(' in pattern.lower() or 'dump' in pattern.lower():
                                    caching_types_found.add('file')
                                elif '@cache' in pattern.lower() or 'memoize' in pattern.lower() or 'lru' in pattern.lower():
                                    caching_types_found.add('function')
                                elif 'etag' in pattern.lower() or 'control' in pattern.lower() or 'modified' in pattern.lower():
                                    caching_types_found.add('http')
                                else:
                                    caching_types_found.add('in-memory')
                        
                        # If we found caching patterns
                        if found_patterns:
                            files_with_caching += 1
                            
                            # Identify which libraries are used
                            for library in libraries:
                                for pattern in found_patterns:
                                    if library.lower() in pattern.lower() or library.lower() in content.lower():
                                        caching_libraries_found.add(library)
                                        break
                            
                            # Track language-specific patterns
                            lang = ext[1:]  # Remove the dot
                            if lang not in language_caching:
                                language_caching[lang] = set()
                            language_caching[lang].update(found_patterns)
                            
                            # Add to file examples (limit to 5)
                            if len(file_examples) < 5:
                                rel_path = os.path.relpath(file_path, repo_path)
                                # Find a specific caching pattern example
                                for pattern in found_patterns:
                                    match = re.search(pattern, content)
                                    if match:
                                        line = content[max(0, match.start() - 50):min(len(content), match.end() + 50)]
                                        file_examples.append({
                                            "file": rel_path,
                                            "pattern": pattern,
                                            "snippet": line.strip()
                                        })
                                        break
                
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
    
    # Next, check configuration files for caching settings
    for config_item in config_files:
        if os.path.isdir(os.path.join(repo_path, config_item)):
            # Handle directory-based config like .github/workflows/
            config_dir = os.path.join(repo_path, config_item)
            if os.path.exists(config_dir):
                for root, _, files in os.walk(config_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if check_config_file(file_path, repo_path, config_caching_keywords, 
                                        caching_types_found, file_examples):
                            files_with_caching += 1
                        total_files_checked += 1
        else:
            # Handle single config files
            file_path = os.path.join(repo_path, config_item)
            if os.path.isfile(file_path):
                if check_config_file(file_path, repo_path, config_caching_keywords, 
                                    caching_types_found, file_examples):
                    files_with_caching += 1
                total_files_checked += 1
    
    # Check for web server files that often contain caching configs
    web_server_files = [
        "nginx.conf", "apache2.conf", "httpd.conf", ".htaccess", 
        "web.config", "lighttpd.conf", "varnish.vcl"
    ]
    
    for web_file in web_server_files:
        # Look for the file in common locations
        common_locations = [
            "", "config/", "conf/", "etc/", "server/", "apache/", "nginx/", "deploy/"
        ]
        
        for location in common_locations:
            file_path = os.path.join(repo_path, location, web_file)
            if os.path.isfile(file_path):
                if check_config_file(file_path, repo_path, config_caching_keywords, 
                                    caching_types_found, file_examples):
                    files_with_caching += 1
                    # Add "http" type for web server configs
                    caching_types_found.add("http")
                total_files_checked += 1
    
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
    result["file_examples"] = file_examples
    
    # Calculate caching score (0-100 scale)
    score = 0
    
    # Base score for having caching
    if result["has_caching"]:
        score += 30
        
        # Points for caching coverage
        if total_files_checked > 0:
            coverage_ratio = min(1.0, files_with_caching / (total_files_checked * 0.15))  # Assume 15% of files might need caching
            coverage_points = int(coverage_ratio * 30)
            score += coverage_points
        
        # Points for variety of caching types
        type_points = min(25, len(caching_types_found) * 5)
        score += type_points
        
        # Points for using established libraries
        library_points = min(15, len(caching_libraries_found) * 3)
        score += library_points
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["caching_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def check_config_file(file_path, repo_path, keywords, types_found, file_examples):
    """Helper function to check configuration files for caching settings"""
    try:
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
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_caching(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("caching_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running caching check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }