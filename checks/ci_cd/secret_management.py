"""
Secret Management Check

Checks if the repository has proper secret management practices.
"""
import os
import re
import logging
import base64
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_secret_management(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secret management practices in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_secret_management": False,
        "secret_tools": [],
        "has_env_variables": False,
        "has_vault_integration": False,
        "potential_hardcoded_secrets": [],
        "has_gitignore_for_secrets": False,
        "has_encrypted_secrets": False,
        "best_practices_followed": False,
        "files_checked": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for secret management")
        
        # Secret management tools to check for
        secret_tools = {
            "vault": ["vault", "hashicorp vault", "vault.read", "vault-client"],
            "aws_secrets": ["aws secretsmanager", "secretsmanager", "aws secrets"],
            "gcp_secrets": ["google secret manager", "secret manager", "gcp secret"],
            "azure_keyvault": ["azure key vault", "keyvault", "azure vault"],
            "doppler": ["doppler", "doppler-secrets"],
            "sops": ["sops", "mozilla sops"],
            "sealed_secrets": ["sealed-secrets", "kubeseal"],
            "env_variables": [".env", "env.yaml", "env.yml", "environment variables"],
            "github_secrets": ["github secrets", "GITHUB_TOKEN", "github.token"],
            "gitlab_ci_variables": ["gitlab ci variables", "CI_JOB_TOKEN"],
            "ansible_vault": ["ansible-vault", "ansible vault"],
            "credstash": ["credstash"],
            "bitwarden": ["bitwarden", "bw get"]
        }
        
        # Files that might indicate secret management
        secret_management_files = [
            ".env", ".env.example", ".env.sample", ".env.template",
            "secrets.yaml", "secrets.yml", "secrets.json", "secrets.properties",
            "vault.yaml", "vault.yml", "vault.json", "vault.hcl", "vault.policy",
            "secretsmanager.yaml", "secretsmanager.yml", "secretsmanager.json",
            "keyvault.yaml", "keyvault.yml", "keyvault.json",
            "doppler.yaml", "doppler.yml", "doppler.json",
            "sops.yaml", "sops.yml", ".sops.yaml", ".sops.yml",
            "sealed-secrets.yaml", "sealed-secrets.yml",
            "ansible-vault-password.txt", ".vault_pass", ".vault-password"
        ]
        
        # Directories that might contain secret management configurations
        secret_management_dirs = [
            "secrets", "vault", "secretsmanager", "keyvault",
            "credentials", "secure", "encrypted", "env"
        ]
        
        # Patterns for potential hardcoded secrets (basic checks)
        potential_secret_patterns = [
            # API keys, tokens, credentials
            r'(?:access|api|app|auth)_?(key|token|secret)[\s=:]+[\'"`][^\s\'"`]{16,}[\'"`]',
            r'(?:password|passwd|pwd)[\s=:]+[\'"`][^\s\'"`]{8,}[\'"`]',
            r'(?:secret|token)[\s=:]+[\'"`][^\s\'"`]{8,}[\'"`]',
            
            # AWS
            r'(?:aws|AWS).?(?:access|secret).?(?:key|token)[\s=:]+[\'"`][^\s\'"`]{16,}[\'"`]',
            r'[\'"`](?:AKIA|ASIA)[A-Z0-9]{16}[\'"`]',  # AWS access key pattern
            
            # Database connection strings
            r'(?:mongodb|postgres|mysql|mariadb|jdbc|redis|database).*(?:\/\/|\@).*[\'"`]',
            
            # OAuth
            r'(?:oauth|client)_?(?:id|token|secret)[\s=:]+[\'"`][^\s\'"`]{16,}[\'"`]',
            
            # Private keys
            r'BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY',
            
            # GCP
            r'[\'"`](?:project|service-account).*google.*\.com[\'"`]',
            
            # Azure
            r'[\'"`](?:[a-zA-Z0-9][-a-zA-Z0-9]{3,}\.[a-zA-Z0-9()]{1,30}\.(?:windows\.net|database\.azure\.com))[\'"`]',
            
            # Slack, GitHub, CI services
            r'(?:slack|github|travis|circle|jenkins).*token[\s=:]+[\'"`][^\s\'"`]{8,}[\'"`]'
        ]
        
        # CI/CD configuration files that might contain secret management setup
        ci_files = [
            ".github/workflows/*.yml", ".github/workflows/*.yaml",
            ".gitlab-ci.yml", "azure-pipelines.yml",
            "Jenkinsfile", "circle.yml", ".circleci/config.yml",
            ".travis.yml", "bitbucket-pipelines.yml"
        ]
        
        # Check if there's a .gitignore for secret files
        gitignore_path = os.path.join(repo_path, ".gitignore")
        if os.path.isfile(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Common patterns for ignoring secret files
                    secret_ignore_patterns = [
                        ".env", "*.env", ".env.*", "env.*",
                        "secret", "secrets", "credentials", "creds",
                        ".vault_pass", "vault-password", 
                        "*.pem", "*.key", "id_rsa", "*.jks", "*.p12",
                        "*.password", "*.secret", "*.token", "*.apikey"
                    ]
                    
                    for pattern in secret_ignore_patterns:
                        if pattern in content:
                            result["has_gitignore_for_secrets"] = True
                            break
            except Exception as e:
                logger.error(f"Error reading .gitignore file: {e}")
        
        files_checked = 0
        secret_files_found = []
        tools_found = set()
        has_potential_secrets = False
        
        # First pass: check for secret management files and directories
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
            
            # Check if directory is related to secret management
            for secret_dir in secret_management_dirs:
                if f"/{secret_dir}/" in root.lower() or root.lower().endswith(f"/{secret_dir}"):
                    result["has_secret_management"] = True
                    
                    # Add files in secret management directories
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_path)
                        secret_files_found.append(rel_path)
            
            # Check for secret management files
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Check for specific secret management files
                if file.lower() in [f.lower() for f in secret_management_files] or any(rel_path.lower().endswith(f"/{f.lower()}") for f in secret_management_files):
                    result["has_secret_management"] = True
                    if rel_path not in secret_files_found:
                        secret_files_found.append(rel_path)
                    
                    # Check if the file is a .env file or template
                    if file.lower().startswith(".env"):
                        result["has_env_variables"] = True
                        tools_found.add("env_variables")
                
                # Check for CI files that might contain secret management
                _, ext = os.path.splitext(file)
                if ext.lower() in ['.yml', '.yaml', '.json', '.gradle', '.xml'] or file in ['Jenkinsfile', 'Dockerfile']:
                    files_checked += 1
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            
                            # Check for mentions of secret management tools
                            for tool, keywords in secret_tools.items():
                                if tool not in tools_found:  # Skip tools we've already found
                                    for keyword in keywords:
                                        if keyword.lower() in content:
                                            result["has_secret_management"] = True
                                            tools_found.add(tool)
                                            if rel_path not in secret_files_found:
                                                secret_files_found.append(rel_path)
                                            break
                            
                            # Check for vault integration specifically
                            if "vault" in content and not result["has_vault_integration"]:
                                vault_patterns = [
                                    r'vault\s*\.\s*(?:read|write|delete)',
                                    r'vault\s*\.\s*token',
                                    r'vault\s+(?:path|policy)',
                                    r'hashicorp/vault',
                                    r'vault-agent'
                                ]
                                for pattern in vault_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_vault_integration"] = True
                                        if "vault" not in tools_found:
                                            tools_found.add("vault")
                                        break
                            
                            # Check for encrypted secrets
                            if not result["has_encrypted_secrets"]:
                                encrypted_patterns = [
                                    r'ENCRYPTED[\s=:]{1,5}[\'"`].+?[\'"`]',
                                    r'ENC\[.+?\]',
                                    r'eyJ[A-Za-z0-9_-]{10,}',  # Base64 pattern
                                    r'AQ[A-Za-z0-9_-]{10,}',   # AWS KMS pattern
                                    r'sealed-secrets',
                                    r'sops:'
                                ]
                                for pattern in encrypted_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_encrypted_secrets"] = True
                                        break
                            
                            # Check for potential hardcoded secrets
                            if not has_potential_secrets:  # Only find a few examples
                                for pattern in potential_secret_patterns:
                                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                                    for match in matches:
                                        match_text = match.group(0)
                                        # Add to potential hardcoded secrets (limit to 5 examples)
                                        if len(result["potential_hardcoded_secrets"]) < 5:
                                            # Mask the actual secret value in the report
                                            masked_match = re.sub(r'[\'"`]([^\s\'"`]{8,})[\'"`]', r"'***MASKED***'", match_text)
                                            result["potential_hardcoded_secrets"].append({
                                                "file": rel_path,
                                                "line": content[:match.start()].count('\n') + 1,
                                                "content": masked_match
                                            })
                                            has_potential_secrets = True
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
    
        # Update result with findings
        result["secret_tools"] = sorted(list(tools_found))
        result["files_checked"] = files_checked
        
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'secret_management' in repo_data:
        logger.info("No local repository available. Using API data for secret management check.")
        
        secret_data = repo_data.get('secret_management', {})
        
        # Copy API data to result
        result["has_secret_management"] = secret_data.get('has_secret_management', False)
        result["secret_tools"] = secret_data.get('tools', [])
        result["has_env_variables"] = secret_data.get('has_env_variables', False)
        result["has_vault_integration"] = secret_data.get('has_vault_integration', False)
        result["has_gitignore_for_secrets"] = secret_data.get('has_gitignore_for_secrets', False)
        result["has_encrypted_secrets"] = secret_data.get('has_encrypted_secrets', False)
        
        # Potential hardcoded secrets should be detected locally for security
        result["potential_hardcoded_secrets"] = []
    else:
        logger.debug("Using primarily local analysis for secret management check")
        logger.warning("No local repository path or API data provided for secret management check")
    
    # Check for best practices
    result["best_practices_followed"] = (
        result["has_secret_management"] and 
        result["has_gitignore_for_secrets"] and 
        (result["has_env_variables"] or result["has_vault_integration"] or result["has_encrypted_secrets"]) and
        len(result["potential_hardcoded_secrets"]) == 0
    )
    
    # Calculate secret management score (0-100 scale)
    score = 0
    
    # Points for having secret management setup
    if result["has_secret_management"]:
        score += 25
    
    # Points for various secret management aspects
    if result["has_gitignore_for_secrets"]:
        score += 15
    
    if result["has_env_variables"]:
        score += 15
    
    if result["has_vault_integration"] or any(tool in tools_found for tool in ["vault", "aws_secrets", "gcp_secrets", "azure_keyvault"]):
        score += 20
    
    if result["has_encrypted_secrets"]:
        score += 15
    
    # Penalty for potential hardcoded secrets
    potential_secrets_penalty = min(40, len(result["potential_hardcoded_secrets"]) * 8)
    score = max(0, score - potential_secrets_penalty)
    
    # Bonus for following best practices
    if result["best_practices_followed"]:
        score = min(100, score + 10)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["secret_management_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the secret management check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_secret_management(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("secret_management_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running secret management check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }