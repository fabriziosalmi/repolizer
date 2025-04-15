"""
Third-Party Code Check

Checks if the repository properly handles and documents third-party code.
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

# Add timeout handling similar to the other checks
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

def check_third_party_code(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check for proper third-party code handling in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_third_party_code": False,
        "third_party_documented": False,
        "third_party_segregated": False,
        "third_party_licenses_included": False,
        "third_party_attribution": False,
        "has_vendor_directory": False,
        "has_external_directory": False,
        "has_third_party_directory": False,
        "has_third_party_notice": False,
        "files_checked": 0,
        "third_party_files": [],
        "third_party_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 30  # 30 seconds total timeout for the entire analysis
    MAX_DIRS_TO_CHECK = 100  # Limit the number of directories to scan
    
    # Track analysis start time for global timeout
    start_time = datetime.now()
    analysis_terminated_early = False
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # Try to use API data as fallback
        if repo_data and "dependencies" in repo_data:
            result["has_third_party_code"] = True
            # With API data only, we can't determine other attributes reliably
            result["third_party_score"] = 30  # Basic score for having dependencies
        
        return result
    
    # Files that might document third-party code
    documentation_files = [
        "THIRD_PARTY.md", "third_party.md", "THIRD_PARTY_LICENSES.md", "third_party_licenses.md",
        "NOTICE", "NOTICE.md", "ATTRIBUTION.md", "attribution.md", "VENDORS.md", "vendors.md",
        "LICENSE-THIRD-PARTY", "ThirdPartyNotices"
    ]
    
    # Directories that might contain third-party code
    third_party_dirs = [
        "vendor", "vendors", "third_party", "third-party", "external", "ext", "lib", "libs",
        "node_modules", "packages", "deps", "dependencies"
    ]
    
    # Perform local analysis with timeout protection
    files_checked = 0
    third_party_files = []
    dirs_checked = 0
    
    try:
        logger.debug(f"Analyzing repository at {repo_path} for third-party code")
        
        # Check for documentation files with timeout protection
        for doc_file in documentation_files:
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
            
            file_path = os.path.join(repo_path, doc_file)
            if os.path.isfile(file_path):
                files_checked += 1
                relative_path = os.path.relpath(file_path, repo_path)
                third_party_files.append(relative_path)
                
                # Mark as having third-party documentation
                result["third_party_documented"] = True
                result["has_third_party_code"] = True
                
                # Check content for attributions and licenses
                content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                if content is not None:
                    content = content.lower()  # Convert to lowercase for matching
                    
                    # Check for attribution
                    if "copyright" in content or "©" in content or "(c)" in content:
                        result["third_party_attribution"] = True
                    
                    # Check for license references
                    if "license" in content or "licence" in content or "permitted" in content:
                        result["third_party_licenses_included"] = True
                    
                    # If this is a NOTICE file, mark it
                    if "notice" in doc_file.lower():
                        result["has_third_party_notice"] = True
        
        # Check for third-party directories with timeout protection
        if not analysis_terminated_early:
            for tp_dir in third_party_dirs:
                # Check if we've exceeded the global timeout
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                    logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping directory analysis.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                    break
                
                dir_path = os.path.join(repo_path, tp_dir)
                if os.path.isdir(dir_path):
                    # Mark as having third-party code
                    result["has_third_party_code"] = True
                    result["third_party_segregated"] = True
                    
                    # Check specific directory types
                    if tp_dir in ["vendor", "vendors"]:
                        result["has_vendor_directory"] = True
                    elif tp_dir in ["third_party", "third-party"]:
                        result["has_third_party_directory"] = True
                    elif tp_dir in ["external", "ext"]:
                        result["has_external_directory"] = True
                    
                    # Check for LICENSE files inside these directories with limited traversal
                    license_files = 0
                    dirs_traversed = 0
                    
                    for root, _, files in os.walk(dir_path):
                        dirs_traversed += 1
                        dirs_checked += 1
                        
                        # Limit directory traversal to prevent hanging
                        if dirs_traversed > MAX_DIRS_TO_CHECK:
                            logger.warning(f"Reached maximum directory check limit ({MAX_DIRS_TO_CHECK}) for {tp_dir}. Limiting traversal.")
                            result["early_termination"] = {
                                "reason": "max_dirs_reached",
                                "limit": MAX_DIRS_TO_CHECK,
                                "details": f"Limited traversal of {tp_dir} directory"
                            }
                            break
                            
                        # Check if we've exceeded the global timeout
                        elapsed_time = (datetime.now() - start_time).total_seconds()
                        if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                            logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds during directory traversal.")
                            analysis_terminated_early = True
                            result["early_termination"] = {
                                "reason": "global_timeout",
                                "elapsed_seconds": round(elapsed_time, 1),
                                "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                            }
                            break
                            
                        for file in files:
                            if file.upper() in ["LICENSE", "LICENSE.TXT", "LICENSE.MD", "COPYING"]:
                                license_files += 1
                                break  # Only count one license file per subdirectory
                    
                    if license_files > 0:
                        result["third_party_licenses_included"] = True
        
        # Check for dependency files which indicate third-party code
        if not analysis_terminated_early:
            dependency_files = ["package.json", "requirements.txt", "Gemfile", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "composer.json"]
            for dep_file in dependency_files:
                # Check if we've exceeded the global timeout
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                    logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping dependency file analysis.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                    break
                
                file_path = os.path.join(repo_path, dep_file)
                if os.path.isfile(file_path):
                    files_checked += 1
                    result["has_third_party_code"] = True
                    
                    # Check package.json more thoroughly with timeout protection
                    if dep_file == "package.json":
                        try:
                            content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                            if content is not None:
                                data = json.loads(content)
                                if "dependencies" in data or "devDependencies" in data:
                                    result["has_third_party_code"] = True
                        except json.JSONDecodeError:
                            logger.warning(f"JSON decode error in {file_path}")
                        except Exception as e:
                            logger.warning(f"Error analyzing package.json: {e}")
                    
                    # Check if there's corresponding documentation in the same directory
                    if not result["third_party_documented"]:
                        dir_path = os.path.dirname(file_path)
                        for doc_file in ["THIRD_PARTY.md", "NOTICE.md", "ATTRIBUTION.md"]:
                            doc_path = os.path.join(dir_path, doc_file)
                            if os.path.isfile(doc_path):
                                result["third_party_documented"] = True
                                break
        
        # If we haven't found third-party directories, check README for mentions
        if not result["has_third_party_code"] and not analysis_terminated_early:
            readme_files = ["README.md", "README", "README.txt", "docs/README.md"]
            for readme in readme_files:
                # Check if we've exceeded the global timeout
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                    logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping README analysis.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                    break
                
                file_path = os.path.join(repo_path, readme)
                if os.path.isfile(file_path):
                    content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                    if content is not None:
                        content = content.lower()  # Convert to lowercase for matching
                        files_checked += 1
                        
                        # Check for third-party mentions with simpler approach
                        third_party_terms = [
                            "third party", "third-party", "external library", "external code",
                            "vendor library", "dependency", "dependencies", "packages", "modules"
                        ]
                        
                        for term in third_party_terms:
                            if term in content:
                                result["has_third_party_code"] = True
                                
                                # Check if there's a section about it - simplified regex approach
                                section_headers = [
                                    '## third party',
                                    '## third-party',
                                    '## external libraries',
                                    '## dependencies',
                                    '## vendor libraries'
                                ]
                                
                                for header in section_headers:
                                    if header in content:
                                        result["third_party_documented"] = True
                                        break
                                
                                break
    
    except Exception as e:
        logger.error(f"Error analyzing repository: {e}")
        result["errors"] = str(e)
    
    # Only use API data as fallback if local analysis didn't identify third-party code
    if not result["has_third_party_code"] and repo_data:
        if "dependencies" in repo_data and repo_data["dependencies"]:
            result["has_third_party_code"] = True
        elif "languages" in repo_data and len(repo_data["languages"]) > 0:
            # Most repositories with code have some dependencies, make an educated guess
            # based on the programming languages used
            high_dep_langs = ["javascript", "typescript", "java", "python", "ruby", "php", "c#"]
            for lang in high_dep_langs:
                if lang.lower() in [l.lower() for l in repo_data["languages"]]:
                    result["has_third_party_code"] = True
                    break
    
    # Update result with findings
    result["files_checked"] = files_checked
    result["third_party_files"] = third_party_files
    
    # Clean up early_termination if not needed
    if result.get("early_termination") is None:
        result.pop("early_termination", None)
    if result.get("errors") is None:
        result.pop("errors", None)
    
    # Calculate third-party code handling score (0-100 scale)
    score = 0
    
    if not result["has_third_party_code"]:
        # If no third-party code detected, give a neutral score
        score = 50
    else:
        # Base score for having third-party code
        score += 20
        
        # Points for documentation
        if result["third_party_documented"]:
            score += 25
        
        # Points for segregation
        if result["third_party_segregated"]:
            score += 20
        
        # Points for licenses
        if result["third_party_licenses_included"]:
            score += 20
        
        # Points for attribution
        if result["third_party_attribution"]:
            score += 15
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["third_party_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check third-party code handling
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.info(f"Starting third-party code check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"third_party_code_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached third-party code check result for {repo_name}")
            return cached_result
        
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_third_party_code(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"Third-party code check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("third_party_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.info(f"Completed third-party code check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running third-party code check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_third_party_code": False,
                "third_party_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }