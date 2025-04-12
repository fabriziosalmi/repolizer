"""
Dependency Licenses Check

Checks if the repository's dependencies have compatible licenses and are properly documented.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_dependency_licenses(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check dependency licenses in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_dependencies": False,
        "documented_dependencies": 0,
        "undocumented_dependencies": 0,
        "risky_licenses": 0,
        "dependency_files": [],
        "dependency_types": [],
        "files_checked": 0,
        "dependency_license_score": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for dependency licenses")
        
        # Files that might contain dependency information
        dependency_files = {
            "package.json": "npm",
            "package-lock.json": "npm",
            "yarn.lock": "yarn",
            "requirements.txt": "python",
            "setup.py": "python",
            "Pipfile": "pipenv",
            "Pipfile.lock": "pipenv",
            "go.mod": "go",
            "go.sum": "go",
            "Gemfile": "ruby",
            "Gemfile.lock": "ruby",
            "pom.xml": "maven",
            "build.gradle": "gradle",
            "build.gradle.kts": "gradle",
            "build.sbt": "sbt",
            "cargo.toml": "cargo",
            "cargo.lock": "cargo",
            "composer.json": "composer",
            "composer.lock": "composer",
            "pubspec.yaml": "dart",
            "pubspec.lock": "dart"
        }
        
        # Dependency documentation files
        doc_files = [
            "DEPENDENCIES.md", "dependencies.md", "NOTICE", "NOTICE.md", "THIRD_PARTY_LICENSES.md",
            "third_party_licenses.md", "LICENSE-THIRD_PARTY", "THIRD_PARTY.md", "third_party.md",
            "docs/dependencies.md", "docs/third_party.md", ".github/DEPENDENCIES.md"
        ]
        
        # Risky license keywords to look for
        risky_license_terms = [
            "agpl", "affero", "commons clause", "non-commercial", "noncommercial", "no commercial", 
            "not for commercial", "proprietary", "all rights reserved", "no license", "no-license",
            "unlicensed"
        ]
        
        files_checked = 0
        found_dependency_files = []
        dependency_types_found = set()
        
        # Check dependency files
        for dep_file, dep_type in dependency_files.items():
            file_path = os.path.join(repo_path, dep_file)
            if os.path.isfile(file_path):
                try:
                    files_checked += 1
                    relative_path = os.path.relpath(file_path, repo_path)
                    found_dependency_files.append(relative_path)
                    dependency_types_found.add(dep_type)
                    result["has_dependencies"] = True
                    
                    # For some formats, we can check for license information
                    if dep_file == "package.json":
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            try:
                                pkg_data = json.load(f)
                                deps = {}
                                if "dependencies" in pkg_data:
                                    deps.update(pkg_data["dependencies"])
                                if "devDependencies" in pkg_data:
                                    deps.update(pkg_data["devDependencies"])
                                
                                result["documented_dependencies"] += len(deps)
                                
                                # License information might be in package.json itself
                                if "license" in pkg_data:
                                    # Check for risky licenses
                                    license_str = str(pkg_data["license"]).lower()
                                    for risky_term in risky_license_terms:
                                        if risky_term in license_str:
                                            result["risky_licenses"] += 1
                                            break
                            except json.JSONDecodeError:
                                logger.error(f"Error decoding JSON in {file_path}")
                    
                    elif dep_file == "requirements.txt":
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            # Count non-empty, non-comment lines as dependencies
                            deps = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
                            result["documented_dependencies"] += len(deps)
                    
                    elif dep_file == "Gemfile":
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            # Count gem declarations
                            gems = re.findall(r'gem\s+[\'"]([^\'"]+)[\'"]', content)
                            result["documented_dependencies"] += len(gems)
                    
                    elif dep_file == "go.mod":
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            # Count require statements
                            requires = re.findall(r'require\s+([^\s]+)', content)
                            result["documented_dependencies"] += len(requires)
                    
                    elif dep_file == "pom.xml":
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            # Count dependency elements
                            dependencies = re.findall(r'<dependency>', content)
                            result["documented_dependencies"] += len(dependencies)
                
                except Exception as e:
                    logger.error(f"Error reading dependency file {file_path}: {e}")
        
        # Check for dependency documentation
        has_dependency_docs = False
        for doc_file in doc_files:
            file_path = os.path.join(repo_path, doc_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        has_dependency_docs = True
                        
                        # Look for risky license mentions
                        for risky_term in risky_license_terms:
                            if risky_term in content:
                                result["risky_licenses"] += 1
                                break
                        
                        # Estimate documented dependencies from content
                        dependency_mentions = re.findall(r'(dependency|package|library|module|component|gem|npm|pypi)', content, re.IGNORECASE)
                        if dependency_mentions and result["documented_dependencies"] == 0:
                            # Rough estimate of documented dependencies
                            result["documented_dependencies"] += len(dependency_mentions) // 2
                            
                except Exception as e:
                    logger.error(f"Error reading doc file {file_path}: {e}")
        
        # Check README for dependency documentation
        if result["has_dependencies"] and not has_dependency_docs:
            readme_files = ["README.md", "README", "README.txt", "docs/README.md"]
            for readme in readme_files:
                file_path = os.path.join(repo_path, readme)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            files_checked += 1
                            
                            # Check for dependency sections
                            section_headers = [
                                r'## dependencies',
                                r'## requirements',
                                r'## packages',
                                r'## libraries',
                                r'## third party'
                            ]
                            
                            has_dependency_section = False
                            for header in section_headers:
                                if re.search(header, content, re.IGNORECASE):
                                    has_dependency_section = True
                                    break
                            
                            if has_dependency_section:
                                # Estimate documented dependencies from content
                                dependency_mentions = re.findall(r'(dependency|package|library|module|component|gem|npm|pypi)', content, re.IGNORECASE)
                                if dependency_mentions and result["documented_dependencies"] == 0:
                                    # Rough estimate of documented dependencies
                                    result["documented_dependencies"] += len(dependency_mentions) // 2
                                    has_dependency_docs = True
                    
                    except Exception as e:
                        logger.error(f"Error reading README file {file_path}: {e}")
                        
                    # Break after checking first found README
                    if os.path.isfile(file_path):
                        break
        
        # Estimate undocumented dependencies if we have dependencies but no docs
        if result["has_dependencies"] and result["documented_dependencies"] == 0 and not has_dependency_docs:
            result["undocumented_dependencies"] = len(found_dependency_files) * 5  # Rough estimate
        
        # Update result with findings
        result["dependency_files"] = found_dependency_files
        result["dependency_types"] = sorted(list(dependency_types_found))
        result["files_checked"] = files_checked
        
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'dependency_licenses' in repo_data:
        logger.info("No local repository available. Using API data for dependency licenses check.")
        
        dep_data = repo_data.get('dependency_licenses', {})
        
        # Update result with dependency info from API
        result["has_dependencies"] = dep_data.get('has_dependencies', False)
        result["documented_dependencies"] = dep_data.get('documented_dependencies', 0)
        result["undocumented_dependencies"] = dep_data.get('undocumented_dependencies', 0)
        result["risky_licenses"] = dep_data.get('risky_licenses', 0)
        result["dependency_files"] = dep_data.get('dependency_files', [])
        result["dependency_types"] = dep_data.get('dependency_types', [])
    else:
        logger.warning("No local repository path or API data provided for dependency licenses check")
    
    # Calculate dependency license score (0-100 scale)
    score = 0
    
    # No dependencies is neither good nor bad, give a neutral score
    if not result["has_dependencies"]:
        score = 50
    else:
        # Base score for having dependencies
        score += 20
        
        # Points for documenting dependencies
        if result["documented_dependencies"] > 0:
            doc_points = min(40, result["documented_dependencies"])
            score += doc_points
        
        # Deduct points for undocumented dependencies
        if result["undocumented_dependencies"] > 0:
            undoc_penalty = min(30, result["undocumented_dependencies"] * 2)
            score -= undoc_penalty
        
        # Deduct points for risky licenses
        if result["risky_licenses"] > 0:
            risky_penalty = min(40, result["risky_licenses"] * 10)
            score -= risky_penalty
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["dependency_license_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify dependency licenses
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_dependency_licenses(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("dependency_license_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running dependency licenses check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }