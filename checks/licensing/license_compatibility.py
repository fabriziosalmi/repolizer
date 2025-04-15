"""
License Compatibility Check

Checks if the repository's licenses are compatible with each other and with dependencies.
"""
import os
import re
import logging
import time
import platform
import threading
import signal
import json
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

# Common licenses and their compatibility matrix
# True means compatible, False means incompatible
# This is a simplified version and not legal advice
LICENSE_COMPATIBILITY = {
    "mit": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-2.0": True, "gpl-3.0": True, "lgpl-2.1": True, "lgpl-3.0": True,
        "mpl-2.0": True, "unlicense": True, "isc": True
    },
    "apache-2.0": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-3.0": True, "lgpl-3.0": True, "mpl-2.0": True, "unlicense": False,
        "gpl-2.0": False, "lgpl-2.1": False, "isc": True
    },
    "gpl-3.0": {
        "mit": False, "apache-2.0": False, "bsd-2-clause": False, "bsd-3-clause": False,
        "gpl-2.0": False, "gpl-3.0": True, "lgpl-2.1": False, "lgpl-3.0": False,
        "mpl-2.0": False, "unlicense": False, "isc": False
    },
    "gpl-2.0": {
        "mit": False, "apache-2.0": False, "bsd-2-clause": False, "bsd-3-clause": False,
        "gpl-2.0": True, "gpl-3.0": False, "lgpl-2.1": False, "lgpl-3.0": False,
        "mpl-2.0": False, "unlicense": False, "isc": False
    },
    "lgpl-3.0": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-2.0": False, "gpl-3.0": True, "lgpl-2.1": True, "lgpl-3.0": True,
        "mpl-2.0": True, "unlicense": False, "isc": True
    },
    "mpl-2.0": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-2.0": False, "gpl-3.0": True, "lgpl-2.1": True, "lgpl-3.0": True,
        "mpl-2.0": True, "unlicense": False, "isc": True
    }
}

# License SPDX identifiers for detection
LICENSE_IDENTIFIERS = {
    "mit": ["mit license", "mit", "expat license"],
    "apache-2.0": ["apache license 2.0", "apache-2.0", "apache license, version 2.0", "apache 2.0"],
    "gpl-3.0": ["gnu general public license v3.0", "gpl-3.0", "gpl 3", "gplv3"],
    "gpl-2.0": ["gnu general public license v2.0", "gpl-2.0", "gpl 2", "gplv2"],
    "lgpl-3.0": ["gnu lesser general public license v3.0", "lgpl-3.0", "lgpl 3", "lgplv3"],
    "lgpl-2.1": ["gnu lesser general public license v2.1", "lgpl-2.1", "lgpl 2.1", "lgplv2.1"],
    "bsd-3-clause": ["bsd 3-clause", "bsd-3-clause", "revised bsd license"],
    "bsd-2-clause": ["bsd 2-clause", "bsd-2-clause", "simplified bsd license"],
    "mpl-2.0": ["mozilla public license 2.0", "mpl-2.0", "mpl 2.0"],
    "unlicense": ["unlicense", "public domain"],
    "isc": ["isc license", "isc"]
}

def detect_license_from_text(license_text: str) -> str:
    """
    Detect license type from the license text
    
    Args:
        license_text: The content of a license file
        
    Returns:
        The identified license SPDX ID or "unknown"
    """
    if not license_text:
        return "unknown"
    
    license_text = license_text.lower()
    
    for license_id, keywords in LICENSE_IDENTIFIERS.items():
        for keyword in keywords:
            if keyword in license_text:
                # Additional check for more accuracy
                if license_id == "mit" and "permission is hereby granted" in license_text and "without restriction" in license_text:
                    return "mit"
                elif license_id.startswith("gpl") and "gnu general public license" in license_text:
                    if "version 3" in license_text or "v3.0" in license_text:
                        return "gpl-3.0"
                    elif "version 2" in license_text or "v2.0" in license_text:
                        return "gpl-2.0"
                elif license_id.startswith("apache") and "apache license" in license_text and ("2.0" in license_text or "version 2.0" in license_text):
                    return "apache-2.0"
                elif license_id.startswith("bsd") and "redistribution and use" in license_text:
                    if "neither the name of the copyright holder" in license_text:
                        return "bsd-3-clause"
                    else:
                        return "bsd-2-clause"
                elif license_id == "mpl-2.0" and "mozilla public license" in license_text and "version 2.0" in license_text:
                    return "mpl-2.0"
                
    return "unknown"

def is_compatible(primary_license: str, secondary_license: str) -> bool:
    """
    Check if two licenses are compatible
    
    Args:
        primary_license: Main license SPDX ID
        secondary_license: Secondary license SPDX ID
        
    Returns:
        True if licenses are compatible, False otherwise
    """
    if primary_license == "unknown" or secondary_license == "unknown":
        return False
    
    if primary_license not in LICENSE_COMPATIBILITY or secondary_license not in LICENSE_COMPATIBILITY.get(primary_license, {}):
        return False
    
    return LICENSE_COMPATIBILITY[primary_license][secondary_license]

def check_package_json_dependencies(repo_path: str, timeout: int = 2) -> List[str]:
    """
    Extract licenses from NPM dependencies in package.json
    
    Args:
        repo_path: Path to the repository
        timeout: Timeout in seconds for file operations
        
    Returns:
        List of dependency licenses found
    """
    dependency_licenses = []
    package_json_path = os.path.join(repo_path, "package.json")
    
    if os.path.exists(package_json_path):
        try:
            content = safe_read_file(package_json_path, timeout=timeout)
            if content is None:
                return dependency_licenses
                
            package_data = json.loads(content)
                
            # Check license field if it exists
            if "license" in package_data:
                license_info = package_data["license"]
                if isinstance(license_info, str):
                    dependency_licenses.append(license_info.lower())
                elif isinstance(license_info, dict) and "type" in license_info:
                    dependency_licenses.append(license_info["type"].lower())
            
            # Sometimes npm projects list licenses of dependencies
            if "dependencies" in package_data:
                # To properly check this, we would need to analyze node_modules
                # This is a placeholder for more comprehensive checking
                pass
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in package.json at {package_json_path}")
        except Exception as e:
            logger.error(f"Error reading package.json: {e}")
    
    return dependency_licenses

def check_requirements_txt_dependencies(repo_path: str, timeout: int = 2) -> List[str]:
    """
    Extract licenses from Python requirements.txt
    Note: This is a simplified implementation as requirements.txt doesn't contain license info
    
    Args:
        repo_path: Path to the repository
        timeout: Timeout in seconds for file operations
        
    Returns:
        List of dependency licenses found (empty as this requires external API calls)
    """
    # In a real implementation, this would query PyPI or another source for license info
    return []

def check_license_compatibility(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check license compatibility in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "main_license": "unknown",
        "other_licenses": [],
        "dependency_licenses": [],
        "compatible_licenses": True,
        "compatibility_issues": [],
        "license_files": [],
        "files_checked": 0,
        "compatibility_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 20  # 20 seconds total timeout for the entire analysis
    
    # First check if repository is available locally for more accurate analysis
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        # Skip local analysis, use API data later
    else:
        try:
            logger.debug(f"Analyzing local repository at {repo_path} for license compatibility")
            
            # Track analysis start time for global timeout
            start_time = datetime.now()
            analysis_terminated_early = False
            
            # Files that might contain license information
            license_files = [
                "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
                "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
                ".github/LICENSE.md", "docs/LICENSE.md"
            ]
            
            files_checked = 0
            found_license_files = []
            licenses_detected = []
            
            # Check license files with timeout protection
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
                        
                        # Detect license type
                        license_type = detect_license_from_text(content)
                        if license_type != "unknown":
                            licenses_detected.append(license_type)
                            result["has_license"] = True
            
            # If multiple licenses detected, assume first one is main and others are additional
            if licenses_detected:
                result["main_license"] = licenses_detected[0]
                
                # Add other detected licenses to other_licenses list
                for license_type in licenses_detected[1:]:
                    if license_type not in result["other_licenses"]:
                        result["other_licenses"].append(license_type)
            
            # Check for dependency licenses if we haven't terminated early
            if not analysis_terminated_early:
                # Check if we've exceeded the global timeout
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                    logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Skipping dependency analysis.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                else:
                    # Check for NPM dependencies
                    npm_licenses = check_package_json_dependencies(repo_path, timeout=FILE_READ_TIMEOUT)
                    if npm_licenses:
                        result["dependency_licenses"].extend(npm_licenses)
                    
                    # Check for Python dependencies
                    python_licenses = check_requirements_txt_dependencies(repo_path, timeout=FILE_READ_TIMEOUT)
                    if python_licenses:
                        result["dependency_licenses"].extend(python_licenses)
                    
                    # Update result with findings
                    result["license_files"] = found_license_files
                    result["files_checked"] = files_checked
        
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}")
            result["errors"] = str(e)
    
    # Only use API data if we couldn't determine license from local analysis
    if result["main_license"] == "unknown" and repo_data and "license" in repo_data:
        logger.debug("Using API data for license compatibility check")
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            result["has_license"] = True
            result["main_license"] = license_info["spdx_id"].lower()
    
    # Check compatibility between main license and other licenses
    if result["main_license"] != "unknown":
        for other_license in result["other_licenses"] + result["dependency_licenses"]:
            if not is_compatible(result["main_license"], other_license):
                result["compatible_licenses"] = False
                result["compatibility_issues"].append(f"{result['main_license']} is not compatible with {other_license}")
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate license compatibility score (0-100 scale)
    score = 0
    
    # Points for having a license
    if result["has_license"]:
        score += 50
        
        # Points for known license
        if result["main_license"] != "unknown":
            score += 20
        
        # Points for license compatibility
        if result["compatible_licenses"]:
            score += 30
        else:
            # Deduct points for each compatibility issue
            deduction = min(30, len(result["compatibility_issues"]) * 10)
            score -= deduction
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["compatibility_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify license compatibility
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.debug(f"Starting license compatibility check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"license_compatibility_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached license compatibility check result for {repo_name}")
            return cached_result
        
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_license_compatibility(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"License compatibility check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("compatibility_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.debug(f"✅ Completed license compatibility check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running license compatibility check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_license": False,
                "main_license": "unknown",
                "compatibility_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }