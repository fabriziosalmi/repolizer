"""
Code Smells Check

Identifies potential code smells and anti-patterns in the repository.
"""
import os
import re
import logging
import time
import threading
import platform
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed

# Setup logging
logger = logging.getLogger(__name__)

# Global flag to indicate if analysis should stop
STOP_ANALYSIS = False

def check_code_smells(repo_path: str = None, repo_data: Dict = None, timeout_seconds: int = 60) -> Dict[str, Any]:
    """
    Check for code smells in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        timeout_seconds: Maximum time allowed for the check in seconds
        
    Returns:
        Dictionary with check results
    """
    # Reset global flag
    global STOP_ANALYSIS
    STOP_ANALYSIS = False
    
    # Set a timer to force termination
    def force_timeout():
        global STOP_ANALYSIS
        STOP_ANALYSIS = True
        logger.warning(f"Force timeout triggered after {timeout_seconds} seconds")
    
    # Schedule the timeout
    timeout_timer = threading.Timer(timeout_seconds, force_timeout)
    timeout_timer.daemon = True
    timeout_timer.start()
    
    try:
        # Start timing the execution
        start_time = time.time()
        
        # Force timeout even if signal-based timeout fails
        hard_timeout = start_time + timeout_seconds
        
        result = {
            "code_smells_found": False,
            "smell_count": 0,
            "smells_by_category": {
                "long_method": 0,
                "large_class": 0,
                "primitive_obsession": 0,
                "long_parameter_list": 0,
                "duplicate_code": 0,
                "inappropriate_intimacy": 0,
                "feature_envy": 0,
                "magic_numbers": 0,
                "commented_code": 0,
                "dead_code": 0
            },
            "smells_by_language": {},
            "detected_smells": [],
            "files_checked": 0,
            "timed_out": False,
            "processing_time": 0
        }
        
        # Check if repository is available locally
        if not repo_path or not os.path.isdir(repo_path):
            logger.warning("No local repository path provided or path is not a directory")
            return result
        
        # File extensions and patterns by language
        language_patterns = {
            "python": {
                "extensions": [".py"],
                "function_pattern": r'def\s+(\w+)\s*\(([^)]*)\)',
                "class_pattern": r'class\s+(\w+)',
                "method_pattern": r'def\s+(\w+)\s*\(self,\s*([^)]*)\)',
                "import_pattern": r'import\s+(\w+)|from\s+(\w+)\s+import',
                "magic_number_pattern": r'(^|[^\w.])[-+]?\d+(?:\.\d+)?(?!\w|\.|px|\%)',
                "commented_code_pattern": r'^\s*#\s*(def|class|if|while|for|import|with)'
            },
            "javascript": {
                "extensions": [".js", ".jsx", ".ts", ".tsx"],
                "function_pattern": r'function\s+(\w+)\s*\(([^)]*)\)|(\w+)\s*[=:]\s*function\s*\(([^)]*)\)|(\w+)\s*[=:]\s*\(([^)]*)\)\s*=>',
                "class_pattern": r'class\s+(\w+)',
                "method_pattern": r'(\w+)\s*\(([^)]*)\)\s*{',
                "import_pattern": r'import\s+.*\s+from\s+[\'"](.+)[\'"]|require\([\'"](.+)[\'"]\)',
                "magic_number_pattern": r'(^|[^\w.])[-+]?\d+(?:\.\d+)?(?!\w|\.|px|\%)',
                "commented_code_pattern": r'^\s*\/\/\s*(function|class|if|while|for|import|const|let|var)'
            },
            "java": {
                "extensions": [".java"],
                "function_pattern": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\(([^)]*)\)',
                "class_pattern": r'class\s+(\w+)',
                "method_pattern": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\(([^)]*)\)',
                "import_pattern": r'import\s+([^;]+);',
                "magic_number_pattern": r'(^|[^\w.])[-+]?\d+(?:\.\d+)?(?!\w|\.|px|\%)',
                "commented_code_pattern": r'^\s*\/\/\s*(public|private|class|if|while|for|import)'
            }
        }
        
        # Thresholds for code smells
        thresholds = {
            "long_method_lines": 50,
            "large_class_methods": 20,
            "long_parameter_list": 5,
            "magic_numbers_per_file": 10,
            "commented_code_per_file": 5
        }
        
        # Initialize language-specific stats
        for lang in language_patterns:
            result["smells_by_language"][lang] = {
                "files": 0,
                "smells": 0,
                "by_category": {cat: 0 for cat in result["smells_by_category"]}
            }
        
        files_checked = 0
        smell_count = 0
        
        # Helper function to update smell counts
        def record_smell(language: str, category: str, file_path: str, line: int, description: str):
            nonlocal smell_count
            
            # Update overall counts
            smell_count += 1
            result["smells_by_category"][category] += 1
            result["code_smells_found"] = True
            
            # Update language-specific counts
            result["smells_by_language"][language]["smells"] += 1
            result["smells_by_language"][language]["by_category"][category] += 1
            
            # Add to detected smells list (limit to 50 examples)
            if len(result["detected_smells"]) < 50:
                relative_path = os.path.relpath(file_path, repo_path)
                result["detected_smells"].append({
                    "file": relative_path,
                    "line": line,
                    "category": category,
                    "description": description
                })

        # Collect files to analyze first
        files_to_analyze = []
        
        try:
            # Set a timeout for file collection
            file_collection_timeout = min(timeout_seconds * 0.3, 15)  # Max 15s or 30% of total time
            file_collection_end = time.time() + file_collection_timeout
            
            # Walk the repository to find files
            for root, _, files in os.walk(repo_path):
                # Check timeout for file collection
                if STOP_ANALYSIS or time.time() > file_collection_end or time.time() > hard_timeout:
                    logger.warning(f"File collection timed out after {time.time() - start_time:.2f} seconds")
                    result["timed_out"] = True
                    break
                    
                # Skip common directories to avoid wasting time
                if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/']):
                    continue
                    
                for file in files:
                    # Check timeout again for each file
                    if STOP_ANALYSIS or time.time() > file_collection_end or time.time() > hard_timeout:
                        break
                        
                    file_path = os.path.join(root, file)
                    _, ext = os.path.splitext(file_path)
                    ext = ext.lower()
                    
                    # Determine language for this file
                    file_language = None
                    for lang, config in language_patterns.items():
                        if ext in config["extensions"]:
                            file_language = lang
                            break
                    
                    # Skip files we don't know how to analyze
                    if not file_language:
                        continue
                    
                    # Skip files larger than 1MB to avoid processing massive files
                    try:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        if file_size_mb > 1:
                            logger.info(f"Skipping large file: {file_path} ({file_size_mb:.2f} MB)")
                            continue
                    except Exception as e:
                        logger.error(f"Error checking file size for {file_path}: {e}")
                        continue
                        
                    # Add to files to analyze
                    files_to_analyze.append((file_path, file_language))
                    
                    # Stop collecting files if we already have plenty
                    if len(files_to_analyze) >= 500:
                        logger.info(f"Limiting analysis to 500 files to ensure completion")
                        break
        except Exception as e:
            logger.error(f"Error walking repository: {e}")
        
        # Check if we should continue or if we've already timed out
        if STOP_ANALYSIS or time.time() > hard_timeout:
            result["timed_out"] = True
            result["processing_time"] = round(time.time() - start_time, 2)
            return result

        # Limit the number of files to analyze if there are too many
        max_files_to_analyze = 200
        if len(files_to_analyze) > max_files_to_analyze:
            logger.info(f"Limiting analysis to {max_files_to_analyze} files out of {len(files_to_analyze)}")
            
            # Take a stratified sample by extension/language
            files_by_language = {}
            for file_path, language in files_to_analyze:
                if language not in files_by_language:
                    files_by_language[language] = []
                files_by_language[language].append((file_path, language))
            
            # Sample files from each language
            sampled_files = []
            for language, files in files_by_language.items():
                # Get proportional number of files for this language
                count = max(1, int(max_files_to_analyze * len(files) / len(files_to_analyze)))
                if len(files) <= count:
                    sampled_files.extend(files)
                else:
                    # Take files from beginning, middle, and end
                    step = len(files) // count
                    for i in range(0, min(count, len(files))):
                        idx = min(i * step, len(files) - 1)
                        sampled_files.append(files[idx])
            
            # Use the sampled files
            files_to_analyze = sampled_files[:max_files_to_analyze]
        
        # Calculate time per file
        remaining_time = max(1, hard_timeout - time.time())
        time_per_file = max(0.5, min(3, remaining_time / len(files_to_analyze)))
        logger.info(f"Allocating {time_per_file:.2f} seconds per file analysis for {len(files_to_analyze)} files")
        
        # Use a thread pool to analyze files in parallel with timeout protection
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as executor:
            futures = {
                executor.submit(analyze_file_with_timeout, 
                               file_path, language, language_patterns, thresholds, time_per_file): 
                (file_path, language) 
                for file_path, language in files_to_analyze
            }
            
            # Process results as they complete
            for future in as_completed(futures):
                # Check if we should stop
                if STOP_ANALYSIS or time.time() > hard_timeout:
                    result["timed_out"] = True
                    logger.warning(f"Analysis timed out after {time.time() - start_time:.2f} seconds")
                    
                    # Cancel any pending futures
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    break
                
                file_path, language = futures[future]
                
                try:
                    analysis_result = future.result(timeout=0.1)  # Just grab completed result
                    if analysis_result:
                        file_smells, file_timed_out = analysis_result
                        
                        if file_timed_out:
                            logger.warning(f"Analysis of {file_path} timed out")
                            continue
                        
                        # Update counts
                        files_checked += 1
                        result["smells_by_language"][language]["files"] += 1
                        
                        # Record all smells found for this file
                        for smell in file_smells:
                            record_smell(language, smell['category'], file_path, smell['line'], smell['description'])
                except FutureTimeoutError:
                    logger.warning(f"Retrieving result for {file_path} timed out")
                    continue
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    continue
        
        # Update final smell count and files checked
        result["smell_count"] = smell_count
        result["files_checked"] = files_checked
        
        # Calculate code smells score (0-100 scale, higher is better)
        smell_score = 100
        
        if files_checked > 0:
            # Calculate smell density (smells per file)
            smell_density = smell_count / files_checked
            
            if smell_density >= 5:
                smell_score = 0  # Critical: Many code smells per file
            elif smell_density >= 3:
                smell_score = 20  # Severe: Several code smells per file
            elif smell_density >= 2:
                smell_score = 40  # Major: Some code smells per file
            elif smell_density >= 1:
                smell_score = 60  # Moderate: Occasional code smells
            elif smell_density >= 0.5:
                smell_score = 80  # Minor: Few code smells
            elif smell_density > 0:
                smell_score = 90  # Minimal: Very few code smells
        
        # Specific penalties for certain categories
        if result["smells_by_category"]["large_class"] > 0:
            smell_score = max(0, smell_score - 10)  # Large classes are particularly problematic
        
        if result["smells_by_category"]["long_method"] > 5:
            smell_score = max(0, smell_score - 10)  # Many long methods indicate poor design
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(smell_score, 1)
        result["code_smells_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
        
        # Record processing time
        result["processing_time"] = round(time.time() - start_time, 2)
        
        # Force timed_out flag if we exceeded timeout or if global flag is set
        if result["processing_time"] >= timeout_seconds or STOP_ANALYSIS:
            result["timed_out"] = True
        
        return result
    finally:
        # Clean up the timer
        timeout_timer.cancel()

def analyze_file_with_timeout(file_path: str, language: str, language_patterns: Dict, 
                             thresholds: Dict, timeout: float = 2.0) -> Tuple[List, bool]:
    """
    Analyze a file with a timeout to prevent hanging
    
    Args:
        file_path: Path to the file
        language: Programming language of the file
        language_patterns: Dictionary of regex patterns for each language
        thresholds: Dictionary of thresholds for detecting smells
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (detected_smells, timed_out_flag)
    """
    global STOP_ANALYSIS
    
    # Quick check for global timeout
    if STOP_ANALYSIS:
        return ([], True)
    
    try:
        # Set a slightly shorter timeout to ensure we return before the outer timeout hits
        actual_timeout = max(0.2, timeout * 0.9)
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(analyze_file, file_path, language, language_patterns, thresholds)
            try:
                result = future.result(timeout=actual_timeout)
                return (result, False)  # False indicates no timeout
            except FutureTimeoutError:
                logger.warning(f"Analysis of {file_path} timed out after {timeout} seconds")
                future.cancel()
                return ([], True)  # True indicates timeout
    except Exception as e:
        logger.error(f"Error analyzing file {file_path}: {e}")
        return ([], False)

def analyze_file(file_path: str, language: str, language_patterns: Dict, thresholds: Dict) -> List[Dict]:
    """
    Analyze a code file for smells
    
    Args:
        file_path: Path to the file
        language: Programming language of the file
        language_patterns: Dictionary of regex patterns for each language
        thresholds: Dictionary of thresholds for detecting smells
        
    Returns:
        List of detected smells
    """
    global STOP_ANALYSIS
    
    # Check if we should stop
    if STOP_ANALYSIS:
        return []
    
    detected_smells = []
    
    try:
        # Safety check for file size before reading
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 1:  # Skip files larger than 1MB
            logger.info(f"Skipping large file during analysis: {file_path} ({file_size_mb:.2f} MB)")
            return []
        
        # Read with a limit on content size
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read limited amount to avoid memory issues
            content = f.read(1024 * 1024)  # Read at most 1MB
    except Exception as e:
        logger.error(f"Could not read file {file_path}: {e}")
        return []
    
    # If file reading took too long, we might need to exit
    if STOP_ANALYSIS:
        return []
    
    # Get language-specific patterns
    language_config = language_patterns.get(language, {})
    if not language_config:
        return []
    
    lines = content.split('\n')
    
    # Limit lines to avoid excessive processing
    max_lines = 5000
    if len(lines) > max_lines:
        logger.info(f"Limiting analysis to {max_lines} lines for {file_path}")
        lines = lines[:max_lines]
    
    # Periodic timeout check
    if STOP_ANALYSIS:
        return detected_smells
    
    # Check for large classes
    try:
        class_matches = re.finditer(language_config["class_pattern"], content, re.MULTILINE)
        for match in class_matches:
            # Periodic timeout check
            if STOP_ANALYSIS:
                return detected_smells
                
            class_name = match.group(1)
            class_start = match.start()
            class_line = content[:class_start].count('\n') + 1
            
            # Count methods in class (simple approach)
            if language == "python":
                # Find methods in Python class (indented under class)
                class_content = content[class_start:]
                methods = re.findall(language_config["method_pattern"], class_content)
                method_count = len(methods)
            else:
                # For other languages, estimate by finding methods after class declaration
                next_class_match = re.search(language_config["class_pattern"], content[class_start + len(match.group(0)):])
                class_end = next_class_match.start() + class_start + len(match.group(0)) if next_class_match else len(content)
                class_content = content[class_start:class_end]
                methods = re.findall(language_config["method_pattern"], class_content)
                method_count = len(methods)
            
            if method_count > thresholds["large_class_methods"]:
                detected_smells.append({
                    "category": "large_class", 
                    "line": class_line,
                    "description": f"Class '{class_name}' has {method_count} methods (threshold: {thresholds['large_class_methods']})"
                })
    except Exception as e:
        logger.error(f"Error analyzing classes in {file_path}: {e}")
    
    # Periodic timeout check
    if STOP_ANALYSIS:
        return detected_smells
    
    # Check for long methods/functions
    try:
        function_matches = re.finditer(language_config["function_pattern"], content, re.MULTILINE)
        for match in function_matches:
            # Periodic timeout check
            if STOP_ANALYSIS:
                return detected_smells
                
            function_name = match.group(1) if match.group(1) else \
                          (match.group(3) if match.groups()[2:] and match.group(3) else \
                           (match.group(5) if match.groups()[4:] and match.group(5) else "anonymous"))
            
            # Get parameters
            param_group_idx = next((i for i, g in enumerate(match.groups()[1:], 2) if g is not None), 2)
            params = match.group(param_group_idx) if param_group_idx < len(match.groups()) + 1 else ""
            param_count = len([p for p in params.split(',') if p.strip()]) if params else 0
            
            # Check for long parameter list
            if param_count > thresholds["long_parameter_list"]:
                function_line = content[:match.start()].count('\n') + 1
                detected_smells.append({
                    "category": "long_parameter_list",
                    "line": function_line,
                    "description": f"Function '{function_name}' has {param_count} parameters (threshold: {thresholds['long_parameter_list']})"
                })
            
            # Estimate function length (lines)
            function_start = match.end()
            function_line = content[:match.start()].count('\n') + 1
            
            # Find function body (simple approach)
            if language == "python":
                # For Python, count indented lines after function declaration
                func_lines = 0
                cur_line = function_line
                while cur_line < len(lines):
                    if cur_line >= len(lines) or (cur_line > function_line and not lines[cur_line].startswith(' ') and lines[cur_line].strip()):
                        break
                    func_lines += 1
                    cur_line += 1
            else:
                # For other languages, find matching closing bracket
                # This is a simplistic approach and won't work for all cases
                opening_brackets = 1
                closing_pos = function_start
                max_search = min(len(content), function_start + 50000)  # Limit search to avoid hanging
                for i in range(function_start, max_search):
                    if content[i] == '{':
                        opening_brackets += 1
                    elif content[i] == '}':
                        opening_brackets -= 1
                        if opening_brackets == 0:
                            closing_pos = i
                            break
                
                func_lines = content[function_start:closing_pos].count('\n') + 1
            
            if func_lines > thresholds["long_method_lines"]:
                detected_smells.append({
                    "category": "long_method",
                    "line": function_line,
                    "description": f"Function '{function_name}' is {func_lines} lines long (threshold: {thresholds['long_method_lines']})"
                })
    except Exception as e:
        logger.error(f"Error analyzing functions in {file_path}: {e}")
    
    # Periodic timeout check
    if STOP_ANALYSIS:
        return detected_smells
    
    # Check for magic numbers - with frequency limit to avoid excessive regex
    try:
        # Limit processing to avoid regex catastrophic backtracking
        # Start with a small segment of the file
        sample_content = '\n'.join(lines[:min(1000, len(lines))])
        
        magic_numbers = re.findall(language_config["magic_number_pattern"], sample_content)
        # Filter out common non-magic numbers like 0, 1, -1
        magic_numbers = [n for n in magic_numbers if n not in ['0', '1', '-1', '2', '100', '1.0', '0.0']]
        
        if len(magic_numbers) > thresholds["magic_numbers_per_file"]:
            detected_smells.append({
                "category": "magic_numbers",
                "line": 0,
                "description": f"File contains {len(magic_numbers)} magic numbers (threshold: {thresholds['magic_numbers_per_file']})"
            })
    except Exception as e:
        logger.error(f"Error analyzing magic numbers in {file_path}: {e}")
    
    # Periodic timeout check
    if STOP_ANALYSIS:
        return detected_smells
    
    # Check for commented code
    try:
        # Analyze only a sample of lines for commented code to avoid excessive processing
        sample_lines = lines[:min(1000, len(lines))]
        commented_code_lines = []
        
        for i, line in enumerate(sample_lines):
            # Check every 100 lines for timeout
            if i % 100 == 0 and STOP_ANALYSIS:
                return detected_smells
                
            try:
                if re.match(language_config["commented_code_pattern"], line):
                    commented_code_lines.append(i + 1)
            except Exception:
                # Skip problematic regex patterns
                continue
        
        if len(commented_code_lines) > thresholds["commented_code_per_file"]:
            detected_smells.append({
                "category": "commented_code",
                "line": commented_code_lines[0],
                "description": f"File contains {len(commented_code_lines)} commented code lines (threshold: {thresholds['commented_code_per_file']})"
            })
    except Exception as e:
        logger.error(f"Error analyzing commented code in {file_path}: {e}")
    
    return detected_smells

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code smells check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Set a global timeout for the entire process
        global STOP_ANALYSIS
        STOP_ANALYSIS = False
        
        # Create a timer that will set the flag after timeout
        timer = threading.Timer(60, lambda: setattr(globals(), 'STOP_ANALYSIS', True))
        timer.daemon = True
        timer.start()
        
        try:
            # Use a thread with timeout to ensure the check completes
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(check_code_smells, local_path, repository, timeout_seconds=55)
                try:
                    # Force a hard timeout after 60 seconds
                    result = future.result(timeout=60)
                    
                    # Return the result
                    return {
                        "status": "completed",
                        "score": result.get("code_smells_score", 0),
                        "result": result,
                        "errors": None
                    }
                except FutureTimeoutError:
                    logger.error("Code smells check did not complete within the timeout period")
                    # Try to cancel the future
                    future.cancel()
                    # Return a timeout result
                    return {
                        "status": "timeout",
                        "score": 0,
                        "result": {
                            "error": "Analysis timed out after 60 seconds",
                            "timed_out": True,
                            "processing_time": 60,
                            "files_checked": 0  # We couldn't analyze any files
                        },
                        "errors": "Analysis timed out after 60 seconds"
                    }
        finally:
            # Cancel the timer
            timer.cancel()
            
    except Exception as e:
        logger.error(f"Error running code smells check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }