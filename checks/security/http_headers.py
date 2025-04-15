import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_http_headers_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secure HTTP header implementation and best practices
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for HTTP security headers analysis
    """
    result = {
        "has_security_headers": False,
        "security_headers_detected": [],
        "has_csp": False,
        "has_xframe_options": False,
        "has_hsts": False,
        "has_content_type_options": False,
        "has_referrer_policy": False,
        "has_permissions_policy": False,
        "http_headers_score": 0,
        "files_checked": 0,
        "files_with_headers": [],
        "potential_issues": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Security headers to check for
    security_headers = {
        "content-security-policy": [
            r'content-security-policy',
            r'Content-Security-Policy',
            r'CSP',
            r'csp\s*:',
            r'script-src',
            r'style-src',
            r'img-src',
            r'connect-src',
            r'default-src'
        ],
        "x-frame-options": [
            r'x-frame-options',
            r'X-Frame-Options',
            r'DENY',
            r'SAMEORIGIN',
            r'frameOptions',
            r'frame-ancestors'
        ],
        "strict-transport-security": [
            r'strict-transport-security',
            r'Strict-Transport-Security',
            r'HSTS',
            r'max-age=',
            r'includeSubDomains',
            r'preload'
        ],
        "x-content-type-options": [
            r'x-content-type-options',
            r'X-Content-Type-Options',
            r'nosniff',
            r'contentTypeOptions'
        ],
        "referrer-policy": [
            r'referrer-policy',
            r'Referrer-Policy',
            r'no-referrer',
            r'same-origin',
            r'strict-origin',
            r'referrerPolicy'
        ],
        "permissions-policy": [
            r'permissions-policy',
            r'Permissions-Policy',
            r'feature-policy',
            r'Feature-Policy',
            r'geolocation=',
            r'camera=',
            r'microphone='
        ],
        "x-xss-protection": [
            r'x-xss-protection',
            r'X-XSS-Protection',
            r'1;\s*mode=block'
        ]
    }
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.cs', '.html', '.conf']
    
    # Config and framework-specific files that commonly contain header configurations
    header_config_files = [
        'web.config',                      # ASP.NET
        'app.config',                      # .NET
        'global.asax',                     # ASP.NET
        'security.config.js',              # Custom security config
        'middleware.js',                   # Express/Node.js
        'app.js',                          # Express/Node.js
        'server.js',                       # Node.js
        'nginx.conf',                      # Nginx
        'apache.conf',                     # Apache
        '.htaccess',                       # Apache
        'httpd.conf',                      # Apache
        'settings.py',                     # Django
        'middleware.py',                   # Django
        'SecurityConfig.java',             # Spring
        'WebSecurityConfig.java',          # Spring Security
        'security.xml',                    # Spring Security
        'application.properties',          # Spring Boot
        'application.yml',                 # Spring Boot
        'config/application.rb',           # Rails
        'config/environments/production.rb', # Rails
        'config/initializers/secure_headers.rb', # Rails with secure_headers gem
        'header_config.php',               # PHP
        'header.php'                       # PHP
    ]
    
    # Header setting patterns in different frameworks
    framework_header_patterns = {
        "express": [
            r'helmet',
            r'app\.use\(helmet',
            r'res\.set\(',
            r'res\.header\(',
            r'res\.setHeader\(',
            r'response\.headers\['
        ],
        "django": [
            r'SECURE_',
            r'MIDDLEWARE',
            r'SecurityMiddleware',
            r'django-csp',
            r'HttpResponse\[[\'"]',
            r'response\[[\'"]'
        ],
        "rails": [
            r'SecureHeaders',
            r'headers\[[\'"]',
            r'response\.headers\[',
            r'config\.action_dispatch\.default_headers'
        ],
        "asp.net": [
            r'<add\s+name=[\'"]',
            r'AddHeader',
            r'httpContext.Response.Headers',
            r'Response.AppendHeader',
            r'Response.Headers.Add'
        ],
        "spring": [
            r'addHeaderWriter',
            r'HeaderWriterFilter',
            r'HttpSecurity',
            r'headers\(\)',
            r'Response\.addHeader'
        ],
        "golang": [
            r'w\.Header\(\)\.Set',
            r'w\.Header\(\)\.Add',
            r'http\.Header'
        ],
        "php": [
            r'header\([\'"]',
            r'Header set',
            r'header_set\('
        ]
    }
    
    # Track files checked and files with headers
    files_checked = 0
    files_with_headers = set()
    
    # Look for potential CSP misconfigurations
    csp_unsafe_patterns = [
        r'unsafe-inline',
        r'unsafe-eval',
        r'data:',
        r'default-src\s+[\'"]?\*[\'"]?',
        r'script-src\s+[\'"]?\*[\'"]?'
    ]
    
    # First, check common header configuration files
    for config_file in header_config_files:
        # Look in standard locations
        for directory in ['', 'config/', 'app/', 'src/', 'security/']:
            config_path = os.path.join(repo_path, directory, config_file)
            if os.path.isfile(config_path):
                files_checked += 1
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        has_header = False
                        # Check for security headers
                        for header, patterns in security_headers.items():
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                # Set specific header flag
                                if header == "content-security-policy":
                                    result["has_csp"] = True
                                    # Check for potentially unsafe CSP configurations
                                    for unsafe_pattern in csp_unsafe_patterns:
                                        if re.search(unsafe_pattern, content, re.IGNORECASE):
                                            result["potential_issues"].append({
                                                "file": os.path.relpath(config_path, repo_path),
                                                "issue": f"Potentially unsafe CSP directive: {unsafe_pattern}",
                                                "impact": "high"
                                            })
                                elif header == "x-frame-options":
                                    result["has_xframe_options"] = True
                                elif header == "strict-transport-security":
                                    result["has_hsts"] = True
                                elif header == "x-content-type-options":
                                    result["has_content_type_options"] = True
                                elif header == "referrer-policy":
                                    result["has_referrer_policy"] = True
                                elif header == "permissions-policy":
                                    result["has_permissions_policy"] = True
                                
                                # Add to detected headers list if not already there
                                if header not in result["security_headers_detected"]:
                                    result["security_headers_detected"].append(header)
                                    result["has_security_headers"] = True
                                    has_header = True
                        
                        if has_header:
                            files_with_headers.add(os.path.relpath(config_path, repo_path))
                        
                except Exception as e:
                    logger.warning(f"Error reading config file {config_path}: {e}")
    
    # If we didn't find all headers in config files, search for them in code files
    if not all([
        result["has_csp"],
        result["has_xframe_options"],
        result["has_hsts"],
        result["has_content_type_options"],
        result["has_referrer_policy"],
        result["has_permissions_policy"]
    ]):
        # Look for header implementation in server-side code
        for root, _, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
                
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                if file_ext in code_file_extensions:
                    # Skip files we've already checked
                    if any(file.endswith(config_file) for config_file in header_config_files):
                        continue
                    
                    # Check if file might contain header-setting code
                    try:
                        files_checked += 1
                        
                        # Quick check for potential header implementation first
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content_preview = f.read(4000)  # Just scan beginning of the file
                            if not re.search(r'header|security|response|Header|CSP|XSS|HSTS', content_preview):
                                continue
                        
                        # If potentially relevant, perform full analysis
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Check for framework-specific header setting patterns
                            header_setting_code = False
                            for framework, patterns in framework_header_patterns.items():
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                    header_setting_code = True
                                    break
                            
                            if header_setting_code:
                                # Check for security headers
                                for header, patterns in security_headers.items():
                                    # Skip headers we've already found
                                    if header == "content-security-policy" and result["has_csp"]:
                                        continue
                                    elif header == "x-frame-options" and result["has_xframe_options"]:
                                        continue
                                    elif header == "strict-transport-security" and result["has_hsts"]:
                                        continue
                                    elif header == "x-content-type-options" and result["has_content_type_options"]:
                                        continue
                                    elif header == "referrer-policy" and result["has_referrer_policy"]:
                                        continue
                                    elif header == "permissions-policy" and result["has_permissions_policy"]:
                                        continue
                                    
                                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                        # Set specific header flag
                                        if header == "content-security-policy":
                                            result["has_csp"] = True
                                        elif header == "x-frame-options":
                                            result["has_xframe_options"] = True
                                        elif header == "strict-transport-security":
                                            result["has_hsts"] = True
                                        elif header == "x-content-type-options":
                                            result["has_content_type_options"] = True
                                        elif header == "referrer-policy":
                                            result["has_referrer_policy"] = True
                                        elif header == "permissions-policy":
                                            result["has_permissions_policy"] = True
                                        
                                        # Add to detected headers list if not already there
                                        if header not in result["security_headers_detected"]:
                                            result["security_headers_detected"].append(header)
                                            result["has_security_headers"] = True
                        
                        # Add file to tracked files with headers if any headers found
                        if header_setting_code and any(not result.get(f"has_{header.replace('-', '_').replace('x_', '')}", False) for header in security_headers.keys()):
                            relative_path = os.path.relpath(file_path, repo_path)
                            files_with_headers.add(relative_path)
                    
                    except Exception as e:
                        logger.warning(f"Error processing file {file_path}: {e}")
    
    # Update result with file metrics
    result["files_checked"] = files_checked
    result["files_with_headers"] = list(files_with_headers)
    
    # Calculate HTTP headers security score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on HTTP security headers implementation.
        
        The score consists of:
        - Base scores for each critical security header:
          - Content Security Policy (0-25 points)
          - X-Frame-Options (0-15 points)
          - Strict-Transport-Security (0-20 points)
          - X-Content-Type-Options (0-15 points)
          - Referrer-Policy (0-10 points)
          - Permissions-Policy (0-15 points)
        - Implementation quality bonus (0-10 points)
        - Penalty for potential security misconfigurations (0-30 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Base points for each security header
        csp_score = 25 if result_data.get("has_csp", False) else 0
        xframe_score = 15 if result_data.get("has_xframe_options", False) else 0
        hsts_score = 20 if result_data.get("has_hsts", False) else 0
        cto_score = 15 if result_data.get("has_content_type_options", False) else 0
        referrer_score = 10 if result_data.get("has_referrer_policy", False) else 0
        permissions_score = 15 if result_data.get("has_permissions_policy", False) else 0
        
        # Calculate raw base score
        raw_score = csp_score + xframe_score + hsts_score + cto_score + referrer_score + permissions_score
        
        # Implementation quality bonus - more headers = better security posture
        headers_count = len(result_data.get("security_headers_detected", []))
        quality_bonus = 0
        
        if headers_count >= 3:
            quality_bonus = 5
        if headers_count >= 5:
            quality_bonus = 10
            
        # Penalty for potential security issues
        issues = result_data.get("potential_issues", [])
        issue_count = len(issues)
        
        # Weight issues by impact
        high_impact_issues = sum(1 for issue in issues if issue.get("impact") == "high")
        medium_impact_issues = issue_count - high_impact_issues
        
        issue_penalty = (high_impact_issues * 10) + (medium_impact_issues * 5)
        issue_penalty = min(30, issue_penalty)  # Cap at 30 points
        
        # Calculate final score
        final_score = raw_score + quality_bonus - issue_penalty
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, final_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "csp_score": csp_score,
            "xframe_score": xframe_score,
            "hsts_score": hsts_score, 
            "content_type_options_score": cto_score,
            "referrer_policy_score": referrer_score,
            "permissions_policy_score": permissions_score,
            "raw_score": raw_score,
            "quality_bonus": quality_bonus,
            "issue_penalty": issue_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["http_headers_score"] = calculate_score(result)
    
    return result

def get_headers_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the HTTP headers security check results"""
    if not result.get("has_security_headers", False):
        return "Implement security headers to protect against common web vulnerabilities. Start with Content-Security-Policy, Strict-Transport-Security, and X-Content-Type-Options."
    
    score = result.get("http_headers_score", 0)
    has_csp = result.get("has_csp", False)
    has_hsts = result.get("has_hsts", False)
    has_issues = len(result.get("potential_issues", [])) > 0
    
    if score >= 80:
        return "Excellent security headers implementation. Continue maintaining good security practices."
    
    recommendations = []
    
    if not has_csp:
        recommendations.append("Implement Content-Security-Policy to prevent XSS attacks.")
    
    if not has_hsts:
        recommendations.append("Add Strict-Transport-Security header to enforce HTTPS usage.")
    
    if not result.get("has_xframe_options", False):
        recommendations.append("Set X-Frame-Options to prevent clickjacking attacks.")
    
    if not result.get("has_content_type_options", False):
        recommendations.append("Add X-Content-Type-Options: nosniff to prevent MIME type sniffing.")
    
    if has_issues:
        recommendations.append("Fix the identified security header misconfigurations, especially any unsafe CSP directives.")
    
    if not recommendations:
        return "Good security headers implementation. Consider adding any missing headers for comprehensive protection."
    
    return " ".join(recommendations)

def normalize_score(score: float) -> int:
    """
    Normalize score to be between 1-100, with 0 reserved for errors/skipped checks.
    
    Args:
        score: Raw score value
        
    Returns:
        Normalized score between 1-100
    """
    if score <= 0:
        return 1  # Minimum score for completed checks
    elif score > 100:
        return 100  # Maximum score
    else:
        return int(round(score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the HTTP headers security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"http_headers_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached HTTP headers check result for {repository.get('name', 'unknown')}")
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
        result = check_http_headers_security(local_path, repository)
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("http_headers_score", 0)
        final_score = normalize_score(score)
        
        logger.debug(f"✅ HTTP headers security check completed with score: {final_score}")
        
        # Return the result with enhanced metadata
        return {
            "score": final_score,
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "files_with_headers": len(result.get("files_with_headers", [])),
                "security_headers": {
                    "csp": result.get("has_csp", False),
                    "x_frame_options": result.get("has_xframe_options", False),
                    "hsts": result.get("has_hsts", False),
                    "content_type_options": result.get("has_content_type_options", False),
                    "referrer_policy": result.get("has_referrer_policy", False),
                    "permissions_policy": result.get("has_permissions_policy", False)
                },
                "headers_count": len(result.get("security_headers_detected", [])),
                "potential_issues": len(result.get("potential_issues", [])),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_headers_recommendation(result)
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
        error_msg = f"Error running HTTP headers security check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }