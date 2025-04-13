"""
Type Safety Check

Analyzes the repository's code for type safety features and type annotations.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time

# Setup logging
logger = logging.getLogger(__name__)

def check_type_safety(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for type safety features in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    start_time = time.time()
    
    # Overall execution timeout - halt processing if it takes too long
    max_execution_time = 120  # 2 minutes maximum for the entire check
    
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
            r'/\*\*(?:(?!\*/).)*@type(?:(?!\*/).)*\*/',  # JSDoc type
            r'/\*\*(?:(?!\*/).)*@param(?:(?!\*/).)*\{(?:(?!\*/).)*\}(?:(?!\*/).)*\*/',  # JSDoc param type
            r'/\*\*(?:(?!\*/).)*@returns?(?:(?!\*/).)*\{(?:(?!\*/).)*\}(?:(?!\*/).)*\*/'  # JSDoc return type
        ],
        "php": [
            r'function\s+\w+\s*\(.*\)\s*:\s*\w+',  # PHP 7+ return type
            r'function\s+\w+\s*\(\s*\w+\s*\$\w+(?:\s*,\s*\w+\s*\$\w+)*\s*\)',  # PHP 7+ type hints
            r'@param\s+\w+',  # PHPDoc param type
            r'@return\s+\w+'  # PHPDoc return type
        ],
        "ruby": [
            r'sig\s+do',  # Sorbet sig block
            r'T\.(?:untyped|nilable|any|bool|enum|class_of)',  # Sorbet types
            r'T::(Boolean|String|Symbol|Integer|Float|Array|Hash)'  # Sorbet types
        ]
    }
    
    # Patterns to detect type checking configuration
    type_check_config_patterns = {
        "python": [
            r'mypy\.ini', r'\.mypy\.ini', r'\.mypy_cache',
            r'pytype\.cfg',
            r'\.pyre_configuration'
        ],
        "javascript": [
            r'tsconfig\.json', r'jsconfig\.json', r'\.flowconfig',
            r'@ts-check', r'@ts-nocheck', r'@flow'
        ],
        "php": [
            r'phpstan\.neon', r'psalm\.xml', r'\.phan'
        ],
        "ruby": [
            r'sorbet', r'\.rb[sm]'
        ]
    }
    
    files_checked = 0
    language_counts = {"statically_typed": {}, "optionally_typed": {}}
    type_annotations_counts = {}
    total_files_by_language = {}
    type_checker_found = set()
    
    # Use a set to track directories to skip for faster lookup
    skip_dirs = {'/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/', '/vendor/', '/venv/',
                '/cache/', '/.pytest_cache/', '/coverage/', '/target/', '/out/', '/.idea/', '/.vscode/'}
    
    # Maximum number of files to analyze per language to prevent performance issues
    max_files_per_language = 150  # Reduced to improve performance
    max_total_files = 800  # Overall file limit
    files_per_language = {}
    
    # Get all eligible files first to improve performance
    eligible_files = []
    total_file_count = 0
    
    # Use a timeout for the file discovery to prevent hanging
    file_discovery_timeout = 20  # 20 seconds max for file discovery
    file_discovery_start = time.time()
    
    # Maximum file size to analyze (in bytes) - skip larger files
    max_file_size = 500 * 1024  # 500KB maximum file size
    
    try:
        for root, _, files in os.walk(repo_path):
            # Check if overall execution timeout has been reached
            if time.time() - start_time > max_execution_time:
                logger.warning(f"Overall execution timeout reached after {max_execution_time}s. Finalizing results.")
                break
                
            # Check timeout for file discovery
            if time.time() - file_discovery_start > file_discovery_timeout:
                logger.warning(f"File discovery timeout after {file_discovery_timeout}s. Proceeding with files found so far.")
                break
            
            # Normalize path for directory skipping check
            normalized_root = root.replace('\\', '/')
            if any(skip_dir in normalized_root for skip_dir in skip_dirs):
                continue
                
            for file in files:
                # Check overall file limit
                if total_file_count >= max_total_files:
                    logger.info(f"Reached maximum file count limit ({max_total_files}). Stopping file discovery.")
                    break
                    
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()
                
                # Skip files larger than 1MB to prevent hanging on large files
                try:
                    if os.path.getsize(file_path) > 1024 * 1024:
                        logger.debug(f"Skipping large file: {file_path}")
                        continue
                except (OSError, IOError) as e:
                    logger.debug(f"Error checking file size: {e}")
                    continue
                
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
                    logger.info(f"Reached maximum file count limit ({max_total_files}).")
                    break
            
            # Check if we've reached the max total files limit (after inner loop)
            if total_file_count >= max_total_files:
                break
    except (PermissionError, OSError) as e:
        logger.error(f"File system access error during file discovery: {e}")
    except Exception as e:
        logger.error(f"Error during file discovery: {e}")
    
    # Log statistics
    logger.info(f"Found {len(eligible_files)} eligible files for analysis across {len(files_per_language)} languages")
    
    # Analyze files more efficiently with parallel processing
    def analyze_file(file_data):
        file_path, file_language, typing_category = file_data
        file_result = {
            "has_annotation": False,
            "checker_tools": set(),
            "issues": []
        }
        
        # Only analyze optionally typed files
        if typing_category == "optionally_typed":
            try:
                # Check if file still exists and is accessible before reading
                if not os.path.exists(file_path) or not os.path.isfile(file_path):
                    logger.debug(f"File no longer exists or is not accessible: {file_path}")
                    return file_path, file_language, file_result
                
                # Use a timeout for file reading to prevent hanging
                file_read_timeout = 1.5  # 1.5 seconds max per file read
                
                # Read file with timeout
                content = None
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # Use a limited read to avoid memory issues with large files
                        content = f.read(max_file_size)
                except UnicodeDecodeError:
                    logger.debug(f"Unicode decode error in file {file_path}")
                    return file_path, file_language, file_result
                except (PermissionError, OSError) as e:
                    logger.debug(f"File system error reading {file_path}: {e}")
                    return file_path, file_language, file_result
                except Exception as e:
                    logger.debug(f"Error reading file {file_path}: {e}")
                    return file_path, file_language, file_result
                
                if content:
                    # Look for type annotations
                    if file_language in type_annotation_patterns:
                        for pattern in type_annotation_patterns[file_language]:
                            if re.search(pattern, content, re.MULTILINE):
                                file_result["has_annotation"] = True
                                break
                    
                    # Check for type checker imports/usage
                    if file_language in type_checkers:
                        for checker in type_checkers[file_language]:
                            checker_pattern = fr'\b{re.escape(checker)}\b'
                            if re.search(checker_pattern, content, re.IGNORECASE):
                                file_result["checker_tools"].add(checker)
                    
                    # Look for potential type issues in files with annotations
                    if file_result["has_annotation"]:
                        # Check for explicit 'Any' usage which bypasses type checking
                        if file_language == "python" and re.search(r'\bAny\b', content):
                            relative_path = os.path.relpath(file_path, repo_path)
                            file_result["issues"].append({
                                "file": relative_path,
                                "issue": "Uses 'Any' type which bypasses type checking"
                            })
                        
                        # For TypeScript/JavaScript, look for 'any' usage
                        if file_language in ["javascript", "typescript"] and re.search(r'\bany\b', content):
                            relative_path = os.path.relpath(file_path, repo_path)
                            file_result["issues"].append({
                                "file": relative_path,
                                "issue": "Uses 'any' type which bypasses type checking"
                            })
                        
                        # For PHP, look for mixed type hints
                        if file_language == "php" and re.search(r'\bmixed\b', content):
                            relative_path = os.path.relpath(file_path, repo_path)
                            file_result["issues"].append({
                                "file": relative_path,
                                "issue": "Uses 'mixed' type which is less strict"
                            })
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
        
        return file_path, file_language, file_result
    
    # Use ThreadPoolExecutor for parallelism with controlled concurrency and timeouts
    max_workers = min(8, os.cpu_count() or 4)  # Optimized worker count
    analysis_results = []
    
    # Use a per-file timeout
    file_analysis_timeout = 3  # 3 seconds max per file analysis
    
    # Set overall analysis timeout
    analysis_start_time = time.time()
    analysis_timeout = 40  # 40 seconds max for entire analysis
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all file analysis tasks
        future_to_file = {executor.submit(analyze_file, file_data): file_data for file_data in eligible_files}
        
        # Process results as they complete, with timeout
        for future in as_completed(future_to_file):
            # Check if overall execution timeout has been reached
            if time.time() - start_time > max_execution_time:
                logger.warning(f"Overall execution timeout reached. Processing results collected so far.")
                executor.shutdown(wait=False)  # Stop processing remaining files
                break
                
            # Check if overall analysis timeout has been reached
            if time.time() - analysis_start_time > analysis_timeout:
                logger.warning(f"Analysis timeout after {analysis_timeout}s. Processing results collected so far.")
                executor.shutdown(wait=False)  # Stop processing remaining files
                break
                
            try:
                result_data = future.result(timeout=file_analysis_timeout)
                analysis_results.append(result_data)
            except TimeoutError:
                file_data = future_to_file[future]
                logger.warning(f"Timeout analyzing file: {file_data[0]}")
            except Exception as e:
                file_data = future_to_file[future]
                logger.error(f"Error analyzing file {file_data[0]}: {e}")
    
    # Process analysis results
    all_issues = []
    for file_path, file_language, file_result in analysis_results:
        files_checked += 1
        
        if file_result["has_annotation"]:
            type_annotations_counts[file_language] += 1
            result["has_type_annotations"] = True
            result["type_metrics"]["files_with_annotations"] += 1
        
        for checker in file_result["checker_tools"]:
            type_checker_found.add(checker)
            result["has_type_checking"] = True
        
        all_issues.extend(file_result["issues"])
    
    # Only keep the first 10 issues to avoid flooding the results
    result["type_issues"] = all_issues[:10]
    
    # Check for type checker config files with a timeout
    config_check_timeout = 3  # 3 seconds max for config file checks
    config_check_start = time.time()
    
    try:
        for lang, patterns in type_check_config_patterns.items():
            # Check if overall execution timeout has been reached
            if time.time() - start_time > max_execution_time:
                logger.warning("Overall execution timeout reached during config checks.")
                break
                
            # Check timeout for config file checks
            if time.time() - config_check_start > config_check_timeout:
                logger.warning(f"Config file check timeout after {config_check_timeout}s.")
                break
                
            for pattern in patterns:
                # Look for configuration files in root or common directories
                for config_dir in ['', 'config/', '.config/', '.github/']:
                    # Check timeout inside inner loop too
                    if time.time() - config_check_start > config_check_timeout:
                        break
                        
                    config_path = os.path.join(repo_path, config_dir)
                    
                    # Skip if the directory doesn't exist
                    if not os.path.exists(config_path) or not os.path.isdir(config_path):
                        continue
                    
                    # Check for exact file match
                    full_pattern_path = os.path.join(config_path, pattern)
                    if os.path.exists(full_pattern_path):
                        result["has_type_checking"] = True
                        if lang in type_checkers:
                            for checker in type_checkers[lang]:
                                if checker in pattern:
                                    type_checker_found.add(checker)
                                    break
                        break
                    
                    # Check for glob pattern match with timeout
                    try:
                        for file in os.listdir(config_path):
                            # Check timeout
                            if time.time() - config_check_start > config_check_timeout:
                                break
                                
                            if os.path.isfile(os.path.join(config_path, file)) and glob_match(pattern, file):
                                result["has_type_checking"] = True
                                if lang in type_checkers:
                                    for checker in type_checkers[lang]:
                                        if checker in pattern:
                                            type_checker_found.add(checker)
                                            break
                                break
                    except (FileNotFoundError, PermissionError) as e:
                        logger.debug(f"Could not access directory {config_path}: {e}")
                    except Exception as e:
                        logger.debug(f"Error listing files in {config_path}: {e}")
    except Exception as e:
        logger.error(f"Error during config file checks: {e}")

    # Categorize languages by type safety
    for lang, count in language_counts["statically_typed"].items():
        if lang not in result["typed_languages"]:
            result["typed_languages"].append(lang)
    
    for lang, count in language_counts["optionally_typed"].items():
        total = total_files_by_language.get(lang, 0)
        typed = type_annotations_counts.get(lang, 0)
        
        # Consider a language "typed" if at least 40% of files have type annotations
        if total > 0 and typed / total >= 0.4:
            if lang not in result["typed_languages"]:
                result["typed_languages"].append(lang)
        else:
            if lang not in result["untyped_languages"]:
                result["untyped_languages"].append(lang)
    
    # Calculate overall type annotation ratio for optionally typed languages
    total_optional_files = sum(total_files_by_language.values())
    total_typed_files = sum(type_annotations_counts.values())
    
    if total_optional_files > 0:
        result["type_annotation_ratio"] = round(total_typed_files / total_optional_files, 2)
        result["type_metrics"]["typed_code_coverage"] = result["type_annotation_ratio"] * 100
    
    result["files_checked"] = files_checked
    result["type_check_tools"] = sorted(list(type_checker_found))
    
    # Calculate type safety score (1-100 scale)
    score = 1  # Minimum score for a successful check
    
    # Points for having static typing
    if result["typed_languages"]:
        # Base points for static typing (up to 40)
        static_typed_langs = [lang for lang in result["typed_languages"] 
                             if lang in language_extensions["statically_typed"]]
        static_typed_points = min(40, len(static_typed_langs) * 15)
        score += static_typed_points
    
    # Points for type annotations in optionally typed languages (up to 35)
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
    
    # Points for using type checking tools (up to 25)
    if result["has_type_checking"]:
        checker_points = min(25, len(result["type_check_tools"]) * 8)
        score += checker_points
    
    # Penalty for type issues (up to -15)
    issue_count = len(result["type_issues"])
    if issue_count > 0:
        penalty = min(15, issue_count * 1.5)
        score = max(1, score - penalty)  # Ensure score doesn't go below 1
    
    # Cap score at 100
    result["type_safety_score"] = min(100, round(score, 1))
    
    # Performance metrics
    execution_time = time.time() - start_time
    logger.info(f"Type safety check completed in {execution_time:.2f} seconds, analyzed {files_checked} files")
    
    # If execution timeout was reached, add a note to results
    if execution_time >= max_execution_time:
        result["execution_note"] = "Check was stopped due to timeout. Results may be incomplete."
    
    return result

def glob_match(pattern: str, filename: str) -> bool:
    """Simple glob pattern matching for configuration files"""
    try:
        import re
        pattern_regex = pattern.replace('.', r'\.').replace('*', r'.*')
        return bool(re.match(f"^{pattern_regex}$", filename))
    except Exception as e:
        logger.debug(f"Error in glob matching: {e}")
        return False

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the type safety check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 1-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with internal timeouts to prevent hanging
        result = check_type_safety(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("type_safety_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running type safety check: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,  # Score 0 for failed checks
            "result": {"error": str(e)},
            "errors": str(e)
        }