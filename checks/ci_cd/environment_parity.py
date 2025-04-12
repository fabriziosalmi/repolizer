"""
Environment Parity Check

Checks if the repository maintains consistency across different environments.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_environment_parity(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for environment consistency and parity in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "environments_detected": [],
        "environment_configs_found": False,
        "has_env_separation": False,
        "has_env_variables": False,
        "has_env_promotion": False,
        "has_config_management": False,
        "env_configuration_files": [],
        "environment_variables": [],
        "files_checked": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for environment parity")
        
        # Common environment names
        environment_names = [
            "dev", "development", "test", "testing", "qa", "staging", "stage", 
            "uat", "pre-prod", "preprod", "production", "prod"
        ]
        
        # File patterns that might contain environment configuration
        env_file_patterns = [
            r'\.env\..*', r'env\..*', r'config\..*env.*\.json',
            r'.*\.env\..*', r'application-.*\.properties', r'application-.*\.yml',
            r'terraform\..*\.tfvars', r'.*\.tfvars',
            r'.*/environments/.*', r'.*/env/.*', r'.*/config/.*env.*'
        ]
        
        # Infrastructure definition files
        infra_file_extensions = [
            '.tf', '.yaml', '.yml', '.json', '.template', '.toml', '.properties'
        ]
        
        # CI/CD config files
        ci_file_patterns = [
            '.github/workflows/*.yml', '.github/workflows/*.yaml',
            '.gitlab-ci.yml', 'azure-pipelines.yml',
            'Jenkinsfile', 'circle.yml', '.circleci/config.yml',
            '.travis.yml', 'bitbucket-pipelines.yml'
        ]
        
        # Environment variable definition patterns
        env_var_patterns = [
            r'env(\.|:|,|\s+|=)', r'environment(\.|:|,|\s+|=)',
            r'ENV\w+', r'process\.env', r'os\.environ',
            r'environment:.*\s+name:',
            r'ENVIRONMENT=', r'ENV=',
            r'\.env', r'dotenv'
        ]
        
        # Environment promotion patterns (for checking CI/CD files)
        promotion_patterns = [
            r'promot.*\s+to', r'deploy.*\s+to.*\s+(stag|prod|qa)',
            r'pipeline.*\s+stag(e|ing)', r'pipeline.*\s+prod(uction)?',
            r'approv.*\s+to.*\s+(stag|prod|qa)', r'manual\s+approval',
            r'production\s+deployment', r'release\s+to\s+production',
            r'deploy\s+to\s+environment'
        ]
        
        # Config management patterns
        config_management_patterns = [
            r'config.*\s+management', r'env.*\s+var.*\s+management',
            r'parameterstore', r'secretsmanager', r'vault',
            r'consul.*\s+kv', r'etcd', r'zookeeper',
            r'config(map|uration).*\s+service', r'spring\s+cloud\s+config',
            r'env.*\s+injection'
        ]
        
        files_checked = 0
        env_config_files = []
        environments_found = set()
        environment_vars = set()
        
        # First: Check for environment directory structure
        env_dirs = ["environments", "env", "configs", "deployments", "k8s", "terraform"]
        for env_dir in env_dirs:
            dir_path = os.path.join(repo_path, env_dir)
            if os.path.isdir(dir_path):
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    if os.path.isdir(item_path) and item.lower() in environment_names:
                        environments_found.add(item.lower())
                        result["environment_configs_found"] = True
        
        # Second pass: look for environment configuration files and detect environments
        for root, _, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, repo_path)
                files_checked += 1
                
                # Check for environment-specific names in paths or files
                for env in environment_names:
                    env_pattern = fr'/{env}(?:/|$|\.)|\b{env}\b'
                    if re.search(env_pattern, relative_path, re.IGNORECASE):
                        environments_found.add(env.lower())
                        break
                
                # Check for environment config file patterns
                for pattern in env_file_patterns:
                    if re.search(pattern, relative_path, re.IGNORECASE):
                        result["environment_configs_found"] = True
                        env_config_files.append(relative_path)
                        break
                
                # Check file content for environment configurations
                _, ext = os.path.splitext(file)
                if (ext in infra_file_extensions or 
                    any(re.search(pattern, relative_path, re.IGNORECASE) for pattern in ci_file_patterns) or
                    ".env" in file.lower()):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Look for environment names in the file content
                            for env in environment_names:
                                env_pattern = fr'\b{env}\b'
                                if re.search(env_pattern, content, re.IGNORECASE):
                                    environments_found.add(env.lower())
                            
                            # Check for environment variables
                            for pattern in env_var_patterns:
                                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                                for match in matches:
                                    match_text = match.group(0)
                                    if not result["has_env_variables"]:
                                        result["has_env_variables"] = True
                                    
                                    # Try to extract variable names
                                    var_match = re.search(r'(\w+)=', match_text)
                                    if var_match:
                                        environment_vars.add(var_match.group(1))
                            
                            # Check for environment promotion (CI/CD files)
                            if any(ci_pattern in relative_path for ci_pattern in ['workflow', 'pipeline', 'jenkins', 'travis', 'circle']):
                                for pattern in promotion_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_env_promotion"] = True
                                        break
                            
                            # Check for config management
                            for pattern in config_management_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_config_management"] = True
                                    break
                    
                    except Exception as e:
                        logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Additional check for environment files in .github/workflows
        workflows_dir = os.path.join(repo_path, ".github/workflows")
        if os.path.isdir(workflows_dir):
            for file in os.listdir(workflows_dir):
                if file.endswith(".yml") or file.endswith(".yaml"):
                    file_path = os.path.join(workflows_dir, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Look for environment matrix or environment-specific jobs
                            if re.search(r'matrix:\s+environment:', content, re.IGNORECASE) or \
                               re.search(r'environment:\s*\n\s+name:', content, re.IGNORECASE):
                                result["has_env_separation"] = True
                                
                                # Try to extract environment names from matrix
                                env_matches = re.findall(r'environment:.*\[(.*?)\]', content, re.IGNORECASE | re.DOTALL)
                                if env_matches:
                                    for env_match in env_matches:
                                        for env in environment_names:
                                            if re.search(fr'\b{env}\b', env_match, re.IGNORECASE):
                                                environments_found.add(env.lower())
                    except Exception as e:
                        logger.error(f"Error analyzing workflow file {file_path}: {e}")
        
        # Determine if there is environment separation
        if len(environments_found) >= 2:
            result["has_env_separation"] = True
        
        # Sort and add discovered environments to the result
        result["environments_detected"] = sorted(list(environments_found))
        result["env_configuration_files"] = env_config_files
        result["environment_variables"] = sorted(list(environment_vars))
        result["files_checked"] = files_checked
    
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'environment_parity' in repo_data:
        logger.info("No local repository available. Using API data for environment parity check.")
        
        env_data = repo_data.get('environment_parity', {})
        
        # Update result with environment info from API
        result["environments_detected"] = env_data.get('environments', [])
        result["environment_configs_found"] = env_data.get('configs_found', False)
        result["has_env_separation"] = env_data.get('has_separation', False)
        result["has_env_variables"] = env_data.get('has_variables', False)
        result["has_env_promotion"] = env_data.get('has_promotion', False)
        result["has_config_management"] = env_data.get('has_config_management', False)
    else:
        logger.debug("Using primarily local analysis for environment parity check")
        logger.warning("No local repository path or API data provided for environment parity check")
    
    # Calculate environment parity score (0-100 scale)
    score = 0
    
    # Points for detecting multiple environments
    if result["has_env_separation"]:
        # More environments found means better separation
        env_count_score = min(30, len(result["environments_detected"]) * 10)
        score += env_count_score
    
    # Points for environment configuration files
    if result["environment_configs_found"]:
        # More config files indicate better environment management
        config_files_score = min(20, len(result["env_configuration_files"]) * 2)
        score += config_files_score
    
    # Points for environment variables
    if result["has_env_variables"]:
        score += 15
    
    # Points for environment promotion
    if result["has_env_promotion"]:
        score += 20
    
    # Points for config management
    if result["has_config_management"]:
        score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["environment_parity_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the environment parity check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_environment_parity(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("environment_parity_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running environment parity check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }