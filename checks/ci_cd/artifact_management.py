"""
Artifact Management Check

Checks if the repository has proper artifact handling and storage.
"""
import os
import re
import logging
import json
from typing import Dict, Any, List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

# Setup logging
logger = logging.getLogger(__name__)

def check_artifact_management(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for artifact management features in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_artifact_storage": False,
        "has_versioning": False,
        "has_registry_config": False,
        "artifact_types": [],
        "storage_locations": [],
        "ci_artifacts_handled": False,
        "release_artifacts_handled": False,
        "files_checked": 0,
        "potential_issues": []
    }
    
    # First check if repository is available locally
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for artifact management")
        
        # File types and patterns to check for faster processing
        ci_config_paths = [
            ".github/workflows",
            ".gitlab",
            ".circleci",
            "azure-pipelines"
        ]
        
        ci_config_files = [
            ".github/workflows/*.yml", ".github/workflows/*.yaml",
            ".gitlab-ci.yml", "azure-pipelines.yml",
            "Jenkinsfile", "circle.yml", ".circleci/config.yml",
            ".travis.yml", "bitbucket-pipelines.yml"
        ]
        
        artifact_configs = [
            "pom.xml", "build.gradle", "package.json", "setup.py",
            "docker-compose.yml", "Dockerfile", ".npmrc", ".pypirc",
            "gradle.properties", "build.properties", ".m2/settings.xml",
            "nuget.config", "Chart.yaml", ".artifactory/*"
        ]
        
        # Patterns to look for in files - maps to result keys for faster processing
        pattern_to_result_map = {
            # Artifact storage patterns
            r'artifact': "has_artifact_storage",
            r'publish': "has_artifact_storage",
            r'upload': "has_artifact_storage",
            r'registry': "has_artifact_storage",
            r'deploy': "has_artifact_storage",
            r'package': "has_artifact_storage",
            
            # Versioning patterns
            r'version\s*[:=]': "has_versioning",
            r'tag\s+version': "has_versioning",
            r'\d+\.\d+\.\d+': "has_versioning",
            r'semver': "has_versioning",
            
            # Registry patterns
            r'registry\.': "has_registry_config",
            r'repository\.': "has_registry_config",
            r'artifactory': "has_registry_config",
            r'nexus': "has_registry_config",
            
            # CI artifacts patterns
            r'upload[-_]artifact': "ci_artifacts_handled",
            r'store[-_]artifact': "ci_artifacts_handled",
            r'save[-_]artifact': "ci_artifacts_handled",
            r'archiveArtifacts': "ci_artifacts_handled",
            
            # Release artifacts patterns
            r'release\s*artifacts': "release_artifacts_handled",
            r'publish\s*release': "release_artifacts_handled",
            r'deploy\s*artifacts': "release_artifacts_handled",
            r'publish\s*to\s*(registry|repository)': "release_artifacts_handled"
        }
        
        # Artifact types to identify
        artifact_type_patterns = {
            "docker": [r'docker', r'container', r'image', r'Dockerfile'],
            "jar": [r'\.jar', r'maven', r'gradle'],
            "npm": [r'\.tgz', r'npm', r'package\.json'],
            "python": [r'\.whl', r'\.tar\.gz', r'pypi', r'setup\.py'],
            "nuget": [r'\.nupkg', r'nuget'],
            "binary": [r'\.exe', r'\.bin', r'\.so', r'\.dll', r'binary'],
            "helm": [r'chart', r'helm'],
            "terraform": [r'terraform', r'\.tfstate']
        }
        
        # Common registry and storage services
        storage_services = {
            "docker_registry": [r'docker\s+registry', r'dockerhub', r'container\s+registry', r'ghcr\.io', r'docker\.io'],
            "artifactory": [r'artifactory', r'jfrog'],
            "nexus": [r'nexus\s+repository', r'sonatype'],
            "github_packages": [r'github\s+packages', r'ghcr\.io'],
            "s3": [r'aws\s+s3', r's3\s+bucket'],
            "gcs": [r'gcp\s+storage', r'gcs\s+bucket', r'google\s+cloud\s+storage'],
            "azure_storage": [r'azure\s+storage', r'azure\s+blob'],
            "maven_central": [r'maven\s+central', r'sonatype\s+oss'],
            "npm_registry": [r'npm\s+registry', r'npmjs\.com'],
            "pypi": [r'pypi', r'python\s+package\s+index'],
            "nuget_gallery": [r'nuget\s+gallery', r'nuget\.org']
        }
        
        # Maximum file size to analyze (5MB)
        max_file_size = 5 * 1024 * 1024
        
        # Directories to skip for faster processing
        skip_dirs = [
            'node_modules', '.git', 'dist', 'build', 'vendor', 
            'bower_components', 'public/assets', 'coverage'
        ]
        
        # Gather eligible files first - high priority targets
        high_priority_files = []
        
        # Helper function to resolve glob patterns
        def resolve_glob_pattern(pattern):
            files = []
            dir_name = os.path.dirname(pattern)
            file_pattern = os.path.basename(pattern)
            dir_path = os.path.join(repo_path, dir_name)
            
            if os.path.isdir(dir_path):
                for file in os.listdir(dir_path):
                    if fnmatch.fnmatch(file, file_pattern):
                        file_path = os.path.join(dir_name, file)
                        files.append(file_path)
            return files
            
        # Expand glob patterns in config file lists
        expanded_configs = []
        for pattern in ci_config_files + artifact_configs:
            if '*' in pattern:
                expanded_configs.extend(resolve_glob_pattern(pattern))
            else:
                expanded_configs.append(pattern)
        
        # First pass: check known artifact-related files
        for file_path_rel in expanded_configs:
            file_path = os.path.join(repo_path, file_path_rel)
            
            # Skip if file doesn't exist or is too large
            if not os.path.isfile(file_path):
                continue
                
            try:
                file_size = os.path.getsize(file_path)
                if file_size > max_file_size:
                    continue
            except (OSError, IOError):
                continue
                
            high_priority_files.append(file_path_rel)
        
        # Function to analyze a single file
        def analyze_file(file_path_rel):
            file_path = os.path.join(repo_path, file_path_rel)
            findings = {
                "artifact_storage": False,
                "versioning": False,
                "registry_config": False,
                "ci_artifacts": False,
                "release_artifacts": False,
                "artifact_types": set(),
                "storage_locations": set()
            }
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for patterns with direct mapping to results
                    for pattern, result_key in pattern_to_result_map.items():
                        if re.search(pattern, content, re.IGNORECASE):
                            result_key_to_findings = {
                                "has_artifact_storage": "artifact_storage",
                                "has_versioning": "versioning",
                                "has_registry_config": "registry_config",
                                "ci_artifacts_handled": "ci_artifacts",
                                "release_artifacts_handled": "release_artifacts"
                            }
                            findings_key = result_key_to_findings.get(result_key)
                            if findings_key:
                                findings[findings_key] = True
                    
                    # Identify artifact types
                    for artifact_type, type_patterns in artifact_type_patterns.items():
                        for type_pattern in type_patterns:
                            if re.search(type_pattern, content, re.IGNORECASE):
                                findings["artifact_types"].add(artifact_type)
                                break
                    
                    # Identify storage locations
                    for storage, storage_patterns in storage_services.items():
                        for storage_pattern in storage_patterns:
                            if re.search(storage_pattern, content, re.IGNORECASE):
                                findings["storage_locations"].add(storage)
                                break
                    
                    # Special case for Dockerfile
                    if os.path.basename(file_path).lower() == 'dockerfile':
                        findings["artifact_storage"] = True
                        findings["artifact_types"].add("docker")
                    
                    # Special case for package.json
                    if os.path.basename(file_path).lower() == 'package.json':
                        # Check for publish scripts
                        if re.search(r'"publish"|"deploy"|"release"', content):
                            findings["artifact_storage"] = True
                            findings["artifact_types"].add("npm")
                            findings["release_artifacts"] = True
                
                return findings
                
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
                return None
        
        # Analyze high priority files first
        high_priority_results = []
        files_checked = 0
        
        # Process high priority files in parallel
        with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 4, 8)) as executor:
            future_to_file = {executor.submit(analyze_file, file_rel): file_rel for file_rel in high_priority_files}
            
            for future in as_completed(future_to_file):
                file_rel = future_to_file[future]
                try:
                    findings = future.result()
                    if findings:
                        high_priority_results.append(findings)
                        files_checked += 1
                except Exception as e:
                    logger.error(f"Error processing file {file_rel}: {e}")
        
        # Aggregate high priority findings
        for findings in high_priority_results:
            result["has_artifact_storage"] |= findings["artifact_storage"]
            result["has_versioning"] |= findings["versioning"]
            result["has_registry_config"] |= findings["registry_config"]
            result["ci_artifacts_handled"] |= findings["ci_artifacts"]
            result["release_artifacts_handled"] |= findings["release_artifacts"]
            result["artifact_types"].extend([t for t in findings["artifact_types"] if t not in result["artifact_types"]])
            result["storage_locations"].extend([s for s in findings["storage_locations"] if s not in result["storage_locations"]])
        
        # If we still need more information, do a broader search
        if not result["has_artifact_storage"] or not result["has_versioning"] or len(result["artifact_types"]) == 0:
            logger.info("High priority scan insufficient. Performing broader repository scan for artifacts.")
            
            # Secondary file patterns that might contain artifact info
            secondary_files = []
            
            # Walking for specific directories first for better performance
            for root, dirs, files in os.walk(repo_path):
                # Skip specified directories
                dirs[:] = [d for d in dirs if not any(skip_pat in d for skip_pat in skip_dirs)]
                
                rel_root = os.path.relpath(root, repo_path)
                
                # Skip if we're too deep (optimization)
                if rel_root.count(os.sep) > 3:
                    continue
                
                # Target key directories with higher chance of having artifact config
                is_important_dir = any(ci_path in rel_root for ci_path in ci_config_paths) or \
                                  rel_root in ['.', 'ci', 'scripts', 'deploy', 'release']
                
                if is_important_dir:
                    for file in files:
                        if file.lower() in ['build.sh', 'deploy.sh', 'release.sh', 'publish.sh', 
                                          'build.gradle', 'settings.gradle', 'build.xml',
                                          'maven-settings.xml', 'package.json']:
                            file_path = os.path.join(rel_root, file)
                            if file_path not in high_priority_files:
                                secondary_files.append(file_path)
            
            # Process secondary files if needed
            if secondary_files:
                secondary_results = []
                
                with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 4, 8)) as executor:
                    future_to_file = {executor.submit(analyze_file, file_rel): file_rel for file_rel in secondary_files}
                    
                    for future in as_completed(future_to_file):
                        file_rel = future_to_file[future]
                        try:
                            findings = future.result()
                            if findings:
                                secondary_results.append(findings)
                                files_checked += 1
                        except Exception as e:
                            logger.error(f"Error processing secondary file {file_rel}: {e}")
                
                # Aggregate secondary findings
                for findings in secondary_results:
                    result["has_artifact_storage"] |= findings["artifact_storage"]
                    result["has_versioning"] |= findings["versioning"]
                    result["has_registry_config"] |= findings["registry_config"]
                    result["ci_artifacts_handled"] |= findings["ci_artifacts"]
                    result["release_artifacts_handled"] |= findings["release_artifacts"]
                    result["artifact_types"].extend([t for t in findings["artifact_types"] if t not in result["artifact_types"]])
                    result["storage_locations"].extend([s for s in findings["storage_locations"] if s not in result["storage_locations"]])
        
        result["files_checked"] = files_checked
        
        # Extra inference - if we have Docker or package.json, infer some basic artifact management
        if not result["has_artifact_storage"]:
            dockerfile_path = os.path.join(repo_path, 'Dockerfile')
            if os.path.isfile(dockerfile_path) or "docker" in result["artifact_types"]:
                result["has_artifact_storage"] = True
                if "docker" not in result["artifact_types"]:
                    result["artifact_types"].append("docker")
                if not result["storage_locations"]:
                    result["storage_locations"].append("docker_registry")
            
            package_json_path = os.path.join(repo_path, 'package.json')
            if os.path.isfile(package_json_path):
                try:
                    with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if "version" in content and ("scripts" in content and any(cmd in content for cmd in ["publish", "deploy", "release"])):
                            result["has_artifact_storage"] = True
                            result["has_versioning"] = True
                            if "npm" not in result["artifact_types"]:
                                result["artifact_types"].append("npm")
                            if not result["storage_locations"]:
                                result["storage_locations"].append("npm_registry")
                except Exception:
                    pass
                    
        # Check for potential issues
        if result["has_artifact_storage"] and not result["has_versioning"]:
            result["potential_issues"].append({
                "issue": "Artifacts are managed but versioning not detected",
                "severity": "medium",
                "recommendation": "Add versioning strategy for artifacts (semantic versioning recommended)"
            })
            
        if result["has_artifact_storage"] and not result["has_registry_config"]:
            result["potential_issues"].append({
                "issue": "Artifacts are managed but no registry configuration found",
                "severity": "medium",
                "recommendation": "Add configuration for artifact registry/storage"
            })
    
    # Only use API data if we don't have meaningful local results
    if repo_data and (not result["has_artifact_storage"] or not result["artifact_types"]):
        logger.info("Local analysis insufficient. Supplementing with API data for artifact management check.")
        
        # Extract artifact information from API data if available
        if 'artifacts' in repo_data:
            artifacts_data = repo_data.get('artifacts', {})
            
            # Update result with artifact info from API, but only for missing fields
            if not result["has_artifact_storage"]:
                result["has_artifact_storage"] = artifacts_data.get('has_artifacts', False)
            
            if not result["has_versioning"]:
                result["has_versioning"] = artifacts_data.get('has_versioning', False)
            
            if not result["has_registry_config"]:
                result["has_registry_config"] = artifacts_data.get('has_registry', False)
            
            if not result["artifact_types"]:
                result["artifact_types"] = artifacts_data.get('types', [])
            
            if not result["storage_locations"]:
                result["storage_locations"] = artifacts_data.get('storage', [])
            
            if not result["ci_artifacts_handled"]:
                result["ci_artifacts_handled"] = artifacts_data.get('ci_artifacts', False)
            
            if not result["release_artifacts_handled"]:
                result["release_artifacts_handled"] = artifacts_data.get('release_artifacts', False)
    else:
        logger.debug("Using primarily local analysis for artifact management check")
    
    # Calculate artifact management score
    result["artifact_management_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data: Dict[str, Any]) -> float:
    """
    Calculate a weighted score based on artifact management quality.
    
    Score components:
    - Base score for having artifact storage (0-25 points)
    - Score for versioning (0-20 points)
    - Score for registry configuration (0-15 points)
    - Score for CI artifacts handling (0-15 points)
    - Score for release artifacts handling (0-15 points)
    - Bonus for artifact type diversity (0-5 points)
    - Bonus for storage location diversity (0-5 points)
    - Penalty for issues (-15 points max)
    
    Returns:
        Score in the range of 1-100, or 0 for failed checks
    """
    # Extract relevant metrics
    has_artifact_storage = result_data.get("has_artifact_storage", False)
    has_versioning = result_data.get("has_versioning", False)
    has_registry_config = result_data.get("has_registry_config", False)
    ci_artifacts_handled = result_data.get("ci_artifacts_handled", False)
    release_artifacts_handled = result_data.get("release_artifacts_handled", False)
    artifact_types = result_data.get("artifact_types", [])
    storage_locations = result_data.get("storage_locations", [])
    potential_issues = result_data.get("potential_issues", [])
    files_checked = result_data.get("files_checked", 0)
    
    # Minimum score for successful execution even if results are poor
    if files_checked == 0:
        return 1
    
    # Base score: 0 points if no artifact storage detected
    base_score = 0
    
    # 1. Base points for having artifact storage
    if has_artifact_storage:
        base_score = 25
    else:
        # If no artifact storage found but check ran successfully, return minimum score
        return 1
    
    # 2. Points for versioning
    versioning_score = 20 if has_versioning else 0
    
    # 3. Points for registry configuration
    registry_score = 15 if has_registry_config else 0
    
    # 4. Points for CI artifacts handling
    ci_score = 15 if ci_artifacts_handled else 0
    
    # 5. Points for release artifacts handling
    release_score = 15 if release_artifacts_handled else 0
    
    # 6. Bonus for artifact type diversity
    artifact_diversity_score = min(5, len(artifact_types))
    
    # 7. Bonus for storage location diversity
    storage_diversity_score = min(5, len(storage_locations))
    
    # Calculate raw score
    raw_score = (base_score + versioning_score + registry_score + 
                 ci_score + release_score + 
                 artifact_diversity_score + storage_diversity_score)
    
    # Apply penalty for issues
    issue_penalty = min(15, len(potential_issues) * 5)
    
    # Calculate final score
    final_score = max(1, min(100, raw_score - issue_penalty))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "base_score": base_score,
        "versioning_score": versioning_score,
        "registry_score": registry_score,
        "ci_score": ci_score,
        "release_score": release_score,
        "artifact_diversity_score": artifact_diversity_score,
        "storage_diversity_score": storage_diversity_score,
        "raw_score": raw_score,
        "issue_penalty": issue_penalty,
        "final_score": final_score
    }
    
    # Return the final score, ensuring integer values where appropriate
    rounded_score = round(final_score, 1)
    return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

def get_artifact_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the artifact management check results"""
    score = result.get("artifact_management_score", 0)
    has_artifact_storage = result.get("has_artifact_storage", False)
    has_versioning = result.get("has_versioning", False)
    has_registry_config = result.get("has_registry_config", False)
    ci_artifacts_handled = result.get("ci_artifacts_handled", False)
    release_artifacts_handled = result.get("release_artifacts_handled", False)
    artifact_types = result.get("artifact_types", [])
    
    if score >= 80:
        return "Excellent artifact management implementation with proper versioning and registry configuration."
    
    if not has_artifact_storage:
        return "No artifact management detected. Consider implementing automated artifact builds and storage in your CI pipeline."
    
    recommendations = []
    
    if not has_versioning:
        recommendations.append("Implement version management for your artifacts (semantic versioning recommended).")
    
    if not has_registry_config:
        recommendations.append("Configure an artifact registry or repository for consistent storage and distribution.")
    
    if not ci_artifacts_handled:
        recommendations.append("Set up artifact storage in your CI pipeline to preserve build outputs.")
    
    if not release_artifacts_handled:
        recommendations.append("Implement release artifact publishing to make distributions available to users.")
    
    if not artifact_types:
        recommendations.append("No specific artifact types detected. Ensure your build process creates appropriate artifacts for your project type.")
    
    if not recommendations:
        return f"Good artifact management with a score of {score}. Consider improving artifact versioning and distribution strategy."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the artifact management check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Track execution time
        import time
        start_time = time.time()
        
        # Prioritize local path if available
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_artifact_management(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.info(f"Artifact management check completed in {execution_time:.2f}s with score: {result.get('artifact_management_score', 0)}")
        
        # Return the result with the score and metadata
        return {
            "status": "completed",
            "score": result.get("artifact_management_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "artifact_types": result.get("artifact_types", []),
                "storage_locations": result.get("storage_locations", []),
                "has_versioning": result.get("has_versioning", False),
                "ci_artifacts_handled": result.get("ci_artifacts_handled", False),
                "release_artifacts_handled": result.get("release_artifacts_handled", False),
                "execution_time": f"{execution_time:.2f}s",
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_artifact_recommendation(result)
            },
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running artifact management check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }