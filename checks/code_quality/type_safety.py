"""
Type Safety Check

Analyzes the repository's code for type safety features and type annotations.
"""
import os
import re
import logging
import threading
import traceback
import concurrent.futures
# Removed signal import
from typing import Dict, Any, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time

# Setup logging
logger = logging.getLogger(__name__)

# Global timeout mechanism to ensure the check never hangs
CHECK_TIMEOUT = 45  # Reduced overall timeout to 45 seconds

# Removed TimeoutException class
# Removed timeout_handler function

def check_type_safety(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for type safety features in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    # Removed SIGALRM and threading.Timer setup
    
    # Keep the start_time for internal checks
    start_time = time.time()
    
    # Overall execution timeout - halt processing if it takes too long
    max_execution_time = 40  # Further reduced from 60 to 40 seconds maximum for the entire check
    
    result = {
        "has_type_annotations": False,
        "has_type_checking": False,
        "type_annotation_ratio": 0.0,
        "type_check_tools": [],
        "typed_languages": [],
        "untyped_languages": [],
        "type_issues": [],
        "files_checked": 0,
        "type_metrics": {
            "files_with_annotations": 0,
            "typed_code_coverage": 0.0,
            "strict_mode_enabled": False,
            "advanced_types_usage": False
        },
        "quality_indicators": {
            "consistent_annotations": True,
            "annotation_style": None,
            "third_party_type_stubs": False
        },
        "performance_info": {
            "early_termination": False,
            "timeout_reason": None,
            "file_scan_time": 0,
            "analysis_time": 0
        }
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Language extensions and their type safety status
    language_extensions = {
        # Statically typed languages
        "statically_typed": {
            "java": [".java"],
            "c#": [".cs"],
            "go": [".go"],
            "rust": [".rs"],
            "kotlin": [".kt", ".kts"],
            "swift": [".swift"],
            "c++": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
            "typescript": [".ts", ".tsx"],
            "scala": [".scala"],
            "haskell": [".hs"],
            "fsharp": [".fs", ".fsx"]
        },
        # Languages with optional type annotations
        "optionally_typed": {
            "python": [".py"],
            "javascript": [".js", ".jsx"],
            "php": [".php"],
            "ruby": [".rb"]
        }
    }
    
    # Type checking tools by language
    type_checkers = {
        "python": ["mypy", "pytype", "pyre", "typing"],
        "javascript": ["flow", "typescript", "jsdoc", "@ts-check"],
        "php": ["phpstan", "psalm", "phan"],
        "ruby": ["sorbet", "rbs", "typeprof"]
    }
    
    # Patterns to detect type annotations by language
    type_annotation_patterns = {
        "python": [
            r'def\s+\w+\s*\((?:[^)]*:[\s\w\[\]\'",\.]+[^)]*)+\)\s*->',  # Function return type
            r'(?:\w+)\s*:\s*(?:int|str|float|bool|list|dict|tuple|set|Any|Optional)',  # Variable type
            r'from\s+typing\s+import',  # Typing imports
            r'import\s+typing'  # Typing imports
        ],
        "javascript": [
            r'function\s+\w+\s*\(.*\)\s*:\s*\w+',  # TypeScript function return type
            r'const\s+\w+\s*:\s*\w+',  # TypeScript variable type
            r'let\s+\w+\s*:\s*\w+',  # TypeScript variable type
            r'var\s+\w+\s*:\s*\w+',  # TypeScript variable type
        ],
        "php": [
            r'function\s+\w+\s*\(.*\)\s*:\s*\w+',  # PHP 7+ return type
            r'@param\s+\w+',  # PHPDoc param type
            r'@return\s+\w+'  # PHPDoc return type
        ],
        "ruby": [
            r'sig\s+do',  # Sorbet sig block
            r'T\.'  # Sorbet types
        ]
    }
    
    # Patterns to detect type checking configuration (simplified for performance)
    type_check_config_patterns = {
        "python": ["mypy.ini", ".mypy.ini", "pytype.cfg", "pyre_configuration"],
        "javascript": ["tsconfig.json", "jsconfig.json", ".flowconfig"],
        "php": ["phpstan.neon", "psalm.xml"],
        "ruby": ["sorbet"]
    }
    
    files_checked = 0
    language_counts = {"statically_typed": {}, "optionally_typed": {}}
    type_annotations_counts = {}
    total_files_by_language = {}
    type_checker_found = set()
    
    # Use a set to track directories to skip for faster lookup
    skip_dirs = {'/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/', '/vendor/', '/venv/',
                '/cache/', '/.pytest_cache/', '/coverage/', '/target/', '/out/', '/.idea/', '/.vscode/',
                '/packages/', '/data/', '/logs/', '/docs/', '/third_party/', '/external/', '/media/',
                '/assets/', '/images/', '/img/', '/uploads/', '/downloads/', '/temp/', '/tmp/'}
    
    # Additional skip_files patterns
    skip_files = {'.min.js', '.min.css', '.map', '.lock', '.svg', '.png', '.jpg', '.jpeg', 
                 '.gif', '.ico', '.pdf', '.zip', '.tar.gz', '.env', '.mo', '.po', '.log', '.md', '.rst', '.txt'}
    
    # Maximum number of files to analyze per language to prevent performance issues
    max_files_per_language = 30  # Further reduced from 75 to 30 
    max_total_files = 100  # Reduced from 300 to 100 overall file limit
    files_per_language = {}
    
    # Get all eligible files first to improve performance
    eligible_files = []
    total_file_count = 0
    
    # Use a timeout for the file discovery to prevent hanging
    file_discovery_timeout = 5  # Reduced from 10 to 5 seconds max for file discovery
    file_discovery_start = time.time()
    
    # Maximum file size to analyze (in bytes) - skip larger files
    max_file_size = 50 * 1024  # Reduced from 100KB to 50KB maximum file size
    
    # Removed the outer try...except TimeoutException...finally block
    # The main logic starts here directly
    
    try: # Keep inner try for file system errors during discovery
        # Set up a walk limit to avoid traversing enormous repos
        dir_count = 0
        max_dir_count = 100  # Reduced from 500 to 100 maximum number of directories to traverse
        
        # Safety: Use scandir instead of walk for better performance and finer control
        def limited_walk(root_dir, max_depth=3, current_depth=0):
            """Limited, controlled directory traversal with depth limit"""
            if current_depth > max_depth:
                return
            
            try:
                with os.scandir(root_dir) as entries:
                    dirs = []
                    files = []
                    
                    for entry in entries:
                        if time.time() - file_discovery_start > file_discovery_timeout:
                            break
                            
                        try:
                            if entry.is_dir():
                                # Skip blacklisted directories
                                normalized_path = entry.path.replace('\\', '/')
                                if any(skip_dir in normalized_path for skip_dir in skip_dirs):
                                    continue
                                dirs.append(entry.path)
                            elif entry.is_file():
                                # Skip files that should be ignored
                                if any(pattern in entry.name.lower() for pattern in skip_files):
                                    continue
                                
                                try:
                                    # Skip files that are too large
                                    file_size = entry.stat().st_size
                                    if file_size > max_file_size:
                                        continue
                                except (OSError, IOError):
                                    continue
                                    
                                files.append(entry.path)
                        except (PermissionError, OSError):
                            continue
                    
                    yield root_dir, dirs, files
                    
                    # Process subdirectories with depth limit
                    for dir_path in dirs:
                        if time.time() - file_discovery_start > file_discovery_timeout:
                            break
                        yield from limited_walk(dir_path, max_depth, current_depth + 1)
            except (PermissionError, OSError):
                return
        
        # Use the limited, controlled walk function
        for root, dirs, files in limited_walk(repo_path, max_depth=2):  # Limit to 2 levels deep
            # Check timeouts and limits (these remain important for performance)
            current_time = time.time()
            if current_time - start_time > max_execution_time:
                logger.warning(f"Internal execution timeout reached after {max_execution_time}s. Finalizing results.")
                result["performance_info"]["early_termination"] = True
                result["performance_info"]["timeout_reason"] = "internal_execution_limit"
                break # Stop processing
                
            if current_time - file_discovery_start > file_discovery_timeout:
                logger.warning(f"File discovery timeout after {file_discovery_timeout}s. Proceeding with files found so far.")
                result["performance_info"]["early_termination"] = True
                result["performance_info"]["timeout_reason"] = "file_discovery"
                break # Stop discovery
            
            # Increment directory counter and check limit
            dir_count += 1
            if dir_count > max_dir_count:
                logger.warning(f"Directory count limit ({max_dir_count}) reached. Stopping file discovery.")
                result["performance_info"]["early_termination"] = True
                result["performance_info"]["timeout_reason"] = "dir_count_limit"
                break
            
            # Limit the number of files to examine per directory for performance
            file_sample = files[:20]  # Reduced from 50 to 20 files per directory
            
            for file_path in file_sample:
                # Check overall file limit
                if total_file_count >= max_total_files:
                    logger.info(f"Reached maximum file count limit ({max_total_files}). Stopping file discovery.")
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "file_count_limit"
                    break
                
                # Get file extension
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()
                
                # Determine file language
                file_language = None
                typing_category = None
                
                # Check if file is statically typed language
                for lang, extensions in language_extensions["statically_typed"].items():
                    if ext in extensions:
                        file_language = lang
                        typing_category = "statically_typed"
                        break
                
                # If not statically typed, check if it's optionally typed
                if not file_language:
                    for lang, extensions in language_extensions["optionally_typed"].items():
                        if ext in extensions:
                            file_language = lang
                            typing_category = "optionally_typed"
                            break
                
                # Skip files that aren't in our language sets
                if not file_language:
                    continue
                    
                # Count languages
                if typing_category:
                    if file_language in language_counts[typing_category]:
                        language_counts[typing_category][file_language] += 1
                    else:
                        language_counts[typing_category][file_language] = 1
                    
                    # Initialize type annotation counts for optionally typed languages
                    if typing_category == "optionally_typed":
                        if file_language not in type_annotations_counts:
                            type_annotations_counts[file_language] = 0
                        
                        if file_language not in total_files_by_language:
                            total_files_by_language[file_language] = 0
                        
                        total_files_by_language[file_language] += 1
                        
                        # Track files per language to limit analysis
                        if file_language not in files_per_language:
                            files_per_language[file_language] = 0
                        
                        if files_per_language[file_language] < max_files_per_language:
                            files_per_language[file_language] += 1
                            eligible_files.append((file_path, file_language, typing_category))
                            total_file_count += 1
                
                # For statically typed languages, just count the file
                elif typing_category == "statically_typed":
                    files_checked += 1
                    total_file_count += 1
                    
                # Check if we've reached the max total files limit
                if total_file_count >= max_total_files:
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "file_count_limit"
                    break
    except (PermissionError, OSError) as e:
        logger.error(f"File system access error during file discovery: {e}")
    except Exception as e:
        logger.error(f"Error during file discovery: {str(e)}")
        # Log traceback for unexpected errors during discovery
        logger.debug(traceback.format_exc())

    # Record file scan time
    file_scan_time = time.time() - file_discovery_start
    result["performance_info"]["file_scan_time"] = round(file_scan_time, 2)
    
    # Log statistics
    logger.debug(f"Found {len(eligible_files)} eligible files for analysis across {len(files_per_language)} languages in {file_scan_time:.2f}s")
    
    # Early return: If no files to analyze or too few, just return basic results
    # This helps avoid processing overhead for simple repos
    if len(eligible_files) == 0:
        logger.info("No eligible files found for analysis. Returning early.")
        
        # Set statically typed languages if any
        for lang in language_counts["statically_typed"]:
            if lang not in result["typed_languages"]:
                result["typed_languages"].append(lang)
        
        # Calculate a basic score
        score = 1
        if result["typed_languages"]:
            static_typed_langs = [lang for lang in result["typed_languages"] 
                                 if lang in language_extensions["statically_typed"]]
            score += min(40, len(static_typed_langs) * 15)
        
        result["type_safety_score"] = min(100, score)
        result["files_checked"] = files_checked
        
        return result
    
    # Limit files to analyze for performance - very important!
    if len(eligible_files) > 50:  # Further reduced from 250 to 50
        import random
        random.shuffle(eligible_files)
        eligible_files = eligible_files[:50]
        logger.info(f"Sampling down to 50 files for analysis to improve performance")
    
    # Start analysis timer
    analysis_start_time = time.time()
    
    # Inline quick analysis for very small repos
    if len(eligible_files) <= 5:  # For tiny repos, avoid ThreadPoolExecutor overhead
        logger.info("Using fast-path analysis for small codebase")
        analysis_results = []
        for file_data in eligible_files:
            file_path, file_language, typing_category = file_data
            
            # Only analyze optionally typed files
            if typing_category != "optionally_typed":
                continue
            
            file_result = {"has_annotation": False, "checker_tools": set(), "issues": []}
            
            try:
                # Skip if too large or doesn't exist
                if not os.path.exists(file_path) or os.path.getsize(file_path) > max_file_size:
                    continue
                
                # Simple content scan
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(max_file_size)
                    
                    # Use direct string search for better performance
                    if file_language == "python":
                        if "typing" in content or ": " in content or " -> " in content:
                            file_result["has_annotation"] = True
                    elif file_language == "javascript":
                        if ": " in content or "@param" in content:
                            file_result["has_annotation"] = True
                    
                    # Check for type checker tool imports
                    if file_language in type_checkers:
                        for checker in type_checkers[file_language]:
                            if checker in content:
                                file_result["checker_tools"].add(checker)
                
                analysis_results.append((file_path, file_language, file_result))
            except Exception:
                continue
    else:
        # For larger repos, use ThreadPoolExecutor with aggressive timeouts
        # Analyze files more efficiently with parallel processing
        def analyze_file(file_data):
            # Use a per-file timeout for the whole function using time tracking
            start = time.time()
            max_analysis_time = 0.5  # Further reduced from 0.8 to 0.5 seconds max per file
            
            file_path, file_language, typing_category = file_data
            file_result = {
                "has_annotation": False,
                "checker_tools": set(),
                "issues": []
            }
            
            # Only analyze optionally typed files
            if typing_category == "optionally_typed":
                try:
                    # Fast checks first - skip file if it's not there or too large
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        return file_path, file_language, file_result
                    
                    try:
                        file_size = os.stat(file_path).st_size
                        if file_size > max_file_size or file_size == 0:
                            return file_path, file_language, file_result
                    except:
                        return file_path, file_language, file_result
                    
                    # Read file
                    content = None
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            # Use a limited read
                            content = f.read(max_file_size)
                    except:
                        return file_path, file_language, file_result
                    
                    if not content:
                        return file_path, file_language, file_result
                        
                    # Check if we've spent too much time already
                    if time.time() - start > max_analysis_time / 2:
                        return file_path, file_language, file_result
                    
                    # Fast path detection using string search instead of regex where possible
                    if file_language == "python":
                        if any(x in content for x in ["typing", ": ", " -> ", "Optional", "List[", "Dict["]):
                            file_result["has_annotation"] = True
                    elif file_language == "javascript":
                        if any(x in content for x in [": ", "@param", "@type", "function"]):
                            file_result["has_annotation"] = True
                    elif file_language == "php":
                        if any(x in content for x in ["@param", "@return", "function"]):
                            file_result["has_annotation"] = True
                    elif file_language == "ruby":
                        if any(x in content for x in ["sig", "T."]):
                            file_result["has_annotation"] = True
                    
                    # If fast path didn't find anything and we have time, try regex patterns
                    if not file_result["has_annotation"] and time.time() - start < max_analysis_time * 0.8:
                        if file_language in type_annotation_patterns:
                            for pattern in type_annotation_patterns[file_language][:2]:  # Limit to first 2 patterns
                                if time.time() - start > max_analysis_time:
                                    break
                                try:
                                    if re.search(pattern, content[:10000], re.MULTILINE):  # Limit search to first 10KB
                                        file_result["has_annotation"] = True
                                        break
                                except:
                                    continue
                    
                    # Check for type checker imports/usage
                    if file_language in type_checkers and time.time() - start < max_analysis_time:
                        for checker in type_checkers[file_language]:
                            if checker in content:
                                file_result["checker_tools"].add(checker)
                    
                    # Skip issue detection - too expensive and not critical
                except Exception:
                    pass
            
            return file_path, file_language, file_result
        
        # Use ThreadPoolExecutor with controlled concurrency and timeouts
        max_workers = min(3, os.cpu_count() or 2)  # Further reduced from 4 to 3
        analysis_results = []
        
        # Set overall analysis timeout
        analysis_timeout = 15  # Further reduced from 25 to 15 seconds
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {}
            
            # Submit all file analysis tasks
            for file_data in eligible_files:
                # Check if overall time limit exceeded before submitting
                if time.time() - start_time > max_execution_time:
                    logger.warning(f"Internal execution timeout reached before submitting all tasks.")
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "internal_execution_limit"
                    break
                future = executor.submit(analyze_file, file_data)
                future_to_file[future] = file_data
            
            # Process results as they complete
            for future in as_completed(future_to_file):
                # Check timeouts (these remain important)
                current_time = time.time()
                if current_time - start_time > max_execution_time:
                    logger.warning(f"Internal execution timeout reached during analysis. Stopping.")
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "internal_execution_limit"
                    # Attempt to cancel remaining futures
                    for f in future_to_file:
                        if not f.done():
                            f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                    
                if current_time - analysis_start_time > analysis_timeout:
                    logger.warning(f"Internal analysis timeout after {analysis_timeout}s. Processing results collected so far.")
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "internal_analysis_timeout"
                    # Attempt to cancel remaining futures
                    for f in future_to_file:
                        if not f.done():
                            f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                    
                try:
                    # Short timeout for individual file result
                    result_data = future.result(timeout=1.0)
                    analysis_results.append(result_data)
                except (TimeoutError, concurrent.futures.TimeoutError):
                    # Log if a specific file analysis timed out, but continue
                    logger.debug(f"Analysis of file {future_to_file[future]} timed out.")
                except concurrent.futures.CancelledError:
                    logger.debug(f"Analysis of file {future_to_file[future]} was cancelled.")
                except Exception as e:
                    # Log other errors during file analysis
                    logger.debug(f"Error analyzing file {future_to_file[future]}: {e}")
    
    # Record analysis time
    analysis_time = time.time() - analysis_start_time
    result["performance_info"]["analysis_time"] = round(analysis_time, 2)
    
    # Process the results we have
    all_issues = []
    for file_path, file_language, file_result in analysis_results:
        files_checked += 1
        
        if file_result["has_annotation"]:
            if file_language in type_annotations_counts:
                type_annotations_counts[file_language] += 1
            result["has_type_annotations"] = True
            result["type_metrics"]["files_with_annotations"] += 1
        
        for checker in file_result["checker_tools"]:
            type_checker_found.add(checker)
            result["has_type_checking"] = True
        
        all_issues.extend(file_result["issues"])
    
    # Only keep the first 5 issues
    result["type_issues"] = all_issues[:5]
    
    # Very quick check for config files in the root directory only
    if time.time() - start_time < max_execution_time - 1: # Check if some time left
        for lang, patterns in type_check_config_patterns.items():
            # Only check languages we found in the repo
            if lang not in language_counts["optionally_typed"] and lang not in language_counts["statically_typed"]:
                continue
                
            for pattern in patterns:
                # Only check exact files in root directory
                config_path = os.path.join(repo_path, pattern)
                if os.path.isfile(config_path):
                    result["has_type_checking"] = True
                    if lang in type_checkers:
                        for checker in type_checkers[lang]:
                            if checker in pattern:
                                type_checker_found.add(checker)
                                break
    
    # Categorize languages by type safety
    for lang, count in language_counts["statically_typed"].items():
        if lang not in result["typed_languages"]:
            result["typed_languages"].append(lang)
    
    for lang, count in language_counts["optionally_typed"].items():
        total = total_files_by_language.get(lang, 0)
        typed = type_annotations_counts.get(lang, 0)
        
        # Consider a language "typed" if at least 25% of files have type annotations
        # (Reduced from 30% to 25% to be more lenient)
        if total > 0 and typed / total >= 0.25:
            if lang not in result["typed_languages"]:
                result["typed_languages"].append(lang)
        else:
            if lang not in result["untyped_languages"]:
                result["untyped_languages"].append(lang)
    
    # Calculate overall type annotation ratio
    total_optional_files = sum(total_files_by_language.values())
    total_typed_files = sum(type_annotations_counts.values())
    
    if total_optional_files > 0:
        result["type_annotation_ratio"] = round(total_typed_files / total_optional_files, 2)
        result["type_metrics"]["typed_code_coverage"] = result["type_annotation_ratio"] * 100
    
    result["files_checked"] = files_checked
    result["type_check_tools"] = sorted(list(type_checker_found))
    
    # Calculate type safety score (1-100 scale)
    score = 1  # Minimum score
    
    # Points for having static typing
    if result["typed_languages"]:
        # Base points for static typing (up to 40)
        static_typed_langs = [lang for lang in result["typed_languages"] 
                             if lang in language_extensions["statically_typed"]]
        static_typed_points = min(40, len(static_typed_langs) * 15)
        score += static_typed_points
    
    # Points for type annotations
    if result["has_type_annotations"]:
        ratio = result["type_annotation_ratio"]
        if ratio >= 0.8:
            score += 35  # Excellent type coverage
        elif ratio >= 0.6:
            score += 25  # Very good type coverage
        elif ratio >= 0.4:
            score += 15  # Good type coverage
        elif ratio >= 0.2:
            score += 8   # Moderate type coverage
        else:
            score += 4   # Minimal type coverage
    
    # Points for using type checking tools
    if result["has_type_checking"]:
        checker_points = min(25, len(result["type_check_tools"]) * 8)
        score += checker_points
    
    # Penalty for type issues
    issue_count = len(result["type_issues"])
    if issue_count > 0:
        penalty = min(15, issue_count * 1.5)
        score = max(1, score - penalty)
    
    # Cap score at 100
    result["type_safety_score"] = min(100, round(score, 1))
    
    # Performance metrics
    execution_time = time.time() - start_time
    logger.debug(f"Type safety check completed processing in {execution_time:.2f} seconds, analyzed {files_checked} files")
    
    # Add note if execution was early terminated due to internal limits
    if result["performance_info"]["early_termination"]:
        reason = result['performance_info']['timeout_reason'] or 'internal limit'
        result["execution_note"] = f"Check terminated early due to {reason}. Results may be partial."
    
    # Removed the final cleanup block for signal handler
    return result

def simple_glob_match(pattern: str, filename: str) -> bool:
    """Simplified glob pattern matching for config files - just check for exact match"""
    return pattern == filename  # Simplest possible check for better performance

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the type safety check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 1-100 scale
    """
    # Keep the existing run_check logic which uses threading.Timer implicitly via join timeout
    start_run_time = time.time()
    try:
        local_path = repository.get('local_path')
        
        result_container = {"result": None, "done": False, "error": None}
        
        def run_core_check():
            try:
                # Call the modified check_type_safety function
                result_container["result"] = check_type_safety(local_path, repository)
            except Exception as e:
                logger.error(f"Error within check_type_safety thread: {e}", exc_info=True)
                result_container["error"] = e
            finally:
                result_container["done"] = True
        
        check_thread = threading.Thread(target=run_core_check)
        check_thread.daemon = True
        check_thread.start()
        
        # Wait with timeout (this is the primary timeout mechanism now)
        check_thread.join(CHECK_TIMEOUT) # Use the defined CHECK_TIMEOUT
        
        run_duration = time.time() - start_run_time

        if not result_container["done"]:
            logger.error(f"Type safety check thread timed out after {CHECK_TIMEOUT} seconds")
            # Return a timeout status
            return {
                "status": "timeout",
                "score": 0,
                "result": {
                    "error": f"Check timed out after {CHECK_TIMEOUT} seconds",
                    "timed_out": True,
                    "processing_time": CHECK_TIMEOUT,
                    # Add default values for expected keys
                    "has_type_annotations": False,
                    "has_type_checking": False,
                    "type_safety_score": 0,
                    "typed_languages": [],
                    "untyped_languages": [],
                    "execution_note": f"Check timed out after {CHECK_TIMEOUT} seconds.",
                    "performance_info": {"early_termination": True, "timeout_reason": "thread_timeout"}
                },
                "errors": "timeout"
            }
        
        if result_container["error"]:
             # Handle errors that occurred inside the thread
             error = result_container["error"]
             logger.error(f"Type safety check failed with error: {error}", exc_info=error)
             return {
                 "status": "failed",
                 "score": 0,
                 "result": {
                     "error": str(error),
                     "timed_out": False,
                     "processing_time": round(run_duration, 2),
                     # Add default values
                     "has_type_annotations": False,
                     "has_type_checking": False,
                     "type_safety_score": 0,
                     "typed_languages": [],
                     "untyped_languages": [],
                     "execution_note": f"Check failed with error: {str(error)}.",
                     "performance_info": {"early_termination": True, "timeout_reason": "error"}
                 },
                 "errors": str(error)
             }

        # Get the result from the container
        result = result_container["result"]
        
        # Add processing time if not already timed out internally
        if "processing_time" not in result:
             result["processing_time"] = round(run_duration, 2)

        # Determine status based on internal timeout flags
        status = "completed"
        errors = None
        if result.get("performance_info", {}).get("early_termination"):
             timeout_reason = result.get("performance_info", {}).get("timeout_reason")
             if "timeout" in timeout_reason or "limit" in timeout_reason:
                 status = "timeout" # Treat internal timeouts/limits as timeout status
                 errors = "internal timeout/limit"
             else: # e.g., error during discovery
                 status = "completed_partial" # Or consider 'failed' depending on severity
                 errors = result.get("execution_note")

        return {
            "status": status,
            "score": result.get("type_safety_score", 0),
            "result": result,
            "errors": errors
        }
    except Exception as e:
        # Catch errors in run_check itself
        logger.error(f"Outer error running type safety check: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"error": str(e)},
            "errors": str(e)
        }