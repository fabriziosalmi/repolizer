"""
Dependency Freshness Check

Analyzes the repository's dependencies for freshness and security updates.
"""
import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_dependency_freshness(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for dependency freshness in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "dependency_files_found": [],
        "total_dependencies": 0,
        "outdated_dependencies": 0,
        "deprecated_dependencies": 0,
        "security_vulnerabilities": 0,
        "average_freshness": 0,
        "by_ecosystem": {},
        "potentially_outdated": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Dependency file patterns by ecosystem
    dependency_files = {
        "javascript": ["package.json", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json"],
        "python": ["requirements.txt", "Pipfile", "Pipfile.lock", "setup.py", "pyproject.toml"],
        "ruby": ["Gemfile", "Gemfile.lock"],
        "php": ["composer.json", "composer.lock"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts", "gradle/dependencies.gradle"],
        "dotnet": ["*.csproj", "packages.config", "paket.dependencies"],
        "golang": ["go.mod", "go.sum", "Gopkg.toml", "Gopkg.lock"],
        "rust": ["Cargo.toml", "Cargo.lock"],
        "swift": ["Package.swift", "Podfile", "Podfile.lock"],
        "docker": ["Dockerfile"]
    }
    
    # Common version patterns in dependency files
    version_patterns = {
        "semantic": r'(\d+\.\d+\.\d+)(?:-[a-zA-Z0-9.-]+)?',
        "python_pin": r'==\s*(\d+\.\d+\.\d+)',
        "python_range": r'>=\s*(\d+\.\d+\.\d+)(?:,\s*<\s*(\d+\.\d+\.\d+))?',
        "caret": r'\^\s*(\d+\.\d+\.\d+)',
        "tilde": r'~\s*(\d+\.\d+\.\d+)',
        "maven": r'<version>([^<]+)</version>',
        "gradle": r'version\s*=?\s*[\'"]([^\'"]+)[\'"]'
    }
    
    # Patterns for potentially outdated dependencies
    outdated_indicators = {
        "deprecated_syntax": [
            r'DEPRECATED',
            r'deprecated',
            r'no longer maintained',
            r'no longer supported'
        ],
        "security_issues": [
            r'security',
            r'vulnerability',
            r'CVE-\d{4}-\d+',
            r'exploit'
        ],
        "old_version_indicators": [
            # Dependencies that haven't been updated in a very long time
            r'(\d{4})-(\d{2})-(\d{2})'  # Date in YYYY-MM-DD format
        ]
    }
    
    files_checked = 0
    dependency_files_found = []
    
    # Track dependencies by ecosystem
    ecosystem_dependencies = {}
    for ecosystem in dependency_files:
        ecosystem_dependencies[ecosystem] = {"total": 0, "outdated": 0, "files": []}
    
    # First pass: find dependency files
    for ecosystem, file_patterns in dependency_files.items():
        for pattern in file_patterns:
            if '*' in pattern:
                # Handle glob patterns
                pattern_regex = pattern.replace('.', '\.').replace('*', '.*')
                for root, _, files in os.walk(repo_path):
                    for file in files:
                        if re.match(pattern_regex, file):
                            file_path = os.path.join(root, file)
                            dependency_files_found.append((file_path, ecosystem))
                            ecosystem_dependencies[ecosystem]["files"].append(os.path.relpath(file_path, repo_path))
            else:
                # Handle exact file names
                for root, _, files in os.walk(repo_path):
                    if pattern in files:
                        file_path = os.path.join(root, pattern)
                        dependency_files_found.append((file_path, ecosystem))
                        ecosystem_dependencies[ecosystem]["files"].append(os.path.relpath(file_path, repo_path))
    
    total_dependencies = 0
    outdated_dependencies = 0
    deprecated_dependencies = 0
    security_vulnerabilities = 0
    
    # Map of ecosystem to max dependency age in days
    old_thresholds = {
        "javascript": 365,  # 1 year
        "python": 540,      # 1.5 years
        "ruby": 365,
        "php": 365,
        "java": 730,        # 2 years
        "dotnet": 730,
        "golang": 365,
        "rust": 365,
        "swift": 365,
        "docker": 180       # 6 months
    }
    
    today = datetime.now()
    
    # Second pass: analyze each dependency file
    for file_path, ecosystem in dependency_files_found:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                files_checked += 1
                
                # Parse dependencies based on file type
                filename = os.path.basename(file_path)
                
                if filename == "package.json":
                    # Parse NPM dependencies
                    try:
                        data = json.loads(content)
                        deps = {}
                        
                        # Combine all dependency types
                        for dep_type in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
                            if dep_type in data:
                                deps.update(data[dep_type])
                        
                        for dep_name, version in deps.items():
                            total_dependencies += 1
                            ecosystem_dependencies["javascript"]["total"] += 1
                            
                            # Check for old versions or deprecated dependencies
                            for pattern in outdated_indicators["deprecated_syntax"]:
                                if re.search(pattern, version, re.IGNORECASE):
                                    outdated_dependencies += 1
                                    deprecated_dependencies += 1
                                    ecosystem_dependencies["javascript"]["outdated"] += 1
                                    result["potentially_outdated"].append({
                                        "name": dep_name,
                                        "version": version,
                                        "file": os.path.relpath(file_path, repo_path),
                                        "reason": "Deprecated"
                                    })
                                    break
                            
                            # Check for major versions well behind the latest
                            if version.startswith('^') and version[1].isdigit() and int(version[1]) < 2:
                                # Potentially outdated major version
                                result["potentially_outdated"].append({
                                    "name": dep_name,
                                    "version": version,
                                    "file": os.path.relpath(file_path, repo_path),
                                    "reason": "Potentially outdated major version"
                                })
                                outdated_dependencies += 1
                                ecosystem_dependencies["javascript"]["outdated"] += 1
                    
                    except json.JSONDecodeError:
                        logger.error(f"Error parsing package.json: {file_path}")
                
                elif filename == "requirements.txt":
                    # Parse Python requirements
                    lines = content.splitlines()
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse dependency specification
                            parts = re.split(r'[=<>~!]', line, 1)
                            if len(parts) > 0:
                                dep_name = parts[0].strip()
                                version = parts[1].strip() if len(parts) > 1 else "latest"
                                
                                total_dependencies += 1
                                ecosystem_dependencies["python"]["total"] += 1
                                
                                # Check for pinned versions with old version numbers
                                version_match = re.search(version_patterns["python_pin"], line)
                                if version_match:
                                    version_str = version_match.group(1)
                                    version_parts = version_str.split('.')
                                    
                                    # Check for very old versions (0.x.y likely means outdated)
                                    if version_parts[0] == '0' and int(version_parts[1]) < 5:
                                        outdated_dependencies += 1
                                        ecosystem_dependencies["python"]["outdated"] += 1
                                        result["potentially_outdated"].append({
                                            "name": dep_name,
                                            "version": version_str,
                                            "file": os.path.relpath(file_path, repo_path),
                                            "reason": "Very old version number"
                                        })
                
                elif filename == "pom.xml":
                    # Parse Maven dependencies
                    dependency_matches = re.finditer(r'<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>\s*<version>([^<]+)</version>', content, re.DOTALL)
                    
                    for match in dependency_matches:
                        group_id = match.group(1)
                        artifact_id = match.group(2)
                        version = match.group(3)
                        
                        dep_name = f"{group_id}:{artifact_id}"
                        total_dependencies += 1
                        ecosystem_dependencies["java"]["total"] += 1
                        
                        # Check for SNAPSHOT versions (development versions)
                        if 'SNAPSHOT' in version:
                            result["potentially_outdated"].append({
                                "name": dep_name,
                                "version": version,
                                "file": os.path.relpath(file_path, repo_path),
                                "reason": "SNAPSHOT version in use"
                            })
                            outdated_dependencies += 1
                            ecosystem_dependencies["java"]["outdated"] += 1
                
                elif filename == "go.mod":
                    # Parse Go dependencies
                    require_blocks = re.findall(r'require\s*\(\s*([\s\S]*?)\s*\)', content)
                    for block in require_blocks:
                        for line in block.splitlines():
                            line = line.strip()
                            if line and not line.startswith('//'):
                                parts = line.split()
                                if len(parts) >= 2:
                                    dep_name = parts[0]
                                    version = parts[1]
                                    
                                    total_dependencies += 1
                                    ecosystem_dependencies["golang"]["total"] += 1
                                    
                                    # Check for very old versions
                                    if version.startswith('v0.'):
                                        outdated_dependencies += 1
                                        ecosystem_dependencies["golang"]["outdated"] += 1
                                        result["potentially_outdated"].append({
                                            "name": dep_name,
                                            "version": version,
                                            "file": os.path.relpath(file_path, repo_path),
                                            "reason": "Pre-1.0 version"
                                        })
                
                # Check for security vulnerabilities in any file
                for pattern in outdated_indicators["security_issues"]:
                    if re.search(pattern, content, re.IGNORECASE):
                        security_vulnerabilities += 1
                        break
                
                # Check for date indicators suggesting old dependencies
                date_matches = re.finditer(r'(\d{4})-(\d{2})-(\d{2})', content)
                for match in date_matches:
                    try:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                        
                        if 2000 <= year <= today.year:  # Validate reasonable date
                            dependency_date = datetime(year, month, day)
                            age_days = (today - dependency_date).days
                            
                            # Check if significantly old based on ecosystem
                            if age_days > old_thresholds.get(ecosystem, 365):
                                # This might indicate an outdated dependency
                                if len(result["potentially_outdated"]) < 20:  # Limit examples
                                    context_before = content[max(0, match.start() - 30):match.start()]
                                    context_after = content[match.end():min(len(content), match.end() + 30)]
                                    
                                    # Try to extract dependency name from context
                                    dep_context = context_before + match.group(0) + context_after
                                    dep_match = re.search(r'[\'"]?([\w\-\./@]+)[\'"]?\s*[:,=][\'"]?', dep_context)
                                    dep_name = dep_match.group(1) if dep_match else "unknown"
                                    
                                    result["potentially_outdated"].append({
                                        "name": dep_name,
                                        "date": f"{year}-{month:02d}-{day:02d}",
                                        "age_days": age_days,
                                        "file": os.path.relpath(file_path, repo_path),
                                        "reason": f"Dependency date is {age_days} days old"
                                    })
                                    outdated_dependencies += 1
                                    ecosystem_dependencies[ecosystem]["outdated"] += 1
                    except (ValueError, OverflowError):
                        # Invalid date format
                        pass
        
        except Exception as e:
            logger.error(f"Error analyzing dependency file {file_path}: {e}")
    
    # Update dependency statistics
    result["dependency_files_found"] = [os.path.relpath(file_path, repo_path) for file_path, _ in dependency_files_found]
    result["total_dependencies"] = total_dependencies
    result["outdated_dependencies"] = outdated_dependencies
    result["deprecated_dependencies"] = deprecated_dependencies
    result["security_vulnerabilities"] = security_vulnerabilities
    result["files_checked"] = files_checked
    
    # Calculate average freshness score
    if total_dependencies > 0:
        freshness_ratio = 1 - (outdated_dependencies / total_dependencies)
        result["average_freshness"] = round(freshness_ratio * 100)
    else:
        result["average_freshness"] = 100  # Default to 100% if no dependencies found
    
    # Update ecosystem statistics
    result["by_ecosystem"] = {}
    for ecosystem, stats in ecosystem_dependencies.items():
        if stats["total"] > 0:
            result["by_ecosystem"][ecosystem] = {
                "total": stats["total"],
                "outdated": stats["outdated"],
                "freshness": round((1 - stats["outdated"] / stats["total"]) * 100) if stats["total"] > 0 else 100,
                "files": stats["files"]
            }
    
    # Calculate dependency freshness score (0-100 scale)
    if total_dependencies > 0:
        # Base score from freshness ratio
        base_score = round(freshness_ratio * 80)
        
        # Penalty for security vulnerabilities
        security_penalty = min(30, security_vulnerabilities * 10)
        
        # Penalty for deprecated dependencies
        deprecated_penalty = min(20, deprecated_dependencies * 5)
        
        # Final score
        score = max(0, base_score - security_penalty - deprecated_penalty)
    else:
        # No dependencies found, neutral score
        score = 50
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["dependency_freshness_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the dependency freshness check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_dependency_freshness(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("dependency_freshness_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running dependency freshness check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }