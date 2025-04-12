"""
Dependency Management Check

Checks if the repository manages dependencies effectively.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Tuple
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_dependency_management(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check dependency management in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_dependency_management": False,
        "dependency_tool": None,
        "has_version_pinning": False,
        "version_pinning_type": None,  # exact, range, unpinned
        "has_lockfile": False,
        "has_dependency_updates": False,
        "dependency_count": 0,
        "direct_dependencies": 0,
        "dev_dependencies": 0,
        "outdated_dependencies": 0,
        "dependency_files": [],
        "files_checked": 0,
        "dependency_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # This check relies entirely on local filesystem analysis
    # Repo data is not used for dependency management check
    
    # Files and tools for dependency management
    dependency_tools = {
        "npm": ["package.json", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json"],
        "pip": ["requirements.txt", "Pipfile", "Pipfile.lock", "pyproject.toml", "poetry.lock", "setup.py"],
        "maven": ["pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile"],
        "bundler": ["Gemfile", "Gemfile.lock"],
        "composer": ["composer.json", "composer.lock"],
        "cargo": ["Cargo.toml", "Cargo.lock"],
        "go": ["go.mod", "go.sum"],
        "nuget": ["packages.config", "*.csproj", "*.vbproj", "paket.dependencies", "paket.lock"]
    }
    
    # Lockfiles for dependency tools
    lockfiles = {
        "npm": ["package-lock.json", "yarn.lock", "npm-shrinkwrap.json"],
        "pip": ["Pipfile.lock", "poetry.lock"],
        "maven": ["gradle.lockfile"],
        "bundler": ["Gemfile.lock"],
        "composer": ["composer.lock"],
        "cargo": ["Cargo.lock"],
        "go": ["go.sum"],
        "nuget": ["paket.lock"]
    }
    
    # Files to check for dependency updates
    update_files = [
        ".github/dependabot.yml", ".github/dependabot.yaml",
        ".github/workflows/dependency-update.yml", 
        ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml",
        "renovate.json", ".renovaterc", ".renovaterc.json"
    ]
    
    files_checked = 0
    found_dependency_files = []
    detected_tool = None
    has_lockfile = False
    has_version_pinning = False
    pinning_type = None
    direct_deps = 0
    dev_deps = 0
    outdated_deps = 0
    
    # Check for dependency management files
    for tool, file_patterns in dependency_tools.items():
        for pattern in file_patterns:
            # Handle glob patterns
            if "*" in pattern:
                # Simple glob handling for extension matching
                extension = pattern.replace("*", "")
                for root, _, files in os.walk(repo_path):
                    for file in files:
                        if file.endswith(extension):
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, repo_path)
                            found_dependency_files.append(rel_path)
                            files_checked += 1
                            
                            if not detected_tool:
                                detected_tool = tool
                                result["has_dependency_management"] = True
            else:
                # Direct file matching
                file_path = os.path.join(repo_path, pattern)
                if os.path.isfile(file_path):
                    rel_path = os.path.relpath(file_path, repo_path)
                    found_dependency_files.append(rel_path)
                    files_checked += 1
                    
                    if not detected_tool:
                        detected_tool = tool
                        result["has_dependency_management"] = True
                    
                    # Check if this is a lockfile
                    if tool in lockfiles and pattern in lockfiles[tool]:
                        has_lockfile = True
                    
                    # Analyze version pinning and dependency counts
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # npm - package.json
                            if pattern == "package.json":
                                try:
                                    pkg_data = json.loads(content)
                                    
                                    # Count dependencies
                                    if "dependencies" in pkg_data:
                                        deps = pkg_data["dependencies"]
                                        direct_deps += len(deps)
                                        
                                        # Check for version pinning (e.g., "^1.0.0" vs "1.0.0")
                                        if deps:
                                            first_dep = list(deps.values())[0]
                                            if first_dep.startswith('^') or first_dep.startswith('~'):
                                                has_version_pinning = True
                                                pinning_type = "range"
                                            elif first_dep.startswith('>=') or first_dep.startswith('>'):
                                                pinning_type = "minimum"
                                            elif re.match(r'^\d', first_dep):
                                                has_version_pinning = True
                                                pinning_type = "exact"
                                    
                                    if "devDependencies" in pkg_data:
                                        dev_deps += len(pkg_data["devDependencies"])
                                    
                                except json.JSONDecodeError:
                                    logger.error(f"Error parsing package.json: {file_path}")
                            
                            # pip - requirements.txt
                            elif pattern == "requirements.txt":
                                # Count direct dependencies
                                lines = content.split('\n')
                                deps = [line.strip() for line in lines 
                                        if line.strip() and not line.strip().startswith('#')]
                                direct_deps += len(deps)
                                
                                # Check for version pinning
                                if deps:
                                    # Check first dependency for pinning style
                                    first_dep = deps[0]
                                    if "==" in first_dep:
                                        has_version_pinning = True
                                        pinning_type = "exact"
                                    elif ">=" in first_dep or "~=" in first_dep:
                                        pinning_type = "minimum"
                                    elif ">" in first_dep:
                                        pinning_type = "range"
                            
                            # Maven - pom.xml
                            elif pattern == "pom.xml":
                                # Crude XML parsing to find dependencies
                                dependency_count = content.count("<dependency>")
                                direct_deps += dependency_count
                                
                                # Check for version pinning using regex
                                if "<version>" in content:
                                    # Check if versions use properties or exact versions
                                    version_matches = re.findall(r'<version>([^<]+)</version>', content)
                                    if version_matches:
                                        has_version_pinning = True
                                        # Check if versions use properties (${...})
                                        if any("${" in v for v in version_matches):
                                            pinning_type = "property"
                                        else:
                                            pinning_type = "exact"
                            
                            # Go - go.mod
                            elif pattern == "go.mod":
                                # Count require statements
                                require_matches = re.findall(r'require\s+([^\s]+)\s+([^\s]+)', content)
                                direct_deps += len(require_matches)
                                
                                # Check for version pinning
                                if require_matches:
                                    has_version_pinning = True
                                    pinning_type = "exact"  # Go modules use exact versions
                            
                            # Cargo - Cargo.toml
                            elif pattern == "Cargo.toml":
                                if "[dependencies]" in content:
                                    # Count dependencies
                                    dependencies_section = content.split("[dependencies]")[1].split("[")[0]
                                    deps = re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=', dependencies_section, re.MULTILINE)
                                    direct_deps += len(deps)
                                    
                                    # Check for version pinning
                                    version_matches = re.findall(r'version\s*=\s*"([^"]+)"', dependencies_section)
                                    if version_matches:
                                        has_version_pinning = True
                                        # Check if versions use ^ or exact
                                        if any("^" in v for v in version_matches):
                                            pinning_type = "range"
                                        else:
                                            pinning_type = "exact"
                    
                    except Exception as e:
                        logger.error(f"Error analyzing dependency file {file_path}: {e}")
    
    # Check for dependency update mechanisms
    has_dependency_updates = False
    for update_file in update_files:
        file_path = os.path.join(repo_path, update_file)
        if os.path.isfile(file_path):
            has_dependency_updates = True
            files_checked += 1
            
            # Add to found files if not already included
            rel_path = os.path.relpath(file_path, repo_path)
            if rel_path not in found_dependency_files:
                found_dependency_files.append(rel_path)
    
    # Check CI files for dependency update references if we haven't found specific update files
    if not has_dependency_updates:
        ci_files = [
            ".github/workflows/ci.yml", ".github/workflows/main.yml",
            ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml",
            "Jenkinsfile", ".circleci/config.yml"
        ]
        
        for ci_file in ci_files:
            file_path = os.path.join(repo_path, ci_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Look for dependency update references
                        if ("dependabot" in content or "renovate" in content or 
                            "dependency update" in content or "update dependencies" in content):
                            has_dependency_updates = True
                            
                            # Add to found files
                            rel_path = os.path.relpath(file_path, repo_path)
                            if rel_path not in found_dependency_files:
                                found_dependency_files.append(rel_path)
                            
                            break
                except Exception as e:
                    logger.error(f"Error checking CI file {file_path}: {e}")
    
    # Update result with findings
    result["dependency_tool"] = detected_tool
    result["has_lockfile"] = has_lockfile
    result["has_version_pinning"] = has_version_pinning
    result["version_pinning_type"] = pinning_type
    result["has_dependency_updates"] = has_dependency_updates
    result["dependency_count"] = direct_deps + dev_deps
    result["direct_dependencies"] = direct_deps
    result["dev_dependencies"] = dev_deps
    result["outdated_dependencies"] = outdated_deps  # Would require more analysis
    result["dependency_files"] = found_dependency_files
    result["files_checked"] = files_checked
    
    # Calculate dependency management score (0-100 scale)
    score = 0
    
    # Points for having dependency management
    if result["has_dependency_management"]:
        score += 30
        
        # Points for having a lockfile
        if result["has_lockfile"]:
            score += 25
        
        # Points for version pinning
        if result["has_version_pinning"]:
            if result["version_pinning_type"] == "exact":
                score += 20
            elif result["version_pinning_type"] == "range" or result["version_pinning_type"] == "property":
                score += 15
            else:
                score += 10
        
        # Points for dependency updates
        if result["has_dependency_updates"]:
            score += 25
            
        # Adjustments based on dependency count
        if result["dependency_count"] > 0:
            if result["dependency_count"] > 100:
                # Penalty for excessive dependencies
                score -= 10
        
        # Outdated dependencies would reduce score, but we're not analyzing that here
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["dependency_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check dependency organization
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository - required for this check
        local_path = repository.get('local_path')
        
        if not local_path or not os.path.isdir(local_path):
            return {
                "status": "skipped",
                "score": 0,
                "result": {"message": "No local repository path available"},
                "errors": "Local repository path is required for dependency management analysis"
            }
        
        # Run the check with local path only
        # API data is not used for this check
        result = check_dependency_management(local_path, None)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("dependency_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running dependency management check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }