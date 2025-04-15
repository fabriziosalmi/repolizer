"""
Infrastructure as Code Check

Checks if the repository implements Infrastructure as Code (IaC) practices.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_infrastructure_as_code(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for Infrastructure as Code implementations in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_iac": False,
        "iac_tools_detected": [],
        "infrastructure_defined": False,
        "deployment_automated": False,
        "iac_files_count": 0,
        "config_management_used": False,
        "has_iac_tests": False,
        "has_iac_validation": False,
        "iac_directories": [],
        "files_checked": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path} for Infrastructure as Code")
        
        # IaC tool file patterns
        iac_file_patterns = {
            "terraform": [r'\.tf$', r'\.tfvars$', r'terraform\.state$'],
            "cloudformation": [r'\.template$', r'\.json$', r'\.yaml$', r'\.yml$'],
            "ansible": [r'playbook.*\.ya?ml$', r'inventory.*\.ya?ml$', r'roles/.*\.ya?ml$'],
            "puppet": [r'\.pp$', r'Puppetfile$'],
            "chef": [r'\.rb$', r'Berksfile$', r'metadata\.rb$'],
            "kubernetes": [r'deployment\.ya?ml$', r'service\.ya?ml$', r'ingress\.ya?ml$'],
            "docker": [r'Dockerfile$', r'docker-compose\.ya?ml$'],
            "pulumi": [r'Pulumi\.ya?ml$', r'index\.(ts|js|py)$'],
            "serverless": [r'serverless\.ya?ml$', r'\.serverless/'],
            "cdk": [r'cdk\.json$', r'cdk\.out/']
        }
        
        # Directories where IaC files are typically located
        iac_directories = [
            "terraform", "cloudformation", "ansible", "puppet", "chef", 
            "kubernetes", "k8s", "docker", "infrastructure", "infra", 
            "deploy", "deployment", "iac", "stacks", "templates"
        ]
        
        # Patterns to check for IaC validation
        validation_patterns = [
            r'terraform\s+validate', r'terraform\s+plan',
            r'cfn-lint', r'cfn-nag', r'cloudformation\s+validate',
            r'ansible-lint', r'yamllint',
            r'puppet\s+parser\s+validate', r'puppet-lint',
            r'foodcritic', r'cookstyle',
            r'kubeval', r'kubeconform', r'kubectl\s+apply\s+--dry-run',
            r'hadolint', r'dockerlint',
            r'pulumi\s+preview', r'cdk\s+synth'
        ]
        
        # Patterns to check for IaC tests
        test_patterns = [
            r'terratest', r'kitchen-terraform', r'rspec-terraform',
            r'cfn-test', r'taskcat',
            r'molecule', r'ansible-test',
            r'rspec-puppet', r'puppet\s+spec',
            r'inspec', r'kitchen-test',
            r'goss', r'container-structure-test',
            r'infra.*\s+test', r'test.*\s+infra'
        ]
        
        # Patterns for automated deployment
        deployment_patterns = [
            r'terraform\s+apply', r'terragrunt\s+apply',
            r'aws\s+cloudformation\s+deploy', r'sam\s+deploy',
            r'ansible-playbook', r'ansible\s+run',
            r'puppet\s+apply',
            r'chef\s+client', r'chef\s+apply',
            r'kubectl\s+apply', r'helm\s+install', r'helm\s+upgrade',
            r'docker\s+stack\s+deploy', r'docker-compose\s+up',
            r'pulumi\s+up', r'cdk\s+deploy'
        ]
        
        # Check for config management
        config_management_patterns = [
            r'variables\.tf', r'\.tfvars',
            r'Parameters:', r'Outputs:',
            r'vars:', r'defaults:',
            r'hiera', r'hieradata',
            r'attributes/', r'data_bags/',
            r'ConfigMap', r'Secret',
            r'.env', r'environment:'
        ]
        
        files_checked = 0
        iac_files_found = 0
        tool_matches = {tool: 0 for tool in iac_file_patterns}
        directory_matches = set()
        
        # First pass: look for IaC directories and files
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
            
            # Check if we're in a potential IaC directory
            relative_path = os.path.relpath(root, repo_path)
            base_dir = relative_path.split(os.sep)[0] if os.sep in relative_path else relative_path
            
            if base_dir.lower() in [d.lower() for d in iac_directories]:
                directory_matches.add(base_dir)
                
            # Check files
            for file in files:
                file_path = os.path.join(root, file)
                files_checked += 1
                
                # Check for IaC file patterns
                for tool, patterns in iac_file_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, file, re.IGNORECASE):
                            result["has_iac"] = True
                            iac_files_found += 1
                            tool_matches[tool] += 1
                            
                            # Add to iac directories if not already present
                            if base_dir not in result["iac_directories"]:
                                result["iac_directories"].append(base_dir)
                            
                            # We found a match, no need to check other patterns for this file
                            break
        
        # Add detected tools to result
        for tool, count in tool_matches.items():
            if count > 0 and tool not in result["iac_tools_detected"]:
                result["iac_tools_detected"].append(tool)
        
        # Second pass: analyze content of IaC files for validation, testing, and deployment
        has_validation = False
        has_tests = False
        has_deployment = False
        has_config_management = False
        
        if result["has_iac"]:
            # Look for CI/CD files that might contain IaC validation or deployment
            ci_cd_files = [
                ".github/workflows/*.yml", ".github/workflows/*.yaml",
                ".gitlab-ci.yml", "azure-pipelines.yml",
                "Jenkinsfile", ".circleci/config.yml",
                ".travis.yml", "bitbucket-pipelines.yml"
            ]
            
            for ci_pattern in ci_cd_files:
                if '*' in ci_pattern:
                    # Handle glob patterns
                    dir_name = os.path.dirname(ci_pattern)
                    file_pattern = os.path.basename(ci_pattern)
                    dir_path = os.path.join(repo_path, dir_name)
                    
                    if os.path.isdir(dir_path):
                        for file in os.listdir(dir_path):
                            if re.match(file_pattern.replace('*', '.*'), file):
                                ci_file_path = os.path.join(dir_path, file)
                                try:
                                    with open(ci_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        
                                        # Check for validation
                                        if not has_validation:
                                            for pattern in validation_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    has_validation = True
                                                    break
                                        
                                        # Check for deployment
                                        if not has_deployment:
                                            for pattern in deployment_patterns:
                                                if re.search(pattern, content, re.IGNORECASE):
                                                    has_deployment = True
                                                    break
                                except Exception as e:
                                    logger.error(f"Error analyzing CI file {ci_file_path}: {e}")
                else:
                    ci_file_path = os.path.join(repo_path, ci_pattern)
                    if os.path.isfile(ci_file_path):
                        try:
                            with open(ci_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                # Check for validation
                                if not has_validation:
                                    for pattern in validation_patterns:
                                        if re.search(pattern, content, re.IGNORECASE):
                                            has_validation = True
                                            break
                                
                                # Check for deployment
                                if not has_deployment:
                                    for pattern in deployment_patterns:
                                        if re.search(pattern, content, re.IGNORECASE):
                                            has_deployment = True
                                            break
                        except Exception as e:
                            logger.error(f"Error analyzing CI file {ci_file_path}: {e}")
            
            # Check iac directories for IaC files and analyze them
            for root, _, files in os.walk(repo_path):
                # Skip non-IaC directories to speed up analysis
                relative_path = os.path.relpath(root, repo_path)
                base_dir = relative_path.split(os.sep)[0] if os.sep in relative_path else relative_path
                
                if base_dir not in result["iac_directories"] and not any(d.lower() in relative_path.lower() for d in iac_directories):
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Check if this is an IaC file
                    is_iac_file = False
                    for patterns in iac_file_patterns.values():
                        if any(re.search(pattern, file, re.IGNORECASE) for pattern in patterns):
                            is_iac_file = True
                            break
                    
                    # For IaC files, check content
                    if is_iac_file:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                result["infrastructure_defined"] = True
                                
                                # Check for config management
                                if not has_config_management:
                                    for pattern in config_management_patterns:
                                        if re.search(pattern, content, re.IGNORECASE):
                                            has_config_management = True
                                            break
                        except Exception as e:
                            logger.error(f"Error analyzing IaC file {file_path}: {e}")
                    
                    # Check test directories for IaC testing
                    if not has_tests and ('test' in file_path.lower() or 'spec' in file_path.lower()):
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                for pattern in test_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        has_tests = True
                                        break
                        except Exception as e:
                            logger.error(f"Error analyzing test file {file_path}: {e}")
        
        result["files_checked"] = files_checked
        result["iac_files_count"] = iac_files_found
        result["has_iac_validation"] = has_validation
        result["has_iac_tests"] = has_tests
        result["deployment_automated"] = has_deployment
        result["config_management_used"] = has_config_management
    
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'infrastructure_as_code' in repo_data:
        logger.info("No local repository available. Using API data for Infrastructure as Code check.")
        
        iac_data = repo_data.get('infrastructure_as_code', {})
        
        # Update result with IaC info from API
        result["has_iac"] = iac_data.get('has_iac', False)
        result["iac_tools_detected"] = iac_data.get('tools', [])
        result["infrastructure_defined"] = iac_data.get('infrastructure_defined', False)
        result["deployment_automated"] = iac_data.get('deployment_automated', False)
        result["iac_files_count"] = iac_data.get('files_count', 0)
        result["config_management_used"] = iac_data.get('config_management_used', False)
        result["has_iac_tests"] = iac_data.get('has_tests', False)
        result["has_iac_validation"] = iac_data.get('has_validation', False)
    else:
        logger.debug("Using primarily local analysis for Infrastructure as Code check")
        logger.warning("No local repository path or API data provided for Infrastructure as Code check")
    
    # Calculate IaC score (0-100 scale)
    score = 0
    
    # Points for having IaC
    if result["has_iac"]:
        score += 30
        
        # Points for infrastructure defined in code
        if result["infrastructure_defined"]:
            score += 15
        
        # Points for automated deployment
        if result["deployment_automated"]:
            score += 15
        
        # Points for validation
        if result["has_iac_validation"]:
            score += 15
        
        # Points for testing
        if result["has_iac_tests"]:
            score += 15
        
        # Points for config management
        if result["config_management_used"]:
            score += 10
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["iac_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the Infrastructure as Code check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_infrastructure_as_code(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("iac_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running Infrastructure as Code check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }