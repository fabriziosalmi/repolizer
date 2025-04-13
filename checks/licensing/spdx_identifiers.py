"""
SPDX Identifiers Check

Checks if the repository uses proper SPDX license identifiers.
"""
import os
import re
import logging
import time
import platform
import threading
import signal
from typing import Dict, Any, List, Set, Tuple, Optional
from contextlib import contextmanager
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

# Add timeout handling
class TimeoutException(Exception):
    """Custom exception for timeouts."""
    pass

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
        original_handler = None  # To satisfy finally block

    try:
        yield
    finally:
        if can_use_signal:
            signal.alarm(0)  # Disable the alarm
            # Restore the original signal handler if there was one
            if original_handler is not None:
                signal.signal(signal.SIGALRM, original_handler)

def safe_read_file(file_path, timeout=2, read_lines=None):
    """Safely read a file with timeout protection."""
    try:
        with time_limit(timeout):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if read_lines is not None:
                    # Only read the specified number of lines
                    lines = []
                    for _ in range(read_lines):
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line)
                    return ''.join(lines)
                else:
                    return f.read()
    except TimeoutException:
        logger.warning(f"Timeout reading file: {file_path}")
        return None
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
        return None

# List of valid SPDX license identifiers
# This is a subset - the full list is available at https://spdx.org/licenses/
SPDX_IDENTIFIERS = {
    "MIT", "Apache-2.0", "GPL-3.0-only", "GPL-3.0-or-later", "GPL-2.0-only", "GPL-2.0-or-later",
    "LGPL-3.0-only", "LGPL-3.0-or-later", "LGPL-2.1-only", "LGPL-2.1-or-later",
    "BSD-3-Clause", "BSD-2-Clause", "MPL-2.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "Unlicense", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "ISC", "0BSD", "Zlib",
    "EPL-2.0", "EPL-1.0", "CDDL-1.0", "EUPL-1.2", "BSL-1.0"
}

# Legacy/deprecated SPDX identifiers that should be updated
DEPRECATED_IDENTIFIERS = {
    "GPL-3.0": "GPL-3.0-only or GPL-3.0-or-later",
    "GPL-2.0": "GPL-2.0-only or GPL-2.0-or-later",
    "LGPL-3.0": "LGPL-3.0-only or LGPL-3.0-or-later", 
    "LGPL-2.1": "LGPL-2.1-only or LGPL-2.1-or-later",
    "AGPL-3.0": "AGPL-3.0-only or AGPL-3.0-or-later"
}

def check_spdx_identifiers(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check for proper SPDX license identifiers in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "has_spdx_identifier": False,
        "spdx_identifier": None,
        "is_valid_identifier": False,
        "is_deprecated_identifier": False,
        "spdx_in_package_json": False,
        "spdx_in_license_file": False,
        "spdx_in_readme": False,
        "spdx_in_source_files": False,
        "files_with_spdx": [],
        "files_checked": 0,
        "spdx_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 30  # 30 seconds total timeout for the entire analysis
    MAX_SOURCE_FILES = 20  # Maximum number of source files to check
    MAX_FILE_SIZE = 100000  # 100KB
    
    # Files to check for SPDX identifiers
    files_to_check = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
        "README.md", "README", "README.txt"
    ]
    
    # SPDX identifier pattern
    spdx_pattern = r'(?i)SPDX-License-Identifier:\s*([A-Za-z0-9\.\-]+)'
    
    files_checked = 0
    files_with_spdx = []
    identifiers_found = set()
    
    # Track analysis start time for global timeout
    start_time = datetime.now()
    analysis_terminated_early = False
    
    # First perform local analysis if we have a local repository path
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
    else:
        try:
            logger.info(f"Analyzing repository at {repo_path} for SPDX identifiers")
            
            # Check specific files for SPDX identifiers
            for file_name in files_to_check:
                # Check if we've exceeded the global timeout
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                    logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping analysis.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                    break
                
                file_path = os.path.join(repo_path, file_name)
                if os.path.isfile(file_path):
                    # Check file size before opening
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > MAX_FILE_SIZE:  # Skip files larger than 100KB
                            continue
                    except OSError:
                        continue
                    
                    # Use safe_read_file with timeout
                    content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                    if content is None:
                        continue
                    
                    files_checked += 1
                    relative_path = os.path.relpath(file_path, repo_path)
                    
                    # Package.json handling for license field
                    if file_name == "package.json":
                        import json
                        try:
                            with time_limit(FILE_READ_TIMEOUT):  # Add timeout for JSON parsing
                                data = json.loads(content)
                                if "license" in data:
                                    license_value = data["license"]
                                    if isinstance(license_value, str):
                                        spdx = license_value.strip()
                                        identifiers_found.add(spdx)
                                        
                                        if spdx in SPDX_IDENTIFIERS or spdx in DEPRECATED_IDENTIFIERS:
                                            result["has_spdx_identifier"] = True
                                            result["spdx_in_package_json"] = True
                                            files_with_spdx.append(relative_path)
                                            
                                            if not result["spdx_identifier"]:
                                                result["spdx_identifier"] = spdx
                                                
                                            if spdx in SPDX_IDENTIFIERS:
                                                result["is_valid_identifier"] = True
                                            elif spdx in DEPRECATED_IDENTIFIERS:
                                                result["is_deprecated_identifier"] = True
                        except (json.JSONDecodeError, TimeoutException) as e:
                            logger.warning(f"Error parsing package.json: {e}")
                    
                    # Look for SPDX identifiers in content
                    try:
                        with time_limit(FILE_READ_TIMEOUT):  # Add timeout for regex
                            matches = re.findall(spdx_pattern, content)
                            if matches:
                                for spdx in matches:
                                    spdx = spdx.strip()
                                    identifiers_found.add(spdx)
                                    
                                    if spdx in SPDX_IDENTIFIERS or spdx in DEPRECATED_IDENTIFIERS:
                                        result["has_spdx_identifier"] = True
                                        files_with_spdx.append(relative_path)
                                        
                                        if not result["spdx_identifier"]:
                                            result["spdx_identifier"] = spdx
                                            
                                        if spdx in SPDX_IDENTIFIERS:
                                            result["is_valid_identifier"] = True
                                        elif spdx in DEPRECATED_IDENTIFIERS:
                                            result["is_deprecated_identifier"] = True
                                        
                                        # Track where we found SPDX identifiers
                                        if "LICENSE" in file_name.upper() or "COPYING" in file_name.upper():
                                            result["spdx_in_license_file"] = True
                                        elif file_name.upper().startswith("README"):
                                            result["spdx_in_readme"] = True
                                        
                                        # Don't need to continue if we found one
                                        break
                    except TimeoutException:
                        logger.warning(f"Regex search timed out for {relative_path}")
                    
                    # Also look for license declarations without SPDX prefix
                    if not result["has_spdx_identifier"]:
                        try:
                            with time_limit(FILE_READ_TIMEOUT):  # Add timeout for regex
                                for spdx_id in SPDX_IDENTIFIERS:
                                    # Look for the SPDX ID on its own line or as a badge
                                    if re.search(r'(?m)^' + re.escape(spdx_id) + r'$', content) or \
                                       re.search(r'badge/license-' + re.escape(spdx_id) + r'-', content):
                                        result["has_spdx_identifier"] = True
                                        result["spdx_identifier"] = spdx_id
                                        result["is_valid_identifier"] = True
                                        
                                        if "LICENSE" in file_name.upper() or "COPYING" in file_name.upper():
                                            result["spdx_in_license_file"] = True
                                        elif file_name.upper().startswith("README"):
                                            result["spdx_in_readme"] = True
                                            
                                        files_with_spdx.append(relative_path)
                                        break
                        except TimeoutException:
                            logger.warning(f"Alternative license search timed out for {relative_path}")
            
            # Check source files for SPDX headers if we haven't found them elsewhere
            if not result["has_spdx_identifier"] and not analysis_terminated_early:
                source_extensions = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.php', '.rb']
                source_files_checked = 0
                
                # Use os.walk with a timeout wrapper
                dirs_checked = 0
                MAX_DIRS = 50  # Limit directory traversal
                
                for root, dirs, files in os.walk(repo_path):
                    # Check if we've exceeded the global timeout
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                        logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping source file analysis.")
                        analysis_terminated_early = True
                        result["early_termination"] = {
                            "reason": "global_timeout",
                            "elapsed_seconds": round(elapsed_time, 1),
                            "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                        }
                        break
                    
                    # Skip hidden directories and common non-source dirs
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', 'dist', 'build']]
                    
                    # Count directories checked
                    dirs_checked += 1
                    if dirs_checked > MAX_DIRS:
                        logger.warning(f"Reached maximum directories to check ({MAX_DIRS})")
                        break
                    
                    # Limit directory depth for large repositories
                    rel_path = os.path.relpath(root, repo_path)
                    depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                    if depth > 3:  # Don't go too deep
                        dirs[:] = []
                        continue
                    
                    for file in files:
                        # Check if we've exceeded the global timeout again
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                            logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds during file loop.")
                            analysis_terminated_early = True
                            result["early_termination"] = {
                                "reason": "global_timeout",
                                "elapsed_seconds": round(elapsed_time, 1),
                                "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                            }
                            break
                        
                        _, ext = os.path.splitext(file)
                        
                        # Only check source files with known extensions
                        if ext not in source_extensions:
                            continue
                        
                        file_path = os.path.join(root, file)
                        
                        # Skip large files
                        try:
                            if os.path.getsize(file_path) > MAX_FILE_SIZE:  # 100KB
                                continue
                        except OSError:
                            continue
                        
                        # Only check up to MAX_SOURCE_FILES source files
                        source_files_checked += 1
                        if source_files_checked > MAX_SOURCE_FILES:
                            logger.info(f"Reached maximum source files to check ({MAX_SOURCE_FILES})")
                            break
                        
                        # Read first 30 lines where license notices typically appear
                        header = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT, read_lines=30)
                        if header is None:
                            continue
                        
                        # Look for SPDX identifiers
                        try:
                            with time_limit(FILE_READ_TIMEOUT):  # Add timeout for regex
                                matches = re.findall(spdx_pattern, header)
                                if matches:
                                    for spdx in matches:
                                        spdx = spdx.strip()
                                        identifiers_found.add(spdx)
                                        
                                        if spdx in SPDX_IDENTIFIERS or spdx in DEPRECATED_IDENTIFIERS:
                                            result["has_spdx_identifier"] = True
                                            result["spdx_in_source_files"] = True
                                            relative_path = os.path.relpath(file_path, repo_path)
                                            files_with_spdx.append(relative_path)
                                            
                                            if not result["spdx_identifier"]:
                                                result["spdx_identifier"] = spdx
                                                
                                            if spdx in SPDX_IDENTIFIERS:
                                                result["is_valid_identifier"] = True
                                            elif spdx in DEPRECATED_IDENTIFIERS:
                                                result["is_deprecated_identifier"] = True
                                            
                                            # Only need one file with SPDX
                                            break
                        except TimeoutException:
                            logger.warning(f"SPDX pattern search timed out for source file")
                            continue
                    
                    # Break if we've found what we need or checked enough files
                    if result["has_spdx_identifier"] or source_files_checked > MAX_SOURCE_FILES:
                        break
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            result["errors"] = str(e)
    
    # Use API data only as fallback if local analysis didn't identify a license
    if not result["has_spdx_identifier"] and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            spdx_id = license_info["spdx_id"]
            if spdx_id.upper() != "NOASSERTION":
                result["has_license"] = True
                result["spdx_identifier"] = spdx_id
                
                if spdx_id in SPDX_IDENTIFIERS:
                    result["has_spdx_identifier"] = True
                    result["is_valid_identifier"] = True
                elif spdx_id in DEPRECATED_IDENTIFIERS:
                    result["has_spdx_identifier"] = True
                    result["is_deprecated_identifier"] = True
    
    # Update result with findings
    result["has_license"] = result["has_license"] or result["has_spdx_identifier"]
    result["files_with_spdx"] = files_with_spdx
    result["files_checked"] = files_checked
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate SPDX identifier score (0-100 scale)
    score = 0
    
    # Points for having a SPDX identifier
    if result["has_spdx_identifier"]:
        score += 50
        
        # Points for valid (non-deprecated) identifier
        if result["is_valid_identifier"]:
            score += 20
        elif result["is_deprecated_identifier"]:
            score += 10
        
        # Points for SPDX in license file (best place)
        if result["spdx_in_license_file"]:
            score += 20
        
        # Points for SPDX in other places
        other_places_points = 0
        if result["spdx_in_package_json"]:
            other_places_points += 15
        if result["spdx_in_readme"]:
            other_places_points += 10
        if result["spdx_in_source_files"]:
            other_places_points += 15
            
        # Cap additional points at 30
        score += min(30, other_places_points)
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["spdx_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify SPDX license identifiers
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.info(f"Starting SPDX identifiers check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"spdx_identifiers_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached SPDX identifiers check result for {repo_name}")
            return cached_result
        
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_spdx_identifiers(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"SPDX identifiers check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("spdx_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.info(f"Completed SPDX identifiers check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running SPDX identifiers check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_license": False,
                "has_spdx_identifier": False,
                "spdx_identifier": None,
                "spdx_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }