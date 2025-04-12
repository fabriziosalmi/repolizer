"""
Artifact Management Check

Checks if the repository has proper artifact handling and storage.
"""
import os
import re
import logging
from typing import Dict, Any, List

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
        "files_checked": 0
    }
    
    # First check if repository is available locally
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for artifact management")
        
        # File types and patterns to check
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
        
        # Patterns to look for in files
        artifact_patterns = [
            # General artifact patterns
            r'artifact',
            r'publish',
            r'upload',
            r'registry',
            r'release',
            r'deploy',
            r'package',
            r'versioning',
            
            # CI-specific artifact patterns
            r'actions/upload-artifact',
            r'actions/download-artifact',
            r'artifacts?:',
            r'cache:',
            r'store_artifacts',
            r'archiveArtifacts',
            r'Save\s+artifact',
            
            # Cloud/registry patterns
            r'docker\s+push',
            r'aws\s+s3',
            r'gcp\s+storage',
            r'azure\s+storage',
            r'maven\s+deploy',
            r'npm\s+publish',
            r'pypi',
            r'nuget\s+push',
            r'artifactory',
            r'jfrog',
            r'nexus',
            r'oci\s+registry'
        ]
        
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
        
        files_checked = 0
        
        # Expand file patterns to include subdirectories
        expanded_file_list = []
        for pattern in ci_config_files + artifact_configs:
            if '*' in pattern:
                # Handle glob patterns
                dir_name = os.path.dirname(pattern)
                file_pattern = os.path.basename(pattern)
                dir_path = os.path.join(repo_path, dir_name)
                
                if os.path.isdir(dir_path):
                    for file in os.listdir(dir_path):
                        if re.match(file_pattern.replace('*', '.*'), file):
                            expanded_file_list.append(os.path.join(dir_name, file))
            else:
                expanded_file_list.append(pattern)
        
        # Check specific files for artifact management configurations
        for file_path_rel in expanded_file_list:
            file_path = os.path.join(repo_path, file_path_rel)
            
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        
                        # Look for artifact patterns
                        for pattern in artifact_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_artifact_storage"] = True
                                
                                # Check for versioning
                                version_patterns = [r'version', r'tag', r'release', r'v\d+\.\d+\.\d+']
                                for ver_pattern in version_patterns:
                                    if re.search(ver_pattern, content, re.IGNORECASE):
                                        result["has_versioning"] = True
                                        break
                                
                                # Check for registry configuration
                                registry_patterns = [r'registry', r'repository', r'storage', r'artifact.*config']
                                for reg_pattern in registry_patterns:
                                    if re.search(reg_pattern, content, re.IGNORECASE):
                                        result["has_registry_config"] = True
                                        break
                                
                                # Check for CI artifacts handling
                                ci_artifact_patterns = [r'ci.*artifact', r'build.*artifact', r'actions/upload-artifact']
                                for ci_pattern in ci_artifact_patterns:
                                    if re.search(ci_pattern, content, re.IGNORECASE):
                                        result["ci_artifacts_handled"] = True
                                        break
                                
                                # Check for release artifacts handling
                                release_patterns = [r'release.*artifact', r'publish.*artifact', r'deploy.*artifact']
                                for rel_pattern in release_patterns:
                                    if re.search(rel_pattern, content, re.IGNORECASE):
                                        result["release_artifacts_handled"] = True
                                        break
                                
                                # Identify artifact types
                                for artifact_type, type_patterns in artifact_type_patterns.items():
                                    for type_pattern in type_patterns:
                                        if re.search(type_pattern, content, re.IGNORECASE) and artifact_type not in result["artifact_types"]:
                                            result["artifact_types"].append(artifact_type)
                                            break
                                
                                # Identify storage locations
                                for storage, storage_patterns in storage_services.items():
                                    for storage_pattern in storage_patterns:
                                        if re.search(storage_pattern, content, re.IGNORECASE) and storage not in result["storage_locations"]:
                                            result["storage_locations"].append(storage)
                                            break
                
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Deeper analysis: Search all root directories for potential artifact indicators
        for root, dirs, files in os.walk(repo_path):
            # Skip common large/irrelevant directories to speed up processing
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
                
            for file in files:
                # Check specific artifact-related file types
                file_path = os.path.join(root, file)
                file_lower = file.lower()
                
                # Check if this is an artifact configuration file we haven't scanned yet
                if file_lower in ['.npmrc', '.pypirc', 'gradle.properties', 'pom.xml', 'nuget.config']:
                    result["has_registry_config"] = True
                    
                    # Check file content for registry information
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            files_checked += 1
                            
                            # Identify storage locations
                            for storage, storage_patterns in storage_services.items():
                                for storage_pattern in storage_patterns:
                                    if re.search(storage_pattern, content, re.IGNORECASE) and storage not in result["storage_locations"]:
                                        result["storage_locations"].append(storage)
                    except Exception as e:
                        logger.error(f"Error checking registry file {file_path}: {e}")
                
                # Check if this is a CI/CD file that might handle artifacts
                elif (file_lower.endswith('.yml') or file_lower.endswith('.yaml')) and 'workflow' in root.lower():
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            files_checked += 1
                            
                            # Look for artifact handling in these CI files
                            if re.search(r'artifact', content, re.IGNORECASE):
                                result["has_artifact_storage"] = True
                                
                                # Check for CI artifacts handling specifically
                                if re.search(r'upload[-_]artifact|store[-_]artifact', content, re.IGNORECASE):
                                    result["ci_artifacts_handled"] = True
                                
                                # Check for versioning
                                if not result["has_versioning"] and re.search(r'version|tag|release', content, re.IGNORECASE):
                                    result["has_versioning"] = True
                    except Exception as e:
                        logger.error(f"Error checking CI file {file_path}: {e}")
                
                # Check build scripts which might handle artifacts
                elif file_lower in ['build.sh', 'build.gradle', 'deploy.sh', 'release.sh', 'Jenkinsfile']:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            files_checked += 1
                            
                            # Check for artifact management
                            if re.search(r'artifact|publish|upload|deploy', content, re.IGNORECASE):
                                result["has_artifact_storage"] = True
                                
                                # Check for release artifact handling
                                if re.search(r'release|deploy|prod', content, re.IGNORECASE):
                                    result["release_artifacts_handled"] = True
                    except Exception as e:
                        logger.error(f"Error checking build script file {file_path}: {e}")
        
        result["files_checked"] = files_checked
        
        # Extra checks to infer artifact management if we have minimal evidence
        if not result["has_artifact_storage"]:
            # If we have Dockerfiles, we probably have artifact management
            if os.path.isfile(os.path.join(repo_path, 'Dockerfile')) or "docker" in result["artifact_types"]:
                result["has_artifact_storage"] = True
                if "docker" not in result["artifact_types"]:
                    result["artifact_types"].append("docker")
                if "docker_registry" not in result["storage_locations"]:
                    result["storage_locations"].append("docker_registry")
            
            # If we have package.json with scripts for publishing, we have artifact management
            package_json_path = os.path.join(repo_path, 'package.json')
            if os.path.isfile(package_json_path):
                try:
                    with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if re.search(r'"publish"|"deploy"|"release"', content, re.IGNORECASE):
                            result["has_artifact_storage"] = True
                            if "npm" not in result["artifact_types"]:
                                result["artifact_types"].append("npm")
                            if "npm_registry" not in result["storage_locations"]:
                                result["storage_locations"].append("npm_registry")
                except Exception:
                    pass
    
    # Only fall back to API data if we don't have meaningful local results
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
    
    # Calculate artifact management score (0-100 scale)
    score = 0
    
    # Points for having artifact storage
    if result["has_artifact_storage"]:
        score += 25
    
    # Points for versioning
    if result["has_versioning"]:
        score += 20
    
    # Points for registry configuration
    if result["has_registry_config"]:
        score += 15
    
    # Points for CI artifacts
    if result["ci_artifacts_handled"]:
        score += 15
    
    # Points for release artifacts
    if result["release_artifacts_handled"]:
        score += 15
    
    # Bonus points for variety of artifact types and storage locations
    artifact_type_score = min(5, len(result["artifact_types"]))
    storage_location_score = min(5, len(result["storage_locations"]))
    score += artifact_type_score + storage_location_score
    
    # Ensure score is within 0-100 range
    score = max(0, min(100, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["artifact_management_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the artifact management check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path if available
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_artifact_management(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("artifact_management_score", 0),
            "result": result,
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