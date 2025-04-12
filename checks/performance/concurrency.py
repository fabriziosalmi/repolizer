"""
Concurrency Check

Checks if the repository implements proper concurrency patterns for handling parallel operations.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_concurrency(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for concurrency patterns in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_concurrency": False,
        "concurrency_patterns": [],
        "concurrency_libraries": [],
        "language_specific_patterns": {},
        "files_with_concurrency": 0,
        "total_files_checked": 0,
        "files_examples": [],
        "concurrency_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Define language-specific concurrency patterns to look for
    concurrency_patterns = {
        # Python
        ".py": {
            "patterns": [
                r'import\s+threading', r'import\s+multiprocessing', r'import\s+concurrent\.futures',
                r'import\s+asyncio', r'async\s+def', r'await\s+', r'with\s+ThreadPoolExecutor',
                r'with\s+ProcessPoolExecutor', r'\.submit\(', r'\.map\(', r'threading\.Thread\(',
                r'multiprocessing\.Process\(', r'Lock\(\)', r'RLock\(\)', r'Semaphore\(',
                r'Event\(\)', r'from\s+celery', r'@celery', r'@task'
            ],
            "libraries": ['threading', 'multiprocessing', 'concurrent.futures', 'asyncio', 'celery']
        },
        # JavaScript
        ".js": {
            "patterns": [
                r'new\s+Promise\(', r'Promise\.all\(', r'Promise\.race\(', r'async\s+function',
                r'async\s+=>', r'await\s+', r'\.then\(', r'SetTimeout\(', r'SetInterval\(',
                r'worker_threads', r'new\s+Worker\(', r'cluster\.fork\(', r'child_process',
                r'Observable', r'Subject', r'from\s+\'rxjs\'', r'import\s+{.*?}\s+from\s+\'rxjs\'',
                r'webworker', r'import\s+{.*?Worker.*?}\s+from'
            ],
            "libraries": ['Promise', 'async/await', 'worker_threads', 'cluster', 'child_process', 'rxjs', 'webworker']
        },
        # Java
        ".java": {
            "patterns": [
                r'implements\s+Runnable', r'extends\s+Thread', r'ExecutorService', r'ThreadPool',
                r'Callable<', r'CompletableFuture', r'Future<', r'CountDownLatch', r'CyclicBarrier',
                r'Semaphore', r'ReentrantLock', r'AtomicInteger', r'AtomicBoolean', r'AtomicReference',
                r'ConcurrentHashMap', r'synchronized', r'volatile', r'parallelStream\(\)', r'parallel\(\)'
            ],
            "libraries": ['Thread', 'ExecutorService', 'CompletableFuture', 'java.util.concurrent', 'ParallelStream']
        },
        # Go
        ".go": {
            "patterns": [
                r'go\s+func', r'go\s+\w+\(', r'<-', r'make\(\s*chan\s+', r'select\s*{',
                r'sync\.Mutex', r'sync\.RWMutex', r'WaitGroup', r'sync\.Once', r'sync\.Map',
                r'sync\.Pool', r'sync\.Cond'
            ],
            "libraries": ['goroutines', 'channels', 'sync']
        },
        # C#
        ".cs": {
            "patterns": [
                r'Task\.Run', r'async\s+Task', r'await\s+', r'Parallel\.[A-Z]',
                r'ConcurrentDictionary', r'ConcurrentQueue', r'ConcurrentBag',
                r'ThreadPool', r'ManualResetEvent', r'SemaphoreSlim', r'Interlocked\.',
                r'lock\s*\(', r'volatile', r'Action<'
            ],
            "libraries": ['Task', 'Parallel', 'System.Threading', 'System.Collections.Concurrent', 'System.Threading.Tasks']
        },
        # Ruby
        ".rb": {
            "patterns": [
                r'Thread\.new', r'require\s+[\'"]thread[\'"]', r'Mutex\.new', r'Queue\.new',
                r'ConditionVariable\.new', r'thread\.join', r'thread\.kill',
                r'Parallel\.map', r'Parallel\.each', r'sidekiq', r'resque'
            ],
            "libraries": ['Thread', 'Mutex', 'Queue', 'Parallel', 'sidekiq', 'resque']
        },
        # TypeScript
        ".ts": {
            "patterns": [
                r'new\s+Promise\(', r'Promise\.all\(', r'Promise\.race\(', r'async\s+function',
                r'async\s+=>', r'await\s+', r'\.then\(', r'SetTimeout\(', r'SetInterval\(',
                r'worker_threads', r'new\s+Worker\(', r'Observable', r'Subject', r'from\s+\'rxjs\''
            ],
            "libraries": ['Promise', 'async/await', 'worker_threads', 'rxjs', 'webworker']
        }
    }
    
    # Add common extensions that should be treated like others
    for base_ext, patterns in list(concurrency_patterns.items()):
        if base_ext == ".js":
            concurrency_patterns[".jsx"] = patterns
            concurrency_patterns[".mjs"] = patterns
        elif base_ext == ".ts":
            concurrency_patterns[".tsx"] = patterns
    
    # Configuration files that might indicate concurrency settings
    config_files = [
        "package.json", "tsconfig.json", "webpack.config.js", "Procfile",
        "docker-compose.yml", ".gitlab-ci.yml", ".github/workflows/",
        "pyproject.toml", "setup.py", "pom.xml", "build.gradle",
        "Gemfile", "Cargo.toml", "Dockerfile", "nginx.conf"
    ]
    
    # Concurrency configuration keywords in config files
    config_concurrency_keywords = [
        "worker", "thread", "pool", "parallel", "async", "concurrent",
        "cluster", "fork", "process", "job", "queue", "scaling",
        "load balancing", "distributed", "celery", "sidekiq", "bull"
    ]
    
    total_files_checked = 0
    files_with_concurrency = 0
    concurrency_patterns_found = set()
    concurrency_libraries_found = set()
    language_patterns = {}
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
            
            # Check if this file extension has defined concurrency patterns
            if ext in concurrency_patterns:
                file_path = os.path.join(root, file)
                
                # Skip very large files
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 1000000:  # 1MB
                        continue
                except OSError:
                    continue
                
                total_files_checked += 1
                patterns = concurrency_patterns[ext]["patterns"]
                libraries = concurrency_patterns[ext]["libraries"]
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for concurrency patterns
                        found_patterns = []
                        for pattern in patterns:
                            if re.search(pattern, content):
                                found_patterns.append(pattern)
                                # Remove regex syntax for readability
                                clean_pattern = pattern.replace(r'\s+', ' ').replace(r'\(', '(').replace(r'\.', '.')
                                concurrency_patterns_found.add(clean_pattern)
                        
                        # If we found concurrency patterns
                        if found_patterns:
                            files_with_concurrency += 1
                            
                            # Identify which libraries are used
                            for library in libraries:
                                for pattern in found_patterns:
                                    if library.lower() in pattern.lower():
                                        concurrency_libraries_found.add(library)
                                        break
                            
                            # Track language-specific patterns
                            lang = ext[1:]  # Remove the dot
                            if lang not in language_patterns:
                                language_patterns[lang] = set()
                            language_patterns[lang].update(found_patterns)
                            
                            # Add to file examples (limit to 5)
                            if len(file_examples) < 5:
                                rel_path = os.path.relpath(file_path, repo_path)
                                # Find a specific concurrency pattern example
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
    
    # Next, check configuration files for concurrency settings
    for config_item in config_files:
        if os.path.isdir(os.path.join(repo_path, config_item)):
            # Handle directory-based config like .github/workflows/
            config_dir = os.path.join(repo_path, config_item)
            for root, _, files in os.walk(config_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    check_config_file(file_path, repo_path, config_concurrency_keywords, 
                                    concurrency_patterns_found, file_examples)
                    total_files_checked += 1
        else:
            # Handle single config files
            file_path = os.path.join(repo_path, config_item)
            if os.path.isfile(file_path):
                check_config_file(file_path, repo_path, config_concurrency_keywords, 
                                concurrency_patterns_found, file_examples)
                total_files_checked += 1
    
    # Convert language patterns to a serializable format
    lang_patterns_dict = {}
    for lang, patterns in language_patterns.items():
        lang_patterns_dict[lang] = list(patterns)
    
    # Update result with findings
    result["has_concurrency"] = files_with_concurrency > 0
    result["concurrency_patterns"] = sorted(list(concurrency_patterns_found))
    result["concurrency_libraries"] = sorted(list(concurrency_libraries_found))
    result["language_specific_patterns"] = lang_patterns_dict
    result["files_with_concurrency"] = files_with_concurrency
    result["total_files_checked"] = total_files_checked
    result["files_examples"] = file_examples
    
    # Calculate concurrency score (0-100 scale)
    score = 0
    
    # Base score for having concurrency
    if result["has_concurrency"]:
        score += 30
        
        # Points for concurrency coverage (% of files with concurrency)
        if total_files_checked > 0:
            coverage_ratio = min(1.0, files_with_concurrency / (total_files_checked * 0.2))  # Assume 20% of files might need concurrency
            coverage_points = int(coverage_ratio * 30)
            score += coverage_points
        
        # Points for variety of concurrency patterns
        pattern_points = min(20, len(concurrency_patterns_found) * 2)
        score += pattern_points
        
        # Points for using established libraries
        library_points = min(20, len(concurrency_libraries_found) * 5)
        score += library_points
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["concurrency_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def check_config_file(file_path, repo_path, keywords, patterns_found, file_examples):
    """Helper function to check configuration files for concurrency settings"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            
            # Check for concurrency keywords
            has_concurrency_config = False
            for keyword in keywords:
                if keyword in content:
                    has_concurrency_config = True
                    patterns_found.add(f"config:{keyword}")
                    
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
    except Exception as e:
        logger.error(f"Error reading config file {file_path}: {e}")

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check concurrent request handling
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_concurrency(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("concurrency_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running concurrency check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }