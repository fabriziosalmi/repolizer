"""
License Updates Check

Checks if the repository's license is up-to-date and properly maintained.
"""
import os
import re
import logging
import time
import platform
import threading
import signal
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
from contextlib import contextmanager

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

def safe_read_file(file_path, timeout=2):
    """Safely read a file with timeout protection."""
    try:
        with time_limit(timeout):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    except TimeoutException:
        logger.warning(f"Timeout reading file: {file_path}")
        return None
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
        return None

def check_license_updates(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check for license updates in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "license_id": "unknown",
        "license_updated": False,
        "last_update_year": None,
        "current_year": datetime.now().year,
        "license_outdated": False,
        "license_files": [],
        "copyright_years": [],
        "files_checked": 0,
        "update_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 20  # 20 seconds total timeout for the entire analysis
    
    # Files that might contain license information
    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
        ".github/LICENSE.md", "docs/LICENSE.md"
    ]
    
    # Patterns for extracting year information
    year_patterns = [
        r'(?i)copyright\s*(?:\(c\)|\©)?\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)',
        r'(?i)©\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)',
        r'(?i)\(c\)\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)',
        r'(?i)year\s*(?:of)?\s*copyright:?\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)'
    ]
    
    files_checked = 0
    copyright_years = []
    found_license_files = []
    license_content = ""
    
    # Track analysis start time for global timeout
    start_time = datetime.now()
    analysis_terminated_early = False
    
    # Check if we have a local repository path
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        # Skip local analysis, using API data later
    else:
        try:
            logger.debug(f"Analyzing repository at {repo_path} for license updates")
            
            # Check license files for year information with timeout protection
            for lic_file in license_files:
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
                
                file_path = os.path.join(repo_path, lic_file)
                if os.path.isfile(file_path):
                    # Use safe_read_file with timeout
                    content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                    if content is not None:
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        found_license_files.append(relative_path)
                        result["has_license"] = True
                        
                        # Store license content for later license type detection
                        if not license_content:
                            license_content = content.lower()
                        
                        # Extract year information
                        for pattern in year_patterns:
                            matches = re.findall(pattern, content)
                            for match in matches:
                                # Extract the last year mentioned (in case of ranges like 2018-2023)
                                year_text = match.strip()
                                if "-" in year_text:
                                    year_parts = year_text.split("-")
                                    if len(year_parts) >= 2 and year_parts[1].strip().isdigit():
                                        year = int(year_parts[1].strip())
                                        copyright_years.append(year)
                                elif year_text.isdigit():
                                    year = int(year_text)
                                    copyright_years.append(year)
                                
                                # Only need one year reference
                                if copyright_years:
                                    break
                            
                            if copyright_years:
                                break
            
            # Identify license type from content if we have a license file
            if license_content:
                # Simple license detection based on text patterns
                if "mit license" in license_content or ("permission is hereby granted" in license_content and "without restriction" in license_content):
                    result["license_id"] = "mit"
                elif "apache license" in license_content and "version 2.0" in license_content:
                    result["license_id"] = "apache-2.0"
                elif "gnu general public license" in license_content:
                    if "version 3" in license_content:
                        result["license_id"] = "gpl-3.0"
                    elif "version 2" in license_content:
                        result["license_id"] = "gpl-2.0"
                elif "redistribution and use" in license_content:
                    if "neither the name of the copyright holder" in license_content:
                        result["license_id"] = "bsd-3-clause"
                    else:
                        result["license_id"] = "bsd-2-clause"
                elif "mozilla public license" in license_content and "version 2.0" in license_content:
                    result["license_id"] = "mpl-2.0"
        
            # If no year found in license files and not terminated early, check other common files
            if not copyright_years and not analysis_terminated_early:
                other_files = ["README.md", "NOTICE", "NOTICE.md"]
                for other_file in other_files:
                    # Check if we've exceeded the global timeout
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                        logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping other files analysis.")
                        analysis_terminated_early = True
                        result["early_termination"] = {
                            "reason": "global_timeout",
                            "elapsed_seconds": round(elapsed_time, 1),
                            "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                        }
                        break
                    
                    file_path = os.path.join(repo_path, other_file)
                    if os.path.isfile(file_path):
                        # Use safe_read_file with timeout
                        content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                        if content is not None:
                            files_checked += 1
                            
                            # Extract year information
                            for pattern in year_patterns:
                                matches = re.findall(pattern, content)
                                for match in matches:
                                    # Extract the last year mentioned
                                    year_text = match.strip()
                                    if "-" in year_text:
                                        year_parts = year_text.split("-")
                                        if len(year_parts) >= 2 and year_parts[1].strip().isdigit():
                                            year = int(year_parts[1].strip())
                                            copyright_years.append(year)
                                    elif year_text.isdigit():
                                        year = int(year_text)
                                        copyright_years.append(year)
                                    
                                    # Only need one year reference
                                    if copyright_years:
                                        break
                                
                                if copyright_years:
                                    break
        
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            result["errors"] = str(e)
    
    # Use API data as fallback if local analysis didn't identify a license
    if result["license_id"] == "unknown" and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            result["has_license"] = True
            result["license_id"] = license_info["spdx_id"].lower()
    
    # If we found years, determine if the license is up-to-date
    current_year = datetime.now().year
    result["current_year"] = current_year
    
    if copyright_years:
        # Use the most recent year found
        latest_year = max(copyright_years)
        result["last_update_year"] = latest_year
        result["copyright_years"] = copyright_years
        
        # License is considered outdated if the latest year is more than 2 years old
        if latest_year >= current_year - 1:
            result["license_updated"] = True
        else:
            result["license_outdated"] = True
    
    # Update result with findings
    result["license_files"] = found_license_files
    result["files_checked"] = files_checked
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate license update score (0-100 scale)
    score = 0
    
    # Points for having a license
    if result["has_license"]:
        score += 50
        
        # Points for license being updated
        if result["license_updated"]:
            score += 40
        elif result["last_update_year"]:
            # Partial points based on how recent the update was
            years_outdated = current_year - result["last_update_year"]
            if years_outdated <= 2:
                score += 30
            elif years_outdated <= 4:
                score += 20
            else:
                score += 10
        
        # Points for having multiple license files (better coverage)
        if len(found_license_files) > 1:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["update_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check license updates
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.debug(f"Starting license updates check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"license_updates_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached license updates check result for {repo_name}")
            return cached_result
        
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_license_updates(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"License updates check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("update_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.debug(f"✅ Completed license updates check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running license updates check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_license": False,
                "license_id": "unknown",
                "update_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }