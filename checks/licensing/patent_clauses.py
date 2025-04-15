"""
Patent Clauses Check

Checks if the repository's license includes appropriate patent clauses.
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

def safe_read_file(file_path, timeout=3):
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

# Licenses with explicit patent grants
LICENSES_WITH_PATENT_GRANTS = {
    "Apache-2.0": {
        "explicit_grant": True,
        "patent_text": "subject to the terms and conditions of this license, each contributor hereby grants to you a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable patent license"
    },
    "MPL-2.0": {
        "explicit_grant": True,
        "patent_text": "each contributor hereby grants you a world-wide, royalty-free, non-exclusive license under patents"
    },
    "GPL-3.0-only": {
        "explicit_grant": True,
        "patent_text": "each contributor grants you a non-exclusive, worldwide, royalty-free patent license"
    },
    "GPL-3.0-or-later": {
        "explicit_grant": True,
        "patent_text": "each contributor grants you a non-exclusive, worldwide, royalty-free patent license"
    },
    "EPL-2.0": {
        "explicit_grant": True,
        "patent_text": "subject to the terms of this license, each contributor grants you a non-exclusive, worldwide, royalty-free patent license"
    },
    "BSL-1.0": {
        "explicit_grant": True,
        "patent_text": "the copyright holders and contributors grant you a worldwide, royalty-free, non-exclusive license under patent claims"
    }
}

# Licenses without explicit patent grants
LICENSES_WITHOUT_PATENT_GRANTS = {
    "MIT": {
        "explicit_grant": False,
        "patent_risk": "moderate",
        "note": "Does not explicitly address patents, but may include implied license."
    },
    "BSD-3-Clause": {
        "explicit_grant": False,
        "patent_risk": "moderate",
        "note": "Does not explicitly address patents, but may include implied license."
    },
    "BSD-2-Clause": {
        "explicit_grant": False,
        "patent_risk": "moderate",
        "note": "Does not explicitly address patents, but may include implied license."
    },
    "GPL-2.0-only": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "No explicit patent grant, may have compatibility issues with patents."
    },
    "GPL-2.0-or-later": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "No explicit patent grant, may have compatibility issues with patents."
    },
    "Unlicense": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "Does not address patents at all."
    },
    "CC0-1.0": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "Explicitly disclaims patent license in some jurisdictions."
    }
}

def check_patent_clauses(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check for patent clauses in the repository's license
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "license_id": "unknown",
        "has_patent_clause": False,
        "patent_clause_type": "none",  # none, explicit, implied
        "patent_risk_level": "unknown",  # low, moderate, high
        "custom_patent_clause": False,
        "has_patent_file": False,
        "patent_files": [],
        "license_files_checked": [],
        "files_checked": 0,
        "patent_clause_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 30  # 30 seconds total timeout for the entire analysis
    
    # Files to check for patent information
    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
        ".github/LICENSE.md", "docs/LICENSE.md"
    ]
    
    # Files specifically for patents
    patent_files = [
        "PATENTS", "PATENTS.md", "PATENTS.txt", "patent_grant.md", "patent_grant.txt",
        "PATENT_LICENSE", "PATENT_LICENSE.md", "PATENT_LICENSE.txt"
    ]
    
    # Patent-related terms to look for
    patent_terms = [
        "patent", "invention", "intellectual property", "ip rights",
        "patent license", "patent grant", "patent infringement", "patent claim"
    ]
    
    files_checked = 0
    license_files_checked = []
    found_patent_files = []
    has_custom_patent_text = False
    license_content = ""
    detected_license_id = "unknown"
    
    # Track analysis start time for global timeout
    start_time = datetime.now()
    analysis_terminated_early = False
    
    # First check if we have a local repository path
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        # Skip local analysis, using API data later
    else:
        try:
            logger.debug(f"Analyzing repository at {repo_path} for patent clauses")
            
            # First check specific patent files with timeout protection
            for pat_file in patent_files:
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
                
                file_path = os.path.join(repo_path, pat_file)
                if os.path.isfile(file_path):
                    content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                    if content is not None:
                        content = content.lower()  # Convert to lowercase for case-insensitive matching
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        found_patent_files.append(relative_path)
                        
                        # If we find a PATENTS file, mark it
                        result["has_patent_file"] = True
                        result["has_patent_clause"] = True
                        result["patent_clause_type"] = "explicit"
                        result["patent_risk_level"] = "low"
                        result["custom_patent_clause"] = True
            
            # If early termination occurred, skip the rest of the file checks
            if analysis_terminated_early:
                logger.warning("Analysis terminated early during patent file checks")
            else:
                # Next, check license files for license identification and patent clauses
                for lic_file in license_files:
                    # Check global timeout again
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
                        content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                        if content is not None:
                            content = content.lower()  # Convert to lowercase for matching
                            files_checked += 1
                            relative_path = os.path.relpath(file_path, repo_path)
                            license_files_checked.append(relative_path)
                            
                            # Store license content for later analysis
                            if not license_content:
                                license_content = content
                                result["has_license"] = True
                                
                                # Try to identify the license type from content - simplified regex approach
                                if "apache license" in content and "version 2.0" in content:
                                    detected_license_id = "Apache-2.0"
                                elif "mozilla public license" in content and "version 2.0" in content:
                                    detected_license_id = "MPL-2.0"
                                elif "gnu general public license" in content:
                                    if "version 3" in content:
                                        if "or any later version" in content or "or (at your option) any later version" in content:
                                            detected_license_id = "GPL-3.0-or-later"
                                        else:
                                            detected_license_id = "GPL-3.0-only"
                                    elif "version 2" in content:
                                        if "or any later version" in content or "or (at your option) any later version" in content:
                                            detected_license_id = "GPL-2.0-or-later"
                                        else:
                                            detected_license_id = "GPL-2.0-only"
                                elif "mit license" in content or ("permission is hereby granted" in content and "without restriction" in content):
                                    detected_license_id = "MIT"
                                elif "redistribution and use" in content:
                                    if "neither the name of the copyright holder" in content:
                                        detected_license_id = "BSD-3-Clause"
                                    else:
                                        detected_license_id = "BSD-2-Clause"
                                elif "boost software license" in content:
                                    detected_license_id = "BSL-1.0"
                                elif "eclipse public license" in content and "version 2.0" in content:
                                    detected_license_id = "EPL-2.0"
                                
                                # Set the detected license
                                if detected_license_id != "unknown":
                                    result["license_id"] = detected_license_id
                            
                            # Check if license has known patent grant based on identified license
                            if detected_license_id in LICENSES_WITH_PATENT_GRANTS:
                                patent_text = LICENSES_WITH_PATENT_GRANTS[detected_license_id]["patent_text"].lower()
                                # Use a simple contains check rather than expensive regex for performance
                                if patent_text in content:
                                    result["has_patent_clause"] = True
                                    result["patent_clause_type"] = "explicit"
                                    result["patent_risk_level"] = "low"
                            elif detected_license_id in LICENSES_WITHOUT_PATENT_GRANTS:
                                license_data = LICENSES_WITHOUT_PATENT_GRANTS[detected_license_id]
                                result["patent_clause_type"] = "implied" if license_data["patent_risk"] == "moderate" else "none"
                                result["patent_risk_level"] = license_data["patent_risk"]
                            
                            # If not found with specific text, check for general patent terms
                            # Use a more efficient method that doesn't rely on expensive regex searches
                            if not result["has_patent_clause"]:
                                for term in patent_terms:
                                    if term in content:
                                        # Check if it looks like a patent grant with simpler checks
                                        # Look for terms near each other rather than using regex context
                                        if ("grant" in content or "license" in content) and \
                                           ("right" in content or "permission" in content):
                                            result["has_patent_clause"] = True
                                            result["patent_clause_type"] = "explicit"
                                            result["patent_risk_level"] = "low"
                                            result["custom_patent_clause"] = True
                                            break
                                
                                # Break out of the term loop if we found a patent clause
                                if result["has_patent_clause"]:
                                    break
        
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            result["errors"] = str(e)
    
    # Use API data only as fallback if local analysis didn't identify a license
    if result["license_id"] == "unknown" and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            spdx_id = license_info["spdx_id"]
            result["has_license"] = True
            result["license_id"] = spdx_id
            
            # Check if license has known patent grant
            if spdx_id in LICENSES_WITH_PATENT_GRANTS:
                result["has_patent_clause"] = True
                result["patent_clause_type"] = "explicit"
                result["patent_risk_level"] = "low"
            elif spdx_id in LICENSES_WITHOUT_PATENT_GRANTS:
                license_data = LICENSES_WITHOUT_PATENT_GRANTS[spdx_id]
                result["patent_clause_type"] = "implied" if license_data["patent_risk"] == "moderate" else "none"
                result["patent_risk_level"] = license_data["patent_risk"]
    
    # Update result with findings
    result["patent_files"] = found_patent_files
    result["license_files_checked"] = license_files_checked
    result["files_checked"] = files_checked
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate patent clause score (0-100 scale)
    score = 0
    
    # Base score based on license existence
    if result["has_license"]:
        score += 30
        
        # Points for having a patent clause
        if result["has_patent_clause"]:
            if result["patent_clause_type"] == "explicit":
                score += 50
            elif result["patent_clause_type"] == "implied":
                score += 20
            
            # Bonus for having a dedicated patent file
            if result["has_patent_file"]:
                score += 20
            
            # Adjust based on risk level
            if result["patent_risk_level"] == "low":
                # Already rewarded with above points
                pass
            elif result["patent_risk_level"] == "moderate":
                score -= 10
            elif result["patent_risk_level"] == "high":
                score -= 30
        else:
            # No patent clause is a risk
            score -= 20
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["patent_clause_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify patent clauses
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.info(f"Starting patent clauses check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"patent_clauses_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached patent clauses check result for {repo_name}")
            return cached_result
        
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_patent_clauses(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"Patent clauses check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("patent_clause_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.info(f"Completed patent clauses check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running patent clauses check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_license": False,
                "license_id": "unknown",
                "patent_clause_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }