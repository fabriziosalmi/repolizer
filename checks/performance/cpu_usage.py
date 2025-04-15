import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_cpu_usage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for CPU usage optimization and potential bottlenecks
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for CPU usage optimization analysis
    """
    result = {
        "has_cpu_intensive_operations": False,
        "has_parallelization": False,
        "has_async_processing": False,
        "has_lazy_loading": False,
        "has_caching_mechanisms": False,
        "cpu_usage_score": 0,
        "intensive_operations_found": [],
        "optimization_techniques_found": {},
        "files_checked": 0,
        "files_with_intensive_ops": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Patterns to identify CPU-intensive operations
    intensive_patterns = [
        r'for\s+\w+\s+in\s+range\(\d+\)',  # Large loops
        r'while\s+True',                   # Infinite loops
        r'\.map\(|\.reduce\(|\.filter\(',  # Intensive array operations
        r'np\.(?:dot|matmul|linalg)',      # NumPy matrix operations
        r'\.sort\(|sorted\(',              # Sorting operations
        r'recursion|recursive',            # Recursive functions
        r'image processing|video processing',  # Media processing
        r'data mining|machine learning'    # ML operations
    ]
    
    # Patterns to identify parallelization
    parallel_patterns = [
        r'multiprocessing|concurrent\.futures',  # Python multiprocessing
        r'Thread|ThreadPool|ProcessPool',        # Thread-based parallelism
        r'parallelStream|parallel\(\)',          # Java/Scala parallelism
        r'Promise\.all|async\s+\w+',             # JS promises/async
        r'goroutine|go\s+func',                  # Go concurrency
        r'worker|job queue|task queue',          # Job/worker patterns
        r'@parallel|@async'                       # Decorators for parallelism
    ]
    
    # Patterns to identify async processing
    async_patterns = [
        r'async\s+def|await',              # Python async/await
        r'Promise|async\s+\w+|\.then\(',    # JS async patterns
        r'CompletableFuture|rxjava|Observable',  # Java async
        r'setTimeout|setInterval',         # JS timing functions
        r'EventEmitter|addEventListener',  # Event-based programming
        r'callback|callbackFn'             # Callback patterns
    ]
    
    # Patterns to identify lazy loading
    lazy_patterns = [
        r'lazy\s+|LazyLoading',            # Explicit lazy references
        r'import\s+\{\s*lazy\s*\}',        # React lazy loading
        r'@lazy|@LazyLoaded',              # Lazy decorators
        r'dynamic import|import\(',        # Dynamic imports
        r'loadable\(|React\.lazy',         # React code splitting
        r'yield|generator'                 # Generator pattern
    ]
    
    # Patterns to identify caching mechanisms
    caching_patterns = [
        r'cache|caching|memoize',          # General caching terms
        r'@cached_property|@lru_cache',    # Python cache decorators
        r'redis|memcached',                # Cache services
        r'localStorage|sessionStorage',    # Browser storage
        r'@Cacheable',                     # Java cache annotations
        r'getOrElse|computeIfAbsent'       # Functional caching patterns
    ]
    
    # File extensions to check
    code_file_extensions = ['.py', '.js', '.ts', '.java', '.rb', '.php', '.go', '.c', '.cpp', '.cs']
    files_checked = 0
    files_with_intensive_ops = set()
    
    # Track specific instances of patterns found
    intensive_operations_found = []
    optimization_techniques = {
        "parallelization": [],
        "async_processing": [],
        "lazy_loading": [],
        "caching": []
    }
    
    # Walk through the repository and analyze files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in code_file_extensions:
                files_checked += 1
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        relative_path = os.path.relpath(file_path, repo_path)
                        
                        # Check for CPU-intensive operations
                        for pattern in intensive_patterns:
                            matches = re.finditer(pattern, content, re.IGNORECASE)
                            for match in matches:
                                result["has_cpu_intensive_operations"] = True
                                match_text = match.group(0)
                                
                                # Record this instance (limit to avoid overwhelming results)
                                if len(intensive_operations_found) < 10:
                                    intensive_operations_found.append({
                                        "file": relative_path,
                                        "pattern": pattern,
                                        "code": match_text[:100] + ("..." if len(match_text) > 100 else "")
                                    })
                                
                                # Add to set of files with intensive operations
                                files_with_intensive_ops.add(relative_path)
                                break
                        
                        # Check for parallelization
                        for pattern in parallel_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_parallelization"] = True
                                optimization_techniques["parallelization"].append(relative_path)
                                break
                        
                        # Check for async processing
                        for pattern in async_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_async_processing"] = True
                                optimization_techniques["async_processing"].append(relative_path)
                                break
                        
                        # Check for lazy loading
                        for pattern in lazy_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_lazy_loading"] = True
                                optimization_techniques["lazy_loading"].append(relative_path)
                                break
                        
                        # Check for caching mechanisms
                        for pattern in caching_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_caching_mechanisms"] = True
                                optimization_techniques["caching"].append(relative_path)
                                break
                
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    # Update result with additional information
    result["files_checked"] = files_checked
    result["files_with_intensive_ops"] = list(files_with_intensive_ops)
    result["intensive_operations_found"] = intensive_operations_found
    result["optimization_techniques_found"] = {
        "parallelization": list(set(optimization_techniques["parallelization"]))[:5],
        "async_processing": list(set(optimization_techniques["async_processing"]))[:5],
        "lazy_loading": list(set(optimization_techniques["lazy_loading"]))[:5],
        "caching": list(set(optimization_techniques["caching"]))[:5]
    }
    
    # Calculate CPU usage optimization score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on CPU optimization techniques.
        
        The score consists of:
        - Base score dependent on CPU-intensive operations (0-40 points)
        - Score for parallelization techniques (0-20 points)
        - Score for async processing (0-15 points)
        - Score for lazy loading strategies (0-10 points)
        - Score for caching mechanisms (0-15 points)
        - Coverage bonus for widespread optimization (0-10 points)
        
        Final score is normalized to 0-100 range.
        """
        # If no intensive operations found, default to good score (no optimization needed)
        if not result_data.get("has_cpu_intensive_operations", False):
            return 80
        
        files_with_intensive_ops = len(result_data.get("files_with_intensive_ops", []))
        files_checked = max(1, result_data.get("files_checked", 1))  # Avoid division by zero
        
        # Calculate what percentage of files have intensive operations
        intensive_ops_percentage = files_with_intensive_ops / files_checked
        
        # Base score - starts at 40, reduces based on percentage of files with intensive operations
        # More files with intensive operations = lower base score
        base_score = max(0, 40 - (intensive_ops_percentage * 40))
        
        # Score for optimization techniques
        parallelization_score = 20 if result_data.get("has_parallelization", False) else 0
        async_score = 15 if result_data.get("has_async_processing", False) else 0
        lazy_loading_score = 10 if result_data.get("has_lazy_loading", False) else 0
        caching_score = 15 if result_data.get("has_caching_mechanisms", False) else 0
        
        # Coverage bonus - how many of the 4 optimization techniques are used
        techniques_count = sum([
            result_data.get("has_parallelization", False),
            result_data.get("has_async_processing", False),
            result_data.get("has_lazy_loading", False),
            result_data.get("has_caching_mechanisms", False)
        ])
        
        coverage_bonus = min(10, techniques_count * 2.5)
        
        # Calculate total score
        total_score = base_score + parallelization_score + async_score + lazy_loading_score + caching_score + coverage_bonus
        
        # Ensure the score is in the 0-100 range
        total_score = min(100, max(0, total_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": round(base_score, 1),
            "parallelization_score": parallelization_score,
            "async_score": async_score,
            "lazy_loading_score": lazy_loading_score,
            "caching_score": caching_score,
            "coverage_bonus": coverage_bonus,
            "total_score": round(total_score, 1)
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(total_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["cpu_usage_score"] = calculate_score(result)
    
    return result

def get_cpu_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the CPU usage check results"""
    has_intensive_ops = result.get("has_cpu_intensive_operations", False)
    has_parallelization = result.get("has_parallelization", False)
    has_async = result.get("has_async_processing", False)
    has_lazy = result.get("has_lazy_loading", False)
    has_caching = result.get("has_caching_mechanisms", False)
    score = result.get("cpu_usage_score", 0)
    
    if not has_intensive_ops:
        return "No CPU-intensive operations detected. The codebase appears to be efficient regarding CPU usage."
    
    if score >= 80:
        return "Excellent CPU optimization. The codebase uses multiple techniques to manage CPU-intensive operations effectively."
    
    recommendations = []
    
    if not has_parallelization:
        recommendations.append("Implement parallelization for CPU-intensive tasks using multiprocessing, threads, or worker pools.")
    
    if not has_async:
        recommendations.append("Add asynchronous processing to prevent blocking during CPU-intensive operations.")
    
    if not has_lazy:
        recommendations.append("Consider lazy loading techniques to defer initialization of resource-heavy objects.")
    
    if not has_caching:
        recommendations.append("Implement caching mechanisms to avoid redundant computations.")
    
    if not recommendations:
        return "The codebase has some CPU optimization techniques. Consider applying them more widely across the intensive operations identified."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the CPU usage check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"cpu_usage_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached CPU usage check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        if not local_path:
            logger.warning("No local repository path provided")
            return {
                "status": "partial",
                "score": 0,
                "result": {"message": "No local repository path available for analysis"},
                "errors": "Missing repository path"
            }
        
        # Run the check
        result = check_cpu_usage(local_path, repository)
        
        logger.debug(f"✅ CPU usage check completed with score: {result.get('cpu_usage_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("cpu_usage_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "has_cpu_intensive_operations": result.get("has_cpu_intensive_operations", False),
                "optimization_techniques": {
                    "parallelization": result.get("has_parallelization", False),
                    "async_processing": result.get("has_async_processing", False),
                    "lazy_loading": result.get("has_lazy_loading", False),
                    "caching": result.get("has_caching_mechanisms", False)
                },
                "intensive_ops_count": len(result.get("intensive_operations_found", [])),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_cpu_recommendation(result)
            },
            "errors": None
        }
    except FileNotFoundError as e:
        error_msg = f"Repository files not found: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except PermissionError as e:
        error_msg = f"Permission denied accessing repository files: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except Exception as e:
        error_msg = f"Error running CPU usage check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }