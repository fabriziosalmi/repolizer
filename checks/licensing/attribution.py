"""
Attribution Check

Checks if the repository properly attributes third-party code, libraries, and content.
"""
import os
import re
import logging
import time
import platform
import threading
import signal
from typing import Dict, Any, List, Set, Optional
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

def safe_read_file(file_path, timeout=2, read_bytes=None):
    """Safely read a file with timeout protection."""
    try:
        with time_limit(timeout):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if read_bytes is not None:
                    return f.read(read_bytes)
                else:
                    return f.read()
    except TimeoutException:
        logger.warning(f"Timeout reading file: {file_path}")
        return None
    except Exception as e:
        logger.warning(f"Error reading file {file_path}: {e}")
        return None

def check_attribution(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check for proper attribution in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_attribution": False,
        "attribution_files": [],
        "attribution_types": [],
        "has_third_party_notices": False,
        "has_license_attributions": False,
        "has_contributor_attributions": False,
        "files_checked": 0,
        "attribution_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 20  # 20 seconds total timeout for the entire analysis
    MAX_SOURCE_FILES_TO_CHECK = 10  # Limit source file checking
    MAX_SOURCE_READ_SIZE = 2000  # Bytes to read from source files
    
    # First check if repository is available locally for accurate analysis
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        # Skip local analysis, use API data later
    else:
        try:
            logger.info(f"Analyzing repository at {repo_path} for attribution information")
            
            # Track analysis start time for global timeout
            start_time = datetime.now()
            analysis_terminated_early = False
            
            # Files that might contain attribution information
            attribution_files = [
                "ATTRIBUTION.md", "attribution.md", "NOTICE", "NOTICE.md", "NOTICE.txt",
                "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.txt", "ThirdPartyNotices",
                "CONTRIBUTORS.md", "CREDITS.md", "credits.md", "ACKNOWLEDGMENTS.md", 
                "acknowledgments.md", "AUTHORS.md", "authors.md",
                "LICENSE", "LICENSE.md", "LICENSE.txt",
                ".github/ATTRIBUTION.md", ".github/NOTICE.md",
                "docs/attribution.md", "docs/credits.md", "legal/NOTICE"
            ]
            
            # Attribution terms to look for
            attribution_terms = {
                "third_party": ["third party", "third-party", "3rd party", "external code", "external library"],
                "derived_work": ["derived from", "based on", "adapted from", "inspired by"],
                "copyright": ["copyright", "©", "(c)", "all rights reserved"],
                "license_attribution": ["license", "under the terms", "permission is granted", "permitted by"],
                "contributor": ["contributor", "author", "maintainer", "thanks to", "credit to"]
            }
            
            files_checked = 0
            attribution_types_found = set()
            found_attribution_files = []
            
            # Check specific attribution files with timeout protection
            for attr_file in attribution_files:
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
                
                file_path = os.path.join(repo_path, attr_file)
                if os.path.isfile(file_path):
                    # Use safe_read_file with timeout
                    content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                    if content is not None:
                        content = content.lower()  # Convert to lowercase for easier matching
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        
                        # Check for attribution mentions
                        has_attribution_content = False
                        
                        # Look for attribution types
                        for attr_type, terms in attribution_terms.items():
                            for term in terms:
                                if term in content:
                                    attribution_types_found.add(attr_type)
                                    has_attribution_content = True
                                    
                                    # Update specific attribution type flags
                                    if attr_type == "third_party":
                                        result["has_third_party_notices"] = True
                                    elif attr_type == "license_attribution":
                                        result["has_license_attributions"] = True
                                    elif attr_type == "contributor":
                                        result["has_contributor_attributions"] = True
                        
                        if has_attribution_content:
                            result["has_attribution"] = True
                            found_attribution_files.append(relative_path)
            
            # Next check README and other files if no attribution found yet and not terminated early
            if not result["has_attribution"] and not analysis_terminated_early:
                additional_files = [
                    "README.md", "docs/README.md", 
                    "CONTRIBUTING.md", ".github/CONTRIBUTING.md"
                ]
                
                for add_file in additional_files:
                    # Check if we've exceeded the global timeout
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                        logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping additional files analysis.")
                        analysis_terminated_early = True
                        result["early_termination"] = {
                            "reason": "global_timeout",
                            "elapsed_seconds": round(elapsed_time, 1),
                            "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                        }
                        break
                    
                    file_path = os.path.join(repo_path, add_file)
                    if os.path.isfile(file_path):
                        # Use safe_read_file with timeout
                        content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                        if content is not None:
                            content = content.lower()  # Convert to lowercase for matching
                            files_checked += 1
                            relative_path = os.path.relpath(file_path, repo_path)
                            
                            # Check for attribution sections using simpler string matching
                            section_headers = [
                                '## attribution',
                                '## credits',
                                '## acknowledgments',
                                '## third party',
                                '## third-party',
                                '## licenses',
                                '## authors',
                                '## contributors'
                            ]
                            
                            has_attribution_section = False
                            for header in section_headers:
                                if header in content:
                                    has_attribution_section = True
                                    break
                            
                            if has_attribution_section:
                                # If there's a relevant section, check its content for attribution terms
                                for attr_type, terms in attribution_terms.items():
                                    for term in terms:
                                        if term in content:
                                            attribution_types_found.add(attr_type)
                                            
                                            # Update specific attribution type flags
                                            if attr_type == "third_party":
                                                result["has_third_party_notices"] = True
                                            elif attr_type == "license_attribution":
                                                result["has_license_attributions"] = True
                                            elif attr_type == "contributor":
                                                result["has_contributor_attributions"] = True
                                
                                # If we found at least one attribution type, mark as having attribution
                                if attribution_types_found:
                                    result["has_attribution"] = True
                                    found_attribution_files.append(relative_path)
            
            # Finally, check actual source code for copyright headers or attribution
            # Skip if we've already found solid attribution elsewhere or terminated early
            if len(attribution_types_found) < 2 and not analysis_terminated_early:
                source_extensions = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.php', '.rb']
                source_files_checked = 0
                source_files_with_attribution = 0
                
                # Check up to MAX_SOURCE_FILES_TO_CHECK source files
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
                    
                    # Skip .git and other hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    # Limit depth for large repositories
                    rel_path = os.path.relpath(root, repo_path)
                    depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
                    if depth > 3:  # Don't go too deep
                        dirs[:] = []
                        continue
                    
                    for file in files:
                        _, ext = os.path.splitext(file)
                        if ext.lower() in source_extensions and source_files_checked < MAX_SOURCE_FILES_TO_CHECK:
                            source_files_checked += 1
                            file_path = os.path.join(root, file)
                            
                            # Read only the beginning of the file with timeout
                            content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT, read_bytes=MAX_SOURCE_READ_SIZE)
                            if content is not None:
                                content = content.lower()  # Convert to lowercase for matching
                                
                                # Look for copyright notices or attribution
                                for term in attribution_terms["copyright"] + attribution_terms["license_attribution"]:
                                    if term in content:
                                        source_files_with_attribution += 1
                                        attribution_types_found.add("copyright")
                                        result["has_license_attributions"] = True
                                        break
                    
                    # Stop if we've checked enough files
                    if source_files_checked >= MAX_SOURCE_FILES_TO_CHECK:
                        break
                
                # If at least 25% of checked source files have attribution, consider it present
                if source_files_checked > 0 and source_files_with_attribution / source_files_checked >= 0.25:
                    result["has_attribution"] = True
            
            # Update result with findings
            result["attribution_files"] = found_attribution_files
            result["attribution_types"] = sorted(list(attribution_types_found))
            result["files_checked"] = files_checked
        
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            result["errors"] = str(e)
    
    # Only use API data if local analysis wasn't possible or didn't find attribution
    if not result["has_attribution"] and repo_data and 'attribution' in repo_data:
        logger.info("Using API data for attribution check.")
        
        attribution_data = repo_data.get('attribution', {})
        
        # Update result with attribution info from API
        result["has_attribution"] = attribution_data.get('has_attribution', False)
        result["attribution_files"] = attribution_data.get('files', [])
        result["attribution_types"] = attribution_data.get('types', [])
        result["has_third_party_notices"] = attribution_data.get('third_party_notices', False)
        result["has_license_attributions"] = attribution_data.get('license_attributions', False)
        result["has_contributor_attributions"] = attribution_data.get('contributor_attributions', False)
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate attribution score (0-100 scale)
    score = 0
    
    # Points for having attribution
    if result["has_attribution"]:
        score += 40
        
        # Points for specific attribution files
        if any("NOTICE" in file.upper() for file in result["attribution_files"]) or any("ATTRIBUTION" in file.upper() for file in result["attribution_files"]):
            score += 20
        elif any("LICENSE" in file.upper() for file in result["attribution_files"]) or any("CONTRIBUTORS" in file.upper() for file in result["attribution_files"]):
            score += 10
        
        # Points for attribution variety (types)
        variety_points = min(30, len(result["attribution_types"]) * 10)
        score += variety_points
        
        # Points for specific high-value attribution types
        if result["has_third_party_notices"]:
            score += 10
        
        if result["has_license_attributions"]:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["attribution_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check proper attribution
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.info(f"Starting attribution check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"attribution_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached attribution check result for {repo_name}")
            return cached_result
        
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_attribution(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"Attribution check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("attribution_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.info(f"Completed attribution check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running attribution check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_attribution": False,
                "attribution_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }