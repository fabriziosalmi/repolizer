"""
Configuration Handling Check

Checks if the repository manages configuration properly.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_configuration_handling(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check configuration handling in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_configuration": False,
        "config_formats": [],
        "has_environment_config": False,
        "has_secure_config": False,
        "has_sample_config": False,
        "has_config_validation": False,
        "has_documented_config": False,
        "config_files": [],
        "sensitive_leaks": 0,
        "files_checked": 0,
        "configuration_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # This check relies entirely on local filesystem analysis
    # Repo data is not used for configuration check
    
    # Common configuration file patterns
    config_patterns = {
        "json": [r'config\.json$', r'settings\.json$', r'\.config\.json$'],
        "yaml": [r'config\.ya?ml$', r'settings\.ya?ml$', r'\.config\.ya?ml$'],
        "ini": [r'config\.ini$', r'settings\.ini$', r'\.ini$'],
        "env": [r'\.env(?:\.[a-zA-Z0-9]+)?$', r'env\.(?:sample|example|template)$'],
        "xml": [r'config\.xml$', r'settings\.xml$', r'\.config$'],
        "properties": [r'\.properties$', r'application\.properties$'],
        "toml": [r'config\.toml$', r'\.toml$']
    }
    
    # Environment-specific configuration patterns
    env_config_patterns = [
        r'\.env\.(?:dev|development|test|staging|prod|production)',
        r'(?:dev|development|test|staging|prod|production)\.(?:json|ya?ml|ini|xml|properties)',
        r'config\.(?:dev|development|test|staging|prod|production)\.(?:json|ya?ml|ini|xml|properties)',
        r'application-(?:dev|development|test|staging|prod|production)\.(?:properties|ya?ml)'
    ]
    
    # Sensitive information patterns
    sensitive_patterns = [
        r'(?:password|passwd|pwd)\s*(?:=|:)\s*[\'"]((?!\{\{)[^\'"]*)[\'"]',
        r'(?:secret|api_?key|auth_?token|access_?token|private_?key)\s*(?:=|:)\s*[\'"]((?!\{\{)[^\'"]*)[\'"]',
        r'-----BEGIN (?:RSA|DSA|EC|PGP) PRIVATE KEY-----',
        r'(?:password|passwd|pwd|secret|api_?key|token)(?!\S)',  # Only look for words (not as part of other words)
    ]
    
    # Sample/example configuration patterns
    sample_config_patterns = [
        r'(?:sample|example|template)\.(?:json|ya?ml|ini|env|xml|properties|toml)',
        r'config\.(?:sample|example|template)\.(?:json|ya?ml|ini|env|xml|properties|toml)',
        r'\.env\.(?:sample|example|template)',
        r'(?:sample|example|template)(?:[-_])?(?:config|configuration)\.(?:json|ya?ml|ini|env|xml|properties|toml)'
    ]
    
    # Config validation patterns (files that likely validate config)
    validation_patterns = [
        r'config_?validator\.(?:py|js|java|rb|php|go|cs|ts)',
        r'validate_?config\.(?:py|js|java|rb|php|go|cs|ts)',
        r'schema\.(?:json|ya?ml|xml)',
        r'config_?schema\.(?:json|ya?ml|xml)'
    ]
    
    # Documentation patterns for configuration
    config_doc_patterns = [
        r'config(?:uration)?\.md',
        r'setting(s)?\.md',
        r'environment\.md',
        r'env\.md'
    ]
    
    files_checked = 0
    found_config_files = []
    detected_config_formats = set()
    has_env_config = False
    has_secure_config = False
    has_sample_config = False
    has_config_validation = False
    has_documented_config = False
    sensitive_info_count = 0
    
    # Walk through the repository
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', 'env', '.env']]
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path)
            
            # Skip very large files and binary files
            try:
                if os.path.getsize(file_path) > 1000000:  # 1MB
                    continue
            except OSError:
                continue
                
            # Check for config files
            is_config_file = False
            config_format = None
            
            # Check against config patterns
            for format_type, patterns in config_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        is_config_file = True
                        config_format = format_type
                        detected_config_formats.add(format_type)
                        break
                if is_config_file:
                    break
            
            # Handle .env files specifically since they often have no extension
            if file == ".env":
                is_config_file = True
                config_format = "env"
                detected_config_formats.add("env")
            
            # If not a config file, check if it contains config validation code
            if not is_config_file:
                for pattern in validation_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        has_config_validation = True
                        found_config_files.append(rel_path)
                        files_checked += 1
                        break
            
            # If not a config file or validation file, check if it's a config doc
            if not is_config_file and not has_config_validation:
                for pattern in config_doc_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        has_documented_config = True
                        found_config_files.append(rel_path)
                        files_checked += 1
                        break
            
            # Process the identified config file
            if is_config_file:
                found_config_files.append(rel_path)
                files_checked += 1
                result["has_configuration"] = True
                
                # Check if it's an environment-specific config
                for pattern in env_config_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        has_env_config = True
                        break
                
                # Check if it's a sample config
                for pattern in sample_config_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        has_sample_config = True
                        break
                
                # Look for sensitive information
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Don't check sample/example files for leaks
                        if not has_sample_config:
                            for pattern in sensitive_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    for match in matches:
                                        # Check if the "secret" looks like a real secret (not a placeholder)
                                        if match and len(match) > 0:  # Non-empty match
                                            # Skip common placeholders
                                            placeholders = ['your_', 'YOUR_', 'xxx', 'XXX', 'changeme', 'CHANGEME', 
                                                            'placeholder', 'PLACEHOLDER', 'example', 'EXAMPLE', '***']
                                            if not any(ph in match for ph in placeholders):
                                                sensitive_info_count += 1
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
    
    # Check for common ways to secure config
    secure_config_files = [
        '.gitignore', '.dockerignore', '.env.example', '.env.sample',
        'docker-compose.yml', 'docker-compose.yaml'
    ]
    
    for secure_file in secure_config_files:
        file_path = os.path.join(repo_path, secure_file)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    files_checked += 1
                    
                    # Check for signs of secure config handling
                    if (secure_file in ['.gitignore', '.dockerignore'] and 
                        (re.search(r'\.env', content) or 
                         re.search(r'config.*\.(?:json|ya?ml|ini)', content) or
                         re.search(r'secret', content))):
                        has_secure_config = True
                    
                    # Check environment variable usage in Docker configs
                    elif secure_file in ['docker-compose.yml', 'docker-compose.yaml'] and 'env_file' in content:
                        has_secure_config = True
                        
            except Exception as e:
                logger.error(f"Error reading security file {file_path}: {e}")
    
    # Check for environment variables in code if we haven't confirmed secure config yet
    if not has_secure_config and found_config_files:
        # Check a sample of code files for environment variable usage
        code_extensions = ['.py', '.js', '.ts', '.java', '.rb', '.go', '.php', '.cs']
        env_var_patterns = [
            r'os\.environ', r'process\.env', r'System\.getenv', 
            r'ENV\[', r'getenv\(', r'dotenv', r'\$_ENV'
        ]
        
        code_files_checked = 0
        for root, _, files in os.walk(repo_path):
            # Skip hidden directories and common non-source dirs
            if any(skip in root for skip in ['/node_modules', '/.git', '/venv', '/.venv', '/dist', '/build']):
                continue
                
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() in code_extensions:
                    file_path = os.path.join(root, file)
                    
                    # Only check a reasonable number of files
                    if code_files_checked >= 30:
                        break
                        
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            code_files_checked += 1
                            
                            # Check for environment variable usage
                            for pattern in env_var_patterns:
                                if re.search(pattern, content):
                                    has_secure_config = True
                                    break
                            
                            if has_secure_config:
                                break
                    except Exception:
                        # Skip files that can't be read
                        pass
            
            if code_files_checked >= 30 or has_secure_config:
                break
    
    # Update result with findings
    result["config_formats"] = sorted(list(detected_config_formats))
    result["has_environment_config"] = has_env_config
    result["has_secure_config"] = has_secure_config
    result["has_sample_config"] = has_sample_config
    result["has_config_validation"] = has_config_validation
    result["has_documented_config"] = has_documented_config
    result["config_files"] = found_config_files
    result["sensitive_leaks"] = sensitive_info_count
    result["files_checked"] = files_checked
    
    # Calculate configuration handling score (0-100 scale)
    score = 0
    
    # Points for having configuration
    if result["has_configuration"]:
        score += 30
        
        # Points for secure configuration
        if result["has_secure_config"]:
            score += 25
        
        # Points for environment-specific configuration
        if result["has_environment_config"]:
            score += 15
        
        # Points for sample configuration
        if result["has_sample_config"]:
            score += 10
        
        # Points for configuration validation
        if result["has_config_validation"]:
            score += 10
        
        # Points for documented configuration
        if result["has_documented_config"]:
            score += 10
        
        # Penalty for sensitive information leaks
        if result["sensitive_leaks"] > 0:
            leak_penalty = min(80, result["sensitive_leaks"] * 20)  # Cap at 80 to leave min score of 20
            score -= leak_penalty
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["configuration_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify configuration handling
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository - required for this check
        local_path = repository.get('local_path')
        
        if not local_path or not os.path.isdir(local_path):
            return {
                "status": "skipped",
                "score": 0,
                "result": {"message": "No local repository path available"},
                "errors": "Local repository path is required for configuration handling analysis"
            }
        
        # Run the check with local path only
        # API data is not used for this check
        result = check_configuration_handling(local_path, None)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("configuration_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running configuration handling check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }