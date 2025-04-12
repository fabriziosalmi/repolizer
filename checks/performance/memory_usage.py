import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_memory_usage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for memory usage optimization and memory leak prevention
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_memory_management": False,
        "has_memory_monitoring": False,
        "has_leak_prevention": False,
        "has_garbage_collection_hints": False,
        "has_resource_cleanup": False,
        "memory_usage_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Memory management patterns
    memory_management_patterns = [
        r'memory\s*management',
        r'memory\s*allocation',
        r'memory\s*pool',
        r'buffer\s*pool',
        r'object\s*pool',
        r'weak\s*reference',
        r'WeakMap',
        r'WeakSet',
        r'weak_ptr',
        r'shared_ptr',
        r'unique_ptr',
        r'dispose\(',
        r'delete\s+',
        r'free\(',
        r'malloc\(',
        r'AutoDispose',
        r'@AutoDispose'
    ]
    
    # Memory monitoring patterns
    memory_monitoring_patterns = [
        r'memory\s*profile',
        r'memory\s*monitor',
        r'heap\s*dump',
        r'performance\.memory',
        r'process\.memoryUsage',
        r'getMemoryInfo',
        r'MemoryMXBean',
        r'heap\s*size',
        r'memory\s*leak\s*detect',
        r'LeakCanary',
        r'chrome\.memory',
        r'gc\s*statistics',
        r'maxMemory\(',
        r'totalMemory\('
    ]
    
    # Memory leak prevention patterns
    leak_prevention_patterns = [
        r'removeEventListener',
        r'clearTimeout',
        r'clearInterval',
        r'unsubscribe\(',
        r'dispose\(',
        r'componentWillUnmount',
        r'ngOnDestroy',
        r'disconnectedCallback',
        r'cleanup\(',
        r'beforeDestroy',
        r'destroyed',
        r'unregister',
        r'removeListener',
        r'close\(',
        r'detach\(',
        r'release\(',
        r'unref\(',
        r'using\s+statement',
        r'with\s+statement',
        r'try-finally'
    ]
    
    # Garbage collection hint patterns
    gc_hint_patterns = [
        r'System\.gc\(',
        r'gc\(',
        r'Runtime\.getRuntime\(\)\.gc\(',
        r'CollectGarbage',
        r'collect\(\)',
        r'suggestion',
        r'memory\s*pressure',
        r'nullify',
        r'null\s*=',
        r'delete\s+',
        r'clear\(',
        r'objectPool\.release'
    ]
    
    # Resource cleanup patterns
    resource_cleanup_patterns = [
        r'close\(',
        r'dispose\(',
        r'release\(',
        r'cleanup\(',
        r'finalize\(',
        r'destroy\(',
        r'shutdown\(',
        r'disconnect\(',
        r'clear\(',
        r'reset\(',
        r'unload\(',
        r'unregister\(',
        r'ComponentWillUnmount',
        r'beforeDestroy',
        r'onDestroy',
        r'__del__',
        r'with\s+',
        r'using\s+',
        r'try\s*\{\s*.*\}\s*finally\s*\{',
        r'try-with-resources',
        r'try\s*\(\s*.*\s*\)\s*\{'
    ]
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.java', '.c', '.cpp', '.cs', '.go', '.swift', '.kt']
    
    # Walk through the repository and analyze files
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in code_file_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for memory management
                        if not result["has_memory_management"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in memory_management_patterns):
                                result["has_memory_management"] = True
                        
                        # Check for memory monitoring
                        if not result["has_memory_monitoring"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in memory_monitoring_patterns):
                                result["has_memory_monitoring"] = True
                        
                        # Check for memory leak prevention
                        if not result["has_leak_prevention"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in leak_prevention_patterns):
                                result["has_leak_prevention"] = True
                        
                        # Check for garbage collection hints
                        if not result["has_garbage_collection_hints"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in gc_hint_patterns):
                                result["has_garbage_collection_hints"] = True
                        
                        # Check for resource cleanup
                        if not result["has_resource_cleanup"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in resource_cleanup_patterns):
                                result["has_resource_cleanup"] = True
                        
                        # Break early if we found everything
                        if (result["has_memory_management"] and 
                            result["has_memory_monitoring"] and 
                            result["has_leak_prevention"] and 
                            result["has_garbage_collection_hints"] and 
                            result["has_resource_cleanup"]):
                            break
                
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    # Calculate memory usage score (0-100 scale)
    score = 0
    
    # Award points for each memory optimization technique
    if result["has_memory_management"]:
        score += 20
    
    if result["has_memory_monitoring"]:
        score += 20
    
    if result["has_leak_prevention"]:
        score += 20
    
    if result["has_garbage_collection_hints"]:
        score += 15
    
    if result["has_resource_cleanup"]:
        score += 25
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["memory_usage_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the memory usage optimization check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_memory_usage(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["memory_usage_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running memory usage check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }