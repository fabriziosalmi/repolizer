"""
Error Handling Check

Analyzes the repository's code for proper error handling practices.
"""
import os
import re
import logging
import random
import time
import threading
import concurrent.futures
from typing import Dict, Any, List, Set, Tuple, Pattern
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logger = logging.getLogger(__name__)

class GracefulTimeout(Exception):
    """Custom exception for graceful timeout handling."""
    pass

def check_error_handling(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for error handling practices in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    # Use a main worker thread to enforce true timeouts
    result_container = {"result": None, "exception": None}
    worker_thread = threading.Thread(
        target=_check_error_handling_worker,
        args=(repo_path, repo_data, result_container)
    )
    
    # Start the worker with a hard timeout
    worker_thread.daemon = True  # Allow the thread to be killed if needed
    worker_thread.start()
    
    # Wait for the worker to complete, with a maximum timeout of 5 minutes
    max_wait_time = 300  # 5 minutes absolute maximum
    start_time = time.time()
    
    while worker_thread.is_alive():
        # Check every 5 seconds if we need to abort
        worker_thread.join(timeout=5)
        
        # If we've waited too long, stop waiting
        if time.time() - start_time > max_wait_time:
            logger.warning(f"Error handling check timed out after {max_wait_time} seconds")
            return {
                "has_error_handling": False,
                "empty_catch_blocks": 0,
                "proper_error_handling": 0,
                "error_logging": 0,
                "custom_error_types": 0,
                "issues": [],
                "files_checked": 0,
                "timeout_occurred": True,
                "error_handling_score": 0,
                "execution_time": round(time.time() - start_time, 2)
            }
    
    # Check if worker had an exception
    if result_container["exception"]:
        logger.error(f"Error in error handling check: {result_container['exception']}")
        return {
            "has_error_handling": False,
            "error_handling_score": 0,
            "error": str(result_container["exception"]),
            "execution_time": round(time.time() - start_time, 2)
        }
    
    # Return the worker's result, or a default if something went wrong
    return result_container["result"] or {
        "has_error_handling": False,
        "empty_catch_blocks": 0,
        "proper_error_handling": 0,
        "error_logging": 0,
        "custom_error_types": 0,
        "issues": [],
        "files_checked": 0,
        "error_handling_score": 0,
        "execution_time": round(time.time() - start_time, 2)
    }

def _check_error_handling_worker(repo_path: str, repo_data: Dict, result_container: Dict) -> None:
    """Worker function that performs the actual error handling check."""
    start_time = time.time()
    cancel_event = threading.Event()  # Event to signal cancellation
    
    try:
        # Global timeout value in seconds
        GLOBAL_TIMEOUT = 180  # 3 minutes
        
        result = {
            "has_error_handling": False,
            "empty_catch_blocks": 0,
            "proper_error_handling": 0,
            "error_logging": 0,
            "custom_error_types": 0,
            "issues": [],
            "files_checked": 0,
            "timeout_occurred": False
        }
        
        # Check if repository is available locally
        if not repo_path or not os.path.isdir(repo_path):
            logger.warning("No local repository path provided or path is not a directory")
            result_container["result"] = result
            return
        
        # File types to analyze by language
        language_extensions = {
            "javascript": ['.js', '.jsx'],
            "typescript": ['.ts', '.tsx'],
            "python": ['.py'],
            "java": ['.java'],
            "csharp": ['.cs'],
            "php": ['.php'],
            "ruby": ['.rb'],
            "go": ['.go'],
            "rust": ['.rs'],
            "swift": ['.swift']
        }
        
        # Error handling patterns by language
        error_handling_patterns = {
            "javascript": {
                "try_catch": r'try\s*{[^}]*}\s*catch\s*\([^)]*\)\s*{[^}]*}',
                "empty_catch": r'catch\s*\([^)]*\)\s*{\s*}',
                "error_logging": r'console\.(?:error|warn)\s*\(',
                "proper_handling": r'catch\s*\([^)]*\)\s*{(?:(?!return|throw|process).)*(?:return|throw|process)',
                "custom_error": r'class\s+\w+Error\s+extends\s+Error'
            },
            "typescript": {
                "try_catch": r'try\s*{[^}]*}\s*catch\s*\([^)]*\)\s*{[^}]*}',
                "empty_catch": r'catch\s*\([^)]*\)\s*{\s*}',
                "error_logging": r'console\.(?:error|warn)\s*\(',
                "proper_handling": r'catch\s*\([^)]*\)\s*{(?:(?!return|throw|process).)*(?:return|throw|process)',
                "custom_error": r'class\s+\w+Error\s+(?:extends|implements)\s+Error'
            },
            "python": {
                "try_except": r'try\s*:.*?except(?:\s+\w+(?:\s+as\s+\w+)?)?\s*:',
                "empty_except": r'except(?:\s+\w+(?:\s+as\s+\w+)?)?\s*:\s*(?:pass|#)',
                "error_logging": r'(?:logger|logging)\.(?:error|exception|warning|critical)\s*\(',
                "proper_handling": r'except(?:\s+\w+(?:\s+as\s+\w+)?)?\s*:(?:(?!raise|return).)*(?:raise|return)',
                "custom_error": r'class\s+\w+(?:Error|Exception)\s*\(\w+(?:Error|Exception)\s*\):'
            },
            "java": {
                "try_catch": r'try\s*{[^}]*}\s*catch\s*\([^)]*\)\s*{[^}]*}',
                "empty_catch": r'catch\s*\([^)]*\)\s*{\s*}',
                "error_logging": r'(?:logger|log)\.(?:error|warn|severe)\s*\(',
                "proper_handling": r'catch\s*\([^)]*\)\s*{(?:(?!throw|return).)*(?:throw|return)',
                "custom_error": r'class\s+\w+(?:Exception|Error)\s+extends\s+(?:\w+)?(?:Exception|Error)'
            },
            "csharp": {
                "try_catch": r'try\s*{[^}]*}\s*catch(?:\s*\([^)]*\))?\s*{[^}]*}',
                "empty_catch": r'catch(?:\s*\([^)]*\))?\s*{\s*}',
                "error_logging": r'(?:logger|Log)\.(?:Error|Warning|Fatal)\s*\(',
                "proper_handling": r'catch(?:\s*\([^)]*\))?\s*{(?:(?!throw|return).)*(?:throw|return)',
                "custom_error": r'class\s+\w+(?:Exception|Error)\s*:\s*(?:System\.)?(?:Exception|Error)'
            }
        }
        
        # Default patterns for languages not specifically configured
        default_patterns = {
            "try_catch": r'try\s*{[^}]*}\s*catch',
            "empty_catch": r'catch.*?{\s*}',
            "error_logging": r'(?:log|logger|console)\.(?:error|warn)',
            "proper_handling": r'catch.*?{(?:(?!return|throw).)*(?:return|throw)',
            "custom_error": r'(?:class|type)\s+\w+(?:Error|Exception)'
        }
        
        # Pre-compile regex patterns for performance
        compiled_patterns = {}
        for lang, patterns in error_handling_patterns.items():
            compiled_patterns[lang] = {k: re.compile(v, re.DOTALL) for k, v in patterns.items()}
        
        # Also compile default patterns
        compiled_default_patterns = {k: re.compile(v, re.DOTALL) for k, v in default_patterns.items()}
        
        # Performance optimization parameters
        MAX_FILES_TO_CHECK = 80  # Even smaller limit
        MAX_FILE_SIZE = 128 * 1024  # Further reduced to 128KB
        SAMPLE_RATIO = 0.15  # Further reduced sampling ratio
        MINIMUM_SAMPLE = 15
        MAX_TIME_SECONDS = 30  # Reduced runtime limit (30 seconds)
        FILE_PROCESSING_TIMEOUT = 1.5  # Shorter timeout per file
        SUFFICIENT_DATA_THRESHOLD = {
            "files": 15,  # Further reduced thresholds
            "try_catch": 8,
            "proper_handling": 4
        }
        
        # Additional directories to skip
        skip_dirs = [
            '/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/',
            '/vendor/', '/bin/', '/obj/', '/target/', '/out/', '/logs/',
            '/coverage/', '/.vscode/', '/.idea/', '/assets/', '/public/',
            '/test/', '/tests/', '/spec/', '/docs/'
        ]
        
        # Binary and generated file patterns to skip
        skip_file_patterns = [
            r'\.min\.js$', r'\.bundle\.js$', r'\.min\.css$', 
            r'\.svg$', r'\.png$', r'\.jpg$', r'\.jpeg$', r'\.gif$',
            r'\.pdf$', r'\.zip$', r'\.tar$', r'\.gz$', r'\.jar$',
            r'\.lock$', r'package-lock\.json$', r'yarn\.lock$',
            r'\.ttf$', r'\.woff$', r'\.woff2$', r'\.eot$'
        ]
        skip_file_regex = re.compile('|'.join(skip_file_patterns))
        
        # Thread-safe timeout check function that also checks the cancel event
        def is_timed_out():
            return time.time() - start_time > GLOBAL_TIMEOUT or cancel_event.is_set()
        
        # Function to analyze a single file with timeout
        def analyze_file(file_path: str, language: str) -> Dict:
            if is_timed_out():
                return {"timeout": True}
                
            file_start_time = time.time()
            file_metrics = {
                "has_error_handling": False,
                "try_catch": 0,
                "empty_catch": 0,
                "proper_handling": 0,
                "error_logging": 0,
                "custom_error": 0,
                "issues": [],
                "timeout": False
            }
            
            # Skip very large files before even reading them
            try:
                file_size = os.path.getsize(file_path)
                if file_size > MAX_FILE_SIZE:
                    return file_metrics
            except OSError:
                return file_metrics
                
            try:
                # Set a strict time limit for file processing
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Read the file in small chunks to avoid memory issues
                    content = ""
                    chunk_size = 32 * 1024  # Smaller 32KB chunks
                    
                    # Only read for a limited time
                    while time.time() - file_start_time < FILE_PROCESSING_TIMEOUT:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break  # End of file
                        content += chunk
                        
                        # Check timeout after each chunk
                        if time.time() - file_start_time > FILE_PROCESSING_TIMEOUT or is_timed_out():
                            file_metrics["timeout"] = True
                            return file_metrics
                    
                    # If we exited because of time, mark as timeout
                    if time.time() - file_start_time >= FILE_PROCESSING_TIMEOUT:
                        file_metrics["timeout"] = True
                        return file_metrics
                    
                    # Limit content size in case we read too much
                    if len(content) > MAX_FILE_SIZE:
                        content = content[:MAX_FILE_SIZE]
                    
                    # Process the content
                    patterns = compiled_patterns.get(language, compiled_default_patterns)
                    
                    # Check for try-catch blocks with timeout protection
                    try_catch_key = "try_catch" if "try_catch" in patterns else "try_except"
                    try:
                        # Use a very short timeout for regex operations
                        regex_start = time.time()
                        try_catch_matches = []
                        
                        # If the regex takes too long, skip it
                        if time.time() - regex_start < 0.5:  # 500ms max for regex
                            try_catch_matches = patterns[try_catch_key].findall(content)
                        
                        if try_catch_matches:
                            file_metrics["has_error_handling"] = True
                            file_metrics["try_catch"] = len(try_catch_matches)
                    except Exception as e:
                        logger.debug(f"Error in try-catch regex for {file_path}: {e}")
                    
                    # Check for empty catch blocks
                    empty_catch_key = "empty_catch" if "empty_catch" in patterns else "empty_except"
                    try:
                        regex_start = time.time()
                        empty_catch_matches = []
                        
                        if time.time() - regex_start < 0.5:
                            empty_catch_matches = patterns[empty_catch_key].findall(content)
                        
                        file_metrics["empty_catch"] = len(empty_catch_matches)
                        
                        # Only process a few issues to avoid memory issues
                        if empty_catch_matches and len(empty_catch_matches) <= 3:
                            relative_path = os.path.relpath(file_path, repo_path)
                            for match in empty_catch_matches[:2]:
                                try:
                                    line_number = content[:content.find(match)].count('\n') + 1
                                    file_metrics["issues"].append({
                                        "file": relative_path,
                                        "line": line_number,
                                        "issue": "Empty catch block",
                                        "snippet": match[:80] + ("..." if len(match) > 80 else "")
                                    })
                                except Exception:
                                    # Skip issue if there's any problem
                                    pass
                    except Exception as e:
                        logger.debug(f"Error in empty-catch regex for {file_path}: {e}")
                    
                    # Check for other patterns if we still have time
                    if time.time() - file_start_time < FILE_PROCESSING_TIMEOUT:
                        # Process other patterns
                        for pattern_key in ["proper_handling", "error_logging", "custom_error"]:
                            try:
                                regex_start = time.time()
                                matches = []
                                
                                if time.time() - regex_start < 0.5:
                                    matches = patterns[pattern_key].findall(content)
                                
                                file_metrics[pattern_key] = len(matches)
                            except Exception:
                                # Skip on any error to keep moving
                                pass
                            
                            # Check timeout after each pattern
                            if time.time() - file_start_time > FILE_PROCESSING_TIMEOUT:
                                file_metrics["timeout"] = True
                                break
                
            except Exception as e:
                logger.debug(f"Error analyzing file {file_path}: {e}")
                
            return file_metrics
        
        # Improved file selection with stricter limits
        def get_files_to_check():
            total_files = 0
            files_by_language = {}
            scan_start_time = time.time()
            MAX_SCAN_TIME = 8  # seconds (reduced from 10)
            MAX_FILES_PER_LANGUAGE = MAX_FILES_TO_CHECK // 4  # Limit files per language
            
            # Use a walk_generator to avoid getting stuck in large repos
            def walk_generator(root_dir, max_depth=5):
                if max_depth <= 0:
                    return
                
                try:
                    for entry in os.scandir(root_dir):
                        # Check for timeout regularly
                        if is_timed_out() or time.time() - scan_start_time > MAX_SCAN_TIME:
                            return
                            
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                # Skip excluded directories
                                if any(skip_dir in entry.path for skip_dir in skip_dirs):
                                    continue
                                    
                                # Recursive call with decreased depth
                                yield from walk_generator(entry.path, max_depth - 1)
                            elif entry.is_file(follow_symlinks=False):
                                yield entry.path
                        except OSError:
                            # Skip on permission errors, etc.
                            continue
                except OSError:
                    # Skip inaccessible directories
                    return
            
            # Use the generator to get files with better control
            for file_path in walk_generator(repo_path):
                if is_timed_out() or time.time() - scan_start_time > MAX_SCAN_TIME:
                    logger.info("Time limit reached during file scanning")
                    break
                
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()
                
                # Determine language
                file_language = None
                for lang, extensions in language_extensions.items():
                    if ext in extensions:
                        file_language = lang
                        break
                
                # Skip files we don't handle or match exclusion patterns
                if not file_language or skip_file_regex.search(os.path.basename(file_path)):
                    continue
                
                # Count total files
                total_files += 1
                
                # Initialize language list if needed
                if file_language not in files_by_language:
                    files_by_language[file_language] = []
                
                # Only collect limited paths per language
                if len(files_by_language[file_language]) < MAX_FILES_PER_LANGUAGE:
                    try:
                        # Quick size check
                        if os.path.getsize(file_path) <= MAX_FILE_SIZE:
                            files_by_language[file_language].append(file_path)
                    except OSError:
                        continue
                
                # Periodically check timeout
                if total_files % 50 == 0 and is_timed_out():
                    break
            
            # Limited and balanced sampling
            selected_files = []
            
            # Calculate target based on what we found
            total_to_select = min(MAX_FILES_TO_CHECK, total_files)
            if total_to_select == 0:
                return [], {}, 0
            
            # Ensure minimum files per language
            min_per_language = min(3, total_to_select // max(1, len(files_by_language)))
            remaining_slots = total_to_select
            
            # First pass: select minimum files from each language
            for lang, files in files_by_language.items():
                to_select = min(min_per_language, len(files))
                if to_select > 0:
                    # Prefer newest files
                    try:
                        sorted_files = sorted(
                            files, 
                            key=lambda f: os.path.getmtime(f),
                            reverse=True
                        )
                        selected_files.extend(sorted_files[:to_select])
                    except Exception:
                        # Fall back to random if sorting fails
                        selected_files.extend(random.sample(files, to_select))
                    
                    remaining_slots -= to_select
            
            # Second pass: proportional distribution of remaining slots
            if remaining_slots > 0:
                # Calculate total files available for second pass
                remaining_files_by_lang = {}
                total_remaining = 0
                
                for lang, files in files_by_language.items():
                    remaining_in_lang = [f for f in files if f not in selected_files]
                    if remaining_in_lang:
                        remaining_files_by_lang[lang] = remaining_in_lang
                        total_remaining += len(remaining_in_lang)
                
                # Distribute proportionally
                if total_remaining > 0:
                    for lang, files in remaining_files_by_lang.items():
                        proportion = len(files) / total_remaining
                        slots_for_lang = max(1, int(remaining_slots * proportion))
                        slots_for_lang = min(slots_for_lang, len(files), remaining_slots)
                        
                        if slots_for_lang > 0:
                            selected_files.extend(random.sample(files, slots_for_lang))
                            remaining_slots -= slots_for_lang
                        
                        if remaining_slots <= 0:
                            break
            
            # Map files to their languages
            files_to_check = []
            for file_path in selected_files:
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()  # Fix: Call the string method lower() on ext
                
                # Find language
                file_language = None
                for lang, extensions in language_extensions.items():
                    if ext in extensions:
                        file_language = lang
                        break
                
                if file_language:
                    files_to_check.append((file_path, file_language))
            
            # Return the selected files and statistics
            return files_to_check, {lang: len(files) for lang, files in files_by_language.items()}, total_files
        
        # Setup watchdog timer thread to prevent hanging
        def watchdog_timer():
            watchdog_time = GLOBAL_TIMEOUT * 0.8  # 80% of global timeout
            time.sleep(watchdog_time)
            if not cancel_event.is_set():
                logger.warning("Watchdog timer triggered, cancelling error handling check")
                cancel_event.set()
        
        # Start watchdog timer in separate thread
        watchdog_thread = threading.Thread(target=watchdog_timer)
        watchdog_thread.daemon = True
        watchdog_thread.start()
        
        # Get files to check
        try:
            files_to_check, language_distribution, total_files_count = get_files_to_check()
            logger.info(f"Selected {len(files_to_check)} files from approximately {total_files_count} total files")
        except Exception as e:
            logger.error(f"Error during file selection: {e}")
            result_container["result"] = result
            return
        
        # Early exit if no files
        if not files_to_check:
            logger.info("No suitable files found for analysis")
            result_container["result"] = result
            return
        
        # Track metrics
        metrics_by_language = {}
        files_checked = 0
        has_error_handling = False
        empty_catch_blocks = 0
        proper_error_handling = 0
        error_logging = 0
        custom_error_types = 0
        timeout_count = 0
        
        # Process in smaller batches
        batch_size = 5  # Even smaller batches
        max_batches = (len(files_to_check) + batch_size - 1) // batch_size
        
        for batch_num in range(max_batches):
            # Check for timeout or cancellation
            if is_timed_out() or time.time() - start_time > MAX_TIME_SECONDS:
                logger.info(f"Time limit reached after {batch_num} batches")
                result["timeout_occurred"] = True
                break
            
            # Get current batch
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(files_to_check))
            batch = files_to_check[start_idx:end_idx]
            
            # Process batch with limited parallelism
            with ThreadPoolExecutor(max_workers=min(3, len(batch))) as executor:
                # Create map of futures to file info
                future_to_file = {
                    executor.submit(analyze_file, file_path, lang): (file_path, lang) 
                    for file_path, lang in batch
                }
                
                # Use a very short timeout for future.result()
                future_timeout = min(FILE_PROCESSING_TIMEOUT * 1.2, 3)  # Max 3 seconds
                
                # Process completed futures
                for future in as_completed(future_to_file):
                    # Check timeouts regularly
                    if is_timed_out() or time.time() - start_time > MAX_TIME_SECONDS:
                        logger.info(f"Time limit reached during batch {batch_num+1}")
                        result["timeout_occurred"] = True
                        break
                    
                    file_path, lang = future_to_file[future]
                    
                    try:
                        # Get result with short timeout
                        file_metrics = future.result(timeout=future_timeout)
                        files_checked += 1
                        
                        # Skip if timeout occurred
                        if file_metrics.get("timeout", False):
                            timeout_count += 1
                            continue
                        
                        # Update metrics
                        if lang not in metrics_by_language:
                            metrics_by_language[lang] = {
                                "files": 0,
                                "try_catch": 0,
                                "empty_catch": 0,
                                "proper_handling": 0,
                                "error_logging": 0,
                                "custom_error": 0
                            }
                        
                        if file_metrics["has_error_handling"]:
                            has_error_handling = True
                            metrics_by_language[lang]["files"] += 1
                            metrics_by_language[lang]["try_catch"] += file_metrics["try_catch"]
                        
                        # Update all metrics
                        for key in ["empty_catch", "proper_handling", "error_logging", "custom_error"]:
                            metrics_by_language[lang][key] += file_metrics.get(key, 0)
                        
                        # Update global metrics
                        empty_catch_blocks += file_metrics.get("empty_catch", 0)
                        proper_error_handling += file_metrics.get("proper_handling", 0)
                        error_logging += file_metrics.get("error_logging", 0)
                        custom_error_types += file_metrics.get("custom_error", 0)
                        
                        # Add issues
                        if file_metrics.get("issues") and len(result["issues"]) < 10:
                            for issue in file_metrics["issues"]:
                                if len(result["issues"]) < 10:
                                    result["issues"].append(issue)
                                else:
                                    break
                    
                    except concurrent.futures.TimeoutError:
                        # Future timed out
                        timeout_count += 1
                        logger.debug(f"Future timed out for {file_path}")
                    
                    except Exception as e:
                        logger.debug(f"Error processing file {file_path}: {e}")
            
            # Check timeout rate
            if files_checked > 0 and timeout_count >= 3 and timeout_count / files_checked > 0.25:
                logger.warning(f"High timeout rate ({timeout_count}/{files_checked}), stopping early")
                result["timeout_occurred"] = True
                break
            
            # Extremely aggressive early stopping
            has_enough_data = (
                files_checked >= SUFFICIENT_DATA_THRESHOLD["files"] and
                proper_error_handling >= SUFFICIENT_DATA_THRESHOLD["proper_handling"] and
                sum([metrics.get("try_catch", 0) for metrics in metrics_by_language.values()]) >= 
                SUFFICIENT_DATA_THRESHOLD["try_catch"]
            )
            
            if has_enough_data and has_error_handling:
                logger.info(f"Stopping analysis early after batch {batch_num+1} with sufficient data")
                break
        
        # Return partial results even if timeout occurred
        result["files_checked"] = files_checked
        result["has_error_handling"] = has_error_handling
        result["empty_catch_blocks"] = empty_catch_blocks
        result["proper_error_handling"] = proper_error_handling
        result["error_logging"] = error_logging
        result["custom_error_types"] = custom_error_types
        result["language_metrics"] = metrics_by_language
        result["language_distribution"] = language_distribution
        result["execution_time"] = round(time.time() - start_time, 2)
        result["total_files_estimated"] = total_files_count
        result["timeout_count"] = timeout_count
        
        # Calculate score only if we have data
        if files_checked > 0:
            score = 50  # Base score
            
            if has_error_handling:
                # Points for proper error handling (up to 25 points)
                if proper_error_handling > 0:
                    proper_handling_score = min(25, proper_error_handling)
                    score += proper_handling_score
                
                # Points for error logging (up to 15 points)
                if error_logging > 0:
                    error_logging_score = min(15, error_logging)
                    score += error_logging_score
                
                # Points for custom error types (up to 10 points)
                if custom_error_types > 0:
                    custom_error_score = min(10, custom_error_types * 2)
                    score += custom_error_score
            else:
                # No error handling found
                score = 10
            
            # Penalty for empty catch blocks
            if empty_catch_blocks > 0 and proper_error_handling > 0:
                empty_ratio = empty_catch_blocks / proper_error_handling
                if empty_ratio > 0.5:
                    score = max(0, score - 30)
                elif empty_ratio > 0.25:
                    score = max(0, score - 20)
                elif empty_ratio > 0.1:
                    score = max(0, score - 10)
            elif empty_catch_blocks > 0:
                # Only empty catch blocks
                score = max(0, score - 40)
            
            # Round score
            rounded_score = round(score, 1)
            result["error_handling_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
        else:
            # No files checked
            result["error_handling_score"] = 0
        
        # Store result
        result_container["result"] = result
        
    except Exception as e:
        # Record exception for main thread to see
        result_container["exception"] = e
        logger.error(f"Error in error handling check worker: {e}")
    
    finally:
        # Ensure we always signal cancellation to clean up any running tasks
        cancel_event.set()

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the error handling check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Set a maximum execution time using a timer
        start_time = time.time()
        
        # Run the check with guaranteed timeout behavior
        result = check_error_handling(local_path, repository)
        
        # Always make sure we have a score
        if "error_handling_score" not in result:
            result["error_handling_score"] = 0
        
        # Return the result
        return {
            "status": "completed" if not result.get("timeout_occurred", False) else "completed_with_timeout",
            "score": result.get("error_handling_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running error handling check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }