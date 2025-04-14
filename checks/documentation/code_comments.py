import os
import re
import logging
import time
import signal
import platform
import threading
from typing import Dict, Any, List, Tuple, Optional
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
import concurrent.futures

# Setup logging
logger = logging.getLogger(__name__)

# Check operating system for timeout implementation
IS_UNIX_SIGALRM = platform.system() in ('Linux', 'Darwin')
IS_WINDOWS = platform.system() == 'Windows'

# Global flag to indicate if analysis should stop
STOP_ANALYSIS = False

# Timeout decorator for functions - only used on Unix systems (Linux, macOS)
def timeout_decorator(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # Set the timeout handler
            if IS_UNIX_SIGALRM:
                original_handler = signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
            
            try:
                # On Windows, we'll rely on other timeout mechanisms
                if IS_WINDOWS:
                    return func(*args, **kwargs)
                elif IS_UNIX_SIGALRM:
                    result = func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            finally:
                # Reset the handler and alarm
                if IS_UNIX_SIGALRM:
                    signal.signal(signal.SIGALRM, original_handler)
                    signal.alarm(0)
            
            return result
        return wrapper
    return decorator

def should_abort(hard_timeout=None):
    global STOP_ANALYSIS
    if STOP_ANALYSIS:
        return True
    if hard_timeout is not None and time.time() > hard_timeout:
        STOP_ANALYSIS = True
        return True
    return False

def check_code_comments(repo_path: str = None, repo_data: Dict = None, timeout_seconds: int = 60) -> Dict[str, Any]:
    """
    Analyze code comments quality and density in the repository
    
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
            "total_files_analyzed": 0,
            "files_with_comments": 0,
            "total_code_lines": 0,
            "total_comment_lines": 0,
            "comment_ratio": 0,
            "files_with_docstrings": 0,
            "comment_quality_score": 0,
            "comment_distribution_score": 0,
            "comment_score": 0,
            "timed_out": False,
            "processing_time": 0
        }
        
        # Check if repository is available locally
        if not repo_path or not os.path.isdir(repo_path):
            logger.warning("No local repository path provided or path is not a directory")
            return result
        
        # File extensions to analyze
        code_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cs": "csharp",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".rs": "rust",
        }
        
        # Directories to exclude
        exclude_dirs = [".git", "node_modules", "venv", "env", ".venv", "__pycache__", "build", "dist", ".github"]
        
        # File size limit (in MB)
        file_size_limit = 2  # Lowered from 5 to 2 MB for faster reads
        
        # Collect all valid files first to better distribute processing
        files_to_analyze = []
        
        # Create a safe version of os.walk that respects timeouts
        def safe_walk():
            try:
                max_dirs_to_check = 500  # Lowered from 1000
                dirs_checked = 0
                
                for root, dirs, files in os.walk(repo_path):
                    # Check for timeout or if we've checked too many directories
                    if should_abort(hard_timeout):
                        return
                
                    dirs_checked += 1
                
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
                
                    # Further limit directory traversal for very large repos
                    if len(dirs) > 20:  # Lowered from 50
                        dirs[:] = dirs[:20]
                
                    for file in files:
                        # Check timeout again for each file
                        if should_abort(hard_timeout):
                            return
                        
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in code_extensions:
                            file_path = os.path.join(root, file)
                        
                            # Check file size before adding to analysis list
                            try:
                                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                if file_size_mb <= file_size_limit:
                                    files_to_analyze.append((file_path, code_extensions[file_ext]))
                                    # Early stopping if we have enough files
                                    if len(files_to_analyze) >= 400:  # Lowered from 1000
                                        return
                                else:
                                    logger.info(f"Skipping large file: {file_path} ({file_size_mb:.2f} MB)")
                            except Exception as e:
                                logger.error(f"Error checking file size {file_path}: {e}")
                                continue
                            
                    # Periodically check if we need to stop
                    if len(files_to_analyze) % 50 == 0:  # More frequent check
                        if should_abort(hard_timeout):
                            return
            except BaseException as e:
                logger.error(f"safe_walk failed: {e}")
                STOP_ANALYSIS = True
                return
            
        try:
            # Set a timeout for the file collection phase
            file_collection_timeout = min(timeout_seconds * 0.2, 7)  # Lowered max to 7s or 20%
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(safe_walk)
                try:
                    future.result(timeout=file_collection_timeout)
                except Exception as e:
                    logger.warning(f"File collection timed out or failed: {e}")
                    result["timed_out"] = True
                    STOP_ANALYSIS = True
        except BaseException as e:
            logger.error(f"Error walking repository: {e}")
            STOP_ANALYSIS = True
        
        # Check if we should continue
        if should_abort(hard_timeout):
            result["timed_out"] = True
            result["processing_time"] = round(time.time() - start_time, 2)
            return result
        
        # Limit the number of files to analyze if there are too many
        # This helps ensure we complete within the timeout
        max_files_to_analyze = 20  # Lowered from 40
        if len(files_to_analyze) > max_files_to_analyze:
            logger.info(f"Limiting analysis to {max_files_to_analyze} files out of {len(files_to_analyze)}")
            
            # Take a stratified sample by extension to ensure representation
            files_by_extension = {}
            for file_path, language in files_to_analyze:
                ext = os.path.splitext(file_path)[1].lower()
                if ext not in files_by_extension:
                    files_by_extension[ext] = []
                files_by_extension[ext].append((file_path, language))
            
            # Sample files from each extension
            sampled_files = []
            for ext, files in files_by_extension.items():
                # Calculate how many files to take from this extension
                count = max(1, int(max_files_to_analyze * len(files) / len(files_to_analyze)))
                if len(files) <= count:
                    sampled_files.extend(files)
                else:
                    # Take files from beginning, middle, and end
                    step = len(files) // count
                    for i in range(0, min(count, len(files))):
                        idx = min(i * step, len(files) - 1)
                        sampled_files.append(files[idx])
            
            # If we still have room, add more files
            if len(sampled_files) < max_files_to_analyze:
                remaining = max_files_to_analyze - len(sampled_files)
                for ext, files in files_by_extension.items():
                    remaining_files = [f for f in files if f not in sampled_files]
                    sampled_files.extend(remaining_files[:max(1, remaining//len(files_by_extension))])
                    if len(sampled_files) >= max_files_to_analyze:
                        break
            
            files_to_analyze = sampled_files[:max_files_to_analyze]
        
        # Initialize counters
        total_files = 0
        files_with_comments = 0
        files_with_docstrings = 0
        total_code_lines = 0
        total_comment_lines = 0
        comment_quality_scores = []
        file_comment_ratios = []
        
        # Calculate maximum time per file based on remaining time
        remaining_time = max(1, hard_timeout - time.time())
        remaining_ratio = remaining_time / timeout_seconds
        
        # Adjust per-file timeout based on total files and remaining time
        time_per_file = min(0.2, remaining_time / max(1, len(files_to_analyze)))  # Lowered max per file to 0.2s
        logger.info(f"Allocating {time_per_file:.2f} seconds per file analysis for {len(files_to_analyze)} files")
        
        # If we have very little time left, reduce the number of files further
        if remaining_ratio < 0.5 and len(files_to_analyze) > 10:
            files_to_analyze = files_to_analyze[:10]
            logger.warning(f"Time constraints severe: limiting to 10 files. {remaining_time:.1f}s remaining")
        
        # Use a thread pool to process files with timeout per file - now using as_completed
        try:
            with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 4, len(files_to_analyze))) as executor:
                futures = {
                    executor.submit(analyze_file_with_timeout, file_path, language, time_per_file): 
                    (file_path, language)
                    for file_path, language in files_to_analyze
                }
                
                # Process results as they complete
                for future in as_completed(futures):
                    # Check if we should stop
                    if should_abort(hard_timeout):
                        result["timed_out"] = True
                        logger.warning(f"Analysis timed out after {time.time() - start_time:.2f} seconds")
                        
                        # Cancel remaining futures
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        break
                    
                    file_path, language = futures[future]
                    
                    try:
                        analysis_result = future.result(timeout=0.1)  # Just grab completed result
                        if analysis_result:
                            code_lines, comment_lines, has_docstrings, quality_score, file_timed_out = analysis_result
                            
                            if file_timed_out or should_abort(hard_timeout):
                                logger.warning(f"Analysis of {file_path} timed out or aborted")
                                continue
                            
                            total_files += 1
                            total_code_lines += code_lines
                            total_comment_lines += comment_lines
                            
                            # Calculate per-file comment ratio
                            file_ratio = 0 if code_lines == 0 else (comment_lines / code_lines) * 100
                            file_comment_ratios.append(file_ratio)
                            
                            if comment_lines > 0:
                                files_with_comments += 1
                                comment_quality_scores.append(quality_score)
                            
                            if has_docstrings:
                                files_with_docstrings += 1
                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")
                        STOP_ANALYSIS = True
                        continue
        except BaseException as e:
            logger.error(f"ThreadPoolExecutor failed: {e}")
            STOP_ANALYSIS = True
        
        # Calculate comment ratio and scores
        comment_ratio = 0 if total_code_lines == 0 else (total_comment_lines / total_code_lines) * 100
        
        # Populate result dictionary
        result["total_files_analyzed"] = total_files
        result["files_with_comments"] = files_with_comments
        result["total_code_lines"] = total_code_lines
        result["total_comment_lines"] = total_comment_lines
        result["comment_ratio"] = round(comment_ratio, 2)
        result["files_with_docstrings"] = files_with_docstrings
        
        # Calculate enhanced score (0-100 scale)
        score = 0
        
        # No score if no files were analyzed
        if total_files > 0:
            # % of files with comments (up to 25 points)
            files_with_comments_ratio = files_with_comments / total_files
            files_score = min(files_with_comments_ratio * 25, 25)
            
            # Comment-to-code ratio (up to 25 points)
            # Ideal ratio is around 15-20%
            ratio_score = 0
            if comment_ratio > 0:
                if comment_ratio < 5:
                    ratio_score = comment_ratio * 2  # Low comments get proportional score
                elif comment_ratio < 20:
                    ratio_score = 10 + (comment_ratio - 5) * 1  # Good range gets bonus
                else:
                    ratio_score = 20 + min((comment_ratio - 20) * 0.25, 5)  # Diminishing returns for excessive comments
            
            # Files with docstrings (up to 25 points)
            docstring_ratio = files_with_docstrings / total_files
            docstring_score = min(docstring_ratio * 25, 25)
            
            # Comment quality score (up to 15 points)
            avg_quality = sum(comment_quality_scores) / max(len(comment_quality_scores), 1)
            quality_score = min(avg_quality * 15, 15)
            result["comment_quality_score"] = round(avg_quality * 10, 1)  # Scale of 0-10 for reporting
            
            # Comment distribution score (up to 10 points)
            distribution_score = 0
            if file_comment_ratios and len(file_comment_ratios) > 1:
                # Calculate standard deviation of comment ratios across files
                mean_ratio = sum(file_comment_ratios) / len(file_comment_ratios)
                variance = sum((r - mean_ratio) ** 2 for r in file_comment_ratios) / len(file_comment_ratios)
                std_dev = variance ** 0.5
                
                # Lower standard deviation means more even distribution, which is better
                # Normalize to a 0-10 scale (10 is perfect distribution)
                normalized_std_dev = min(std_dev / 5, 10)  # Cap at 10
                distribution_score = 10 - normalized_std_dev
            
            result["comment_distribution_score"] = round(distribution_score, 1)
            
            score = files_score + ratio_score + docstring_score + quality_score + distribution_score
        
        # Round and use integer if it's a whole number
        rounded_score = round(score, 1)
        result["comment_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
        
        # Record processing time
        result["processing_time"] = round(time.time() - start_time, 2)
        
        # Force timed_out flag if we exceeded timeout or if global flag is set
        if result["processing_time"] >= timeout_seconds or STOP_ANALYSIS or should_abort(hard_timeout):
            result["timed_out"] = True
        
        return result
    except BaseException as e:
        logger.error(f"check_code_comments failed: {e}")
        return {
            "total_files_analyzed": 0,
            "files_with_comments": 0,
            "total_code_lines": 0,
            "total_comment_lines": 0,
            "comment_ratio": 0,
            "files_with_docstrings": 0,
            "comment_quality_score": 0,
            "comment_distribution_score": 0,
            "comment_score": 0,
            "timed_out": True,
            "processing_time": round(time.time() - start_time, 2) if 'start_time' in locals() else 0,
            "error": str(e)
        }
    finally:
        # Clean up the timer
        timeout_timer.cancel()

def analyze_file_with_timeout(file_path: str, language: str, timeout: float = 1.0) -> Optional[Tuple]:
    """
    Analyze a file with a timeout to prevent hanging
    
    Args:
        file_path: Path to the file
        language: Programming language of the file
        timeout: Timeout in seconds
        
    Returns:
        Analysis results or None if timed out
    """
    global STOP_ANALYSIS
    
    # Quick check for global timeout
    if STOP_ANALYSIS:
        return (0, 0, False, 0, True)
    
    try:
        # Set a slightly shorter timeout to ensure we return before the outer timeout hits
        actual_timeout = max(0.05, timeout * 0.8)  # Lowered from 0.1
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(analyze_file, file_path, language)
            try:
                result = future.result(timeout=actual_timeout)
                if STOP_ANALYSIS:
                    return (0, 0, False, 0, True)
                return (*result, False)  # False indicates no timeout
            except Exception as e:
                logger.warning(f"Analysis of {file_path} timed out or failed: {e}")
                STOP_ANALYSIS = True
                future.cancel()
                return (0, 0, False, 0, True)  # True indicates timeout
    except BaseException as e:
        logger.error(f"Error analyzing file {file_path}: {e}")
        STOP_ANALYSIS = True
        return (0, 0, False, 0, True)

def analyze_file(file_path: str, language: str) -> Tuple[int, int, bool, float]:
    """
    Analyze a code file for comments and docstrings
    
    Args:
        file_path: Path to the file
        language: Programming language of the file
        
    Returns:
        Tuple of (code_lines, comment_lines, has_docstrings, quality_score)
    """
    global STOP_ANALYSIS
    
    # Check if we should stop
    if STOP_ANALYSIS:
        return 0, 0, False, 0
    
    try:
        # Safety check for file size before reading
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 2:  # Lowered from 5MB
            logger.info(f"Skipping large file during analysis: {file_path} ({file_size_mb:.2f} MB)")
            return 0, 0, False, 0
        
        # Read with a limit on content size
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read limited amount to avoid memory issues
            content = f.read(256 * 1024)  # Lowered from 512KB to 256KB
    except Exception as e:
        logger.error(f"Could not read file {file_path}: {e}")
        STOP_ANALYSIS = True
        return 0, 0, False, 0
    
    # If file reading took too long, we might need to exit
    if STOP_ANALYSIS:
        return 0, 0, False, 0
    
    code_lines = 0
    comment_lines = 0
    has_docstrings = False
    
    # Count lines of code (excluding blank lines)
    lines = content.split('\n')
    
    # Limit lines to avoid excessive processing
    max_lines = 500  # Lowered from 2000
    if len(lines) > max_lines:
        logger.info(f"Limiting analysis to {max_lines} lines for {file_path}")
        lines = lines[:max_lines]
    
    # Frequent timeout check
    for i in range(0, len(lines), 100):
        if STOP_ANALYSIS:
            return 0, 0, False, 0
    
    code_lines = sum(1 for line in lines if line.strip())
    
    # Language-specific comment patterns
    single_line_comment = None
    multi_line_start = None
    multi_line_end = None
    docstring_pattern = None
    
    if language == "python":
        single_line_comment = r'^\s*#'
        multi_line_start = r'"""'
        multi_line_end = r'"""'
        docstring_pattern = r'^\s*(""".+?"""|\'\'\'(.|\n)+?\'\'\')'
    elif language in ["javascript", "typescript", "java", "c", "cpp", "csharp", "go", "php", "kotlin", "swift", "scala", "rust"]:
        single_line_comment = r'^\s*//'
        multi_line_start = r'/\*'
        multi_line_end = r'\*/'
        docstring_pattern = r'^\s*/\*\*(.|\n)+?\*/'
    elif language == "ruby":
        single_line_comment = r'^\s*#'
        multi_line_start = r'=begin'
        multi_line_end = r'=end'
    
    # Collect all comments for quality analysis
    all_comments = []
    
    # Frequent timeout check
    if STOP_ANALYSIS:
        return code_lines, 0, False, 0
    
    # Count single-line comments
    if single_line_comment:
        for i, line in enumerate(lines):
            if i % 100 == 0 and STOP_ANALYSIS:
                return code_lines, comment_lines, False, 0
                
            if re.match(single_line_comment, line):
                comment_lines += 1
                comment_text = re.sub(single_line_comment, '', line).strip()
                if comment_text:  # Only add non-empty comments
                    all_comments.append(comment_text)
    
    # Frequent timeout check
    if STOP_ANALYSIS:
        return code_lines, comment_lines, False, 0
    
    # Count multi-line comments with timeout protection
    if multi_line_start and multi_line_end:
        in_comment = False
        current_comment = []
        
        for i, line in enumerate(lines):
            if i % 100 == 0 and STOP_ANALYSIS:
                return code_lines, comment_lines, has_docstrings, 0
            
            # Handle entire comment on one line
            if re.search(multi_line_start, line) and re.search(multi_line_end, line):
                comment_lines += 1
                comment_text = re.sub(f"{multi_line_start}.*?{multi_line_end}", '', line, flags=re.DOTALL).strip()
                if comment_text:
                    all_comments.append(comment_text)
                continue
                
            # Handle start of multi-line comment
            if re.search(multi_line_start, line) and not re.search(multi_line_end, line):
                in_comment = True
                comment_lines += 1
                comment_text = re.sub(multi_line_start, '', line).strip()
                if comment_text:
                    current_comment.append(comment_text)
            # Handle middle of multi-line comment
            elif in_comment and not re.search(multi_line_end, line):
                comment_lines += 1
                if line.strip():
                    current_comment.append(line.strip())
            # Handle end of multi-line comment
            elif in_comment and re.search(multi_line_end, line):
                in_comment = False
                comment_lines += 1
                comment_text = re.sub(multi_line_end, '', line).strip()
                if comment_text:
                    current_comment.append(comment_text)
                
                if current_comment:
                    all_comments.append(" ".join(current_comment))
                current_comment = []
    
    # Frequent timeout check
    if STOP_ANALYSIS:
        return code_lines, comment_lines, False, 0
    
    # Check for docstrings - with safety limits
    if docstring_pattern:
        # Simple check first to avoid complex regex on large files
        if "'''" in content or '"""' in content or "/**" in content:
            try:
                # Use a timeout for the regex search to avoid hanging
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        re.search, docstring_pattern, content, re.MULTILINE | re.DOTALL
                    )
                    has_docstrings = bool(future.result(timeout=0.1))  # Lowered from 0.2s
                    
                    # Extract docstrings for quality analysis if we have time
                    if has_docstrings and not STOP_ANALYSIS:
                        future = executor.submit(
                            re.finditer, docstring_pattern, content, re.MULTILINE | re.DOTALL
                        )
                        docstring_matches = list(future.result(timeout=0.1))  # Lowered from 0.2s
                        for match in docstring_matches[:1]:  # Lowered from 3
                            docstring_text = match.group(0).strip()
                            if docstring_text:
                                all_comments.append(docstring_text)
            except (FutureTimeoutError, Exception) as e:
                logger.warning(f"Docstring analysis for {file_path} failed or timed out: {e}")
                # We'll assume no docstrings to be safe
                has_docstrings = False
    
    # Calculate comment quality score (0.0 to 1.0)
    if STOP_ANALYSIS:
        return code_lines, comment_lines, has_docstrings, 0
        
    try:
        quality_score = calculate_comment_quality(all_comments)
    except BaseException as e:
        logger.error(f"calculate_comment_quality failed: {e}")
        STOP_ANALYSIS = True
        return code_lines, comment_lines, has_docstrings, 0
    
    return code_lines, comment_lines, has_docstrings, quality_score

def calculate_comment_quality(comments: List[str]) -> float:
    """
    Calculate the quality score of comments based on various factors
    
    Args:
        comments: List of comment strings
        
    Returns:
        Quality score between 0.0 and 1.0
    """
    if not comments:
        return 0.0
    
    # Limit the number of comments analyzed to avoid timeout
    if len(comments) > 30:  # Lowered from 100
        comments = comments[:30]
    
    total_score = 0.0
    
    for comment in comments:
        comment_score = 0.0
        
        # Limit comment length to avoid excessive processing
        if len(comment) > 300:  # Lowered from 1000
            comment = comment[:300]
        
        # Length factor (too short comments are less useful)
        length = len(comment)
        if length < 3:
            length_score = 0.1
        elif length < 10:
            length_score = 0.3
        elif length < 30:
            length_score = 0.7
        else:
            length_score = 1.0
        
        # Word count factor (more words usually means more information)
        words = comment.split()
        word_count = len(words)
        if word_count < 2:
            word_score = 0.2
        elif word_count < 5:
            word_score = 0.5
        else:
            word_score = 1.0
        
        # Unique words ratio (higher ratio suggests more semantic content)
        unique_words = len(set(word.lower() for word in words))
        unique_ratio = 1.0 if word_count == 0 else unique_words / word_count
        unique_score = min(unique_ratio * 1.5, 1.0)
        
        # Formatting - check if comment has good formatting
        formatting_score = 0.5
        if re.search(r'[.!?]$', comment):  # Proper punctuation
            formatting_score += 0.25
        if comment and comment[0].isupper():  # Starts with capital letter
            formatting_score += 0.25
        
        # Combine scores with different weights
        comment_score = (
            length_score * 0.2 +
            word_score * 0.3 +
            unique_score * 0.3 +
            formatting_score * 0.2
        )
        
        total_score += comment_score
    
    # Average score of all comments
    return total_score / len(comments)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code comments check with a hard process-level timeout.
    """
    import multiprocessing

    # Helper to run in a subprocess
    def _run_check_code_comments(local_path, repository, timeout_seconds):
        try:
            return check_code_comments(local_path, repository, timeout_seconds=timeout_seconds)
        except Exception as e:
            return {
                "total_files_analyzed": 0,
                "files_with_comments": 0,
                "total_code_lines": 0,
                "total_comment_lines": 0,
                "comment_ratio": 0,
                "files_with_docstrings": 0,
                "comment_quality_score": 0,
                "comment_distribution_score": 0,
                "comment_score": 0,
                "timed_out": True,
                "processing_time": timeout_seconds,
                "error": str(e)
            }

    local_path = repository.get('local_path')
    timeout_seconds = 35  # hard timeout for the check (should be < orchestrator's per-check timeout)
    hard_timeout = 40     # hard process kill timeout

    # Use a process pool for hard timeout protection
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_check_code_comments, local_path, repository, timeout_seconds)
        try:
            result = future.result(timeout=hard_timeout)
            return {
                "score": result.get("comment_score", 0),
                "result": result
            }
        except concurrent.futures.TimeoutError:
            # Kill the process and return a minimal result
            future.cancel()
            return {
                "score": 0,
                "result": {
                    "error": f"Analysis timed out after {hard_timeout} seconds (process killed)",
                    "timed_out": True,
                    "processing_time": hard_timeout,
                    "total_files_analyzed": 0
                }
            }
        except Exception as e:
            return {
                "score": 0,
                "result": {
                    "error": str(e),
                    "timed_out": True,
                    "processing_time": hard_timeout,
                    "total_files_analyzed": 0
                }
            }