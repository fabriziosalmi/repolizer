import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_client_side_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for client-side security measures and browser security features
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_client_side_code": False,
        "has_csp_implementation": False,
        "has_xss_protection": False,
        "has_secure_cookies": False,
        "has_client_validation": False,
        "has_secure_local_storage": False,
        "has_safe_dom_manipulation": False,
        "frameworks_detected": [],
        "client_side_security_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Front-end framework patterns
    frontend_frameworks = {
        "react": [r'react', r'react-dom', r'React\.', r'jsx', r'<React', r'createRoot'],
        "angular": [r'angular', r'ng-', r'\[\(ngModel\)\]', r'@Component'],
        "vue": [r'vue', r'Vue\.', r'v-', r'<template', r'createApp'],
        "svelte": [r'svelte', r'<script>.*\$:', r'<svelte'],
        "jquery": [r'jquery', r'\$\(', r'jQuery'],
        "ember": [r'ember', r'EmberApp', r'Ember\.Component']
    }
    
    # Content Security Policy patterns
    csp_patterns = [
        r'content-security-policy',
        r'Content-Security-Policy',
        r'csp\s*:',
        r'default-src',
        r'script-src',
        r'style-src',
        r'<meta\s+http-equiv=[\'"]Content-Security-Policy[\'"]',
        r'helmet\.contentSecurityPolicy',
        r'CSP\s*\(',
        r'Content-Security-Policy-Report-Only'
    ]
    
    # XSS protection patterns
    xss_protection_patterns = [
        r'dangerouslySetInnerHTML',  # React
        r'innerHTML',
        r'v-html',  # Vue
        r'[innerHTML]',  # Angular
        r'bypassSecurityTrustHtml',  # Angular
        r'DOMPurify',
        r'sanitize',
        r'escape',
        r'XSS',
        r'X-XSS-Protection',
        r'crossorigin',
        r'noopener',
        r'noreferrer',
        r'encodeURI',
        r'encodeURIComponent'
    ]
    
    # Secure cookie patterns
    secure_cookie_patterns = [
        r'document\.cookie',
        r'HttpOnly',
        r'Secure',
        r'SameSite',
        r'js-cookie',
        r'cookie-parser',
        r'cookie-session',
        r'secure:\s*true',
        r'httpOnly:\s*true',
        r'sameSite:\s*[\'"]?strict|lax[\'"]?'
    ]
    
    # Client-side validation patterns
    client_validation_patterns = [
        r'validate',
        r'validation',
        r'validator',
        r'formik',
        r'react-hook-form',
        r'yup',
        r'joi',
        r'vuelidate',
        r'v-validate',
        r'required',
        r'pattern',
        r'minlength',
        r'maxlength'
    ]
    
    # Secure local storage patterns
    local_storage_patterns = [
        r'localStorage',
        r'sessionStorage',
        r'IndexedDB',
        r'jwt-decode',
        r'secure-ls',
        r'crypto',
        r'SubtleCrypto',
        r'encrypt',
        r'decrypt',
        r'web-storage-cache'
    ]
    
    # Safe DOM manipulation patterns
    safe_dom_patterns = [
        r'createTextNode',
        r'textContent',
        r'innerText',
        r'sanitizeUrl',
        r'sanitizeHtml',
        r'sanitizeNode',
        r'purify',
        r'setAttribute',
        r'addEventListener',
        r'querySelector',
        r'onchange',
        r'onsubmit'
    ]
    
    # File types to analyze
    client_side_extensions = ['.js', '.jsx', '.ts', '.tsx', '.html', '.vue', '.svelte', '.hbs', '.ejs', '.pug', '.angular']
    
    # Common client-side directories
    client_dirs = ['public', 'static', 'assets', 'js', 'scripts', 'src', 'frontend', 'client', 'ui', 'views', 'pages', 'components']
    
    # Config files to check
    config_files = [
        'package.json',
        'webpack.config.js',
        'vite.config.js',
        'rollup.config.js',
        'next.config.js',
        'nuxt.config.js',
        'angular.json',
        'tailwind.config.js',
        'helmet.js',
        'security.js'
    ]
    
    # Find all client-side files
    client_files = []
    detected_frameworks = set()
    
    # First check configuration files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    result["has_client_side_code"] = True
                    
                    # Detect frameworks from config
                    for framework, patterns in frontend_frameworks.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_frameworks.add(framework)
                    
                    # Check for CSP in config
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in csp_patterns):
                        result["has_csp_implementation"] = True
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Find client-side files throughout the repo
    for root, dirs, files in os.walk(repo_path):
        # Get relative path to identify client-side directories
        rel_path = os.path.relpath(root, repo_path)
        dir_parts = rel_path.split(os.sep)
        
        # Check if current directory seems to be client-side related
        is_client_dir = any(client_dir.lower() in dir_part.lower() for dir_part in dir_parts for client_dir in client_dirs)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in client_side_extensions:
                result["has_client_side_code"] = True
                
                # If in client directory or common client extension, add to files to check
                if is_client_dir or file_ext in ['.html', '.jsx', '.tsx', '.vue', '.svelte']:
                    client_files.append(file_path)
                else:
                    # Quick check for client-side code in other js files
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(4000)  # Just scan beginning of the file
                            if re.search(r'document\.|window\.|DOM|fetch|browser|localStorage|sessionStorage', content):
                                client_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Error scanning file {file_path}: {e}")
    
    # Analyze client-side files for security practices
    for file_path in client_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Detect which frameworks are in use
                for framework, patterns in frontend_frameworks.items():
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                        detected_frameworks.add(framework)
                
                # Check for CSP implementation
                if not result["has_csp_implementation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in csp_patterns):
                        result["has_csp_implementation"] = True
                
                # Check for XSS protection
                if not result["has_xss_protection"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in xss_protection_patterns):
                        result["has_xss_protection"] = True
                
                # Check for secure cookies
                if not result["has_secure_cookies"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_cookie_patterns):
                        result["has_secure_cookies"] = True
                
                # Check for client-side validation
                if not result["has_client_validation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in client_validation_patterns):
                        result["has_client_validation"] = True
                
                # Check for secure local storage
                if not result["has_secure_local_storage"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in local_storage_patterns):
                        result["has_secure_local_storage"] = True
                
                # Check for safe DOM manipulation
                if not result["has_safe_dom_manipulation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in safe_dom_patterns):
                        result["has_safe_dom_manipulation"] = True
                
                # Break early if we found everything
                if (result["has_csp_implementation"] and 
                    result["has_xss_protection"] and 
                    result["has_secure_cookies"] and 
                    result["has_client_validation"] and 
                    result["has_secure_local_storage"] and 
                    result["has_safe_dom_manipulation"]):
                    break
                
        except Exception as e:
            logger.error(f"Error analyzing client-side file {file_path}: {e}")
    
    # Store detected frameworks
    result["frameworks_detected"] = list(detected_frameworks)
    
    # Calculate client-side security score (0-100 scale)
    # Only calculate if the project has client-side code
    if result["has_client_side_code"]:
        score = 0
        
        # Award points for each security feature
        if result["has_csp_implementation"]:
            score += 25  # CSP is very important for client-side security
        
        if result["has_xss_protection"]:
            score += 20  # XSS protection is critical
        
        if result["has_secure_cookies"]:
            score += 15
        
        if result["has_client_validation"]:
            score += 10
        
        if result["has_secure_local_storage"]:
            score += 15
        
        if result["has_safe_dom_manipulation"]:
            score += 15
    else:
        # No client-side code means this check isn't applicable
        score = -1  # Indicates not applicable
    
    # Round and convert to integer if it's a whole number
    if score >= 0:
        rounded_score = round(score, 1)
        result["client_side_security_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    else:
        result["client_side_security_score"] = -1  # Not applicable
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the client-side security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_client_side_security(local_path, repository)
        
        # If the check is not applicable (no client-side code)
        if result["client_side_security_score"] == -1:
            return {
                "score": None,  # None indicates not applicable
                "result": result,
                "status": "not_applicable",
                "errors": None
            }
        
        # Return the result with the score
        return {
            "score": result["client_side_security_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running client-side security check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }
