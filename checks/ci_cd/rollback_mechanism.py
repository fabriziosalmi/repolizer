"""
Rollback Mechanism Check

Checks if the repository has robust rollback capabilities for deployments.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_rollback_mechanism(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for rollback capabilities in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_rollback_capability": False,
        "rollback_methods": [],
        "has_version_control": False,
        "has_immutable_artifacts": False,
        "has_database_migrations": False,
        "has_canary_deployments": False,
        "has_blue_green_deployments": False,
        "files_with_rollback": [],
        "files_checked": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for rollback mechanisms")
        
        # Rollback methods to check for
        rollback_methods = {
            "manual_rollback": ["rollback", "roll back", "revert deployment"],
            "automated_rollback": ["automated rollback", "auto-rollback", "automatic revert"],
            "k8s_rollout_undo": ["kubectl rollout undo", "rollout undo", "rollout revert"],
            "helm_rollback": ["helm rollback", "helm history", "helm previous"],
            "terraform_state": ["terraform state", "terraform import", "terraform revert"],
            "cloudformation_rollback": ["cloudformation rollback", "stack rollback", "cfn rollback"],
            "database_rollback": ["database rollback", "migration rollback", "downgrade"],
            "ami_snapshot": ["ami rollback", "snapshot restore", "image rollback"],
            "docker_tag_rollback": ["docker rollback", "container rollback", "image revert"],
            "feature_flags": ["feature flag", "feature toggle", "feature switch"],
            "blue_green": ["blue-green", "blue green", "green-blue", "swap environments"],
            "canary_deployments": ["canary deployment", "canary release", "traffic shifting"]
        }
        
        # Files that might contain rollback configurations
        rollback_files = [
            "rollback.sh", "rollback.py", "rollback.js", "rollback.yaml", "rollback.yml",
            "deploy.sh", "deploy.py", "deploy.js", "deploy.yaml", "deploy.yml",
            "Jenkinsfile", "azure-pipelines.yml", "circle.yml", ".circleci/config.yml",
            ".github/workflows/*.yml", ".github/workflows/*.yaml", ".travis.yml",
            "gitlab-ci.yml", "bitbucket-pipelines.yml",
            "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
            "kubernetes/*.yml", "kubernetes/*.yaml", "k8s/*.yml", "k8s/*.yaml",
            "helm/*/templates/*.yaml", "helm/*/templates/*.yml", "helmfile.yaml",
            "terraform/*.tf", "main.tf", "cloudformation/*.yaml", "cloudformation/*.yml",
            "db/migrate/*.rb", "migrations/*.sql", "alembic/*.py", "flyway.conf",
            "liquibase.properties", "changelog.xml"
        ]
        
        # Patterns to detect version control in deployment
        version_control_patterns = [
            r'version\s*[:=]\s*[\'"]?[\d\.]+[\'"]?',
            r'tag\s*[:=]\s*[\'"]?[\d\.]+[\'"]?',
            r'release\s*[:=]\s*[\'"]?[\d\.]+[\'"]?',
            r'git\s+tag',
            r'commit\s+hash',
            r'sha\s*[:=]'
        ]
        
        # Patterns to detect immutable artifacts
        immutable_artifacts_patterns = [
            r'docker\s+build.+\s+tag',
            r'image\s*:.+:[\d\.]+',  # Docker image with version tag
            r'artifact\s+publish',
            r'artifact\s+upload',
            r's3\s+upload',
            r'artifactory\s+upload',
            r'nexus\s+upload',
            r'docker\s+push',
            r'helm\s+package',
            r'package\s+version'
        ]
        
        # Patterns to detect database migrations
        database_migration_patterns = [
            r'migrate', r'migration',
            r'liquibase', r'flyway',
            r'alembic', r'knex',
            r'db-migrate', r'sequelize',
            r'evolve', r'change-set',
            r'schema\s+update',
            r'database\s+rollback',
            r'down\s+function',
            r'downgrade'
        ]
        
        # Patterns to detect canary deployments
        canary_patterns = [
            r'canary', r'progressive',
            r'traffic\s+weight', r'traffic\s+percentage',
            r'istio', r'service\s+mesh',
            r'split\s+traffic',
            r'flagger', r'argo\s+rollouts'
        ]
        
        # Patterns to detect blue-green deployments
        blue_green_patterns = [
            r'blue[_\-\s]+green', r'green[_\-\s]+blue',
            r'production\s+slot', r'staging\s+slot',
            r'swap\s+environment',
            r'swap\s+url',
            r'switch\s+traffic',
            r'zero[_\-\s]+downtime'
        ]
        
        files_checked = 0
        rollback_files_found = []
        methods_found = set()
        
        # First pass: check for rollback-specific files and expand patterns
        expanded_rollback_files = []
        for rollback_file in rollback_files:
            if '*' in rollback_file:
                # Handle glob patterns
                dir_name = os.path.dirname(rollback_file)
                file_pattern = os.path.basename(rollback_file)
                dir_path = os.path.join(repo_path, dir_name)
                
                if os.path.isdir(dir_path):
                    for file in os.listdir(dir_path):
                        if re.match(file_pattern.replace('*', '.*'), file):
                            expanded_file = os.path.join(dir_name, file)
                            expanded_rollback_files.append(expanded_file)
                            
                            # Check if file has 'rollback' in name
                            if 'rollback' in file.lower():
                                result["has_rollback_capability"] = True
                                rollback_files_found.append(expanded_file)
            else:
                expanded_rollback_files.append(rollback_file)
                file_path = os.path.join(repo_path, rollback_file)
                if os.path.isfile(file_path) and 'rollback' in rollback_file.lower():
                    result["has_rollback_capability"] = True
                    rollback_files_found.append(rollback_file)
        
        # Second pass: analyze content of identified files
        for file_path_rel in expanded_rollback_files:
            file_path = os.path.join(repo_path, file_path_rel)
            if not os.path.isfile(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    files_checked += 1
                    
                    # Check for rollback keywords
                    if "rollback" in content or "roll back" in content or "revert" in content:
                        result["has_rollback_capability"] = True
                        if file_path_rel not in rollback_files_found:
                            rollback_files_found.append(file_path_rel)
                    
                    # Check for rollback methods
                    for method, keywords in rollback_methods.items():
                        for keyword in keywords:
                            if keyword.lower() in content and method not in methods_found:
                                methods_found.add(method)
                                break
                    
                    # Check for version control in deployments
                    if not result["has_version_control"]:
                        for pattern in version_control_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_version_control"] = True
                                break
                    
                    # Check for immutable artifacts
                    if not result["has_immutable_artifacts"]:
                        for pattern in immutable_artifacts_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_immutable_artifacts"] = True
                                break
                    
                    # Check for database migrations
                    if not result["has_database_migrations"]:
                        for pattern in database_migration_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_database_migrations"] = True
                                break
                    
                    # Check for canary deployments
                    if not result["has_canary_deployments"]:
                        for pattern in canary_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_canary_deployments"] = True
                                methods_found.add("canary_deployments")
                                break
                    
                    # Check for blue-green deployments
                    if not result["has_blue_green_deployments"]:
                        for pattern in blue_green_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_blue_green_deployments"] = True
                                methods_found.add("blue_green")
                                break
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Also check common CI/CD files if not already checked
        ci_cd_files = [
            ".github/workflows", ".circleci", ".gitlab-ci.yml", "azure-pipelines.yml",
            "Jenkinsfile", "bitbucket-pipelines.yml", ".travis.yml", "deploy.sh", "deploy.py",
            "kubernetes", "k8s", "helm", "terraform", "cloudformation", "docker"
        ]
        
        for ci_dir in ci_cd_files:
            ci_path = os.path.join(repo_path, ci_dir)
            
            if os.path.isdir(ci_path):
                # For directories, check key files
                for root, _, files in os.walk(ci_path):
                    for file in files:
                        if file.endswith(('.yml', '.yaml', '.json', '.tf', '.sh', '.py', '.js')):
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, repo_path)
                            
                            if rel_path not in rollback_files_found:
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read().lower()
                                        files_checked += 1
                                        
                                        # Check for rollback keywords
                                        if "rollback" in content or "roll back" in content or "revert" in content:
                                            result["has_rollback_capability"] = True
                                            rollback_files_found.append(rel_path)
                                            
                                            # Check which rollback methods are present
                                            for method, keywords in rollback_methods.items():
                                                for keyword in keywords:
                                                    if keyword.lower() in content and method not in methods_found:
                                                        methods_found.add(method)
                                                        break
                                        
                                        # Continue checking for other patterns if not already found
                                        if not result["has_version_control"]:
                                            for pattern in version_control_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    result["has_version_control"] = True
                                                    break
                                        
                                        if not result["has_immutable_artifacts"]:
                                            for pattern in immutable_artifacts_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    result["has_immutable_artifacts"] = True
                                                    break
                                        
                                        if not result["has_database_migrations"]:
                                            for pattern in database_migration_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    result["has_database_migrations"] = True
                                                    break
                                        
                                        if not result["has_canary_deployments"]:
                                            for pattern in canary_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    result["has_canary_deployments"] = True
                                                    methods_found.add("canary_deployments")
                                                    break
                                        
                                        if not result["has_blue_green_deployments"]:
                                            for pattern in blue_green_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    result["has_blue_green_deployments"] = True
                                                    methods_found.add("blue_green")
                                                    break
                                
                                except Exception as e:
                                    logger.error(f"Error analyzing CI/CD file {file_path}: {e}")
            
            elif os.path.isfile(ci_path) and ci_path not in rollback_files_found:
                try:
                    with open(ci_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Check for rollback keywords
                        if "rollback" in content or "roll back" in content or "revert" in content:
                            result["has_rollback_capability"] = True
                            rel_path = os.path.relpath(ci_path, repo_path)
                            rollback_files_found.append(rel_path)
                            
                            # Check which rollback methods are present
                            for method, keywords in rollback_methods.items():
                                for keyword in keywords:
                                    if keyword.lower() in content and method not in methods_found:
                                        methods_found.add(method)
                                        break
                        
                        # Continue checking for other patterns if not already found
                        if not result["has_version_control"]:
                            for pattern in version_control_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_version_control"] = True
                                    break
                        
                        if not result["has_immutable_artifacts"]:
                            for pattern in immutable_artifacts_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_immutable_artifacts"] = True
                                    break
                        
                        if not result["has_database_migrations"]:
                            for pattern in database_migration_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_database_migrations"] = True
                                    break
                        
                        if not result["has_canary_deployments"]:
                            for pattern in canary_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_canary_deployments"] = True
                                    methods_found.add("canary_deployments")
                                    break
                        
                        if not result["has_blue_green_deployments"]:
                            for pattern in blue_green_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_blue_green_deployments"] = True
                                    methods_found.add("blue_green")
                                    break
                
                except Exception as e:
                    logger.error(f"Error analyzing CI/CD file {ci_path}: {e}")
    
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'rollback_mechanism' in repo_data:
        logger.info("No local repository available. Using API data for rollback mechanism check.")
        
        rollback_data = repo_data.get('rollback_mechanism', {})
        
        # Update result with rollback info from API
        result["has_rollback_capability"] = rollback_data.get('has_rollback', False)
        result["rollback_methods"] = rollback_data.get('methods', [])
        result["has_version_control"] = rollback_data.get('has_version_control', False)
        result["has_immutable_artifacts"] = rollback_data.get('has_immutable_artifacts', False)
        result["has_database_migrations"] = rollback_data.get('has_database_migrations', False)
        result["has_canary_deployments"] = rollback_data.get('has_canary_deployments', False)
        result["has_blue_green_deployments"] = rollback_data.get('has_blue_green_deployments', False)
    else:
        logger.debug("Using primarily local analysis for rollback mechanism check")
        logger.warning("No local repository path or API data provided for rollback mechanism check")
    
    # Calculate rollback mechanism score (0-100 scale)
    score = 0
    
    # Points for having rollback capability
    if result["has_rollback_capability"]:
        score += 20
    
    # Points for version control in deployments
    if result["has_version_control"]:
        score += 15
    
    # Points for immutable artifacts
    if result["has_immutable_artifacts"]:
        score += 15
    
    # Points for database migrations
    if result["has_database_migrations"]:
        score += 15
    
    # Points for advanced deployment strategies
    if result["has_canary_deployments"]:
        score += 15
    
    if result["has_blue_green_deployments"]:
        score += 15
    
    # Bonus for multiple rollback methods
    method_count_bonus = min(20, len(result["rollback_methods"]) * 5)
    score = min(100, score + method_count_bonus)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["rollback_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the rollback mechanism check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_rollback_mechanism(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("rollback_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running rollback mechanism check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }