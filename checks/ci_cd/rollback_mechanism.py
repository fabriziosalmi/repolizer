"""
Rollback Mechanism Check

Checks if the repository has robust rollback capabilities for deployments.
"""
import os
import re
import logging
import time
import signal
from typing import Dict, Any, List
from functools import wraps
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Exception raised when a function times out."""
    pass

def timeout(seconds=60):
    """
    Decorator to timeout a function after specified seconds.
    
    Args:
        seconds: Maximum seconds to allow function to run
        
    Returns:
        Decorated function with timeout capability
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handle_timeout(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # Set the timeout handler
            original_handler = signal.signal(signal.SIGALRM, handle_timeout)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Reset the alarm and restore the original handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
            return result
        return wrapper
    return decorator

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
    
    # Calculate rollback mechanism score with enhanced logic
    return calculate_rollback_score(result)

def calculate_rollback_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate a more nuanced score for the rollback mechanisms.
    
    Args:
        result: The result dictionary with rollback mechanism analysis
        
    Returns:
        Updated result dictionary with calculated score
    """
    # Start with base score - adjust the floor to 1 (not 0) for existing systems
    base_score = 1
    
    # Store scoring components for transparency
    scoring_components = []
    
    # Base points for having any rollback capability
    if result["has_rollback_capability"]:
        base_points = 20
        base_score += base_points
        scoring_components.append(f"Base rollback capability: +{base_points}")
    
    # First dimension: Rollback foundation 
    foundation_score = 0
    
    # Version control in deployments is crucial for rollbacks
    if result["has_version_control"]:
        version_points = 15
        foundation_score += version_points
        scoring_components.append(f"Version-controlled deployments: +{version_points}")
    
    # Immutable artifacts ensure consistent rollbacks
    if result["has_immutable_artifacts"]:
        immutable_points = 15
        foundation_score += immutable_points
        scoring_components.append(f"Immutable deployment artifacts: +{immutable_points}")
    
    # Second dimension: Advanced rollback techniques
    techniques_score = 0
    
    # Database migrations with rollback capability
    if result["has_database_migrations"]:
        db_points = 10
        techniques_score += db_points
        scoring_components.append(f"Database migration rollbacks: +{db_points}")
    
    # Modern deployment strategies with built-in rollback
    if result["has_canary_deployments"]:
        canary_points = 10
        techniques_score += canary_points
        scoring_components.append(f"Canary deployment rollbacks: +{canary_points}")
    
    if result["has_blue_green_deployments"]:
        blue_green_points = 10
        techniques_score += blue_green_points
        scoring_components.append(f"Blue-green deployment rollbacks: +{blue_green_points}")
    
    # Third dimension: Rollback method diversity
    methods_count = len(result.get("rollback_methods", []))
    if methods_count > 0:
        # Give points for each method, but cap at 20
        methods_points = min(20, methods_count * 4)
        scoring_components.append(f"Multiple rollback methods ({methods_count}): +{methods_points}")
        
        # Add total score from all dimensions
        total_dimension_score = min(80, foundation_score + techniques_score + methods_points)
        base_score += total_dimension_score
    else:
        # Add total score from just foundation and techniques dimensions
        total_dimension_score = min(60, foundation_score + techniques_score)
        base_score += total_dimension_score
    
    # Final score should be between 1-100
    final_score = min(100, max(1, base_score))
    
    # Determine rollback maturity category
    if final_score >= 85:
        maturity_category = "excellent"
        maturity_description = "Comprehensive rollback system with multiple methods and advanced deployment strategies"
    elif final_score >= 70:
        maturity_category = "good"
        maturity_description = "Solid rollback capability with version control and at least one advanced deployment strategy"
    elif final_score >= 50:
        maturity_category = "moderate"
        maturity_description = "Basic rollback system with version control but limited advanced capabilities"
    elif final_score >= 30:
        maturity_category = "basic"
        maturity_description = "Minimal rollback capability present but lacking robust mechanisms"
    else:
        maturity_category = "limited"
        maturity_description = "Very limited or no rollback capability detected"
    
    # Generate suggestions based on the analysis
    suggestions = []
    
    if not result["has_rollback_capability"]:
        suggestions.append("Implement basic rollback mechanisms for your deployments")
    else:
        if not result["has_version_control"]:
            suggestions.append("Implement version control for deployments to enable reliable rollbacks")
        
        if not result["has_immutable_artifacts"]:
            suggestions.append("Use immutable artifacts (e.g., versioned Docker images) to ensure consistent rollbacks")
        
        if not result["has_database_migrations"]:
            suggestions.append("Add database migration rollback capability to prevent data inconsistencies")
        
        if not result["has_blue_green_deployments"] and not result["has_canary_deployments"]:
            suggestions.append("Consider implementing blue-green or canary deployments for safer rollbacks")
        
        if len(result.get("rollback_methods", [])) < 2:
            suggestions.append("Implement multiple rollback methods for different failure scenarios")
    
    # Round score to nearest integer
    result["rollback_score"] = round(final_score)
    
    # Add metadata to result
    result["metadata"] = {
        "score_components": scoring_components,
        "maturity_category": maturity_category,
        "maturity_description": maturity_description,
        "suggestions": suggestions,
        "analysis_timestamp": datetime.now().isoformat(),
    }
    
    return result

@timeout(60)  # Apply 1-minute timeout to the check function
def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the rollback mechanism check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    start_time = time.time()
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_rollback_mechanism(local_path, repository)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Return the result with the score and metadata
        return {
            "status": "completed",
            "score": result.get("rollback_score", 0),
            "result": result,
            "errors": None,
            "processing_time_seconds": round(processing_time, 2),
            "suggestions": result.get("metadata", {}).get("suggestions", []),
            "timestamp": datetime.now().isoformat()
        }
    except TimeoutError as e:
        logger.error(f"Timeout error in rollback mechanism check: {e}")
        return {
            "status": "timeout",
            "score": 0,
            "result": {},
            "errors": str(e),
            "processing_time_seconds": 60.0,
            "suggestions": ["Consider optimizing repository structure to improve check performance"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running rollback mechanism check: {e}", exc_info=True)
        processing_time = time.time() - start_time
        return {
            "status": "failed", 
            "score": 0,
            "result": {},
            "errors": f"{type(e).__name__}: {str(e)}",
            "processing_time_seconds": round(processing_time, 2),
            "suggestions": ["Fix errors in repository configuration to enable proper rollback analysis"],
            "timestamp": datetime.now().isoformat()
        }