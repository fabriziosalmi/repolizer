"""
Dependency License Check

Checks what dependencies the repository has and identifies their licenses.
"""
import os
import re
import logging
import time
import threading
import platform
import signal
import json
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
from contextlib import contextmanager

# Setup logging
logger = logging.getLogger(__name__)

# Add timeout handling like we've done for other checks
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

def check_dependency_licenses(repo_path: Optional[str] = None, repo_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Check the licenses of dependencies used by the project
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_dependencies": False,
        "dependency_count": 0,
        "dependencies_with_licenses": 0,
        "dependencies_without_licenses": 0,
        "license_compatibility_issues": 0,
        "dependency_files": [],
        "dependency_types": [],
        "problematic_dependencies": [],
        "dependency_license_score": 0,
        "early_termination": None,
        "errors": None
    }
    
    # Configuration constants
    FILE_READ_TIMEOUT = 2  # seconds per file read
    GLOBAL_ANALYSIS_TIMEOUT = 30  # 30 seconds total timeout for the entire analysis
    MAX_FILES_TO_CHECK = 100  # Limit number of files to check
    MAX_DIR_DEPTH = 5  # Maximum directory depth to traverse
    
    # Track analysis start time for global timeout
    start_time = datetime.now()
    analysis_terminated_early = False
    
    # Skip local analysis if no repo path provided
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Dependency patterns to look for by file type
    dependency_patterns = {
        "package.json": {
            "type": "npm",
            "parser": "json",
            "dependencies_field": ["dependencies", "devDependencies", "peerDependencies"]
        },
        "requirements.txt": {
            "type": "python",
            "parser": "line",
            "line_pattern": r"^([a-zA-Z0-9_.-]+).*$"
        },
        "Pipfile": {
            "type": "python",
            "parser": "toml",
            "dependencies_field": ["packages", "dev-packages"]
        },
        "Pipfile.lock": {
            "type": "python",
            "parser": "json",
            "dependencies_field": ["default", "develop"]
        },
        "pyproject.toml": {
            "type": "python",
            "parser": "toml",
            "dependencies_field": ["tool.poetry.dependencies", "tool.poetry.dev-dependencies"]
        },
        "go.mod": {
            "type": "go",
            "parser": "line",
            "line_pattern": r"^\s*([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\s+.*$"
        },
        "Gemfile": {
            "type": "ruby",
            "parser": "line",
            "line_pattern": r"^\s*gem\s+['\"]([a-zA-Z0-9_.-]+)['\"].*$"
        },
        "Cargo.toml": {
            "type": "rust",
            "parser": "toml",
            "dependencies_field": ["dependencies", "dev-dependencies"]
        },
        "composer.json": {
            "type": "php",
            "parser": "json",
            "dependencies_field": ["require", "require-dev"]
        },
        "pom.xml": {
            "type": "maven",
            "parser": "xml",
            "xpath": "/project/dependencies/dependency/artifactId"
        },
        "build.gradle": {
            "type": "gradle",
            "parser": "line",
            "line_pattern": r"^\s*implementation\s+['\"]([a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+).*['\"].*$"
        }
    }
    
    # License identification patterns
    license_patterns = {
        "MIT": r"mit license|mit|expat license",
        "Apache-2.0": r"apache license 2.0|apache-2.0|apache 2.0|apache2",
        "GPL-3.0": r"gnu general public license v3|gpl-3.0|gpl 3|gplv3",
        "GPL-2.0": r"gnu general public license v2|gpl-2.0|gpl 2|gplv2",
        "BSD-3-Clause": r"bsd 3-clause|bsd-3-clause|new bsd license|modified bsd license",
        "BSD-2-Clause": r"bsd 2-clause|bsd-2-clause|simplified bsd license|freebsd license",
        "ISC": r"isc license|isc",
        "LGPL-3.0": r"gnu lesser general public license v3|lgpl-3.0|lgpl 3|lgplv3",
        "LGPL-2.1": r"gnu lesser general public license v2.1|lgpl-2.1|lgpl 2.1|lgplv2.1",
        "MPL-2.0": r"mozilla public license 2.0|mpl-2.0|mpl 2.0",
        "Unlicense": r"unlicense|public domain",
        "WTFPL": r"do what the fuck you want|wtfpl",
        "CC0-1.0": r"creative commons zero|cc0|cc0-1.0",
        "Zlib": r"zlib license|zlib"
    }
    
    # Check repository for dependency files
    dependencies = []
    dependency_files_found = []
    
    try:
        # Limit directory traversal to prevent hanging
        files_checked = 0
        
        for root, dirs, files in os.walk(repo_path):
            # Check if we've exceeded the global timeout
            elapsed_time = (datetime.now() - start_time).total_seconds()
            if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping dependency file search.")
                analysis_terminated_early = True
                result["early_termination"] = {
                    "reason": "global_timeout",
                    "elapsed_seconds": round(elapsed_time, 1),
                    "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                }
                break
            
            # Limit directory depth
            rel_path = os.path.relpath(root, repo_path)
            depth = len(rel_path.split(os.sep)) if rel_path != '.' else 0
            
            if depth > MAX_DIR_DEPTH:
                dirs[:] = []  # Don't go deeper
                continue
            
            # Skip hidden directories and node_modules
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
            
            # Check for dependency files
            for file in files:
                # Check if we've reached the file limit
                if files_checked >= MAX_FILES_TO_CHECK:
                    logger.debug(f"Reached maximum file check limit ({MAX_FILES_TO_CHECK}). Limiting dependency file search.")
                    analysis_terminated_early = True
                    result["early_termination"] = {
                        "reason": "max_files_reached",
                        "limit": MAX_FILES_TO_CHECK
                    }
                    break
                
                if file in dependency_patterns:
                    file_path = os.path.join(root, file)
                    
                    # Process dependency file with timeout protection
                    logger.debug(f"Found dependency file: {file_path}")
                    dependency_files_found.append(os.path.relpath(file_path, repo_path))
                    
                    # Process dependencies based on file type
                    pattern = dependency_patterns[file]
                    dep_type = pattern["type"]
                    
                    if not dep_type in result["dependency_types"]:
                        result["dependency_types"].append(dep_type)
                    
                    # Read file with timeout protection
                    content = safe_read_file(file_path, timeout=FILE_READ_TIMEOUT)
                    if content is None:
                        logger.warning(f"Could not read dependency file: {file_path}")
                        continue
                    
                    # Parse dependencies based on file format
                    try:
                        with time_limit(FILE_READ_TIMEOUT):  # Timeout for parsing
                            if pattern["parser"] == "json":
                                data = json.loads(content)
                                for field in pattern["dependencies_field"]:
                                    # Handle nested fields
                                    if "." in field:
                                        parts = field.split(".")
                                        current = data
                                        valid = True
                                        for part in parts:
                                            if part in current:
                                                current = current[part]
                                            else:
                                                valid = False
                                                break
                                        if valid and isinstance(current, dict):
                                            for dep_name, version in current.items():
                                                dependencies.append({
                                                    "name": dep_name,
                                                    "type": dep_type,
                                                    "version": version if isinstance(version, str) else None,
                                                    "license": None  # Will try to identify later
                                                })
                                    elif field in data and isinstance(data[field], dict):
                                        for dep_name, version in data[field].items():
                                            dependencies.append({
                                                "name": dep_name,
                                                "type": dep_type,
                                                "version": version if isinstance(version, str) else None,
                                                "license": None  # Will try to identify later
                                            })
                            elif pattern["parser"] == "line":
                                for line in content.splitlines():
                                    line = line.strip()
                                    if line and not line.startswith("#"):
                                        if "line_pattern" in pattern:
                                            match = re.match(pattern["line_pattern"], line)
                                            if match:
                                                dep_name = match.group(1)
                                                dependencies.append({
                                                    "name": dep_name,
                                                    "type": dep_type,
                                                    "version": None,  # Would need additional parsing
                                                    "license": None
                                                })
                                        else:
                                            # Simple line format (e.g., requirements.txt)
                                            # Extract name (before any version specifier)
                                            dep_name = re.split(r'[<>=!~]', line)[0].strip()
                                            if dep_name:
                                                dependencies.append({
                                                    "name": dep_name,
                                                    "type": dep_type,
                                                    "version": None,
                                                    "license": None
                                                })
                    except TimeoutException:
                        logger.warning(f"Parsing dependency file timed out: {file_path}")
                    except Exception as e:
                        logger.error(f"Error parsing dependency file {file_path}: {e}")
                
                files_checked += 1
            
            # Break out of directory walk if we hit limits
            if files_checked >= MAX_FILES_TO_CHECK or analysis_terminated_early:
                break
        
        # Update result with findings
        result["has_dependencies"] = len(dependencies) > 0
        result["dependency_count"] = len(dependencies)
        result["dependency_files"] = dependency_files_found
        
        # Try to identify licenses for dependencies (mock implementation)
        # In a real implementation, this would query package registries
        dependencies_with_licenses = 0
        problematic_dependencies = []
        
        # Simple implementation using common license patterns
        for dep in dependencies:
            # Check if we've exceeded the global timeout
            elapsed_time = (datetime.now() - start_time).total_seconds()
            if elapsed_time > GLOBAL_ANALYSIS_TIMEOUT:
                logger.warning(f"Global analysis timeout reached after {elapsed_time:.1f} seconds. Stopping license identification.")
                analysis_terminated_early = True
                if "early_termination" not in result or result["early_termination"] is None:
                    result["early_termination"] = {
                        "reason": "global_timeout",
                        "elapsed_seconds": round(elapsed_time, 1),
                        "limit_seconds": GLOBAL_ANALYSIS_TIMEOUT
                    }
                break
            
            # Mock license identification - in a real implementation we would
            # query package registries or scan node_modules, etc.
            
            # For NPM packages, look in package-lock.json for more detailed info
            if dep["type"] == "npm" and os.path.exists(os.path.join(repo_path, "package-lock.json")):
                try:
                    with time_limit(FILE_READ_TIMEOUT):
                        with open(os.path.join(repo_path, "package-lock.json"), 'r', encoding='utf-8', errors='ignore') as f:
                            lock_data = json.loads(f.read())
                            if "dependencies" in lock_data and dep["name"] in lock_data["dependencies"]:
                                dep_info = lock_data["dependencies"][dep["name"]]
                                if "license" in dep_info:
                                    dep["license"] = dep_info["license"]
                                    dependencies_with_licenses += 1
                                    continue
                except TimeoutException:
                    logger.warning(f"Timeout reading package-lock.json")
                except Exception as e:
                    logger.error(f"Error reading package-lock.json: {e}")
            
            # Look for well-known packages
            known_licenses = {
                "react": "MIT",
                "lodash": "MIT",
                "express": "MIT",
                "moment": "MIT",
                "requests": "Apache-2.0",
                "numpy": "BSD-3-Clause",
                "pandas": "BSD-3-Clause",
                "django": "BSD-3-Clause",
                "flask": "BSD-3-Clause",
                "tensorflow": "Apache-2.0",
                "pytorch": "BSD-3-Clause",
                "jquery": "MIT",
                "bootstrap": "MIT",
                "rails": "MIT",
                "spring": "Apache-2.0",
                "dotenv": "BSD-2-Clause",
                "chalk": "MIT",
                "commander": "MIT",
                "axios": "MIT",
                "mocha": "MIT",
                "jest": "MIT",
                "eslint": "MIT"
            }
            
            # Check if this is a known package
            for known_name, known_license in known_licenses.items():
                if dep["name"].lower() == known_name.lower() or dep["name"].lower().startswith(f"{known_name}-"):
                    dep["license"] = known_license
                    dependencies_with_licenses += 1
                    break
            
            # If license still unknown, mark as problematic
            if dep["license"] is None:
                problematic_dependencies.append({
                    "name": dep["name"],
                    "type": dep["type"],
                    "reason": "unknown_license"
                })
        
        # Update result with license findings
        result["dependencies_with_licenses"] = dependencies_with_licenses
        result["dependencies_without_licenses"] = result["dependency_count"] - dependencies_with_licenses
        result["problematic_dependencies"] = problematic_dependencies
        
        # Clean up early_termination if not needed
        if "early_termination" in result and result["early_termination"] is None:
            result.pop("early_termination")
        if "errors" in result and result["errors"] is None:
            result.pop("errors")
        
        # Calculate score
        if result["dependency_count"] > 0:
            license_coverage_ratio = dependencies_with_licenses / result["dependency_count"]
            
            # Base score out of 100
            score = 50  # Start at 50
            
            # Add up to 40 points based on license coverage
            score += min(40, int(license_coverage_ratio * 40))
            
            # Add 10 points if all dependencies have licenses
            if license_coverage_ratio == 1.0:
                score += 10
            
            # Ensure score is within 0-100 range
            score = min(100, max(0, score))
            
            # Round and convert to integer if it's a whole number
            rounded_score = round(score, 1)
            result["dependency_license_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
        else:
            # No dependencies found, but that's not necessarily bad
            result["dependency_license_score"] = 80
    
    except Exception as e:
        logger.error(f"Error analyzing dependencies: {e}")
        result["errors"] = str(e)
        result["dependency_license_score"] = 0
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check dependency licenses
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    repo_name = repository.get('name', 'unknown')
    logger.debug(f"Starting dependency licenses check for repository: {repo_name}")
    
    try:
        # Check if we have a cached result
        cache_key = f"dependency_licenses_{repository.get('id', repo_name)}"
        cached_result = repository.get('_cache', {}).get(cache_key)
        
        if cached_result:
            logger.info(f"Using cached dependency licenses check result for {repo_name}")
            return cached_result
        
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check with timeout protection
        start_time = time.time()
        result = check_dependency_licenses(local_path, repository)
        elapsed = time.time() - start_time
        
        if elapsed > 5:  # Log if the check took more than 5 seconds
            logger.warning(f"Dependency licenses check for {repo_name} took {elapsed:.2f} seconds")
        
        # Prepare the final result
        final_result = {
            "status": "completed",
            "score": result.get("dependency_license_score", 0),
            "result": result,
            "errors": result.get("errors")
        }
        
        # Clean up None errors
        if final_result["errors"] is None:
            final_result.pop("errors", None)
        
        # Add to cache if available
        if '_cache' in repository:
            repository['_cache'][cache_key] = final_result
        
        logger.info(f"Completed dependency licenses check for {repo_name} with score: {final_result['score']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error running dependency licenses check for {repo_name}: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "has_dependencies": False,
                "dependency_count": 0,
                "dependency_license_score": 0,
                "errors": str(e)
            },
            "errors": str(e)
        }