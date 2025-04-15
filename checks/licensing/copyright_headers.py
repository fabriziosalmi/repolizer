"""
Copyright Headers Check

Checks if the repository's source files contain appropriate copyright headers.
"""
import os
import re
import logging
import signal
import platform
import threading
import time
import sys
from typing import Dict, Any, List, Set, Tuple, Optional, TypedDict, DefaultDict
from datetime import datetime
from collections import defaultdict
from contextlib import contextmanager

# Setup logging
logger = logging.getLogger(__name__)

class TimeoutException(Exception):
    """Custom exception for timeouts."""
    pass

class GlobalTimeoutException(Exception):
    """Custom exception for the global analysis timeout."""
    pass

# Try to import the filesystem utilities if available
try:
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'utils'))
    from filesystem_utils import (
        time_limit, is_dir_with_timeout, safe_walk, safe_read_file, 
        get_file_size_with_timeout, is_file_with_timeout
    )
    logger.debug("Using filesystem_utils for timeout protection")
    has_filesystem_utils = True
except ImportError:
    logger.info("filesystem_utils module not available, using internal fallbacks")
    has_filesystem_utils = False
    
    # Define our own version if the utilities aren't available
    @contextmanager
    def time_limit(seconds):
        """Context manager for setting a timeout on file operations (Unix/MainThread only)."""
        # Skip setting alarm on Windows or when not in main thread
        is_main_thread = threading.current_thread() is threading.main_thread()
        can_use_signal = platform.system() != 'Windows' and is_main_thread

        if can_use_signal:
            def signal_handler(signum, frame):
                logger.warning(f"File processing triggered timeout after {seconds} seconds.")
                raise TimeoutException(f"File processing timed out after {seconds} seconds")

            original_handler = signal.signal(signal.SIGALRM, signal_handler)
            signal.alarm(seconds)
        else:
            # If signals can't be used, this context manager does nothing for timeout.
            # Rely on the global timeout check instead.
            original_handler = None # To satisfy finally block

        try:
            yield
        finally:
            if can_use_signal:
                signal.alarm(0) # Disable the alarm
                # Restore the original signal handler if there was one
                if original_handler is not None:
                    signal.signal(signal.SIGALRM, original_handler)
                    
    def is_dir_with_timeout(path, timeout=5):
        """Timeout-protected version of os.path.isdir."""
        logger.debug(f"Checking if path is a directory: {path}")
        
        # For Windows or non-main threads where signal can't be used
        if platform.system() == 'Windows' or threading.current_thread() is not threading.main_thread():
            start_time = time.time()
            try:
                result = os.path.isdir(path)
                elapsed = time.time() - start_time
                if elapsed > timeout / 2:
                    logger.debug(f"isdir check on {path} was slow but completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                logger.debug(f"Error checking if {path} is a directory: {e}")
                return False
                
        # Use signals for Unix main thread
        try:
            with time_limit(timeout):
                result = os.path.isdir(path)
                return result
        except Exception as e:
            logger.warning(f"Error checking if {path} is a directory: {e}")
            return False

    def safe_walk(top, timeout=10, max_depth=None, skip_dirs=None):
        """Safe version of os.walk with timeouts."""
        results = []
        
        if not is_dir_with_timeout(top, timeout):
            logger.warning(f"Path doesn't exist or isn't a directory: {top}")
            return results
            
        if skip_dirs is None:
            skip_dirs = []
            
        # Implementation details would be duplicated here, 
        # but for brevity we'll rely on os.walk for the fallback
        # This is less safe but avoids code duplication
        try:
            for root, dirs, files in os.walk(top, topdown=True):
                # Filter out directories to skip
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
                
                # Append the results
                results.append((root, dirs, files))
                
                # Check depth limit
                if max_depth is not None:
                    rel_path = os.path.relpath(root, top)
                    depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                    if depth >= max_depth:
                        dirs[:] = []  # Don't go deeper
        except Exception as e:
            logger.error(f"Error during directory walk: {e}")
            
        return results

# --- Type Definitions for Result Structure ---
# Using TypedDict for better clarity on the expected result structure
class HeaderDetails(TypedDict, total=False):
    years_mentioned: List[str]
    organizations_mentioned: List[str]
    up_to_date: bool
    license_referenced: bool
    multi_line_format: bool
    author_mentioned: bool
    spdx_identifier: bool

class LanguageCoverageStats(TypedDict):
    total_files: int
    files_with_headers: int
    percentage: float

class LanguageCoverage(TypedDict, total=False):
    file_types_with_headers: List[str]
    file_types_without_headers: List[str]
    coverage_by_language: Dict[str, LanguageCoverageStats]

class ExampleDetail(TypedDict):
    file: str
    header: Optional[str] # header might not be present for missing examples
    reason: Optional[str] # reason might be present for missing examples

class Examples(TypedDict):
    good_examples: List[ExampleDetail]
    missing_examples: List[ExampleDetail]

class BenchmarkProject(TypedDict):
    name: str
    score: int

class Benchmarks(TypedDict):
    average_oss_project: int
    top_10_percent: int
    exemplary_projects: List[BenchmarkProject]

class EarlyTermination(TypedDict, total=False):
    reason: str
    limit: Optional[int]
    elapsed_seconds: Optional[float]
    limit_seconds: Optional[int]
    details: Optional[str]

class CopyrightCheckResult(TypedDict, total=False):
    has_copyright_headers: bool
    files_with_headers: int
    files_without_headers: int
    consistent_headers: bool
    consistency_ratio: Optional[float] # Added for clarity
    header_patterns: List[str]
    common_header_format: str
    files_checked: int
    header_details: HeaderDetails
    language_coverage: LanguageCoverage
    examples: Examples
    benchmarks: Benchmarks
    recommendations: List[str]
    copyright_header_score: int
    early_termination: Optional[EarlyTermination]
    errors: Optional[str] # Added for clarity

def check_copyright_headers(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> CopyrightCheckResult:
    """
    Check copyright headers in source files.

    Args:
        repo_path: Path to the repository on local filesystem.
        repo_data: Repository data from API (used if repo_path is not available).

    Returns:
        Dictionary conforming to CopyrightCheckResult TypedDict with check results.
    """
    # Initialize result structure early
    # Note: Explicitly defining keys helps with type checking and understanding
    result: CopyrightCheckResult = {
        "has_copyright_headers": False,
        "files_with_headers": 0,
        "files_without_headers": 0,
        "consistent_headers": False,
        "consistency_ratio": None,
        "header_patterns": [],
        "common_header_format": "",
        "files_checked": 0,
        "header_details": {
            "years_mentioned": [],
            "organizations_mentioned": [],
            "up_to_date": False,
            "license_referenced": False,
            "multi_line_format": False,
            "author_mentioned": False,
            "spdx_identifier": False
        },
        "language_coverage": {
            "file_types_with_headers": [],
            "file_types_without_headers": [],
            "coverage_by_language": {}
        },
        "examples": {
            "good_examples": [],
            "missing_examples": []
        },
        "benchmarks": {
            "average_oss_project": 40,
            "top_10_percent": 85,
            "exemplary_projects": [
                {"name": "Linux Kernel", "score": 95},
                {"name": "Apache Projects", "score": 90},
                {"name": "Mozilla Firefox", "score": 88}
            ]
        },
        "recommendations": [],
        "copyright_header_score": 0,
        "early_termination": None,
        "errors": None
    }

    # --- Configuration Constants ---
    # Moved configuration together for easier modification
    GLOBAL_ANALYSIS_TIMEOUT = 120  # Reduced from 300 to 120 seconds to prevent long hangs
    MAX_FILES_TO_CHECK = 1000  # Reduced from 5000 to prevent excessive processing
    MAX_FILE_SIZE = 250000  # Reduced from 500KB to 250KB
    FILE_SCAN_TIMEOUT = 2  # Reduced from 5 to 2 seconds per file
    DIR_SCAN_TIMEOUT = 5   # Reduced from 10 to 5 seconds per directory scan
    PROGRESS_LOG_INTERVAL = 100  # Reduced from 500 to show progress more frequently
    EXAMPLE_LIMIT = 3  # Max number of good/missing examples to store
    MAX_HEADER_LINES = 20  # Maximum lines to read for header check (reduced from 30)
    FILE_READ_TIMEOUT = 1  # Timeout for individual file reads in seconds

    SOURCE_EXTENSIONS: Dict[str, Optional[str]] = {
        # Programming languages
        '.py': '#', '.js': '//', '.jsx': '//', '.ts': '//', '.tsx': '//',
        '.java': '//', '.c': '//', '.cpp': '//', '.cc': '//', '.h': '//', '.hpp': '//',
        '.cs': '//', '.go': '//', '.php': '//', '.rb': '#', '.swift': '//',
        '.kt': '//', '.rs': '//', '.scala': '//', '.m': '//', '.mm': '//',
        '.sh': '#', '.bash': '#', '.zsh': '#', '.pl': '#', '.pm': '#',
        # Web
        '.html': '<!--', '.htm': '<!--', '.css': '/*', '.scss': '/*', '.sass': '/*',
        '.less': '/*', '.vue': '<!--',
        # Config
        '.xml': '<!--', '.json': None, '.yaml': '#', '.yml': '#', '.toml': '#',
        '.ini': ';', '.cfg': '#', '.conf': '#'
    }
    BINARY_EXTENSIONS: Set[str] = {
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.tar', '.gz', 
        '.jar', '.war', '.exe', '.dll', '.so', '.dylib', '.o', '.a', 
        '.class', '.pyc'
    }
    SKIP_DIRS: Set[str] = {
        '.git', 'node_modules', 'venv', '.venv', 'env', '.env', 'dist', 
        'build', 'target', '.idea', '.vscode', '__pycache__', 'vendor', 
        'bin', 'obj', '.svn', '.hg'
    }

    # --- Regex Patterns ---
    # Grouped regex patterns
    COPYRIGHT_PATTERNS: List[re.Pattern] = [
        re.compile(r'(?i)copyright\s*(?:\(c\)|\©)?\s*(?:[0-9]{4}[-–—]?[0-9]{0,4})'),
        re.compile(r'(?i)copyright\s+(?:by|owner)'),
        re.compile(r'(?i)all\s+rights\s+reserved'),
        re.compile(r'(?i)©\s*[0-9]{4}'),
        re.compile(r'(?i)\(c\)\s*[0-9]{4}')
    ]
    LICENSE_PATTERNS: List[re.Pattern] = [
        re.compile(r'(?i)licensed\s+under'), re.compile(r'(?i)apache\s+license'),
        re.compile(r'(?i)mit\s+license'), re.compile(r'(?i)bsd\s+license'),
        re.compile(r'(?i)gnu\s+general\s+public\s+license'), re.compile(r'(?i)gpl'),
        re.compile(r'(?i)lgpl'), re.compile(r'(?i)mozilla\s+public\s+license'),
        re.compile(r'(?i)spdx-license-identifier') # Include SPDX here too
    ]
    ORG_PATTERNS: List[re.Pattern] = [
        re.compile(r'(?i)copyright\s*(?:\(c\)|\©)?\s*(?:[0-9]{4}[-–—]?[0-9]{0,4})?\s*(?:by)?\s*([A-Za-z0-9][\w\s,\.]+(?:Inc|LLC|Ltd|GmbH|Corp|Corporation|Foundation|Project))'),
        re.compile(r'(?i)(?:©|\(c\))\s*(?:[0-9]{4}[-–—]?[0-9]{0,4})?\s*([A-Za-z0-9][\w\s,\.]+(?:Inc|LLC|Ltd|GmbH|Corp|Corporation|Foundation|Project))')
    ]
    SPDX_PATTERN: re.Pattern = re.compile(r'(?i)SPDX-License-Identifier:\s*([\w\.\-]+)')
    AUTHOR_PATTERN: re.Pattern = re.compile(r'(?i)@author|author:|written by')
    YEAR_PATTERN: re.Pattern = re.compile(r'(?:19|20)\d{2}(?:[-–—]\d{2,4})?')


    # Only attempt analysis if we have a local path - using safe directory check
    if not repo_path:
        logger.info("No repository path provided. Attempting to use API data.")
    elif not is_dir_with_timeout(repo_path, timeout=DIR_SCAN_TIMEOUT): # Use constant
        logger.warning(f"Repository path {repo_path} doesn't exist, isn't accessible, or check timed out. Attempting to use API data.")
    else:
        logger.debug(f"Analyzing local repository at {repo_path} for copyright headers")

        # --- Analysis State ---
        # Type hints added for clarity
        files_checked: int = 0
        files_with_headers: int = 0
        files_without_headers: int = 0
        header_formats: DefaultDict[str, int] = defaultdict(int)
        header_patterns_found: Set[str] = set()
        years_mentioned: Set[str] = set()
        organizations: Set[str] = set()
        license_references: bool = False
        author_mentioned: bool = False
        spdx_identifier: bool = False
        multiline_format: bool = False # Determined per file later

        language_coverage: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "with_headers": 0})
        good_examples: List[ExampleDetail] = []
        missing_examples: List[ExampleDetail] = []

        start_time = datetime.now()
        analysis_terminated_early: bool = False
        last_progress_time = start_time  # Track when we last logged progress

        try:
            logger.debug("Starting repository walk and analysis with timeout protection...")
            
            # Use safe_walk instead of os.walk for timeout protection
            for root, dirs, files in safe_walk(repo_path, timeout=DIR_SCAN_TIMEOUT, 
                                              max_depth=8, skip_dirs=SKIP_DIRS): # Reduced max_depth from 10 to 8
                
                # Check if we should log progress based on time (every 5 seconds)
                current_time = datetime.now()
                if (current_time - last_progress_time).total_seconds() >= 5:
                    logger.debug(f"Walking directory: {root}")
                    last_progress_time = current_time
                    
                # Check for global timeout more frequently
                elapsed_time = (current_time - start_time).total_seconds()
                if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                    logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping analysis.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                    break  # Break instead of raising exception for cleaner exit
                    
                for file in files:
                    # --- Check Global Timeout and File Limits ---
                    if files_checked >= MAX_FILES_TO_CHECK: # Use constant
                        logger.warning(f"Reached maximum file count limit ({MAX_FILES_TO_CHECK}). Stopping analysis.")
                        analysis_terminated_early = True
                        result["early_termination"] = {
                            "reason": "max_files_reached",
                            "limit": MAX_FILES_TO_CHECK
                        }
                        break  # Break instead of raising exception

                    # Check elapsed time again for each file
                    current_time = datetime.now()
                    elapsed_time = (current_time - start_time).total_seconds()
                    if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT: # Use constant
                        logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds during file processing. Stopping analysis.")
                        analysis_terminated_early = True
                        result["early_termination"] = {
                            "reason": "global_timeout",
                            "elapsed_seconds": round(elapsed_time, 1),
                            "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                        }
                        break  # Break instead of raising exception

                    # --- File Filtering with safer operations ---
                    file_path = os.path.join(root, file)
                    try:
                        _, ext = os.path.splitext(file)
                        ext_lower = ext.lower()

                        # Skip non-source files, unknown comment types, binaries
                        if ext_lower not in SOURCE_EXTENSIONS or SOURCE_EXTENSIONS[ext_lower] is None: # Use constant
                            continue
                        if ext_lower in BINARY_EXTENSIONS: # Use constant
                            continue

                        # Check file size before opening - use safe version with shorter timeout
                        if has_filesystem_utils:
                            size = get_file_size_with_timeout(file_path, timeout=FILE_READ_TIMEOUT)
                            if size is None or size > MAX_FILE_SIZE: # Use constant
                                logger.debug(f"Skipping large or inaccessible file: {file_path}")
                                continue
                        else:
                            # Fallback to regular check with try/except
                            try:
                                with time_limit(FILE_READ_TIMEOUT):  # Shorter timeout for size check
                                    if os.path.getsize(file_path) > MAX_FILE_SIZE: # Use constant
                                        logger.debug(f"Skipping large file: {file_path}")
                                        continue
                            except Exception as e:
                                logger.warning(f"Could not stat file {file_path}: {e}. Skipping.")
                                continue
                    except OSError as e:
                        logger.warning(f"Could not stat file {file_path}: {e}. Skipping.")
                        continue

                    # --- Process File ---
                    files_checked += 1
                    rel_path = os.path.relpath(file_path, repo_path)
                    language_coverage[ext_lower]["total"] += 1

                    # More frequent progress logging
                    if files_checked % PROGRESS_LOG_INTERVAL == 0 or (current_time - last_progress_time).total_seconds() >= 5:
                        logger.debug(f"Processed {files_checked} files...")
                        last_progress_time = current_time

                    try:
                        # Use per-file timeout with shorter duration
                        with time_limit(FILE_SCAN_TIMEOUT): # Use constant
                            # --- Check if file is binary (heuristic) ---
                            try:
                                if has_filesystem_utils:
                                    # Use our safer utils if available with shorter timeout
                                    chunk = safe_read_file(file_path, max_size=4096, binary=True, timeout=FILE_READ_TIMEOUT)
                                    if chunk is None or b'\x00' in chunk:
                                        logger.debug(f"Skipping likely binary file: {rel_path}")
                                        files_checked -= 1
                                        language_coverage[ext_lower]["total"] -= 1
                                        continue
                                else:
                                    # Fallback with try/except and shorter timeout
                                    with time_limit(FILE_READ_TIMEOUT):
                                        try:
                                            with open(file_path, 'rb') as f_bin:
                                                chunk = f_bin.read(4096)  # Read smaller chunk
                                                if b'\x00' in chunk:
                                                    logger.debug(f"Skipping likely binary file (null byte found): {rel_path}")
                                                    files_checked -= 1
                                                    language_coverage[ext_lower]["total"] -= 1
                                                    continue
                                        except Exception as e:
                                            logger.warning(f"Error reading binary check from {rel_path}: {e}. Skipping.")
                                            files_checked -= 1
                                            language_coverage[ext_lower]["total"] -= 1
                                            continue
                            except Exception as e:
                                logger.warning(f"Could not read binary chunk from {rel_path}: {e}. Skipping.")
                                files_checked -= 1
                                language_coverage[ext_lower]["total"] -= 1
                                continue

                            # --- Read header text (first ~20 lines instead of 30) ---
                            header_text = ""
                            try:
                                if has_filesystem_utils:
                                    # Our utils has a simpler line-based read with shorter timeout
                                    content = safe_read_file(file_path, max_size=MAX_FILE_SIZE, # Use constant
                                                           timeout=FILE_READ_TIMEOUT, # Use constant
                                                           encoding='utf-8', errors='ignore')
                                    if content is None:
                                        logger.warning(f"Could not read file {rel_path}. Skipping.")
                                        files_without_headers += 1
                                        if len(missing_examples) < EXAMPLE_LIMIT: # Use constant
                                            missing_examples.append({"file": rel_path, "header": None, "reason": "read_error"})
                                        continue
                                        
                                    # Take just the first MAX_HEADER_LINES lines (reduced from 30)
                                    lines = content.splitlines()[:MAX_HEADER_LINES]
                                    header_text = '\n'.join(lines)
                                else:
                                    # Fallback to the manual line reading with shorter timeout
                                    with time_limit(FILE_READ_TIMEOUT):
                                        lines_read = 0
                                        try:
                                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                                for line in f:
                                                    header_text += line
                                                    lines_read += 1
                                                    if lines_read >= MAX_HEADER_LINES:
                                                        break
                                        except UnicodeDecodeError:
                                            # Handle encoding issues gracefully
                                            logger.debug(f"Unicode decode error for {rel_path}. Skipping as likely binary.")
                                            files_without_headers += 1
                                            if len(missing_examples) < EXAMPLE_LIMIT:
                                                missing_examples.append({"file": rel_path, "header": None, "reason": "encoding_error"})
                                            continue
                            except Exception as e:
                                logger.warning(f"Error reading file {rel_path}: {e}. Skipping content analysis.")
                                files_without_headers += 1
                                if len(missing_examples) < EXAMPLE_LIMIT: # Use constant
                                    missing_examples.append({"file": rel_path, "header": None, "reason": "read_error"})
                                continue

                            # --- Rest of the analysis remains the same ---
                            file_has_copyright = False
                            file_has_license_ref = False
                            file_has_spdx = False
                            file_has_author = False
                            file_is_multiline = False

                            # Check for copyright patterns first
                            matched_copyright_pattern_text = None
                            for pattern in COPYRIGHT_PATTERNS: # Use constant
                                match = pattern.search(header_text)
                                if match:
                                    file_has_copyright = True
                                    matched_copyright_pattern_text = match.group(0) # Store first match for format tracking
                                    header_patterns_found.add(pattern.pattern) # Store original regex string

                                    # Simple multiline check (crude but fast)
                                    if header_text.count('copyright') > 1 or header_text.count('©') > 1 or header_text.count('(c)') > 1:
                                        file_is_multiline = True
                                    break # Found one copyright pattern, enough for this check

                            if file_has_copyright:
                                files_with_headers += 1
                                language_coverage[ext_lower]["with_headers"] += 1
                                if matched_copyright_pattern_text: # Ensure not None before using as key
                                    header_formats[matched_copyright_pattern_text] += 1 # Track format consistency

                                # Extract details only if copyright found
                                year_matches = YEAR_PATTERN.findall(header_text) # Use constant
                                years_mentioned.update(year_matches)

                                for org_pattern in ORG_PATTERNS: # Use constant
                                    org_matches = org_pattern.search(header_text)
                                    if org_matches and len(org_matches.groups()) > 0:
                                        organizations.add(org_matches.group(1).strip())

                                for license_pattern in LICENSE_PATTERNS: # Use constant
                                    if license_pattern.search(header_text):
                                        file_has_license_ref = True
                                        license_references = True # Set global flag if found anywhere
                                        break

                                spdx_match = SPDX_PATTERN.search(header_text) # Use constant
                                if spdx_match:
                                    file_has_spdx = True
                                    spdx_identifier = True # Set global flag

                                if AUTHOR_PATTERN.search(header_text): # Use constant
                                    file_has_author = True
                                    author_mentioned = True # Set global flag

                                # Save good example
                                if len(good_examples) < EXAMPLE_LIMIT: # Use constant
                                    header_lines = header_text.split('\n')[:15] # Limit example length
                                    good_examples.append({"file": rel_path, "header": '\n'.join(header_lines), "reason": None})

                            else: # No copyright pattern found
                                files_without_headers += 1
                                # Save missing example
                                if len(missing_examples) < EXAMPLE_LIMIT: # Use constant
                                    missing_examples.append({"file": rel_path, "header": None, "reason": "no_pattern_match"})

                            # Update multi-line status (if any file has it)
                            if file_is_multiline:
                                multiline_format = True

                    except TimeoutException:
                        logger.warning(f"Timeout processing file content: {rel_path}. Counting as 'no header'.")
                        files_without_headers += 1 # Count as no header on timeout
                        if len(missing_examples) < EXAMPLE_LIMIT: # Use constant
                             missing_examples.append({"file": rel_path, "header": None, "reason": "timeout"})
                        continue # Move to the next file
                    except Exception as e:
                        logger.error(f"Unexpected error processing file {rel_path}: {e}", exc_info=True)
                        files_without_headers += 1 # Count as no header on error
                        if len(missing_examples) < EXAMPLE_LIMIT: # Use constant
                             missing_examples.append({"file": rel_path, "header": None, "reason": "error"})
                        continue # Move to the next file
                    
                # Check if we broke out of the file loop due to limits
                if analysis_terminated_early:
                    break
                    
            # If we get here and processed some files but not many, set a warning
            if files_checked > 0 and files_checked < 10 and not analysis_terminated_early:
                logger.warning(f"Only processed {files_checked} files which is unusually low. Check for repository structure issues.")

        # Exceptions to break out of the os.walk loop - handled more gracefully now
        except (StopIteration, GlobalTimeoutException) as e:
            logger.debug(f"File analysis loop terminated early: {type(e).__name__}")
            analysis_terminated_early = True # Ensure flag is set
            # Ensure early_termination reason is set if missing (e.g., exception from walk mock)
            if isinstance(e, GlobalTimeoutException) and result.get("early_termination") is None:
                 result["early_termination"] = {
                     "reason": "global_timeout",
                     "details": "Timeout occurred during directory traversal."
                 }
            elif isinstance(e, StopIteration) and result.get("early_termination") is None:
                 # This case might indicate max files reached without the dict being set earlier
                 result["early_termination"] = {
                     "reason": "max_files_reached", # Assuming StopIteration means max files
                     "details": "Maximum file limit likely reached during traversal."
                 }
        except OSError as e:
            logger.error(f"Filesystem error during repository walk: {e}", exc_info=True)
            result["errors"] = f"Filesystem error during walk: {e}"
            # Allow fallback to API data or return partial results
        except Exception as e:
            logger.error(f"Unexpected error during repository analysis: {e}", exc_info=True)
            result["errors"] = f"Unexpected analysis error: {e}"
            # Allow fallback to API data or return partial results

        # --- Post-Analysis Processing ---
        logger.debug(f"Finished repository walk. Analyzed {files_checked} files.")
        if files_checked > 0:
            result["files_checked"] = files_checked
            result["files_with_headers"] = files_with_headers
            result["files_without_headers"] = files_without_headers

            if files_with_headers > 0:
                result["has_copyright_headers"] = True

                # Check consistency
                if header_formats:
                    # Find the count of the most common format found
                    most_common_count = max(header_formats.values()) if header_formats else 0
                    # Find the format text itself (optional, but good for reporting)
                    most_common_format_text = max(header_formats, key=header_formats.get) if header_formats else ""

                    consistency_ratio = most_common_count / files_with_headers
                    result["consistency_ratio"] = round(consistency_ratio, 2) # Store the ratio
                    if consistency_ratio >= 0.8:
                        result["consistent_headers"] = True
                        result["common_header_format"] = most_common_format_text
                    # Store the ratio even if not consistent for potential partial scoring later
                    # result["consistency_ratio"] = round(consistency_ratio, 2) # Moved up


            result["header_patterns"] = sorted(list(header_patterns_found))
            # Update header_details using the TypedDict structure
            result["header_details"] = {
                "years_mentioned": sorted(list(years_mentioned)),
                "organizations_mentioned": sorted(list(organizations)),
                "license_referenced": license_references,
                "multi_line_format": multiline_format, # Updated global flag
                "author_mentioned": author_mentioned, # Updated global flag
                "spdx_identifier": spdx_identifier # Updated global flag
            }

            current_year = datetime.now().year
            result["header_details"]["up_to_date"] = any(str(current_year) in y for y in years_mentioned)

            # Update language coverage
            lang_coverage_result: Dict[str, LanguageCoverageStats] = {}
            file_types_with: List[str] = []
            file_types_without: List[str] = []
            for ext, stats in language_coverage.items():
                if stats["total"] > 0:
                    coverage_pct = (stats["with_headers"] / stats["total"]) * 100
                    lang_coverage_result[ext] = {
                        "total_files": stats["total"],
                        "files_with_headers": stats["with_headers"],
                        "percentage": round(coverage_pct, 1)
                    }
                    if stats["with_headers"] > 0:
                        file_types_with.append(ext)
                    elif stats["total"] > stats["with_headers"]: # Only add if some files of this type lack headers
                         file_types_without.append(ext)
            
            result["language_coverage"] = {
                "coverage_by_language": lang_coverage_result,
                "file_types_with_headers": sorted(file_types_with),
                "file_types_without_headers": sorted(file_types_without)
            }

            result["examples"] = {
                "good_examples": good_examples,
                "missing_examples": missing_examples
            }

            # Generate recommendations
            recommendations = []
            coverage_ratio = result["files_with_headers"] / result["files_checked"] if result["files_checked"] > 0 else 0
            if result["files_with_headers"] == 0 and result["files_checked"] > 0:
                recommendations.append("Add copyright headers to source files.")
            elif coverage_ratio < 0.5:
                recommendations.append("Increase copyright header coverage across source files (currently < 50%).")
            elif coverage_ratio < 0.8:
                recommendations.append("Improve copyright header coverage across source files (currently < 80%).")


            if not result["consistent_headers"] and result["files_with_headers"] > 5: # Only recommend if enough headers exist to judge consistency
                 recommendations.append("Standardize copyright header format for consistency.")

            if not result["header_details"]["license_referenced"] and result["files_with_headers"] > 0:
                recommendations.append("Include license references (e.g., SPDX identifiers) in copyright headers.")

            if not result["header_details"].get("up_to_date", False) and result["header_details"]["years_mentioned"]: # Only recommend if years were found but are outdated
                recommendations.append(f"Update copyright years to include the current year ({current_year}).")

            if not result["header_details"].get("spdx_identifier", False) and result["header_details"]["license_referenced"]: # Recommend SPDX if other license refs exist but not SPDX
                recommendations.append("Consider adding SPDX license identifiers for machine-readable licensing.")

            if analysis_terminated_early and result.get("early_termination"):
                reason = result["early_termination"].get("reason", "unknown")
                recommendations.append(f"Analysis stopped early due to limits ({reason}); results may be incomplete.")

            result["recommendations"] = recommendations
        # End of local analysis block

    # --- Fallback to API data if local analysis wasn't possible or yielded no results ---
    if result["files_checked"] == 0 and repo_data and 'copyright_headers' in repo_data:
        logger.info("Local analysis yielded no files or wasn't performed. Using API data for copyright headers check.")
        api_copyright_data = repo_data.get('copyright_headers', {})

        # Merge API data into the result structure carefully
        result["has_copyright_headers"] = api_copyright_data.get('has_headers', result["has_copyright_headers"]) # Keep False if API doesn't specify
        # Use API file counts only if local check didn't run at all
        if result["files_checked"] == 0: # Check again, might have been set to 0 after failed walk
             result["files_with_headers"] = api_copyright_data.get('files_with_headers', 0)
             result["files_without_headers"] = api_copyright_data.get('files_without_headers', 0)
             result["files_checked"] = result["files_with_headers"] + result["files_without_headers"]

        result["consistent_headers"] = api_copyright_data.get('consistent_format', result["consistent_headers"])
        result["common_header_format"] = api_copyright_data.get('common_format', result["common_header_format"])
        # Merge patterns carefully - avoid overwriting if local scan found some
        api_patterns = api_copyright_data.get('patterns', [])
        if not result["header_patterns"] and api_patterns:
            result["header_patterns"] = api_patterns

        # Merge header details - prioritize local findings if any exist
        api_details = api_copyright_data.get('header_details', {})
        # Ensure result["header_details"] exists before updating
        if not result.get("header_details"): result["header_details"] = {} 
        if api_details:
             result["header_details"]["years_mentioned"] = result["header_details"].get("years_mentioned") or api_details.get('years', [])
             result["header_details"]["organizations_mentioned"] = result["header_details"].get("organizations_mentioned") or api_details.get('organizations', [])
             result["header_details"]["up_to_date"] = result["header_details"].get("up_to_date") or api_details.get('up_to_date', False)
             result["header_details"]["license_referenced"] = result["header_details"].get("license_referenced") or api_details.get('license_reference', False)
             result["header_details"]["multi_line_format"] = result["header_details"].get("multi_line_format") or api_details.get('multiline', False)
             result["header_details"]["author_mentioned"] = result["header_details"].get("author_mentioned") or api_details.get('author', False)
             result["header_details"]["spdx_identifier"] = result["header_details"].get("spdx_identifier") or api_details.get('spdx', False)

        # Merge language coverage - prioritize local findings
        api_lang_data = api_copyright_data.get('language_coverage', {})
        # Ensure result["language_coverage"] exists
        if not result.get("language_coverage"): result["language_coverage"] = {}
        if api_lang_data:
            # Check if local coverage data is empty before overwriting
            local_coverage_empty = not result["language_coverage"].get("file_types_with_headers") and \
                                   not result["language_coverage"].get("file_types_without_headers") and \
                                   not result["language_coverage"].get("coverage_by_language")
            if local_coverage_empty:
                 result["language_coverage"]["file_types_with_headers"] = api_lang_data.get('with_headers', [])
                 result["language_coverage"]["file_types_without_headers"] = api_lang_data.get('without_headers', [])
                 result["language_coverage"]["coverage_by_language"] = api_lang_data.get('by_language', {})

        # Merge examples - prioritize local
        api_examples = api_copyright_data.get('examples', {})
        # Ensure result["examples"] exists
        if not result.get("examples"): result["examples"] = {"good_examples": [], "missing_examples": []}
        if api_examples:
             result["examples"]["good_examples"] = result["examples"].get("good_examples") or api_examples.get('good', [])
             result["examples"]["missing_examples"] = result["examples"].get("missing_examples") or api_examples.get('missing', [])

        # Merge recommendations - prioritize local
        api_recs = api_copyright_data.get('recommendations', [])
        if not result.get("recommendations") and api_recs:
             result["recommendations"] = api_recs

        # Use API score if available and local analysis didn't produce one
        if result.get("copyright_header_score", 0) == 0 and 'score' in api_copyright_data:
             result["copyright_header_score"] = api_copyright_data.get('score', 0)


    # --- Calculate Final Score ---
    # Calculate score based on local analysis results if available
    # Note: Score calculation logic remains the same, just using the updated result structure
    if result["files_checked"] > 0:
        score = 0
        coverage_ratio = result["files_with_headers"] / result["files_checked"]
        coverage_score = min(50, int(coverage_ratio * 50))
        score += coverage_score

        consistency_score = 0
        if result["consistent_headers"]:
            consistency_score = 15
        elif result.get("consistency_ratio") is not None: # Use calculated ratio for partial points
             # Give points based on the ratio, even if below the 80% threshold
             consistency_score = int(result["consistency_ratio"] * 15)
        score += consistency_score


        completeness_points = 0
        # Use .get() for safer access to potentially missing keys in header_details
        if result.get("header_details", {}).get("up_to_date"): completeness_points += 10
        if result.get("header_details", {}).get("license_referenced"): completeness_points += 10
        if result.get("header_details", {}).get("organizations_mentioned"): completeness_points += 5
        if result.get("header_details", {}).get("spdx_identifier"): completeness_points += 5
        if result.get("header_details", {}).get("author_mentioned"): completeness_points += 5
        score += min(35, completeness_points) # Cap completeness points at 35

        # Ensure score is within 10-100 range
        score = min(100, max(10, score))
        result["copyright_header_score"] = int(round(score)) # Store as integer
    elif result.get("copyright_header_score", 0) == 0 : # If no files checked and no API score used yet
        logger.warning("No files checked locally and no score available from API data. Assigning minimal score.")
        result["copyright_header_score"] = 10 # Assign minimal score if no data at all
        if not result.get("recommendations"): # Ensure recommendations list exists
             result["recommendations"] = []
        result["recommendations"].append("Could not analyze repository files for copyright headers.")

    # Clean up None value if no early termination occurred
    if result.get("early_termination") is None:
        # Use pop with default to avoid KeyError if key somehow doesn't exist
        result.pop("early_termination", None) 
    if result.get("errors") is None:
        result.pop("errors", None)


    return result

# --- Wrapper Function (Mostly unchanged, added better error logging) ---
# Define type for the wrapper function result
class CheckRunnerResult(TypedDict):
    status: str
    score: int
    result: CopyrightCheckResult # Use the detailed type here
    errors: Optional[str]

def run_check(repository: Dict[str, Any]) -> CheckRunnerResult:
    """
    Check copyright notices.

    Args:
        repository: Repository data dictionary which might include a local_path.

    Returns:
        Check results conforming to CheckRunnerResult TypedDict.
    """
    repo_name = repository.get('name', 'unknown')
    logger.debug(f"Starting copyright headers check for repository: {repo_name}")
    check_result_data: Optional[CopyrightCheckResult] = None # Initialize for error handling scope
    try:
        # Cache logic remains the same
        cache_key = f"copyright_headers_{repository.get('id', repo_name)}" # Use name if ID missing
        cached_result: Optional[CheckRunnerResult] = repository.get('_cache', {}).get(cache_key)

        if cached_result:
            logger.info(f"Using cached copyright headers check result for {repo_name}")
            # Ensure score is within bounds even from cache
            if "score" in cached_result:
                 cached_result["score"] = min(100, max(10, cached_result.get("score", 10)))
            # Ensure the cached result conforms to the expected type structure
            # (This is a basic check; more rigorous validation could be added)
            if "status" in cached_result and "result" in cached_result:
                return cached_result
            else:
                logger.warning(f"Cached result for {repo_name} is malformed. Re-running check.")


        local_path = repository.get('local_path')

        # Run the improved check function
        check_result_data = check_copyright_headers(local_path, repository)

        # Final result structure
        final_result: CheckRunnerResult = {
            "status": "completed",
            "score": check_result_data.get("copyright_header_score", 10), # Default to 10 if missing
            "result": check_result_data,
            "errors": check_result_data.get("errors") # Propagate errors reported by the check function
        }

        # Ensure score bounds
        final_result["score"] = min(100, max(10, final_result["score"]))

        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result

        logger.debug(f"✅ Completed copyright headers check for {repo_name} with score: {final_result['score']}")
        return final_result

    except Exception as e:
        logger.error(f"Critical error running copyright headers check for {repo_name}: {str(e)}", exc_info=True)
        # Provide a minimal failure response conforming to CheckRunnerResult
        # Create a minimal CopyrightCheckResult for the 'result' field
        minimal_result_data: CopyrightCheckResult = {
             "recommendations": ["Analysis failed due to an unexpected error. Check logs."],
             "copyright_header_score": 5, # Minimal score on critical failure
             # Add other required keys with default values if necessary based on TypedDict definition
             "has_copyright_headers": False,
             "files_with_headers": 0,
             "files_without_headers": 0,
             "consistent_headers": False,
             "files_checked": 0,
             "header_details": {},
             "language_coverage": {},
             "examples": {"good_examples": [], "missing_examples": []},
             "benchmarks": {"average_oss_project": 40, "top_10_percent": 85, "exemplary_projects": []} # Example default
        }
        # Include partial results if available and if they conform
        partial = locals().get("check_result_data")
        if partial and isinstance(partial, dict): # Basic check if partial results exist
             # Merge known keys from partial into minimal_result_data if needed
             # This part depends heavily on how much partial data is useful/expected
             minimal_result_data.update({k: v for k, v in partial.items() if k in minimal_result_data})


        return {
            "status": "failed",
            "score": 5, # Minimal score on critical failure
            "result": minimal_result_data, # Use the constructed minimal result
            "errors": f"{type(e).__name__}: {str(e)}"
        }