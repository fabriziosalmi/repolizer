import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_session_management(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secure session management practices
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for session security analysis
    """
    result = {
        "has_session_management": False,
        "has_session_expiration": False,
        "has_secure_cookies": False,
        "has_csrf_protection": False,
        "has_session_fixation_protection": False,
        "has_idle_timeout": False,
        "session_frameworks_detected": [],
        "files_with_session_code": [],
        "potential_issues": [],
        "files_checked": 0,
        "session_security_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Session framework patterns
    session_frameworks = {
        "express_session": [r'express-session', r'session\(', r'req\.session'],
        "django_session": [r'django\.contrib\.sessions', r'SESSION_', r'request\.session'],
        "spring_session": [r'@EnableRedisHttpSession', r'SessionRepository', r'HttpSession'],
        "php_session": [r'session_start', r'$_SESSION', r'session_id\('],
        "flask_session": [r'flask_session', r'Session\(', r'session\.[\'"]'],
        "aspnet_session": [r'ISession', r'Session\[', r'HttpContext\.Session'],
        "rails_session": [r'config\.session_store', r'session\[:', r'reset_session']
    }
    
    # Session expiration patterns
    expiration_patterns = [
        r'expir(e|es|ed|ation)',
        r'maxAge',
        r'max[-_]age',
        r'timeout',
        r'ttl',
        r'lifetime',
        r'duration',
        r'session[-_]timeout',
        r'SESSION_COOKIE_AGE',
        r'cookie[-_]max[-_]age'
    ]
    
    # Secure cookie patterns
    secure_cookie_patterns = [
        r'secure[\s:=]+true',
        r'httpOnly[\s:=]+true',
        r'SameSite',
        r'SESSION_COOKIE_SECURE',
        r'SESSION_COOKIE_HTTPONLY',
        r'cookie[-_]secure',
        r'cookie[-_]http[-_]only',
        r'__Host-',
        r'__Secure-',
        r'cookie[\s]*\{[^}]*secure[\s]*:[\s]*true'
    ]
    
    # CSRF protection patterns
    csrf_patterns = [
        r'csrf',
        r'xsrf',
        r'cross[\s-]*site[\s-]*request[\s-]*forgery',
        r'anti[\s-]*forgery',
        r'synchronizer[\s-]*token',
        r'CsrfViewMiddleware',
        r'csrf_token',
        r'_csrf',
        r'verify_authenticity_token'
    ]
    
    # Session fixation protection patterns
    fixation_patterns = [
        r'session[\s-]*fixation',
        r'regenerate[\s-]*id',
        r'migrate[\s-]*session',
        r'change[\s-]*session[\s-]*id',
        r'rotate[\s-]*session',
        r'renew[\s-]*session',
        r'session\.regenerate',
        r'session\.regenerateId',
        r'changeSessionId',
        r'session_regenerate_id',
        r'reset_session'
    ]
    
    # Idle timeout patterns
    idle_timeout_patterns = [
        r'idle[\s-]*timeout',
        r'inactivity[\s-]*timeout',
        r'activity[\s-]*timeout',
        r'sliding[\s-]*expiration',
        r'session\.touch\(',
        r'updateAccessTime',
        r'activity[\s-]*tracker',
        r'lastActivity'
    ]
    
    # File types to analyze
    code_file_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.php', '.rb', '.java', '.cs', '.go', '.html']
    
    # Config files to check
    config_files = [
        'web.config',
        'app.config.js',
        'settings.py',
        'application.properties',
        'application.yml',
        'config/application.rb',
        'config/initializers/session_store.rb',
        'config/environment.rb',
        'package.json',
        'session.config.js',
        'session.php',
        'php.ini',
        'server.xml',
        'web.xml'
    ]
    
    # First, check configuration files for session settings
    detected_frameworks = set()
    
    for config_file in config_files:
        # Look in common config directories
        for config_dir in ['', 'config/', 'src/config/', 'app/config/', 'conf/']:
            config_path = os.path.join(repo_path, config_dir, config_file)
            if os.path.isfile(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for session frameworks
                        for framework, patterns in session_frameworks.items():
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                detected_frameworks.add(framework)
                                result["has_session_management"] = True
                        
                        # Check for session expiration
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in expiration_patterns):
                            result["has_session_expiration"] = True
                        
                        # Check for secure cookies
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_cookie_patterns):
                            result["has_secure_cookies"] = True
                        
                        # Check for CSRF protection
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in csrf_patterns):
                            result["has_csrf_protection"] = True
                        
                        # Check for session fixation protection
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in fixation_patterns):
                            result["has_session_fixation_protection"] = True
                        
                        # Check for idle timeout
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in idle_timeout_patterns):
                            result["has_idle_timeout"] = True
                except Exception as e:
                    logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Look for session-related files throughout the repo
    session_files = []
    files_checked = 0
    
    # Directories and files likely to contain session code
    session_related_dirs = ['auth', 'session', 'middleware', 'security', 'login', 'user']
    session_related_names = ['session', 'auth', 'login', 'security', 'user', 'account', 'middleware']
    
    # Find potential session management files
    for root, _, files in os.walk(repo_path):
        # Check if the directory might be related to sessions
        rel_path = os.path.relpath(root, repo_path)
        dir_parts = rel_path.split(os.sep)
        
        is_session_dir = any(part.lower() in session_related_dirs for part in dir_parts)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in code_file_extensions:
                # Check if file might be related to sessions based on name
                if is_session_dir or any(term.lower() in file.lower() for term in session_related_names):
                    session_files.append(file_path)
                    continue
                
                # Do a quick check for session-related content
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        sample = f.read(4000)  # Just read a sample
                        
                        # Skip if unlikely to contain session-related code
                        if not re.search(r'session|cookie|csrf|token|auth|login', sample, re.IGNORECASE):
                            continue
                        
                        session_files.append(file_path)
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    # Analyze session management files
    for file_path in session_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                files_checked += 1
                relative_path = os.path.relpath(file_path, repo_path)
                
                has_session_code = False
                
                # Check for session frameworks
                for framework, patterns in session_frameworks.items():
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                        detected_frameworks.add(framework)
                        result["has_session_management"] = True
                        has_session_code = True
                
                # Check for session expiration
                if not result["has_session_expiration"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in expiration_patterns):
                        result["has_session_expiration"] = True
                
                # Check for secure cookies
                if not result["has_secure_cookies"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_cookie_patterns):
                        result["has_secure_cookies"] = True
                
                # Check for CSRF protection
                if not result["has_csrf_protection"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in csrf_patterns):
                        result["has_csrf_protection"] = True
                
                # Check for session fixation protection
                if not result["has_session_fixation_protection"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in fixation_patterns):
                        result["has_session_fixation_protection"] = True
                
                # Check for idle timeout
                if not result["has_idle_timeout"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in idle_timeout_patterns):
                        result["has_idle_timeout"] = True
                
                # Check for potential issues
                # Missing expiration check
                if (result["has_session_management"] and not result["has_session_expiration"] and 
                    re.search(r'session', content, re.IGNORECASE) and 
                    not re.search(r'expir|timeout|lifetime|duration', content, re.IGNORECASE)):
                    result["potential_issues"].append({
                        "file": relative_path,
                        "issue": "Session management without explicit expiration",
                        "severity": "high"
                    })
                
                # Insecure cookies check
                if (re.search(r'session|cookie', content, re.IGNORECASE) and 
                    not re.search(r'secure|httpOnly|SameSite', content, re.IGNORECASE)):
                    result["potential_issues"].append({
                        "file": relative_path,
                        "issue": "Cookies used without secure attributes",
                        "severity": "medium"
                    })
                
                # Missing CSRF protection
                if (result["has_session_management"] and not result["has_csrf_protection"] and
                    re.search(r'form|post|submit', content, re.IGNORECASE) and
                    not re.search(r'csrf|xsrf|token', content, re.IGNORECASE)):
                    result["potential_issues"].append({
                        "file": relative_path,
                        "issue": "Form handling without CSRF protection",
                        "severity": "high"
                    })
                
                if has_session_code:
                    result["files_with_session_code"].append(relative_path)
                
        except Exception as e:
            logger.warning(f"Error analyzing session file {file_path}: {e}")
    
    # Store detected frameworks and file count
    result["session_frameworks_detected"] = list(detected_frameworks)
    result["files_checked"] = files_checked
    
    # Calculate session security score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on session security implementation.
        
        The score consists of:
        - Base score for having session management (0-10 points)
        - Score for session expiration implementation (0-20 points)
        - Score for secure cookies configuration (0-20 points)
        - Score for CSRF protection (0-20 points)
        - Score for session fixation protection (0-15 points)
        - Score for idle timeout implementation (0-15 points)
        - Framework quality bonus (0-10 points)
        - Penalty for potential issues (0-30 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Cannot have secure session management without session management
        if not result_data.get("has_session_management", False):
            return 0
            
        # Base score for having session management (10 points)
        base_score = 10
        
        # Core security features
        expiration_score = 20 if result_data.get("has_session_expiration", False) else 0
        secure_cookies_score = 20 if result_data.get("has_secure_cookies", False) else 0
        csrf_score = 20 if result_data.get("has_csrf_protection", False) else 0
        
        # Additional security features
        fixation_score = 15 if result_data.get("has_session_fixation_protection", False) else 0
        idle_timeout_score = 15 if result_data.get("has_idle_timeout", False) else 0
        
        # Framework quality bonus - established frameworks are typically more secure
        frameworks = result_data.get("session_frameworks_detected", [])
        framework_bonus = 0
        
        secure_frameworks = ["django_session", "spring_session", "express_session"]
        if any(framework in secure_frameworks for framework in frameworks):
            framework_bonus = 10
        elif len(frameworks) > 0:
            framework_bonus = 5
        
        # Calculate raw score before penalties
        raw_score = base_score + expiration_score + secure_cookies_score + csrf_score + fixation_score + idle_timeout_score + framework_bonus
        
        # Penalty for potential issues
        issues = result_data.get("potential_issues", [])
        issue_penalty = 0
        
        # Weight issues by severity
        for issue in issues:
            if issue.get("severity") == "high":
                issue_penalty += 10
            elif issue.get("severity") == "medium":
                issue_penalty += 5
        
        # Cap penalty at 30 points
        issue_penalty = min(30, issue_penalty)
        
        # Apply penalty
        final_score = max(0, raw_score - issue_penalty)
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "expiration_score": expiration_score,
            "secure_cookies_score": secure_cookies_score,
            "csrf_score": csrf_score,
            "fixation_score": fixation_score,
            "idle_timeout_score": idle_timeout_score,
            "framework_bonus": framework_bonus,
            "raw_score": raw_score,
            "issue_penalty": issue_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["session_security_score"] = calculate_score(result)
    
    return result

def get_session_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the session management check results"""
    if not result.get("has_session_management", False):
        return "No session management detected. If your application requires user authentication, implement secure session handling with proper expiration, CSRF protection, and secure cookies."
    
    score = result.get("session_security_score", 0)
    issues = result.get("potential_issues", [])
    
    if score >= 80:
        return "Excellent session security implementation. Continue maintaining good security practices."
    
    recommendations = []
    
    if not result.get("has_session_expiration", False):
        recommendations.append("Implement proper session expiration to limit the lifetime of authentication sessions.")
    
    if not result.get("has_secure_cookies", False):
        recommendations.append("Configure cookies with Secure, HttpOnly, and SameSite attributes.")
    
    if not result.get("has_csrf_protection", False):
        recommendations.append("Add CSRF protection for form submissions to prevent cross-site request forgery attacks.")
    
    if not result.get("has_session_fixation_protection", False):
        recommendations.append("Implement session fixation protection by regenerating session IDs after authentication.")
    
    if not result.get("has_idle_timeout", False):
        recommendations.append("Add an idle timeout mechanism to automatically log out inactive users.")
    
    if issues:
        recommendations.append(f"Address the {len(issues)} potential security issues identified in session handling code.")
    
    if not recommendations:
        return "Good session security implementation. Consider additional hardening measures like strict session validation."
    
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
    Run the session management security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"session_management_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached session management check result for {repository.get('name', 'unknown')}")
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
        result = check_session_management(local_path, repository)
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("session_security_score", 0)
        final_score = normalize_score(score)
        
        logger.info(f"Session management check completed with score: {final_score}")
        
        # Return the result with enhanced metadata
        return {
            "score": final_score,
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "has_session_management": result.get("has_session_management", False),
                "frameworks_detected": result.get("session_frameworks_detected", []),
                "security_features": {
                    "expiration": result.get("has_session_expiration", False),
                    "secure_cookies": result.get("has_secure_cookies", False),
                    "csrf_protection": result.get("has_csrf_protection", False),
                    "fixation_protection": result.get("has_session_fixation_protection", False),
                    "idle_timeout": result.get("has_idle_timeout", False)
                },
                "potential_issues": len(result.get("potential_issues", [])),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_session_recommendation(result)
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
        error_msg = f"Error running session management check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }