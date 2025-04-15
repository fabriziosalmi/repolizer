"""
License Compliance Check

Checks if the repository complies with license requirements like displaying notices properly.
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

# Add timeout handling similar to the copyright_headers.py implementation
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

def safe_read_file(file_path, timeout=3, max_lines=None):
    """Safely read a file with timeout protection."""
    try:
        with time_limit(timeout):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if max_lines:
                    lines = []
                    for _ in range(max_lines):
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

def check_license_compliance(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check for license compliance in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "license_id": "unknown",
        "license_requirements_met": False,
        "compliance_issues": [],
        "notice_displayed": False,
        "license_text_complete": False,
        "license_text_modified": False,
        "files_checked": 0,
        "compliance_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 30  # 30 seconds total timeout for the entire analysis
    MAX_FILES_TO_CHECK = 20  # Limit the number of source files to check for notices
    MAX_FILE_SIZE = 100000  # 100KB
    
    # Files that might contain license information
    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
        ".github/LICENSE.md", "docs/LICENSE.md"
    ]
    
    # Requirements for common licenses
    license_requirements = {
        "mit": {
            "notice_required": True,
            "required_text": "permission is hereby granted, free of charge",
            "required_notice": "the above copyright notice and this permission notice shall be included"
        },
        "apache-2.0": {
            "notice_required": True,
            "required_text": "apache license, version 2.0",
            "required_notice": "you must give any other recipients of the work or derivative works a copy of this license"
        },
        "gpl-3.0": {
            "notice_required": True,
            "required_text": "gnu general public license",
            "required_notice": "this program is free software: you can redistribute it and/or modify"
        },
        "gpl-2.0": {
            "notice_required": True,
            "required_text": "gnu general public license version 2",
            "required_notice": "this program is distributed in the hope that it will be useful"
        },
        "bsd-3-clause": {
            "notice_required": True,
            "required_text": "redistribution and use",
            "required_notice": "redistributions of source code must retain the above copyright notice"
        },
        "bsd-2-clause": {
            "notice_required": True,
            "required_text": "redistribution and use",
            "required_notice": "redistributions of source code must retain the above copyright notice"
        },
        "mpl-2.0": {
            "notice_required": True,
            "required_text": "mozilla public license version 2.0",
            "required_notice": "this source code form is subject to the terms of the mozilla public license"
        }
    }
    
    files_checked = 0
    license_file_content = ""
    license_file_found = None
    
    # Track analysis start time for global timeout
    start_time = datetime.now()
    analysis_terminated_early = False
    
    # Check if we have a local repository path
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        # Skip local analysis, using API data later
    else:
        try:
            logger.debug(f"Analyzing repository at {repo_path} for license compliance")
            
            # Check license files to find main license file with timeout protection
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
                        content = content.lower()  # Convert to lowercase for matching
                        files_checked += 1
                        
                        # Store the first license file content we find
                        if not license_file_content:
                            license_file_content = content
                            license_file_found = os.path.relpath(file_path, repo_path)
                            result["has_license"] = True
            
            # If we found a license file, try to identify the license type from content
            if license_file_content:
                # Simple license detection based on text patterns
                if "mit license" in license_file_content or ("permission is hereby granted" in license_file_content and "without restriction" in license_file_content):
                    result["license_id"] = "mit"
                elif "apache license" in license_file_content and "version 2.0" in license_file_content:
                    result["license_id"] = "apache-2.0"
                elif "gnu general public license" in license_file_content:
                    if "version 3" in license_file_content:
                        result["license_id"] = "gpl-3.0"
                    elif "version 2" in license_file_content:
                        result["license_id"] = "gpl-2.0"
                elif "redistribution and use" in license_file_content:
                    if "neither the name of the copyright holder" in license_file_content:
                        result["license_id"] = "bsd-3-clause"
                    else:
                        result["license_id"] = "bsd-2-clause"
                elif "mozilla public license" in license_file_content and "version 2.0" in license_file_content:
                    result["license_id"] = "mpl-2.0"
                
                # Check compliance with license requirements if we know the license
                if result["license_id"] != "unknown" and result["license_id"] in license_requirements:
                    requirements = license_requirements[result["license_id"]]
                    
                    # Check if required text is present
                    if requirements["required_text"] in license_file_content:
                        result["license_text_complete"] = True
                    else:
                        result["compliance_issues"].append(f"License file doesn't contain required text: '{requirements['required_text']}'")
                    
                    # Check if license has been modified significantly
                    # This is a basic check - a real check would be more complex
                    if len(license_file_content) < 100:
                        result["license_text_modified"] = True
                        result["compliance_issues"].append("License text appears to be significantly shortened or modified")
                    
                    # Check if notice requirements are met
                    if requirements["notice_required"] and not analysis_terminated_early:
                        # Check for notices in source files (sample up to MAX_FILES_TO_CHECK files)
                        notice_present = False
                        source_extensions = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.php', '.rb']
                        files_with_notice = 0
                        files_without_notice = 0
                        
                        # Create a set of visited paths to avoid duplicates
                        visited_paths = set()
                        
                        for root, dirs, files in os.walk(repo_path):
                            # Check if we've exceeded the global timeout
                            elapsed_time = (datetime.now() - start_time).total_seconds()
                            if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                                logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping notice analysis.")
                                analysis_terminated_early = True
                                result["early_termination"] = {
                                    "reason": "global_timeout",
                                    "elapsed_seconds": round(elapsed_time, 1),
                                    "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                                }
                                break
                                
                            # Skip hidden directories and common non-source dirs
                            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                                      d not in ['node_modules', 'venv', 'dist', 'build', '.git', '.vscode']]
                            
                            # Safety limit on directory depth
                            rel_path = os.path.relpath(root, repo_path)
                            depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                            if depth > 5:  # Don't go too deep
                                dirs[:] = []
                                continue
                            
                            for file in files:
                                # Check if we've exceeded sample file limit
                                if files_with_notice + files_without_notice >= MAX_FILES_TO_CHECK:
                                    break
                                    
                                _, ext = os.path.splitext(file)
                                
                                # Only check source files
                                if ext.lower() in source_extensions:
                                    file_path = os.path.join(root, file)
                                    
                                    # Skip already visited paths
                                    if file_path in visited_paths:
                                        continue
                                    visited_paths.add(file_path)
                                    
                                    # Skip large files
                                    try:
                                        file_size = os.path.getsize(file_path)
                                        if file_size > MAX_FILE_SIZE:
                                            continue
                                        elif file_size == 0:  # Skip empty files
                                            continue
                                    except OSError:
                                        continue
                                    
                                    # Read file header with timeout
                                    header = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT, max_lines=30)
                                    if header is None:
                                        continue  # Skip on read failure or timeout
                                    
                                    header = header.lower()  # Convert to lowercase for matching
                                    
                                    # Look for license notices or copyright
                                    if requirements["required_notice"] in header or "copyright" in header or result["license_id"] in header:
                                        files_with_notice += 1
                                    else:
                                        files_without_notice += 1
                                    
                                    files_checked += 1
                            
                            # Break if we've checked enough files
                            if files_with_notice + files_without_notice >= MAX_FILES_TO_CHECK:
                                break
                        
                        # Consider notice requirement met if most checked files have notices
                        if files_with_notice > 0 and files_with_notice >= files_without_notice / 2:
                            notice_present = True
                            result["notice_displayed"] = True
                        
                        if not notice_present and files_with_notice + files_without_notice > 0:
                            result["compliance_issues"].append("License notice not properly displayed in source files")
                
                # Overall compliance determination
                if result["license_text_complete"] and (not license_requirements.get(result["license_id"], {}).get("notice_required", False) or result["notice_displayed"]):
                    result["license_requirements_met"] = True
        
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            result["errors"] = str(e)
    
    # Use API data as fallback if local analysis didn't identify a license
    if result["license_id"] == "unknown" and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            result["has_license"] = True
            result["license_id"] = license_info["spdx_id"].lower()
    
    # Update result with findings
    result["files_checked"] = files_checked
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate license compliance score (0-100 scale)
    score = 0
    
    # Points for having a license
    if result["has_license"]:
        score += 40
        
        # Points for known license
        if result["license_id"] != "unknown":
            score += 15
        
        # Points for license compliance
        if result["license_text_complete"]:
            score += 20
        
        if result["notice_displayed"]:
            score += 15
        
        # Deduct points for compliance issues
        if result["compliance_issues"]:
            issue_penalty = min(30, len(result["compliance_issues"]) * 10)
            score -= issue_penalty
        
        # Bonus for meeting all requirements
        if result["license_requirements_met"]:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["compliance_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check license requirements
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.info(f"Starting license compliance check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"license_compliance_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached license compliance check result for {repo_name}")
            return cached_result
        
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_license_compliance(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"License compliance check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("compliance_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.info(f"Completed license compliance check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running license compliance check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_license": False,
                "license_id": "unknown",
                "compliance_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }