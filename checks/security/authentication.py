import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_authentication_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secure authentication mechanisms and implementations
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for authentication security analysis
    """
    result = {
        "has_authentication": False,
        "auth_frameworks_detected": [],
        "has_password_hashing": False,
        "has_mfa_support": False,
        "has_rate_limiting": False,
        "has_session_management": False,
        "has_secure_cookies": False,
        "has_oauth_support": False,
        "has_jwt_implementation": False,
        "authentication_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Authentication framework patterns
    auth_frameworks = {
        "oauth2": [r'oauth2', r'OAuth\s*2', r'authorization_code', r'client_credentials'],
        "jwt": [r'jwt', r'JsonWebToken', r'sign\s*token', r'verify\s*token'],
        "saml": [r'saml', r'SAML', r'SecurityAssertion'],
        "openid": [r'openid', r'OpenID', r'oidc', r'connect'],
        "passport": [r'passport', r'passport-local', r'passport-jwt', r'passport-oauth'],
        "auth0": [r'auth0', r'Auth0', r'auth0-js', r'auth0-lock'],
        "firebase_auth": [r'firebase.auth', r'FirebaseAuth', r'signInWithEmailAndPassword'],
        "django_auth": [r'django.contrib.auth', r'authenticate\(', r'login\(', r'@login_required'],
        "spring_security": [r'spring-security', r'@Secured', r'WebSecurityConfigurerAdapter'],
        "devise": [r'devise', r'Devise', r'devise_for', r'authenticated\?'],
        "nextauth": [r'next-auth', r'NextAuth', r'getSession', r'useSession']
    }
    
    # Password hashing patterns
    password_hashing_patterns = [
        r'bcrypt',
        r'argon2',
        r'pbkdf2',
        r'scrypt',
        r'password_hash',
        r'hash_password',
        r'hashpw',
        r'make_password',
        r'PasswordEncoder',
        r'PasswordHasher',
        r'createHash',
        r'generate_password_hash',
        r'digest\(',
        r'MessageDigest',
        r'SALT',
        r'salt'
    ]
    
    # MFA/2FA patterns
    mfa_patterns = [
        r'two[-_\s]factor',
        r'2fa',
        r'mfa',
        r'multi[-_\s]factor',
        r'one[-_\s]time[-_\s]password',
        r'otp',
        r'totp',
        r'hotp',
        r'authenticator',
        r'verification[-_\s]code',
        r'second[-_\s]factor',
        r'pyotp',
        r'speakeasy'
    ]
    
    # Rate limiting patterns
    rate_limiting_patterns = [
        r'rate[-_\s]limit',
        r'throttl',
        r'ratelimit',
        r'limiter',
        r'max[-_\s]attempts',
        r'too[-_\s]many[-_\s]requests',
        r'429',
        r'brute[-_\s]force[-_\s]protect',
        r'RateLimiterMemory',
        r'RateLimiterRedis',
        r'@RateLimit'
    ]
    
    # Session management patterns
    session_patterns = [
        r'session[-_\s]timeout',
        r'session[-_\s]expir',
        r'session[-_\s]token',
        r'invalidate[-_\s]session',
        r'destroy[-_\s]session',
        r'logout',
        r'sign[-_\s]out',
        r'session[-_\s]cookie',
        r'csrf',
        r'xsrf',
        r'anti[-_\s]forgery',
        r'session\.clear\(',
        r'req\.session'
    ]
    
    # Secure cookies patterns
    secure_cookie_patterns = [
        r'secure[-_\s]cookie',
        r'http[-_\s]only',
        r'httponly',
        r'samesite',
        r'secure\s*[=:]\s*true',
        r'httpOnly\s*[=:]\s*true',
        r'cookie[-_\s]options',
        r'set[-_\s]cookie',
        r'sign[-_\s]cookie',
        r'signed[-_\s]cookie',
        r'cookie[-_\s]signature'
    ]
    
    # OAuth patterns
    oauth_patterns = [
        r'oauth',
        r'OAuth',
        r'authorization[-_\s]code',
        r'client[-_\s]credentials',
        r'access[-_\s]token',
        r'refresh[-_\s]token',
        r'google[-_\s]auth',
        r'facebook[-_\s]auth',
        r'github[-_\s]auth',
        r'twitter[-_\s]auth'
    ]
    
    # JWT patterns
    jwt_patterns = [
        r'jwt',
        r'JWT',
        r'json[-_\s]web[-_\s]token',
        r'jsonwebtoken',
        r'sign[-_\s]token',
        r'verify[-_\s]token',
        r'decode[-_\s]token',
        r'token[-_\s]payload',
        r'jwtSecret',
        r'jwt[-_\s]secret',
        r'jwtVerify'
    ]
    
    # File types and locations to check
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.cs', '.html']
    auth_related_dirs = ['auth', 'authentication', 'login', 'security', 'middleware', 'controllers']
    auth_related_files = ['auth', 'login', 'register', 'signup', 'signin', 'session', 'security', 'user']
    
    # Config files to check
    config_files = [
        'package.json',
        'requirements.txt',
        'Gemfile',
        'composer.json',
        'pom.xml',
        'build.gradle',
        'app.config.js',
        'security.config.js',
        'settings.py',
        'web.config',
        '.env.example'
    ]
    
    # Track detected authentication frameworks
    detected_frameworks = set()
    
    # First check for authentication dependencies in config files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for auth frameworks
                    for framework, patterns in auth_frameworks.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_frameworks.add(framework)
                            result["has_authentication"] = True
                    
                    # Check for password hashing libraries
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in password_hashing_patterns):
                        result["has_password_hashing"] = True
                    
                    # Check for MFA support
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in mfa_patterns):
                        result["has_mfa_support"] = True
                    
                    # Check for OAuth libraries
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in oauth_patterns):
                        result["has_oauth_support"] = True
                    
                    # Check for JWT libraries
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in jwt_patterns):
                        result["has_jwt_implementation"] = True
                    
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Walk through repository structure to find auth-related files
    auth_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Get relative path to identify auth-related directories
        rel_path = os.path.relpath(root, repo_path)
        dir_parts = rel_path.split(os.sep)
        
        # Check if current directory might be auth-related
        is_auth_dir = any(auth_dir.lower() in dir_part.lower() for dir_part in dir_parts for auth_dir in auth_related_dirs)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            # Check if this is a code file
            if file_ext in code_file_extensions:
                # Check if filename indicates auth-related functionality
                if any(auth_file.lower() in file.lower() for auth_file in auth_related_files) or is_auth_dir:
                    auth_files.append(file_path)
                    continue
                
                # For HTML/JS/PHP files, do a quick check for login/auth forms
                if file_ext in ['.html', '.php', '.js', '.jsx', '.ts', '.tsx']:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(4000)  # Just scan beginning of the file
                            if re.search(r'login|signin|signup|register|password|authentication', content, re.IGNORECASE):
                                auth_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Error scanning file {file_path}: {e}")
    
    # Now analyze auth-related files in detail
    for file_path in auth_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Mark that we found authentication code
                result["has_authentication"] = True
                
                # Check for auth frameworks
                for framework, patterns in auth_frameworks.items():
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                        detected_frameworks.add(framework)
                
                # Check for password hashing
                if not result["has_password_hashing"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in password_hashing_patterns):
                        result["has_password_hashing"] = True
                
                # Check for MFA support
                if not result["has_mfa_support"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in mfa_patterns):
                        result["has_mfa_support"] = True
                
                # Check for rate limiting
                if not result["has_rate_limiting"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in rate_limiting_patterns):
                        result["has_rate_limiting"] = True
                
                # Check for session management
                if not result["has_session_management"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in session_patterns):
                        result["has_session_management"] = True
                
                # Check for secure cookies
                if not result["has_secure_cookies"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in secure_cookie_patterns):
                        result["has_secure_cookies"] = True
                
                # Check for OAuth support
                if not result["has_oauth_support"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in oauth_patterns):
                        result["has_oauth_support"] = True
                
                # Check for JWT implementation
                if not result["has_jwt_implementation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in jwt_patterns):
                        result["has_jwt_implementation"] = True
                
                # Break early if we found everything
                if (result["has_password_hashing"] and 
                    result["has_mfa_support"] and 
                    result["has_rate_limiting"] and 
                    result["has_session_management"] and 
                    result["has_secure_cookies"] and 
                    result["has_oauth_support"] and 
                    result["has_jwt_implementation"]):
                    break
                
        except Exception as e:
            logger.error(f"Error analyzing auth file {file_path}: {e}")
    
    # Store detected frameworks
    result["auth_frameworks_detected"] = list(detected_frameworks)
    
    # Calculate authentication security score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on authentication security features.
        
        The score consists of:
        - Base score for having authentication (0-10 points)
        - Score for password hashing implementation (0-25 points)
        - Score for MFA support (0-15 points)
        - Score for rate limiting (0-15 points)
        - Score for session management (0-10 points)
        - Score for secure cookies (0-10 points)
        - Score for OAuth support (0-10 points)
        - Score for JWT implementation (0-5 points)
        - Bonus for multiple frameworks and comprehensive security (0-10 points)
        
        Final score is normalized to 0-100 range.
        """
        # Base score for having authentication
        if not result_data.get("has_authentication", False):
            return 0
            
        base_score = 10
        
        # Core security features
        password_hashing_score = 25 if result_data.get("has_password_hashing", False) else 0
        mfa_score = 15 if result_data.get("has_mfa_support", False) else 0
        rate_limiting_score = 15 if result_data.get("has_rate_limiting", False) else 0
        
        # Additional security features
        session_mgmt_score = 10 if result_data.get("has_session_management", False) else 0
        secure_cookies_score = 10 if result_data.get("has_secure_cookies", False) else 0
        oauth_score = 10 if result_data.get("has_oauth_support", False) else 0
        jwt_score = 5 if result_data.get("has_jwt_implementation", False) else 0
        
        # Calculate raw score before bonuses
        raw_score = base_score + password_hashing_score + mfa_score + rate_limiting_score + session_mgmt_score + secure_cookies_score + oauth_score + jwt_score
        
        # Bonus for comprehensive security implementation
        security_features_count = sum([
            result_data.get("has_password_hashing", False),
            result_data.get("has_mfa_support", False),
            result_data.get("has_rate_limiting", False),
            result_data.get("has_session_management", False),
            result_data.get("has_secure_cookies", False),
            result_data.get("has_oauth_support", False),
            result_data.get("has_jwt_implementation", False)
        ])
        
        frameworks_count = len(result_data.get("auth_frameworks_detected", []))
        
        # Bonus for having multiple security features and frameworks
        comprehensive_bonus = 0
        if security_features_count >= 4:
            comprehensive_bonus += 5
        if security_features_count >= 6:
            comprehensive_bonus += 5
        if frameworks_count >= 2:
            comprehensive_bonus += 5
            
        # Cap bonus at 10 points
        comprehensive_bonus = min(10, comprehensive_bonus)
        
        # Calculate final score
        final_score = raw_score + comprehensive_bonus
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, final_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "password_hashing_score": password_hashing_score,
            "mfa_score": mfa_score,
            "rate_limiting_score": rate_limiting_score,
            "session_mgmt_score": session_mgmt_score,
            "secure_cookies_score": secure_cookies_score,
            "oauth_score": oauth_score,
            "jwt_score": jwt_score,
            "comprehensive_bonus": comprehensive_bonus,
            "raw_score": raw_score,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["authentication_score"] = calculate_score(result)
    
    return result

def get_auth_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the authentication security check results"""
    if not result.get("has_authentication", False):
        return "No authentication mechanisms detected. If your project requires user accounts, implement secure authentication with password hashing and MFA support."
    
    score = result.get("authentication_score", 0)
    has_password_hashing = result.get("has_password_hashing", False)
    has_mfa = result.get("has_mfa_support", False)
    has_rate_limiting = result.get("has_rate_limiting", False)
    has_secure_cookies = result.get("has_secure_cookies", False)
    
    if score >= 80:
        return "Excellent authentication security implementation. Continue maintaining robust security practices."
    
    recommendations = []
    
    if not has_password_hashing:
        recommendations.append("Implement secure password hashing using bcrypt, Argon2, or PBKDF2.")
    
    if not has_mfa:
        recommendations.append("Add multi-factor authentication support to strengthen account security.")
    
    if not has_rate_limiting:
        recommendations.append("Implement rate limiting to prevent brute force attacks on authentication endpoints.")
    
    if not has_secure_cookies:
        recommendations.append("Configure cookies with secure, HttpOnly, and SameSite attributes.")
    
    if not result.get("has_session_management", False):
        recommendations.append("Improve session management with proper timeout and invalidation mechanisms.")
    
    if not recommendations:
        return "Good authentication security. Consider additional hardening measures like security headers and regular security audits."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the authentication security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"auth_security_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached authentication security check result for {repository.get('name', 'unknown')}")
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
        result = check_authentication_security(local_path, repository)
        
        logger.info(f"Authentication security check completed with score: {result.get('authentication_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("authentication_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "has_authentication": result.get("has_authentication", False),
                "frameworks_detected": result.get("auth_frameworks_detected", []),
                "security_features": {
                    "password_hashing": result.get("has_password_hashing", False),
                    "mfa_support": result.get("has_mfa_support", False),
                    "rate_limiting": result.get("has_rate_limiting", False),
                    "session_management": result.get("has_session_management", False),
                    "secure_cookies": result.get("has_secure_cookies", False),
                    "oauth_support": result.get("has_oauth_support", False),
                    "jwt_implementation": result.get("has_jwt_implementation", False)
                },
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_auth_recommendation(result)
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
        error_msg = f"Error running authentication security check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }