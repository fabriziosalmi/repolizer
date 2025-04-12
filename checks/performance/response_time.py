"""
Performance check: Response Time
"""

import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_response_time_optimization(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for response time optimization techniques
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_caching": False,
        "has_cdn_usage": False,
        "has_database_optimization": False,
        "has_backend_optimization": False,
        "has_load_time_metrics": False,
        "response_time_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Patterns for caching detection
    caching_patterns = [
        r'cache-control',
        r'etag',
        r'if-none-match',
        r'last-modified',
        r'expires',
        r'redis',
        r'memcache[d]?',
        r'localCache',
        r'sessionCache',
        r'http-cache',
        r'service-worker',
        r'workbox',
        r'@cacheable'
    ]
    
    # Patterns for CDN usage
    cdn_patterns = [
        r'cdn\.',
        r'cloudfront',
        r'cloudflare',
        r'akamai',
        r'fastly',
        r'jsdelivr',
        r'unpkg',
        r'cdnjs',
        r'content\s*delivery\s*network',
        r'static\.', 
        r'assets\.'
    ]
    
    # Patterns for database optimization
    db_optimization_patterns = [
        r'index(es|ing)?',
        r'query\s*optimization',
        r'query\s*cache',
        r'prepared\s*statement',
        r'connection\s*pool',
        r'batch\s*request',
        r'eager\s*loading',
        r'join\s*fetch',
        r'prefetch_related',
        r'includes\(',
        r'select\(\s*[\'"`].+?[\'"`]\s*\)'
    ]
    
    # Patterns for backend optimization
    backend_optimization_patterns = [
        r'gzip',
        r'brotli',
        r'compression',
        r'throttl(e|ing)',
        r'rate\s*limit',
        r'queue',
        r'worker',
        r'async(\s*await)?',
        r'parallel',
        r'thread\s*pool',
        r'process\s*pool',
        r'debounce',
        r'throttle'
    ]
    
    # Patterns for load time metrics
    load_time_patterns = [
        r'performance\.now',
        r'performance\.mark',
        r'performance\.measure',
        r'time\s*to\s*first\s*byte',
        r'ttfb',
        r'first\s*contentful\s*paint',
        r'fcp',
        r'first\s*paint',
        r'load\s*time',
        r'response\s*time',
        r'new\s*relic',
        r'datadog',
        r'lighthouse',
        r'web\s*vitals'
    ]
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.html', '.css']
    config_files = [
        'package.json', 
        'nginx.conf', 
        'apache.conf', 
        '.htaccess', 
        'docker-compose.yml', 
        'Dockerfile',
        'web.config',
        'serverless.yml',
        'next.config.js',
        'nuxt.config.js',
        'vercel.json',
        'netlify.toml'
    ]
    
    # First, check config files for performance configuration
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for caching configuration
                    if not result["has_caching"]:
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in caching_patterns):
                            result["has_caching"] = True
                    
                    # Check for CDN configuration
                    if not result["has_cdn_usage"]:
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in cdn_patterns):
                            result["has_cdn_usage"] = True
                    
                    # Check for backend optimizations
                    if not result["has_backend_optimization"]:
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in backend_optimization_patterns):
                            result["has_backend_optimization"] = True
                    
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Walk through the repository and analyze files
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in code_file_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for caching
                        if not result["has_caching"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in caching_patterns):
                                result["has_caching"] = True
                        
                        # Check for CDN usage
                        if not result["has_cdn_usage"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in cdn_patterns):
                                result["has_cdn_usage"] = True
                        
                        # Check for database optimization
                        if not result["has_database_optimization"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in db_optimization_patterns):
                                result["has_database_optimization"] = True
                        
                        # Check for backend optimization
                        if not result["has_backend_optimization"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in backend_optimization_patterns):
                                result["has_backend_optimization"] = True
                        
                        # Check for load time metrics
                        if not result["has_load_time_metrics"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in load_time_patterns):
                                result["has_load_time_metrics"] = True
                        
                        # Break early if we found everything
                        if (result["has_caching"] and 
                            result["has_cdn_usage"] and 
                            result["has_database_optimization"] and 
                            result["has_backend_optimization"] and 
                            result["has_load_time_metrics"]):
                            break
                
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    # Calculate response time optimization score (0-100 scale)
    score = 0
    
    # Award points for each response time optimization technique
    if result["has_caching"]:
        score += 25
    
    if result["has_cdn_usage"]:
        score += 20
    
    if result["has_database_optimization"]:
        score += 20
    
    if result["has_backend_optimization"]:
        score += 20
    
    if result["has_load_time_metrics"]:
        score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["response_time_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the response time optimization check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_response_time_optimization(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["response_time_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running response time check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }