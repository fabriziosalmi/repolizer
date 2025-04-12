import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_cors_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secure CORS (Cross-Origin Resource Sharing) configurations
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for CORS security evaluation
    """
    result = {
        "has_cors_config": False,
        "has_restrictive_origins": False,
        "has_secure_cors_headers": False,
        "has_secure_methods": False,
        "has_cors_preflight": False,
        "has_wildcard_concerns": False,
        "frameworks_detected": [],
        "files_with_cors": [],
        "potential_vulnerabilities": [],
        "cors_security_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # CORS configuration patterns
    cors_config_patterns = [
        r'cors',
        r'cross[-_\s]origin',
        r'Access-Control-Allow-Origin',
        r'Access-Control-Allow-Methods',
        r'Access-Control-Allow-Headers',
        r'Access-Control-Allow-Credentials',
        r'Access-Control-Max-Age'
    ]
    
    # Framework-specific CORS patterns
    cors_frameworks = {
        "express": [r'cors\(', r'app\.use\(cors\)', r'express[-_\s]cors'],
        "django": [r'CorsMiddleware', r'CORS_ALLOW_', r'corsheaders'],
        "spring": [r'@CrossOrigin', r'CorsConfiguration', r'CorsRegistry'],
        "flask": [r'CORS\(', r'flask[-_\s]cors', r'after_request'],
        "aspnet": [r'app\.UseCors\(', r'services\.AddCors\(', r'EnableCors'],
        "rails": [r'config\.middleware\.insert_before.*Rack::Cors', r'resource.*:headers'],
        "laravel": [r'Cors[\\\s].*ServiceProvider', r'HandleCors', r'middleware.*cors']
    }
    
    # Patterns for restrictive origins (not using *)
    restrictive_origins_patterns = [
        r'Access-Control-Allow-Origin[\'"\s]*:[\'"\s]*[\'"](?!https?://\*|[\'"])(?!.*\*).*?[\'"]',
        r'allowedOrigins[\'"\s]*:[\'"\s]*\[[^\]]*\]',
        r'origins[\'"\s]*:[\'"\s]*\[[^\]]*\]',
        r'CORS_ALLOWED_ORIGINS',
        r'CORS_ORIGIN_WHITELIST',
        r'allowed[-_\s]origins',
        r'origin[-_\s]whitelist',
        r'setAllowedOrigins',
        r'setOrigins',
    ]
    
    # Patterns for wildcard/insecure CORS
    wildcard_patterns = [
        r'Access-Control-Allow-Origin[\'"\s]*:[\'"\s]*[\'"]?\*[\'"]?',
        r'allowed[-_\s]origins[\'"\s]*:[\'"\s]*[\'"]?\*[\'"]?',
        r'origins[\'"\s]*:[\'"]?\*[\'"]?',
        r'CORS_ALLOW_ALL_ORIGINS[\'"\s]*=[\'"\s]*True',
        r'Access-Control-Allow-Credentials[\'"\s]*:[\'"\s]*true',
        r'credentials[\'"\s]*:[\'"\s]*true',
        r'cors\(\{\s*origin:\s*[\'"]?\*[\'"]?,\s*credentials:\s*true'
    ]
    
    # Secure CORS headers patterns
    secure_headers_patterns = [
        r'Access-Control-Allow-Headers',
        r'allowed[-_\s]headers',
        r'allowedHeaders',
        r'CORS_ALLOW_HEADERS',
        r'setAllowedHeaders',
        r'expose[-_\s]headers',
        r'exposedHeaders',
        r'CORS_EXPOSE_HEADERS'
    ]
    
    # Secure methods patterns
    secure_methods_patterns = [
        r'Access-Control-Allow-Methods[\'"\s]*:[\'"\s]*[\'"][^\'"]*(GET|POST)[^\']*[\'"]',
        r'allowed[-_\s]methods[\'"\s]*:[\'"\s]*\[[^\]]*?(GET|POST)[^\]]*\]',
        r'CORS_ALLOW_METHODS',
        r'setAllowedMethods',
        r'methods[\'"\s]*:[\'"\s]*\[[^\]]*?(GET|POST)[^\]]*\]'
    ]
    
    # CORS preflight patterns
    preflight_patterns = [
        r'Access-Control-Max-Age',
        r'max[-_\s]age',
        r'maxAge',
        r'CORS_PREFLIGHT_MAX_AGE',
        r'setMaxAge',
        r'preflightContinue',
        r'handle[-_\s]preflight',
        r'OPTIONS'
    ]
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.cs', '.html', '.conf']
    
    # Config files that might have CORS settings
    config_files = [
        'package.json',
        'server.js',
        'app.js',
        'index.js',
        'config.js',
        'cors.js',
        'middleware.js',
        'settings.py',
        'urls.py',
        'middleware.py',
        'application.rb',
        'routes.rb',
        'cors.rb',
        'web.php',
        'Startup.cs',
        'Program.cs',
        'WebApiConfig.cs',
        'SecurityConfig.java',
        'WebConfig.java',
        'nginx.conf',
        'apache.conf',
        '.htaccess',
        'web.config'
    ]
    
    # Track detected frameworks
    detected_frameworks = set()
    
    # First check common config files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for CORS configuration
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in cors_config_patterns):
                        result["has_cors_config"] = True
                    
                    # Check for CORS frameworks
                    for framework, patterns in cors_frameworks.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_frameworks.add(framework)
                            result["has_cors_config"] = True
                    
                    # Check for restrictive origins
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in restrictive_origins_patterns):
                        result["has_restrictive_origins"] = True
                    
                    # Check for wildcard concerns
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in wildcard_patterns):
                        result["has_wildcard_concerns"] = True
                    
                    # Check for secure headers
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_headers_patterns):
                        result["has_secure_cors_headers"] = True
                    
                    # Check for secure methods
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_methods_patterns):
                        result["has_secure_methods"] = True
                    
                    # Check for preflight configuration
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in preflight_patterns):
                        result["has_cors_preflight"] = True
                    
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # If we didn't find CORS in config files, search through other code files
    if not result["has_cors_config"]:
        for root, _, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
                
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                if file_ext in code_file_extensions and file not in config_files:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Check for CORS configuration
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in cors_config_patterns):
                                result["has_cors_config"] = True
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["files_with_cors"].append(relative_path)
                                
                                # Once we find CORS, check details
                                # Check for CORS frameworks
                                for framework, patterns in cors_frameworks.items():
                                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                        detected_frameworks.add(framework)
                                
                                # Check for restrictive origins
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in restrictive_origins_patterns):
                                    result["has_restrictive_origins"] = True
                                
                                # Check for wildcard concerns
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in wildcard_patterns):
                                    result["has_wildcard_concerns"] = True
                                
                                # Check for secure headers
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_headers_patterns):
                                    result["has_secure_cors_headers"] = True
                                
                                # Check for secure methods
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_methods_patterns):
                                    result["has_secure_methods"] = True
                                
                                # Check for preflight configuration
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in preflight_patterns):
                                    result["has_cors_preflight"] = True
                                
                                # Check for dangerous CORS patterns
                                dangerous_patterns = [
                                    (r'Access-Control-Allow-Origin\s*:\s*[\'"]?\*[\'"]?.*?Access-Control-Allow-Credentials\s*:\s*true', 
                                    "Allowing wildcard origin with credentials is a serious security risk"),
                                    (r'cors\(\{\s*origin:\s*[\'"]?\*[\'"]?,\s*credentials:\s*true', 
                                    "Allowing wildcard origin with credentials in CORS middleware"),
                                    (r'app\.use\(cors\(\{\s*origin\s*:\s*[\'"]?\*[\'"]?', 
                                    "Using wildcard in Express CORS middleware is overly permissive")
                                ]
                                
                                for pattern, message in dangerous_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["potential_vulnerabilities"].append({
                                            "file": relative_path,
                                            "vulnerability": message
                                        })
                                
                                # If we've found everything, we can break
                                if (result["has_restrictive_origins"] and 
                                    result["has_secure_cors_headers"] and 
                                    result["has_secure_methods"] and 
                                    result["has_cors_preflight"]):
                                    break
                    
                    except Exception as e:
                        logger.warning(f"Error reading file {file_path}: {e}")
            
            # Break outer loop if we found everything
            if (result["has_cors_config"] and 
                result["has_restrictive_origins"] and 
                result["has_secure_cors_headers"] and 
                result["has_secure_methods"] and 
                result["has_cors_preflight"]):
                break
    
    # Store detected frameworks
    result["frameworks_detected"] = list(detected_frameworks)
    
    # Calculate CORS security score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on CORS security configuration.
        
        The score consists of:
        - Base score dependent on CORS configuration presence (0-20 points)
        - Score for restrictive origins (0-25 points)
        - Score for secure headers configuration (0-15 points)
        - Score for secure methods configuration (0-15 points)
        - Score for preflight handling (0-15 points)
        - Framework detection bonus (0-10 points)
        - Penalty for wildcard usage (0-40 points deduction)
        - Penalty for detected vulnerabilities (0-60 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # No CORS configuration means we can't evaluate it
        # So we provide a neutral score
        if not result_data.get("has_cors_config", False):
            return 50  # Neutral score
            
        # Start with a base score for having CORS config
        base_score = 20
        
        # Add points for good practices
        restrictive_origins_score = 25 if result_data.get("has_restrictive_origins", False) else 0
        secure_headers_score = 15 if result_data.get("has_secure_cors_headers", False) else 0
        secure_methods_score = 15 if result_data.get("has_secure_methods", False) else 0
        preflight_score = 15 if result_data.get("has_cors_preflight", False) else 0
        
        # Framework bonus - using established CORS libraries is generally safer
        frameworks_detected = len(result_data.get("frameworks_detected", []))
        framework_bonus = min(10, frameworks_detected * 5)
        
        # Calculate raw score before penalties
        raw_score = base_score + restrictive_origins_score + secure_headers_score + secure_methods_score + preflight_score + framework_bonus
        
        # Penalties
        
        # Wildcard penalty - using '*' in origins is a security concern
        wildcard_penalty = 0
        if result_data.get("has_wildcard_concerns", False):
            # If using wildcard with restrictive configurations, smaller penalty
            if result_data.get("has_secure_cors_headers", False) and result_data.get("has_secure_methods", False):
                wildcard_penalty = 20
            else:
                # Major penalty for wildcard without other restrictions
                wildcard_penalty = 40
        
        # Vulnerability penalty - serious security issues found
        vulnerability_penalty = 0
        vulnerabilities = len(result_data.get("potential_vulnerabilities", []))
        if vulnerabilities > 0:
            # Each vulnerability is a severe security issue
            vulnerability_penalty = min(60, vulnerabilities * 30)
        
        # Apply penalties
        final_score = max(0, raw_score - wildcard_penalty - vulnerability_penalty)
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "restrictive_origins_score": restrictive_origins_score,
            "secure_headers_score": secure_headers_score,
            "secure_methods_score": secure_methods_score,
            "preflight_score": preflight_score,
            "framework_bonus": framework_bonus,
            "raw_score": raw_score,
            "wildcard_penalty": wildcard_penalty,
            "vulnerability_penalty": vulnerability_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["cors_security_score"] = calculate_score(result)
    
    return result

def get_cors_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the CORS security check results"""
    if not result.get("has_cors_config", False):
        return "No CORS configuration detected. If your application serves content to other origins, implement proper CORS policies."
    
    score = result.get("cors_security_score", 0)
    
    if score >= 80:
        return "Good CORS security configuration. Continue maintaining secure cross-origin policies."
    
    recommendations = []
    
    if not result.get("has_restrictive_origins", False):
        recommendations.append("Configure specific allowed origins instead of using wildcards ('*').")
    
    if result.get("has_wildcard_concerns", False):
        recommendations.append("Replace wildcard origin ('*') with explicit allowed domains.")
    
    if not result.get("has_secure_cors_headers", False):
        recommendations.append("Specify which headers can be used with cross-origin requests.")
    
    if not result.get("has_secure_methods", False):
        recommendations.append("Restrict allowed HTTP methods to only those required by your API.")
    
    if not result.get("has_cors_preflight", False):
        recommendations.append("Configure proper handling of preflight requests with appropriate max-age.")
    
    if result.get("potential_vulnerabilities", []):
        recommendations.append("Fix the identified CORS vulnerabilities that could lead to security issues.")
    
    if not recommendations:
        return "Your CORS configuration has some security measures. Consider implementing more restrictive policies."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the CORS security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"cors_security_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached CORS security check result for {repository.get('name', 'unknown')}")
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
        result = check_cors_security(local_path, repository)
        
        logger.info(f"CORS security check completed with score: {result.get('cors_security_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("cors_security_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "cors_configured": result.get("has_cors_config", False),
                "frameworks_used": result.get("frameworks_detected", []),
                "restrictive_origins": result.get("has_restrictive_origins", False),
                "wildcard_concerns": result.get("has_wildcard_concerns", False),
                "vulnerabilities_found": len(result.get("potential_vulnerabilities", [])),
                "files_with_cors": len(result.get("files_with_cors", [])),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_cors_recommendation(result)
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
        error_msg = f"Error running CORS security check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }