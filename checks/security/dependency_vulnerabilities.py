import os
import re
import logging
import time
import json
import subprocess
import pkg_resources
import tempfile  # Add missing import for tempfile module
import shutil    # Add missing import for shutil which is used with tempfile
from typing import Dict, Any, List, Tuple, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_dependency_vulnerabilities(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for known vulnerabilities in dependencies
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "dependencies_found": 0,
        "has_dependency_files": False,
        "has_lockfiles": False,
        "outdated_dependencies": [],
        "potential_vulnerabilities": [],
        "dependency_management_tools": [],
        "dependency_vulnerability_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Dependency file patterns
    dependency_files = {
        "npm": ["package.json"],
        "yarn": ["package.json", "yarn.lock"],
        "pnpm": ["package.json", "pnpm-lock.yaml"],
        "pip": ["requirements.txt", "Pipfile", "pyproject.toml", "setup.py"],
        "pipenv": ["Pipfile", "Pipfile.lock"],
        "poetry": ["pyproject.toml", "poetry.lock"],
        "bundler": ["Gemfile", "Gemfile.lock"],
        "composer": ["composer.json", "composer.lock"],
        "gradle": ["build.gradle", "gradle.lockfile"],
        "maven": ["pom.xml"],
        "cargo": ["Cargo.toml", "Cargo.lock"],
        "nuget": ["packages.config", "*.csproj", "*.fsproj", "*.vbproj", "package.config"]
    }
    
    # Lock files to check
    lock_files = [
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Gemfile.lock",
        "composer.lock",
        "gradle.lockfile",
        "Cargo.lock"
    ]
    
    # Detected dependency files
    found_dependency_files = {}
    dependencies = {}
    detected_tools = set()
    vulnerable_deps = []
    
    # Find dependency files in repository
    for tool, files in dependency_files.items():
        for file_pattern in files:
            # Handle glob patterns
            if '*' in file_pattern:
                for root, _, filenames in os.walk(repo_path):
                    for filename in filenames:
                        if re.match(file_pattern.replace('*', '.*'), filename):
                            file_path = os.path.join(root, filename)
                            if tool not in found_dependency_files:
                                found_dependency_files[tool] = []
                            found_dependency_files[tool].append(file_path)
                            detected_tools.add(tool)
            else:
                # Check direct path
                file_path = os.path.join(repo_path, file_pattern)
                if os.path.isfile(file_path):
                    if tool not in found_dependency_files:
                        found_dependency_files[tool] = []
                    found_dependency_files[tool].append(file_path)
                    detected_tools.add(tool)
    
    # Check if we found any dependency files
    if found_dependency_files:
        result["has_dependency_files"] = True
        result["dependency_management_tools"] = list(detected_tools)
    
    # Check for lock files
    for lock_file in lock_files:
        lock_path = os.path.join(repo_path, lock_file)
        if os.path.isfile(lock_path):
            result["has_lockfiles"] = True
            break
    
    # Parse dependencies from files (simplified implementation)
    for tool, files in found_dependency_files.items():
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    file_name = os.path.basename(file_path)
                    
                    # Extract dependencies based on file type
                    if tool == "npm" or tool == "yarn" or tool == "pnpm":
                        # Parse package.json
                        if file_name == "package.json":
                            import json
                            try:
                                package_data = json.loads(content)
                                deps = package_data.get("dependencies", {})
                                dev_deps = package_data.get("devDependencies", {})
                                
                                # Add regular dependencies
                                for dep_name, version in deps.items():
                                    dependencies[dep_name] = {
                                        "version": version.replace('^', '').replace('~', ''),
                                        "ecosystem": "npm",
                                        "dev": False
                                    }
                                
                                # Add dev dependencies
                                for dep_name, version in dev_deps.items():
                                    dependencies[dep_name] = {
                                        "version": version.replace('^', '').replace('~', ''),
                                        "ecosystem": "npm",
                                        "dev": True
                                    }
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse JSON in {file_path}")
                        # Parse lock files
                        elif file_name.endswith(".lock") or file_name.endswith("-lock.yaml") or file_name == "package-lock.json":
                            # Use appropriate parser based on file extension
                            if file_name.endswith(".yaml") or file_name.endswith(".yml"):
                                try:
                                    # Import yaml module (with fallback)
                                    try:
                                        import yaml
                                        try:
                                            # Try to use faster C implementation if available
                                            from yaml import CSafeLoader as SafeLoader
                                        except ImportError:
                                            from yaml import SafeLoader
                                            
                                        # Parse YAML file
                                        lock_data = yaml.load(content, Loader=SafeLoader)
                                        logger.info(f"Successfully parsed YAML file: {file_path}")
                                        
                                        # Extract dependencies from pnpm-lock.yaml
                                        if file_name == "pnpm-lock.yaml" and isinstance(lock_data, dict):
                                            # pnpm-lock.yaml format changed between versions, handle various formats
                                            if "dependencies" in lock_data:
                                                for dep_name, dep_info in lock_data["dependencies"].items():
                                                    if isinstance(dep_info, dict) and "version" in dep_info:
                                                        version = dep_info["version"]
                                                        dependencies[dep_name] = {
                                                            "version": version.replace('^', '').replace('~', ''),
                                                            "ecosystem": "npm",
                                                            "dev": False
                                                        }
                                            # Handle newer pnpm format with packages section
                                            if "packages" in lock_data:
                                                for pkg_path, pkg_info in lock_data["packages"].items():
                                                    if pkg_path.startswith("/"):
                                                        # Extract package name and version from path
                                                        parts = pkg_path.strip("/").split("/")
                                                        if len(parts) >= 2:
                                                            dep_name = parts[0]
                                                            if '@' in dep_name and dep_name.startswith('@'):
                                                                # Handle scoped packages
                                                                if len(parts) >= 3:
                                                                    dep_name = f"{parts[0]}/{parts[1]}"
                                                                    version = parts[2]
                                                                else:
                                                                    continue
                                                            else:
                                                                version = parts[1]
                                                                
                                                            dependencies[dep_name] = {
                                                                "version": version,
                                                                "ecosystem": "npm",
                                                                "dev": pkg_info.get("dev", False) if isinstance(pkg_info, dict) else False
                                                            }
                                    except ImportError:
                                        logger.warning(f"Could not import yaml module to parse {file_path}. Install PyYAML for better results.")
                                except Exception as e:
                                    logger.warning(f"Failed to parse YAML in {file_path}: {str(e)}")
                            elif file_name == "package-lock.json":
                                try:
                                    import json
                                    lock_data = json.loads(content)
                                    
                                    # Extract from NPM lock file format
                                    if "dependencies" in lock_data:
                                        for dep_name, dep_info in lock_data["dependencies"].items():
                                            if isinstance(dep_info, dict) and "version" in dep_info:
                                                version = dep_info["version"]
                                                dependencies[dep_name] = {
                                                    "version": version,
                                                    "ecosystem": "npm",
                                                    "dev": dep_info.get("dev", False)
                                                }
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse JSON in {file_path}")
                    
                    elif tool == "pip" or tool == "pipenv" or tool == "poetry":
                        # Parse requirements.txt or similar
                        if os.path.basename(file_path) == "requirements.txt":
                            for line in content.split('\n'):
                                # Skip comments and empty lines
                                if not line.strip() or line.strip().startswith('#'):
                                    continue
                                    
                                # Parse requirements with versions
                                try:
                                    # Handle various format patterns
                                    if '>=' in line or '<=' in line or '==' in line:
                                        parts = re.split('>=|<=|==', line, 1)
                                        dep_name = parts[0].strip()
                                        version = parts[1].strip() if len(parts) > 1 else ""
                                        
                                        # Handle complex version specs
                                        if ',' in version:
                                            version = version.split(',')[0].strip()
                                        
                                        dependencies[dep_name] = {
                                            "version": version,
                                            "ecosystem": "pip",
                                            "dev": False
                                        }
                                except Exception as e:
                                    try:
                                        logger.warning(f"Failed to parse requirement line: {line}, error: {e}")
                                    except:
                                        logger.warning(f"Failed to parse requirement line (unprintable characters), error: {str(e)}")
                        # Parse Pipfile, poetry.lock, etc.
                        elif os.path.basename(file_path) in ["Pipfile", "poetry.lock", "pyproject.toml"]:
                            if os.path.basename(file_path) == "Pipfile":
                                try:
                                    import toml
                                    pipfile_data = toml.loads(content)
                                    
                                    # Get packages from Pipfile
                                    packages = pipfile_data.get("packages", {})
                                    dev_packages = pipfile_data.get("dev-packages", {})
                                    
                                    # Process regular dependencies
                                    for dep_name, version_info in packages.items():
                                        if isinstance(version_info, str):
                                            version = version_info.replace("==", "").replace("~=", "").replace(">=", "")
                                        else:
                                            version = "*"  # Wildcard if no specific version
                                            
                                        dependencies[dep_name] = {
                                            "version": version,
                                            "ecosystem": "pip",
                                            "dev": False
                                        }
                                        
                                    # Process dev dependencies
                                    for dep_name, version_info in dev_packages.items():
                                        if isinstance(version_info, str):
                                            version = version_info.replace("==", "").replace("~=", "").replace(">=", "")
                                        else:
                                            version = "*"  # Wildcard if no specific version
                                            
                                        dependencies[dep_name] = {
                                            "version": version,
                                            "ecosystem": "pip",
                                            "dev": True
                                        }
                                except ImportError:
                                    logger.warning("TOML library not installed. Install 'toml' for better parsing of Pipfile.")
                                except Exception as e:
                                    logger.warning(f"Failed to parse Pipfile: {str(e)}")
                    
                    # More parsing logic for other dependency ecosystems would go here
                    # For now, this is simplified for demonstration purposes
                    
            except Exception as e:
                logger.error(f"Error analyzing dependency file {file_path}: {e}")
    
    # Update dependency count
    result["dependencies_found"] = len(dependencies)
    
    # Check for vulnerabilities using local analysis
    # Enhanced vulnerability database with more entries
    known_vulnerabilities = load_vulnerability_database()
    
    # Check against our local vulnerability database
    for dep_name, dep_info in dependencies.items():
        ecosystem = dep_info["ecosystem"]
        version = dep_info["version"]
        
        # Check if this dependency is in our known vulnerabilities list
        vulnerable_matches = find_vulnerable_dependency(dep_name, version, ecosystem, known_vulnerabilities)
        
        for vuln_info in vulnerable_matches:
            vulnerable_deps.append({
                "name": dep_name,
                "version": version,
                "ecosystem": ecosystem,
                "vulnerability": vuln_info.get("id", "UNKNOWN"),
                "severity": vuln_info.get("severity", "medium"),
                "description": vuln_info.get("description", ""),
                "url": vuln_info.get("url", "")
            })
    
    # Attempt to enhance results with local safety check for Python dependencies
    if any(tool in detected_tools for tool in ["pip", "pipenv", "poetry"]):
        python_vulns = check_python_vulnerabilities_locally(repo_path, dependencies)
        vulnerable_deps.extend(python_vulns)
    
    # Check for npm vulnerabilities locally if applicable
    if any(tool in detected_tools for tool in ["npm", "yarn", "pnpm"]):
        npm_vulns = check_npm_vulnerabilities_locally(repo_path, dependencies)
        vulnerable_deps.extend(npm_vulns)
    
    # Store vulnerable dependencies (remove duplicates)
    unique_vulns = remove_duplicate_vulnerabilities(vulnerable_deps)
    result["potential_vulnerabilities"] = unique_vulns
    
    # Calculate dependency vulnerability score (0-100 scale)
    score = 100  # Start with perfect score
    
    # Penalize for not having dependency management
    if not result["has_dependency_files"]:
        score -= 20
    
    # Penalize for not having lock files
    if not result["has_lockfiles"] and result["has_dependency_files"]:
        score -= 10
    
    # Penalize for vulnerabilities based on severity
    for vuln in unique_vulns:
        if vuln["severity"] == "critical":
            score -= 25
        elif vuln["severity"] == "high":
            score -= 15
        elif vuln["severity"] == "medium":
            score -= 10
        elif vuln["severity"] == "low":
            score -= 5
    
    # Ensure score is within 0-100 range
    score = max(0, min(100, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["dependency_vulnerability_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def load_vulnerability_database() -> Dict:
    """
    Load a comprehensive database of known vulnerabilities
    This is a local alternative to using GitHub API
    """
    # This would ideally be loaded from a local file that's regularly updated
    # For now, we'll use an expanded hardcoded database for demonstration
    return {
        "log4j-core": [
            {
                "id": "CVE-2021-44228",
                "ecosystem": "maven",
                "versions": [">=2.0.0,<=2.14.1"],
                "severity": "critical",
                "description": "Remote code execution vulnerability in Log4j",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-44228"
            }
        ],
        "lodash": [
            {
                "id": "CVE-2021-23337",
                "ecosystem": "npm",
                "versions": ["<4.17.21"],
                "severity": "high",
                "description": "Command injection vulnerability in Lodash",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-23337"
            },
            {
                "id": "CVE-2020-8203",
                "ecosystem": "npm",
                "versions": ["<4.17.19"],
                "severity": "medium",
                "description": "Prototype pollution in Lodash",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2020-8203"
            }
        ],
        "serialize-javascript": [
            {
                "id": "CVE-2020-7660",
                "ecosystem": "npm",
                "versions": ["<3.1.0"],
                "severity": "high",
                "description": "Remote code execution in serialize-javascript",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2020-7660"
            }
        ],
        "django": [
            {
                "id": "CVE-2021-28658",
                "ecosystem": "pip",
                "versions": ["<2.2.18", "<3.0.14", "<3.1.8"],
                "severity": "medium",
                "description": "Potential directory traversal via uploaded files",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-28658"
            },
            {
                "id": "CVE-2021-33203",
                "ecosystem": "pip",
                "versions": ["<2.2.24", "<3.0.14", "<3.1.12", "<3.2.4"],
                "severity": "high",
                "description": "Potential SQL injection in Django QuerySet.order_by()",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-33203"
            }
        ],
        "axios": [
            {
                "id": "CVE-2020-28168",
                "ecosystem": "npm",
                "versions": ["<0.21.1"],
                "severity": "medium",
                "description": "Server-side request forgery",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2020-28168"
            }
        ],
        "flask": [
            {
                "id": "CVE-2019-1010083",
                "ecosystem": "pip",
                "versions": ["<0.12.3"],
                "severity": "high",
                "description": "Session cookie tampering",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2019-1010083"
            }
        ],
        "jquery": [
            {
                "id": "CVE-2020-11023",
                "ecosystem": "npm",
                "versions": [">=1.2.0,<3.5.0"],
                "severity": "medium",
                "description": "XSS vulnerability in jQuery",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2020-11023"
            }
        ],
        "express": [
            {
                "id": "CVE-2022-24999",
                "ecosystem": "npm",
                "versions": ["<4.17.3", ">=5.0.0,<5.0.0-alpha.8"],
                "severity": "high",
                "description": "Open redirect vulnerability",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2022-24999"
            }
        ]
    }

def find_vulnerable_dependency(dep_name: str, version: str, ecosystem: str, database: Dict) -> List[Dict]:
    """
    Check if a dependency is vulnerable based on the local database
    
    Args:
        dep_name: Name of the dependency
        version: Version string
        ecosystem: Ecosystem (npm, pip, etc.)
        database: Vulnerability database
        
    Returns:
        List of vulnerability info for matches found
    """
    results = []
    
    # If the dependency isn't in our database, return empty list
    if dep_name not in database:
        return results
    
    # Check each vulnerability entry for this dependency
    for vuln_info in database.get(dep_name, []):
        # Skip if ecosystem doesn't match
        if vuln_info["ecosystem"] != ecosystem:
            continue
            
        # Check each vulnerable version range
        for version_range in vuln_info["versions"]:
            if is_version_in_range(version, version_range):
                results.append(vuln_info)
                break
    
    return results

def is_version_in_range(version: str, version_range: str) -> bool:
    """
    Check if a version is within a specified range
    
    Args:
        version: Version to check
        version_range: Range specification (e.g. "<1.0.0", ">=2.0.0,<=3.0.0")
        
    Returns:
        True if version is in range, False otherwise
    """
    try:
        # Simple implementation for demonstration
        # In a real implementation, this would use proper semver logic
        
        # Handle comma-separated ranges (AND logic)
        if "," in version_range:
            ranges = version_range.split(",")
            return all(is_version_in_range(version, r) for r in ranges)
            
        # Handle simple comparison operators
        if version_range.startswith(">="):
            return version >= version_range[2:]
        elif version_range.startswith("<="):
            return version <= version_range[2:]
        elif version_range.startswith(">"):
            return version > version_range[1:]
        elif version_range.startswith("<"):
            return version < version_range[1:]
        elif version_range.startswith("=="):
            return version == version_range[2:]
        else:
            # Exact match if no operator
            return version == version_range
    except Exception as e:
        logger.warning(f"Error comparing versions {version} and {version_range}: {e}")
        return False

def check_python_vulnerabilities_locally(repo_path: str, dependencies: Dict) -> List[Dict]:
    """
    Run local safety check for Python dependencies
    
    Args:
        repo_path: Path to repository
        dependencies: Dictionary of dependencies
        
    Returns:
        List of vulnerabilities found
    """
    results = []
    
    # Only check Python packages
    python_deps = {name: info for name, info in dependencies.items() 
                   if info.get("ecosystem") == "pip"}
    
    if not python_deps:
        return results
        
    try:
        # Try to use safety if installed
        try:
            import safety.cli
            has_safety = True
        except ImportError:
            has_safety = False
            
        if has_safety:
            # Create requirements file from dependencies
            temp_req_path = os.path.join(repo_path, "_temp_requirements_check.txt")
            try:
                with open(temp_req_path, 'w') as f:
                    for name, info in python_deps.items():
                        version = info.get("version", "")
                        if version:
                            f.write(f"{name}=={version}\n")
                        else:
                            f.write(f"{name}\n")
                
                # Run safety check as subprocess to capture output
                try:
                    output = subprocess.check_output(
                        ["safety", "check", "--file", temp_req_path, "--json"],
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
                    
                    # Parse JSON output
                    try:
                        safety_data = json.loads(output)
                        if isinstance(safety_data, list):
                            for vuln in safety_data:
                                # Extract data from safety output
                                if len(vuln) >= 5:
                                    package = vuln[0]
                                    affected_versions = vuln[1]
                                    vuln_id = vuln[4]
                                    
                                    # Add to results
                                    results.append({
                                        "name": package,
                                        "version": python_deps.get(package, {}).get("version", "unknown"),
                                        "ecosystem": "pip",
                                        "vulnerability": vuln_id,
                                        "severity": "high",  # Safety doesn't provide severity, defaulting to high
                                        "description": vuln[2] if len(vuln) > 2 else "",
                                        "url": vuln[3] if len(vuln) > 3 else ""
                                    })
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse safety output as JSON")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Safety check failed: {e}")
            finally:
                # Clean up temp file
                if os.path.exists(temp_req_path):
                    os.remove(temp_req_path)
    except Exception as e:
        logger.warning(f"Error running Python vulnerability check: {e}")
        
    return results

def check_npm_vulnerabilities_locally(repo_path: str, dependencies: Dict) -> List[Dict]:
    """
    Check for npm vulnerabilities using local npm audit if available
    
    Args:
        repo_path: Path to repository
        dependencies: Dictionary of dependencies
        
    Returns:
        List of vulnerabilities found
    """
    results = []
    
    # Only check npm packages
    npm_deps = {name: info for name, info in dependencies.items() 
                if info.get("ecosystem") == "npm"}
    
    if not npm_deps:
        return results
        
    # Check if package.json exists
    package_json_path = os.path.join(repo_path, "package.json")
    if not os.path.exists(package_json_path):
        return results
        
    try:
        # Run npm audit if npm is available
        try:
            # Create a temporary directory to avoid modifying the repo
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy package.json to temp dir
                temp_package_json = os.path.join(temp_dir, "package.json")
                shutil.copy(package_json_path, temp_package_json)
                
                # Copy package-lock.json or yarn.lock if exists
                for lock_file in ["package-lock.json", "yarn.lock", "npm-shrinkwrap.json"]:
                    lock_path = os.path.join(repo_path, lock_file)
                    if os.path.exists(lock_path):
                        shutil.copy(lock_path, os.path.join(temp_dir, lock_file))
                        break
                
                # Run npm audit
                try:
                    proc = subprocess.run(
                        ["npm", "audit", "--json"],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True,
                        timeout=30  # Timeout in seconds
                    )
                    
                    # npm audit returns non-zero when vulnerabilities found
                    if proc.stdout:
                        try:
                            audit_data = json.loads(proc.stdout)
                            
                            # Extract vulnerabilities from npm audit format
                            if "vulnerabilities" in audit_data:
                                for pkg_name, vuln_data in audit_data["vulnerabilities"].items():
                                    severity = vuln_data.get("severity", "medium")
                                    vuln_via = vuln_data.get("via", [])
                                    
                                    if isinstance(vuln_via, list):
                                        for via_item in vuln_via:
                                            if isinstance(via_item, dict):
                                                vuln_id = via_item.get("url", "").split("/")[-1]
                                                version = via_item.get("version", npm_deps.get(pkg_name, {}).get("version", "unknown"))
                                                
                                                results.append({
                                                    "name": pkg_name,
                                                    "version": version,
                                                    "ecosystem": "npm",
                                                    "vulnerability": vuln_id,
                                                    "severity": severity,
                                                    "description": vuln_data.get("title", ""),
                                                    "url": via_item.get("url", "")
                                                })
                                    elif isinstance(vuln_via, dict):
                                        # Handle case when via is a single object
                                        vuln_id = vuln_via.get("url", "").split("/")[-1]
                                        version = vuln_via.get("version", npm_deps.get(pkg_name, {}).get("version", "unknown"))
                                        
                                        results.append({
                                            "name": pkg_name,
                                            "version": version,
                                            "ecosystem": "npm",
                                            "vulnerability": vuln_id,
                                            "severity": severity,
                                            "description": vuln_data.get("title", ""),
                                            "url": vuln_via.get("url", "")
                                        })
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse npm audit output as JSON")
                except subprocess.CalledProcessError:
                    logger.warning("NPM audit returned non-zero exit code")
                except subprocess.TimeoutExpired:
                    logger.warning("NPM audit timed out")
        except Exception as e:
            logger.warning(f"Error running npm audit: {e}")
    except Exception as e:
        logger.warning(f"Error checking npm vulnerabilities: {e}")
        
    return results

def remove_duplicate_vulnerabilities(vulnerabilities: List[Dict]) -> List[Dict]:
    """
    Remove duplicate vulnerability entries
    
    Args:
        vulnerabilities: List of vulnerability dictionaries
        
    Returns:
        Deduplicated list of vulnerabilities
    """
    # Use a set to track unique identifiers
    seen = set()
    unique_vulns = []
    
    for vuln in vulnerabilities:
        # Create a unique identifier for this vulnerability
        vuln_id = f"{vuln['name']}:{vuln['version']}:{vuln['vulnerability']}"
        
        if vuln_id not in seen:
            seen.add(vuln_id)
            unique_vulns.append(vuln)
    
    return unique_vulns

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the dependency vulnerabilities check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check using primarily local analysis
        result = check_dependency_vulnerabilities(local_path, repository)
        
        # Return the result with the score, timestamp and repo_id
        return {
            "score": result["dependency_vulnerability_score"],
            "result": result,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "repo_id": repository.get('id', 'unknown'),
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running dependency vulnerabilities check: {e}")
        return {
            "score": 0,
            "result": {"vulnerabilities": []},
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "repo_id": repository.get('id', 'unknown'),
            "status": "failed",
            "errors": str(e)
        }