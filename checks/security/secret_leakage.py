import os
import re
import logging
from typing import Dict, Any, List, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_secret_leakage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for accidentally committed secrets and credentials
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for secret leakage analysis
    """
    result = {
        "has_secrets": False,
        "potential_secrets_found": 0,
        "secret_types_found": [],
        "secret_locations": [],
        "has_env_usage": False,
        "has_secret_management": False,
        "has_gitignore_for_secrets": False,
        "files_checked": 0,
        "secret_leakage_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Secret patterns by type
    secret_patterns = {
        "api_key": [
            r'api[-_\s]?key[\s:=]+[\'"`][^\s\'"`]{12,}[\'"`]',
            r'api[-_\s]token[\s:=]+[\'"`][^\s\'"`]{12,}[\'"`]',
            r'access[-_\s]?key[\s:=]+[\'"`][^\s\'"`]{12,}[\'"`]',
            r'access[-_\s]token[\s:=]+[\'"`][^\s\'"`]{16,}[\'"`]',
            r'key[\s:=]+[\'"`][a-zA-Z0-9_\-\.]{16,}[\'"`]'
        ],
        "password": [
            r'password[\s:=]+[\'"`][^\s\'"`]{6,}[\'"`]',
            r'passwd[\s:=]+[\'"`][^\s\'"`]{6,}[\'"`]',
            r'pwd[\s:=]+[\'"`][^\s\'"`]{6,}[\'"`]',
            r'pass[\s:=]+[\'"`][^\s\'"`]{6,}[\'"`]'
        ],
        "database_url": [
            r'(?:mysql|postgresql|mongodb|redis)://[a-zA-Z0-9_\-\.:]+:[a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+:[0-9]+\/[a-zA-Z0-9_\-\.]+',
            r'database[-_\s]?url[\s:=]+[\'"`][^\s\'"`]{12,}[\'"`]',
            r'connection[-_\s]?string[\s:=]+[\'"`][^\s\'"`]{12,}[\'"`]',
            r'jdbc:[a-zA-Z0-9]+:[a-zA-Z0-9_\-\.]+:[a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+:[0-9]+'
        ],
        "aws_keys": [
            r'(?:aws|amazon)[-_\s]?access[-_\s]?key[-_\s]?id[\s:=]+[\'"`][A-Z0-9]{16,}[\'"`]',
            r'(?:aws|amazon)[-_\s]?secret[-_\s]?access[-_\s]?key[\s:=]+[\'"`][A-Za-z0-9/+=]{40}[\'"`]',
            r'AKIA[0-9A-Z]{16}'
        ],
        "oauth_tokens": [
            r'oauth[-_\s]?token[\s:=]+[\'"`][a-zA-Z0-9_\-\.]{16,}[\'"`]',
            r'refresh[-_\s]?token[\s:=]+[\'"`][a-zA-Z0-9_\-\.]{16,}[\'"`]',
            r'access[-_\s]?token[\s:=]+[\'"`][a-zA-Z0-9_\-\.]{16,}[\'"`]'
        ],
        "private_keys": [
            r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----',
            r'-----BEGIN\s+PRIVATE\s+KEY-----',
            r'private[-_\s]?key[\s:=]+[\'"`][^\s\'"`]{16,}[\'"`]'
        ],
        "jwt_tokens": [
            r'ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*'
        ]
    }
    
    # Pattern to identify dummy/example keys (to reduce false positives)
    dummy_key_patterns = [
        r'example',
        r'placeholder',
        r'dummy',
        r'sample',
        r'test',
        r'xxxx',
        r'your[-_\s]?key',
        r'changeme',
        r'your_',
        r'dummy_',
        r'x{8,}',
        r'0{8,}',
        r'11111111',
        r'abcdef'
    ]
    
    # Files to check
    files_to_scan = []
    
    # Files that should be excluded from scanning
    excluded_dirs = [
        '.git', 'node_modules', 'vendor', 'venv', 'env', 'tests',
        'dist', 'build', 'coverage', '.github', '.gitlab', '.idea', 
        '.vscode', '__pycache__', '.pytest_cache', 'docs'
    ]
    
    excluded_files = [
        'package-lock.json', 'yarn.lock', 'composer.lock', 'Gemfile.lock',
        'poetry.lock', 'go.sum', 'requirements.txt', 'package.json',
        'example.env', 'example.config', 'sample.env', 'readme.md', 
        'readme.txt', 'changelog.md', 'license.txt', 'license.md'
    ]
    
    # Files that might contain environment variable usage or secret management
    env_files = [
        '.env.example', '.env.sample', '.env.template',
        'config.example.js', 'config.sample.js',
        'app.config.js', 'settings.example.py'
    ]
    
    # Secret management tools
    secret_management_patterns = [
        r'vault', r'secret[-_\s]?manager', r'keychain', r'hashicorp',
        r'aws[-_\s]?secretsmanager', r'aws[-_\s]?kms', r'azurekv',
        r'azure[-_\s]?key[-_\s]?vault', r'gcp[-_\s]?secretmanager',
        r'doppler', r'keychain', r'keystone', r'chamber', r'credstash',
        r'ssm', r'parameterstore', r'secrets[-_\s]?store', r'lockbox',
        r'env\.decrypt', r'key[-_\s]?protect', r'secrets\.yml'
    ]
    
    # Environment variable usage patterns
    env_usage_patterns = [
        r'process\.env', r'os\.(?:environ|getenv)', 
        r'System\.getenv', r'dotenv', r'env\[', r'ENV\[',
        r'environment\.',r'getEnvironment', r'System\.get(Property|Properties)',
        r'secrets\.', r'config\.from_object', r'load_dotenv',
        r'\${[^}]+}', r'\$[A-Za-z_][A-Za-z0-9_]*', r'%[A-Za-z_][A-Za-z0-9_]*%'
    ]
    
    # Check for .gitignore with secret-related entries
    gitignore_path = os.path.join(repo_path, '.gitignore')
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if any(pattern in content for pattern in ['.env', '*.env', 'secrets', 'credentials', 'keys', '*.pem', '*.key']):
                    result["has_gitignore_for_secrets"] = True
        except Exception as e:
            logger.warning(f"Error reading .gitignore: {e}")
    
    # Collect files for scanning
    files_checked = 0
    
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        
        for file in files:
            file_lower = file.lower()
            
            # Skip excluded files
            if file_lower in excluded_files:
                continue
            
            # Skip binary files and large files
            file_path = os.path.join(root, file)
            
            try:
                file_size = os.path.getsize(file_path)
                if file_size > 1000000:  # Skip files > 1MB
                    continue
                
                # Check file extension
                _, ext = os.path.splitext(file_lower)
                if ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.ttf', '.eot', '.mp3', '.mp4', '.avi', '.zip', '.pdf']:
                    continue
                
                # Add file for scanning
                files_to_scan.append(file_path)
                
                # Check if this is an env example file
                if file in env_files:
                    result["has_env_usage"] = True
                    
            except (OSError, IOError) as e:
                logger.warning(f"Error accessing file {file_path}: {e}")
                continue
    
    # Track secret types found
    secret_types_found = set()
    potential_secrets = 0
    secret_locations = []
    
    # Analyze files for secrets
    for file_path in files_to_scan:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                files_checked += 1
                
                # Check for environment variable usage
                if not result["has_env_usage"]:
                    if any(re.search(pattern, content) for pattern in env_usage_patterns):
                        result["has_env_usage"] = True
                
                # Check for secret management tools
                if not result["has_secret_management"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in secret_management_patterns):
                        result["has_secret_management"] = True
                
                # Look for secrets
                for secret_type, patterns in secret_patterns.items():
                    for pattern in patterns:
                        matches = re.finditer(pattern, content)
                        
                        for match in matches:
                            match_text = match.group(0)
                            
                            # Skip if it looks like a dummy/example key
                            if any(re.search(dummy, match_text, re.IGNORECASE) for dummy in dummy_key_patterns):
                                continue
                            
                            # Count it as a potential secret
                            potential_secrets += 1
                            secret_types_found.add(secret_type)
                            
                            # Store location information (limit to 10 to avoid overwhelming)
                            if len(secret_locations) < 10:
                                relative_path = os.path.relpath(file_path, repo_path)
                                
                                # Calculate line number by counting newlines before the secret
                                content_before_match = content[:match.start()]
                                line_number = content_before_match.count('\n') + 1
                                
                                secret_locations.append({
                                    "file": relative_path,
                                    "line": line_number,
                                    "type": secret_type,
                                    "snippet": mask_secret(match_text)
                                })
                
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
    
    # Update results
    result["potential_secrets_found"] = potential_secrets
    result["secret_types_found"] = list(secret_types_found)
    result["secret_locations"] = secret_locations
    result["has_secrets"] = potential_secrets > 0
    result["files_checked"] = files_checked
    
    # Calculate secret leakage score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on secret leakage findings.
        
        The score consists of:
        - Base score (starts at 100 and decreases with secrets found)
        - Penalty for each secret found (graduated, more severe for more secrets)
        - Penalty based on secret types (more sensitive types = higher penalty)
        - Bonus for good security practices (env usage, secret management, gitignore)
        
        Final score is normalized to 0-100 range.
        """
        # Start with full score and deduct based on findings
        base_score = 100
        
        # Extract required values
        secrets_found = result_data.get("potential_secrets_found", 0)
        secret_types = result_data.get("secret_types_found", [])
        has_env_usage = result_data.get("has_env_usage", False)
        has_secret_management = result_data.get("has_secret_management", False)
        has_gitignore = result_data.get("has_gitignore_for_secrets", False)
        
        # No deduction if no secrets found
        if secrets_found == 0:
            secret_penalty = 0
        else:
            # Graduated penalty calculation - more secrets = exponentially higher penalty
            if secrets_found == 1:
                secret_penalty = 20  # Single secret is still bad
            elif secrets_found <= 3:
                secret_penalty = 30  # A few secrets
            elif secrets_found <= 5:
                secret_penalty = 40  # Several secrets
            elif secrets_found <= 10:
                secret_penalty = 50  # Many secrets
            else:
                secret_penalty = 60  # Severe leakage
        
        # Additional penalty based on types of secrets found
        # Some secrets are more critical than others
        type_penalty = 0
        high_severity_types = ["private_keys", "aws_keys", "database_url"]
        medium_severity_types = ["password", "api_key", "oauth_tokens"]
        
        for secret_type in secret_types:
            if secret_type in high_severity_types:
                type_penalty += 10
            elif secret_type in medium_severity_types:
                type_penalty += 5
        
        # Cap type penalty
        type_penalty = min(20, type_penalty)
        
        # Calculate raw score after penalties
        raw_score = base_score - secret_penalty - type_penalty
        
        # Bonus for good security practices
        practice_bonus = 0
        
        if has_env_usage:
            practice_bonus += 15
        
        if has_secret_management:
            practice_bonus += 15
        
        if has_gitignore:
            practice_bonus += 10
        
        # Apply bonus, but can't exceed 100 or go below 0
        final_score = min(100, max(0, raw_score + practice_bonus))
        
        # Ensure very insecure repositories don't get high scores even with bonuses
        if secrets_found > 5 and final_score > 60:
            final_score = 60
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "secret_penalty": secret_penalty,
            "type_penalty": type_penalty,
            "practice_bonus": practice_bonus,
            "raw_score": raw_score,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["secret_leakage_score"] = calculate_score(result)
    
    return result

def mask_secret(secret_text: str) -> str:
    """Mask a secret to avoid exposing it in reports"""
    if len(secret_text) < 8:
        return '********'
    
    # Keep first 2 and last 2 characters, mask the rest
    return secret_text[:2] + '*' * (len(secret_text) - 4) + secret_text[-2:]

def get_secret_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the check results"""
    secrets_found = result.get("potential_secrets_found", 0)
    secret_types = result.get("secret_types_found", [])
    has_env = result.get("has_env_usage", False)
    has_secret_mgmt = result.get("has_secret_management", False)
    has_gitignore = result.get("has_gitignore_for_secrets", False)
    
    if secrets_found == 0:
        if has_env and has_secret_mgmt:
            return "Excellent secret management. No secrets detected and proper environment variable usage."
        elif has_env:
            return "Good practice using environment variables. Consider adding dedicated secret management."
        else:
            return "No secrets detected, but consider implementing environment variables for any future credentials."
    
    recommendations = []
    
    if secrets_found > 0:
        recommendations.append(f"Remove the {secrets_found} potential secrets found in the repository and rotate those credentials immediately.")
    
    if not has_env:
        recommendations.append("Use environment variables or a secrets manager instead of hardcoding sensitive information.")
    
    if not has_secret_mgmt:
        recommendations.append("Implement a dedicated secret management solution like HashiCorp Vault, AWS Secrets Manager, or similar.")
    
    if not has_gitignore:
        recommendations.append("Configure .gitignore to prevent committing common secrets files like .env or credentials files.")
    
    high_severity_types = {"private_keys", "aws_keys", "database_url"}
    if any(secret_type in high_severity_types for secret_type in secret_types):
        recommendations.append("URGENT: High-severity credentials detected. Rotate these credentials immediately.")
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the secret leakage check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"secret_leakage_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached secret leakage check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        if not local_path:
            logger.warning("No local repository path provided")
            return {
                "status": "partial",
                "score": 0,
                "result": {"message": "No local repository path available for analysis"},
                "errors": "Missing repository path"
            }
        
        # Run the check
        result = check_secret_leakage(local_path, repository)
        
        logger.info(f"Secret leakage check completed with score: {result.get('secret_leakage_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("secret_leakage_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "potential_secrets": result.get("potential_secrets_found", 0),
                "secret_types": result.get("secret_types_found", []),
                "security_practices": {
                    "env_variables": result.get("has_env_usage", False),
                    "secret_management": result.get("has_secret_management", False),
                    "gitignore_config": result.get("has_gitignore_for_secrets", False)
                },
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_secret_recommendation(result)
            },
            "errors": None
        }
    except FileNotFoundError as e:
        error_msg = f"Repository files not found: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except PermissionError as e:
        error_msg = f"Permission denied accessing repository files: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except Exception as e:
        error_msg = f"Error running secret leakage check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }